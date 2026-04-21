import csv
import json
import logging
import os
import google.auth
import google.auth.transport.requests
import requests as http_requests
from langchain_google_vertexai import ChatVertexAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from app.config import settings
from app.services.memory_service import get_history, save_message
from app.services import phonebook_service

logger = logging.getLogger(__name__)

_PHONEBOOK_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "telefonbuch.csv")

# --- Multi-Datastore Konfiguration ---
_DS_FIBU = os.environ.get("VERTEX_SEARCH_DATASTORE_FIBU", "") or os.environ.get("VERTEX_SEARCH_DATASTORE", "handbuecher-v2")
_DS_ERP  = os.environ.get("VERTEX_SEARCH_DATASTORE_ERP", "")

_ERP_DS_KEYWORDS = {
    "auftrag", "warenwirtschaft", "artikel", "lieferant", "einkauf",
    "inventur", "kulimi", "chargen", "preiskonditionen", "staffelpreis",
    "bestellung", "disposition", "eevolution", "lager", "scanner",
    "kontrakt", "retoure",
}
_SCHNITTSTELLEN_KEYWORDS = {
    "schnittstelle", "integration", "buchungsübergabe",
    "übergabe an fibu", "erp und fibu", "fibu und erp",
}


def _detect_datastore(question: str) -> str | list[str]:
    """Wählt Datastore(s) anhand der Frage. Gibt einen String oder Liste zurück."""
    lower = question.lower()
    if any(kw in lower for kw in _SCHNITTSTELLEN_KEYWORDS):
        logger.info("Datastore: BEIDE (Schnittstellen-Frage)")
        return [_DS_FIBU, _DS_ERP] if _DS_ERP else _DS_FIBU
    if _DS_ERP and any(kw in lower for kw in _ERP_DS_KEYWORDS):
        logger.info("Datastore: ERP (%s)", _DS_ERP)
        return _DS_ERP
    logger.info("Datastore: FIBU (%s)", _DS_FIBU)
    return _DS_FIBU


_DIGIT_WORDS = {
    "0": "null", "1": "eins", "2": "zwei", "3": "drei", "4": "vier",
    "5": "fünf", "6": "sechs", "7": "sieben", "8": "acht", "9": "neun",
}


def digit_to_word(digit: str) -> str:
    return _DIGIT_WORDS.get(digit, digit)


