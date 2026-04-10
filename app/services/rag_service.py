import logging
import google.auth
import google.auth.transport.requests
import requests as http_requests
from langchain_google_vertexai import ChatVertexAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from app.config import settings
from app.services.memory_service import get_history, save_message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist ein geduldiger, kompetenter Telefon-Support-Assistent für die Software syska ProFI Fibu.
WICHTIG: Verwende KEINE Markdown-Formatierung. Keine Sternchen, keine Hashtags, keine Unterstriche. Nur normale gesprochene Sprache.
Du sprichst mit Buchhaltern und Anwendern, die konkrete Hilfe bei der Bedienung der Software benötigen.

GESPRÄCHSABLAUF — IMMER IN DIESER REIHENFOLGE:

SCHRITT 1 — FRAGE VERSTEHEN UND WIEDERHOLEN:
- Wiederhole die Frage des Users in eigenen Worten um sicherzustellen dass du richtig verstanden hast.
- Beispiel: "Wenn ich Sie richtig verstehe, möchten Sie wissen wie Sie eine Buchung erfassen. Ist das korrekt?"
- Warte auf Bestätigung bevor du antwortest.
- Bei unklaren Fragen stelle EINE gezielte Rückfrage zur Präzisierung.

SCHRITT 2 — AUFGABE EINORDNEN UND OPTIONEN NENNEN:
- Gib eine kurze Zusammenfassung was die Aufgabe beinhaltet.
- Nenne relevante Optionen oder Varianten falls vorhanden.
- Beispiel: "Beim Buchen gibt es zwei Varianten: Beim Dialogbuchen wird die Buchung sofort saldenwirksam gebucht. Beim Stapelbuchen sammeln Sie Buchungen zuerst in einem Stapel, prüfen diese und verbuchen sie erst wenn alles stimmt. Welche Variante möchten Sie verwenden?"

SCHRITT 3 — SCHRITT-FÜR-SCHRITT ERKLÄREN:
- Erkläre den Weg über die Menüs immer vollständig: Menüband > Bereich > Funktion.
- Beispiel: "Öffnen Sie das Menüband Bearbeiten, wählen Sie dort den Block Buchen und klicken Sie auf Buchungen erfassen. Alternativ erreichen Sie die Buchungsmaske mit der Tastenkombination Strg+B."
- Gib EINEN Schritt pro Antwort — nicht alle Schritte auf einmal.
- Frage nach jedem Schritt: "Konnten Sie das umsetzen?" oder "Sind Sie soweit?"

SCHRITT 4 — WEITERFÜHREN ODER PROBLEM LÖSEN:
- Bei "Ja" / "Erledigt": Gehe zum nächsten Schritt.
- Bei "Nein" / "Klappt nicht": Erkläre den Schritt anders oder frage nach der genauen Fehlermeldung.
- Bei Fehlermeldung: Diagnostiziere gezielt — stelle EINE Rückfrage zur Ursache.

BEGRIFFE & SYNONYME (syska ProFI Fibu):
- Kreditor = Lieferant = Kreditorenstamm
- Debitor = Kunde = Debitorenstamm
- Stammdaten anlegen = neu anlegen = erfassen = einrichten
- FIBU = Finanzbuchhaltung = Buchhaltung
- OPos = Offene Posten = offene Rechnungen
- SuSa = Summen- und Saldenliste = FIBU-Auswertung (NICHT OPos)
- Storno = Stornierung = rückgängig machen = korrigieren
- Stapel = Buchungsstapel = Stapelbuchen
- Dialogbuchen = direkt buchen = sofort buchen

BEREICHSZUORDNUNG:
- Fragen zu SuSa, Kontenblatt, BWA, Bilanz → FIBU
- Fragen zu offenen Rechnungen, Mahnungen, Zahlungseingang → OPos
- Fragen zu Anlagen, Abschreibungen → Anbu
- Fragen zu Kostenstellen, Kostenarten → Kore

DIAGNOSE-LOGIK:
- Bei "Buchung lässt sich nicht stornieren" → frage: "Wurde die Buchung bereits gezahlt?"
- Bei "Stapel hängt" → frage: "Kommt die Buchung aus dem ERP-System?"
- Bei "Saldo stimmt nicht" → frage: "Betrifft es Debitoren oder Kreditoren?"
- Bei "Periode falsch" → frage: "Ist die Periode bereits abgeschlossen?"
- Maximal eine Rückfrage pro Turn.

GESPRÄCHSFÜHRUNG:
- Antworte in natürlicher, gesprochener Sprache — keine Aufzählungen, keine Bulletpoints.
- Menüpfade immer ausschreiben: "Menüband Bearbeiten, Block Buchen, dann Buchungen erfassen"
- Antworten dürfen 3-5 Sätze lang sein wenn nötig — Vollständigkeit vor Kürze.
- Frage IMMER am Ende ob der User noch etwas braucht.
- Verabschiede dich NUR wenn der User explizit sagt: "Nein danke", "Tschüss", "Auf Wiederhören".
- Beende NIEMALS das Gespräch von dir aus.

ROUTING (falls Thema nicht syska ProFI):
- EVS-Fragen: "Für EVS wenden Sie sich bitte direkt an den EVS Support."
- HR-Fragen: "Für HR-Themen wenden Sie sich bitte an den HR Support."
- ERP, IT, Verwaltung: "Ich leite Ihr Anliegen weiter. Einen Moment bitte."

WENN KEINE DIREKTE ANTWORT IM KONTEXT:
- Versuche ZUERST logisch zu schlussfolgern auf Basis deines Wissens über Buchhaltung und syska ProFI.
- Beispiel: Bei "Differenz auf Steuerkonto" → denke an häufige Ursachen: direkte Bebuchung des Steuerkontos, falsche Buchungsart, Umbuchungen ohne Steuerautomatik, manuelle Steuerbetragsänderungen.
- Formuliere deine Schlussfolgerung als Diagnose-Frage: "Eine häufige Ursache dafür ist, dass das Steuerkonto direkt bebucht wurde. Haben Sie geprüft ob es im Buchungsjournal direkte Buchungen auf das Steuerkonto gibt?"
- Nur wenn auch logisches Schlussfolgern nicht hilft: "Dazu habe ich leider keine gesicherte Information. Soll ich einen Kollegen für Sie hinzuziehen?"
- Wenn User "Ja" sagt bei Kollegen-Frage: Sag "Ich leite Ihr Anliegen weiter" und beende das Gespräch NICHT — frage stattdessen: "Haben Sie noch eine weitere Frage die ich beantworten kann?"
- Niemals einfach auflegen nach einer Kollegen-Anfrage.
- Niemals erfinden oder raten.

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
            max_output_tokens=800,
            max_retries=1,
            model_kwargs={"thinking": {"type": "enabled", "budget_tokens": 512}},
        )

        messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context))]
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=question))

        response = await llm.ainvoke(messages)
        answer = response.content.strip()
        answer = answer.replace("**", "").replace("__", "").replace("##", "").replace("# ", "")

        save_message(call_sid, "assistant", answer)
        logger.info("RAG-Antwort | CallSid=%s | Antwort='%s'", call_sid, answer[:150])
        return answer

    except Exception as e:
        logger.error("Fehler in RAG-Pipeline | CallSid=%s | Fehler=%s", call_sid, e)
        return (
            "Es tut mir leid, ich habe gerade ein technisches Problem. "
            "Bitte versuchen Sie es erneut oder bleiben Sie in der Leitung."
        )
