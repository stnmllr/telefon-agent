import logging
import google.auth
import google.auth.transport.requests
import requests as http_requests
from langchain_google_vertexai import ChatVertexAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from app.config import settings
from app.services.memory_service import get_history, save_message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist ein freundlicher, geduldiger Telefon-Support-Assistent für die Software syska ProFI Fibu.

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
            "extractiveContentSpec": {"maxExtractiveAnswerCount": 2},
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
        for ea in derived.get("extractive_answers", []):
            if ea.get("content"):
                passages.append(ea["content"])
        if not passages:
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

        messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context))]
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