def load_phonebook() -> str:
    lines = []
    with open(_PHONEBOOK_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            ext_tts = ", ".join(_DIGIT_WORDS[d] for d in row["Durchwahl"] if d in _DIGIT_WORDS)
            parts = [row["Name"], f"Durchwahl {ext_tts}"]
            if row["Beschreibung"]:
                parts.append(row["Beschreibung"])
            if row["Email"]:
                parts.append(row["Email"])
            lines.append(" | ".join(parts))
    return "\n".join(lines)


PHONEBOOK = load_phonebook()

SYSTEM_PROMPT = """Du bist Sofia, der digitale Assistent von Stephan Müller, Kaufmännischer Leiter bei SOPRA System GmbH.

INTERNES TELEFONVERZEICHNIS SOPRA SYSTEM:
{phonebook}

Wenn jemand eine Person sprechen möchte oder eine Durchwahl sucht:
- Schlage zunächst die Person im Telefonbuch nach
- Biete an, eine Nachricht mit Anliegen und Rückrufnummer weiterzuleiten: "Ich kann leider nicht direkt verbinden, aber ich kann eine Nachricht an [Name] schicken. Möchten Sie das?"
- Frage NIEMALS nach einer E-Mail-Adresse des Anrufers — nur nach dem Anliegen und der Rückrufnummer
- Bei NEIN: Nenne die Durchwahl: "[Name] erreichen Sie unter Durchwahl X. Ich kann leider nicht direkt weiterleiten."
- Biete NIEMALS an, jemanden direkt zu verbinden — das ist technisch nicht möglich

DEINE AUFGABE:
- Beantworte Fragen AUSSCHLIESSLICH auf Basis der KONTEXT-Dokumente aus den Handbüchern und der Wissensdatenbank.
- Führe den User Schritt für Schritt durch Prozesse – wie ein geduldiger Kollege am Telefon.
- Antworte immer auf Deutsch, klar und verständlich.
- Halte Antworten kurz genug für ein Telefongespräch (max. 2-3 Sätze pro Antwort).
- Keine Aufzählungen, keine Bulletpoints — nur fließende Sprache.

BEGRIFFE & SYNONYME (syska ProFI Fibu):
- Kreditor = Lieferant = Kreditorenstamm
- Debitor = Kunde = Debitorenstamm
- Stammdaten anlegen = neu anlegen = erfassen = einrichten
- FIBU = Finanzbuchhaltung = Buchhaltung
- OPos = Offene Posten = offene Rechnungen
- SuSa = Summen- und Saldenliste = FIBU-Auswertung (NICHT OPos)
- Storno = Stornierung = rückgängig machen = korrigieren

BEREICHSZUORDNUNG:
- Fragen zu Summen- und Saldenliste, Kontenblatt, BWA, Bilanz → FIBU
- Fragen zu offenen Rechnungen, Mahnungen, Zahlungseingang → OPos
- Fragen zu Anlagen, Abschreibungen → Anbu
- Fragen zu Kostenstellen, Kostenarten → Kore
- Niemals OPos-Kontext für FIBU-Auswertungsfragen verwenden

DIAGNOSE-LOGIK — WICHTIG:
- Wenn ein Problem unklar ist: Stelle EINE gezielte Rückfrage um die Ursache einzugrenzen.
- Beispiel: Bei "Buchung lässt sich nicht stornieren" → frage: "Wurde die Buchung bereits gezahlt?"
- Beispiel: Bei "Stapel hängt" → frage: "Kommt die Buchung aus dem ERP-System?"
- Beispiel: Bei "Saldo stimmt nicht" → frage: "Betrifft es Debitoren oder Kreditoren?"
- Erst nach der Rückfrage die passende Lösung nennen.
- Maximal eine Rückfrage pro Turn — nicht mehrere auf einmal.

GESPRÄCHSFÜHRUNG:
- Bei Prozessfragen: Erkläre NUR den nächsten Schritt. Frage danach: "Konnten Sie das umsetzen?"
- Bei "Ja" oder "Erledigt": Fahre mit dem nächsten Schritt fort.
- Bei "Nein" oder "Klappt nicht": Erkläre den aktuellen Schritt nochmal anders.
- Beende NIEMALS das Gespräch von dir aus.
- Frage IMMER am Ende: "Haben Sie noch eine weitere Frage?"
- Verabschiede dich NUR wenn der User explizit sagt: "Nein danke", "Tschüss", "Auf Wiederhören".

WICHTIG:
- Wenn die Antwort NICHT im Kontext steht: "Dazu habe ich leider keine Information. Soll ich einen Kollegen für Sie hinzuziehen?"
- Niemals erfinden oder raten.

BEIM ERSTEN TURN — ANLIEGEN ERKENNEN UND ROUTING:
Analysiere die erste Antwort des Anrufers sorgfältig.

KATEGORIE A — syska ProFI / Fibu Support:
Erkennungsmerkmale: Buchung, Fibu, Periode, Storno, OPos, Mahnung, Bilanz, Steuerkonto, Stapel, Kontenblatt, syska, ProFI, Jahresabschluss, Debitor, Kreditor, Saldenliste
→ Weiter mit normaler RAG-Pipeline und Schritt-für-Schritt Hilfe

KATEGORIE B — ERP Support:
Erkennungsmerkmale: ERP, Warenwirtschaft, Auftrag, Lieferschein, Artikel, Kulimi, Kundenverwaltung, Produktion, Inventur
→ Frage: "Möchten Sie direkt mit dem ERP Support verbunden werden? Die Durchwahl für den ERP NUG Support ist 112. Oder möchten Sie mir Ihr Problem schildern, damit ich eine Zusammenfassung per E-Mail an den Support schicke?"
→ Bei Durchwahl-Wunsch: Durchwahl nennen
→ Bei E-Mail-Wunsch: Rückrufnummer des Anrufers erfragen, dann E-Mail an support@sopra-system.com

KATEGORIE C — EVS Support:
Erkennungsmerkmale: EVS, Zeiterfassung
→ Frage: "Möchten Sie direkt mit dem EVS Support verbunden werden? Die Durchwahl ist 20. Oder soll ich eine Zusammenfassung Ihres Problems per E-Mail weiterleiten?"
→ Bei Durchwahl-Wunsch: Durchwahl 20 nennen
→ Bei E-Mail-Wunsch: Rückrufnummer erfragen, E-Mail an evs-support@sopra-system.com

KATEGORIE D — HR / Personal:
Erkennungsmerkmale: HR, Personal, Urlaub, Gehalt, Arbeitsvertrag, Krankmeldung
→ Frage: "Für HR-Themen ist die Durchwahl des HR-Supports 116. Möchten Sie dort anrufen, oder kann ich etwas ausrichten?"
→ Bei Nachricht: Rückrufnummer erfragen, E-Mail an hr-support@sopra-system.com

KATEGORIE E — IT-Problem:
Erkennungsmerkmale: Computer, Netzwerk, Drucker, Internet, IT, Software, Login, Passwort, Bildschirm, Laptop, Server
→ Frage: "Den IT-Support erreichen Sie unter Durchwahl 115. Oder möchten Sie mir das Problem kurz schildern, damit ich es weiterleite?"
→ Bei E-Mail-Wunsch: Rückrufnummer erfragen, E-Mail an it-support@sopra-system.com

KATEGORIE F — Interne Verwaltung / Verträge / Rechnungen:
Erkennungsmerkmale: Vertrag, Rechnung, Preis, Angebot, Wartung, Lizenz, Abrechnung, Verwaltung, intern, Ansprechpartner
→ "Für Vertrags- und Verwaltungsthemen ist Stephan Müller Ihr Ansprechpartner, Durchwahl 26. Oder soll ich ihm eine Nachricht hinterlassen?"
→ Bei Nachricht: Rückrufnummer erfragen, E-Mail an Stephan.Mueller@sopra-system.com

KATEGORIE G — Jemanden persönlich sprechen / Telefonbuch-Anfrage:
Erkennungsmerkmale: "Ich möchte X sprechen", "Können Sie mich mit X verbinden", "Was ist die Durchwahl von X", "Ich suche X"

Ablauf IMMER in dieser Reihenfolge:
1. Schlage die Person im Telefonbuch nach (phonebook_service.lookup())
2. Sage: "Ich kann leider nicht direkt verbinden. Ich kann aber eine E-Mail an [Name] schicken mit einer Zusammenfassung Ihres Anliegens und Ihren Kontaktdaten für einen Rückruf. Möchten Sie das?"

3. Bei JA:
   - Frage zuerst nach dem Anliegen: "Was ist der Anlass Ihres Anrufs?"
   - Frage dann nach der Rückrufnummer: "Wie lautet Ihre Rückrufnummer?"
   - Frage NIEMALS nach Name oder E-Mail-Adresse des Anrufers
   - Bestätige: "Ich habe eine Nachricht an [Name] geschickt. Er/Sie wird sich bei Ihnen melden."

4. Bei NEIN:
   - Nenne erst dann die Durchwahl: "Die Durchwahl von [Name] ist [Durchwahl]."
   - Füge hinzu: "Ich kann leider nicht direkt weiterleiten."
   - Frage: "Kann ich Ihnen sonst noch helfen?"

→ Kein Treffer im Telefonbuch: "Diese Person habe ich leider nicht im Verzeichnis. Soll ich eine Nachricht hinterlassen?"

KATEGORIE H — Unklar:
→ "Können Sie mir kurz sagen worum es geht? Ich helfe Ihnen dann gerne weiter."

WICHTIG FÜR ALLE KATEGORIEN:
Frage NIEMALS nach einer E-Mail-Adresse des Anrufers — diese wird nicht benötigt.
Erfasse ausschließlich die Rückrufnummer (Telefonnummer) des Anrufers.

KONTEXT AUS DEN HANDBÜCHERN UND WISSENSDATENBANK:
{context}"""

SHORT_RESPONSES = ["ja", "nein", "ok", "okay", "erledigt", "gemacht", "nicht",
                   "klappt nicht", "funktioniert nicht", "verstanden", "gut"]


def _get_access_token() -> str:
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def _build_search_query(question: str, history: list) -> str:
    q_lower = question.lower().strip()
    is_short = any(q_lower == kw or q_lower.startswith(kw)
                   for kw in SHORT_RESPONSES) and len(question.split()) <= 4

    if is_short and history:
        last_assistant = next(
            (m["content"] for m in reversed(history) if m["role"] == "assistant"),
            None
        )
        if last_assistant:
            first_sentence = last_assistant.split(".")[0][:150]
            enriched = f"{first_sentence} {question}"
            logger.info("Suchanfrage angereichert (Assistant): '%s'", enriched)
            return enriched

        last_user = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"),
            None
        )
        if last_user and len(last_user.split()) > 4:
            enriched = f"{last_user} {question}"
            logger.info("Suchanfrage angereichert (User-Fallback): '%s'", enriched)
            return enriched

    return question


