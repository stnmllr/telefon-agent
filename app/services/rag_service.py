import csv
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
            ext_tts = "-".join(row["Durchwahl"])
            parts = [row["Name"], f"Durchwahl {ext_tts}"]
            if row["Beschreibung"]:
                parts.append(row["Beschreibung"])
            if row["Email"]:
                parts.append(row["Email"])
            lines.append(" | ".join(parts))
    return "\n".join(lines)


PHONEBOOK = load_phonebook()

SYSTEM_PROMPT = """Du bist ein freundlicher, geduldiger Telefon-Support-Assistent für die Software syska ProFI Fibu.

INTERNES TELEFONVERZEICHNIS SOPRA SYSTEM:
{phonebook}

Wenn jemand eine Person sucht oder eine Durchwahl braucht:
- Antworte SOFORT ohne RAG-Suche
- Nenne die Durchwahl direkt: 'Herr Schindler erreichen Sie unter Durchwahl 3 5. Ich kann leider keine direkte Weiterleitung vornehmen. Kann ich Ihnen sonst noch helfen?'
- Biete NIEMALS an jemanden zu verbinden — das ist technisch nicht möglich
- Hänge IMMER den Satz an: 'Ich kann leider keine direkte Weiterleitung vornehmen. Kann ich Ihnen sonst noch helfen?'

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
→ Bei E-Mail-Wunsch: Name und E-Mail-Adresse des Anrufers erfragen, dann E-Mail an support@sopra-system.com mit Zusammenfassung und präzisem Betreff

KATEGORIE C — EVS Support:
Erkennungsmerkmale: EVS, Zeiterfassung
→ Frage: "Möchten Sie direkt mit dem EVS Support verbunden werden? Die Durchwahl ist 20. Oder soll ich eine Zusammenfassung Ihres Problems per E-Mail weiterleiten?"
→ Bei Durchwahl-Wunsch: Durchwahl 20 nennen
→ Bei E-Mail-Wunsch: Name und E-Mail erfragen, E-Mail an evs-support@sopra-system.com

KATEGORIE D — HR / Personal:
Erkennungsmerkmale: HR, Personal, Urlaub, Gehalt, Arbeitsvertrag, Krankmeldung
→ Frage: "Für HR-Themen ist die Durchwahl des HR-Supports 116. Möchten Sie dort anrufen, oder kann ich etwas ausrichten?"
→ Bei Nachricht: Name erfragen, E-Mail an hr-support@sopra-system.com

KATEGORIE E — IT-Problem:
Erkennungsmerkmale: Computer, Netzwerk, Drucker, Internet, IT, Software, Login, Passwort, Bildschirm, Laptop, Server
→ Frage: "Den IT-Support erreichen Sie unter Durchwahl 115. Oder möchten Sie mir das Problem kurz schildern, damit ich es weiterleite?"
→ Bei E-Mail-Wunsch: Name und E-Mail erfragen, E-Mail an it-support@sopra-system.com

KATEGORIE F — Interne Verwaltung / Verträge / Rechnungen:
Erkennungsmerkmale: Vertrag, Rechnung, Preis, Angebot, Wartung, Lizenz, Abrechnung, Verwaltung, intern, Ansprechpartner
→ "Für Vertrags- und Verwaltungsthemen ist Stephan Müller Ihr Ansprechpartner, Durchwahl 26. Oder soll ich ihm eine Nachricht hinterlassen?"
→ Bei Nachricht: Name erfragen, E-Mail an Stephan.Mueller@sopra-system.com

KATEGORIE G — Jemanden persönlich sprechen / Telefonbuch-Anfrage:
Erkennungsmerkmale: "Ich möchte X sprechen", "Können Sie mich mit X verbinden", "Was ist die Durchwahl von X", "Ich suche X"
→ Schlage im Telefonbuch nach (phonebook_service.lookup())
→ Bei Treffer: "X erreichen Sie unter Durchwahl Y." — die E-Mail-Adresse der Person ist im Lookup-Ergebnis enthalten (Feld "email")
→ Kein Treffer: "Diese Person habe ich leider nicht im Verzeichnis. Soll ich eine Nachricht hinterlassen?"
→ Bei Nachricht: Name und E-Mail des Anrufers erfragen, E-Mail an die im Telefonbuch hinterlegte Adresse der gesuchten Person senden

KATEGORIE H — Unklar:
→ "Können Sie mir kurz sagen worum es geht? Ich helfe Ihnen dann gerne weiter."

WICHTIG FÜR ALLE E-MAIL-KATEGORIEN:
Erfrage immer Name und E-Mail-Adresse des Anrufers bevor du die E-Mail sendest.
Die E-Mail soll enthalten: Name des Anrufers, E-Mail-Adresse, Zusammenfassung des Problems, prägnanter Betreff.

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


def _search_datastore(question: str) -> str:
    token = _get_access_token()
    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/"
        f"{settings.gcp_project_id}/locations/{settings.vertex_search_location}"
        f"/collections/default_collection/engines/{settings.vertex_search_engine_id}"
        f"/servingConfigs/default_config:search"
    )
    payload = {
        "query": question,
        "pageSize": settings.rag_top_k,
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


async def answer_question(question: str, call_sid: str = "") -> str:
    try:
        logger.info("RAG-Abfrage | CallSid=%s | Frage='%s'", call_sid, question)

        history = get_history(call_sid)
        save_message(call_sid, "user", question)
        search_query = _build_search_query(question, history)
        context = _search_datastore(search_query)

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

        response = await llm.ainvoke(messages)
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
