import logging
import google.auth
import google.auth.transport.requests
import requests as http_requests
from langchain_google_vertexai import ChatVertexAI
from langchain.schema import HumanMessage
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist ein freundlicher Telefon-Assistent.
Antworte AUSSCHLIESSLICH auf Basis der folgenden Kontext-Dokumente aus unseren Handbüchern.
Halte dich kurz (max. 2–3 Sätze). Antworte auf Deutsch.
Wenn die Antwort NICHT im Kontext steht, sage genau:
"Das kann ich leider nicht beantworten. Ich verbinde Sie gerne mit einem Mitarbeiter weiter."

KONTEXT:
{context}

FRAGE: {question}

ANTWORT:"""


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
        f"default_collection/dataStores/handbuecher/servingConfigs/"
        f"default_config:search"
    )
    payload = {
        "query": question,
        "pageSize": settings.rag_top_k,
        "contentSearchSpec": {
            "snippetSpec": {"returnSnippet": True},
            "summarySpec": {
                "summaryResultCount": 3,
                "languageCode": "de"
            },
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

    # Snippets sammeln
    passages = []
    for result in data.get("results", []):
        derived = result.get("document", {}).get("derivedStructData", {})
        for sn in derived.get("snippets", []):
            if sn.get("snippet"):
                passages.append(sn["snippet"])

    summary = data.get("summary", {}).get("summaryText", "")
    context = "\n\n".join(passages)

    logger.info("Passagen: %d | Summary: %s", len(passages), summary[:100] if summary else "–")
    logger.info("Kontext: %s", context[:300] if context else "LEER")
    return context, summary


async def answer_question(question: str, call_sid: str = "") -> str:
    try:
        logger.info("RAG-Abfrage | CallSid=%s | Frage='%s'", call_sid, question)
        context, summary = _search_datastore(question)

        if summary:
            logger.info("Nutze Summary: %s", summary[:100])
            return summary

        if not context:
            return "Das kann ich leider nicht beantworten. Ich verbinde Sie gerne mit einem Mitarbeiter weiter."

        llm = ChatVertexAI(
            model_name=settings.gemini_model,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.rag_max_tokens,
        )
        prompt = SYSTEM_PROMPT.format(context=context, question=question)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        answer = response.content.strip()
        logger.info("RAG-Antwort | CallSid=%s | Antwort='%s'", call_sid, answer[:100])
        return answer

    except Exception as e:
        logger.error("Fehler in RAG-Pipeline | CallSid=%s | Fehler=%s", call_sid, e)
        return (
            "Es tut mir leid, ich habe gerade ein technisches Problem. "
            "Bitte versuchen Sie es erneut oder bleiben Sie in der Leitung."
        )