def _search_datastore(question: str, datastore_id: str | None = None, page_size: int | None = None) -> str:
    token = _get_access_token()
    if datastore_id:
        url = (
            f"https://discoveryengine.googleapis.com/v1/projects/"
            f"{settings.gcp_project_id}/locations/{settings.vertex_search_location}"
            f"/collections/default_collection/dataStores/{datastore_id}"
            f"/servingConfigs/default_config:search"
        )
    else:
        url = (
            f"https://discoveryengine.googleapis.com/v1/projects/"
            f"{settings.gcp_project_id}/locations/{settings.vertex_search_location}"
            f"/collections/default_collection/engines/{settings.vertex_search_engine_id}"
            f"/servingConfigs/default_config:search"
        )
    payload = {
        "query": question,
        "pageSize": page_size if page_size is not None else settings.rag_top_k,
        "contentSearchSpec": {
            "snippetSpec": {"returnSnippet": True},
            "extractiveContentSpec": {
                "maxExtractiveAnswerCount": 2
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-user-project": settings.gcp_project_id,
    }
    resp = http_requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    passages = []
    for result in data.get("results", []):
        derived = result.get("document", {}).get("derivedStructData", {})
        for sn in derived.get("snippets", []):
            if sn.get("snippet"):
                text = sn["snippet"].replace("<b>", "").replace("</b>", "")
                passages.append(text)

    context = "\n\n".join(passages)
    logger.info("Passagen: %d | Kontext: %s", len(passages), context[:300] if context else "LEER")
    return context


async def answer_question(question: str, call_sid: str = "", lat_logger=None) -> str:
    try:
        logger.info("RAG-Abfrage | CallSid=%s | Frage='%s'", call_sid, question)

        history = get_history(call_sid)
        save_message(call_sid, "user", question)
        search_query = _build_search_query(question, history)
        if lat_logger:
            lat_logger.mark("rag_start")
        datastore = _detect_datastore(search_query)
        if isinstance(datastore, list):
            per_ds = max(1, settings.rag_top_k // 2)
            passages_fibu = _search_datastore(search_query, datastore_id=datastore[0], page_size=per_ds)
            passages_erp  = _search_datastore(search_query, datastore_id=datastore[1], page_size=per_ds)
            context = "\n\n".join(filter(None, [passages_fibu, passages_erp]))
        else:
            ds_id = datastore if datastore != _DS_FIBU or not settings.vertex_search_engine_id else None
            context = _search_datastore(search_query, datastore_id=ds_id)
        if lat_logger:
            lat_logger.mark("rag_done")

        if not context:
            context = "Kein spezifischer Kontext gefunden."

        llm = ChatVertexAI(
            model_name=settings.gemini_model,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.rag_max_tokens,
        )

        messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context, phonebook=PHONEBOOK))]
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=question))

        if lat_logger:
            lat_logger.mark("llm_start")
        response = await llm.ainvoke(messages)
        if lat_logger:
            lat_logger.mark("llm_done")
        answer = response.content.strip()

        save_message(call_sid, "assistant", answer)
        logger.info("RAG-Antwort | CallSid=%s | Antwort='%s'", call_sid, answer[:150])
        return answer

    except Exception as e:
        logger.error("Fehler in RAG-Pipeline | CallSid=%s | Fehler=%s", call_sid, e)
        return (
            "Es tut mir leid, ich habe gerade ein technisches Problem. "
            "Bitte versuchen Sie es erneut oder bleiben Sie in der Leitung."
        )


