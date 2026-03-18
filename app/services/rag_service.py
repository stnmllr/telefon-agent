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
- Beantworte Fragen AUSSCHLIESSLICH auf Basis der KONTEXT-Dokumente aus den Handbüchern.
- Führe den User Schritt für Schritt durch Prozesse – wie ein geduldiger Kollege am Telefon.
- Antworte immer auf Deutsch, klar und verständlich.
- Halte Antworten kurz genug für ein Telefongespräch (max. 4 Sätze pro Antwort).

GESPRÄCHSFÜHRUNG:
- Bei Prozessfragen (Wie mache ich X?): Erkläre Schritt 1, frage dann ob der User diesen Schritt gemacht hat.
- Bei Verständnisfragen (Was ist X?): Erkläre direkt und präzise.
- Bei Folgefragen: Beziehe dich auf den bisherigen Gesprächsverlauf.
- Frage am Ende jeder Antwort: "Konnten Sie das so umsetzen?" oder "Ist das verständlich?"

WICHTIG:
- Wenn die Antwort NICHT im Kontext steht: "Das steht leider nicht in meinen Unterlagen. Ich verbinde Sie mit einem Kollegen."
- Niemals erfinden oder raten – nur aus dem Kontext antworten.

KONTEXT AUS DEN HANDBÜCHERN:
{context}"""


def _get_access_token() -> str:
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def _search_datastore(question: str) -> str:
    token = _get_access_token()
    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/"
        f"{settings.gcp_project_id}/locations/global/collections/"
        f"default_collection/dataStores/{settings.vertex_search_datastore}/servingConfigs/"
        f"default_config:search"
    )
    payload = {
        "query": question,
        "pageSize": settings.rag_top_k,
        "contentSearchSpec": {
            "snippetSpec": {"returnSnippet": True},
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
                # HTML-Tags entfernen
                text = sn["snippet"].replace("<b>", "").replace("</b>", "")
                passages.append(text)

    context = "\n\n".join(passages)
    logger.info("Passagen: %d | Kontext: %s", len(passages), context[:300] if context else "LEER")
    return context


async def answer_question(question: str, call_sid: str = "") -> str:
    try:
        logger.info("RAG-Abfrage | CallSid=%s | Frage='%s'", call_sid, question)

        # Kontext aus Handbüchern laden
        context = _search_datastore(question)

        if not context:
            return "Das steht leider nicht in meinen Unterlagen. Ich verbinde Sie gerne mit einem Kollegen weiter."

        # Gesprächsverlauf laden
        history = get_history(call_sid)

        # LLM aufrufen
        llm = ChatVertexAI(
            model_name=settings.gemini_model,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.rag_max_tokens,
        )

        # Nachrichten aufbauen: System + History + aktuelle Frage
        messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context))]

        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=question))

        response = await llm.ainvoke(messages)
        answer = response.content.strip()

        # Gesprächsverlauf speichern
        save_message(call_sid, "user", question)
        save_message(call_sid, "assistant", answer)

        logger.info("RAG-Antwort | CallSid=%s | Antwort='%s'", call_sid, answer[:150])
        return answer

    except Exception as e:
        logger.error("Fehler in RAG-Pipeline | CallSid=%s | Fehler=%s", call_sid, e)
        return (
            "Es tut mir leid, ich habe gerade ein technisches Problem. "
            "Bitte versuchen Sie es erneut oder bleiben Sie in der Leitung."
        )