async def extract_contact_data(speech_result: str) -> dict:
    """Extrahiert Rückruf-Telefonnummer aus natürlichsprachlicher (gesprochener) Eingabe via Gemini."""
    if not speech_result.strip():
        return {"phone": ""}
    try:
        llm = ChatVertexAI(
            model_name=settings.gemini_model,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
            temperature=0.0,
            max_output_tokens=80,
        )
        prompt = (
            "Extrahiere die Telefonnummer aus folgendem gesprochenen Text.\n\n"
            "Regeln:\n"
            '- "null" → 0, "eins" → 1, "zwei" → 2, usw.\n'
            "- Leerzeichen zwischen Zifferngruppen beibehalten\n"
            "- Nur die Nummer extrahieren, nichts erfinden\n\n"
            "Beispiele:\n"
            '- "meine Nummer ist null acht neun eins zwei drei" → "089 123"\n'
            '- "089 12345" → "089 12345"\n\n'
            f"Text: '{speech_result}'\n\n"
            "Antworte ausschließlich als JSON, ohne Markdown, ohne Backticks:\n"
            '{"phone": "..."}\n'
            "Wenn keine Nummer erkennbar: leeren String."
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        return {"phone": str(data.get("phone", ""))}
    except Exception as e:
        logger.warning("Kontaktdaten-Extraktion fehlgeschlagen: %s", e)
        return {"phone": ""}


async def summarize_conversation(conversation_history: list[dict]) -> str:
    """Generiert eine 2-3 Satz Zusammenfassung des Gesprächsverlaufs auf Deutsch via Gemini."""
    if not conversation_history:
        return "Kein Gesprächsverlauf verfügbar."
    try:
        llm = ChatVertexAI(
            model_name=settings.gemini_model,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
            temperature=0.0,
            max_output_tokens=200,
        )
        turns = "\n".join(
            f"{'Anrufer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
            for m in conversation_history
            if m.get("content", "").strip()
        )
        prompt = (
            "Du fasst einen Kundenanruf in 2-3 Sätzen zusammen. "
            "Fokus: Was wollte der Kunde? Was ist sein konkretes Problem oder Anliegen? "
            "Schreibe aus Perspektive des Anrufers, nicht des Agenten. "
            "Keine Erwähnung von Durchwahlen oder internen Abläufen. "
            "Keine Aufzählungen, nur fließende Sprache.\n\n"
            "Beispiel: \"Herr Müller hat angerufen wegen einer Preiserhöhung auf seiner Rechnung. "
            "Laut Vertrag wurde eine 5-jährige Preisgarantie vereinbart, die noch nicht abgelaufen ist.\"\n\n"
            f"Gesprächsverlauf:\n{turns}"
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        logger.warning("Gesprächszusammenfassung fehlgeschlagen: %s", e)
        return "Zusammenfassung konnte nicht erstellt werden."
