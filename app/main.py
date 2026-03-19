# ============================================================
# agent-service / app/main.py
# FastAPI entrypoint – empfängt Twilio-Webhooks,
# orchestriert STT → RAG → LLM → TTS Pipeline
# ============================================================

import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager

from app.routers import call_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agent-Service gestartet. Umgebung: %s", settings.environment)
    yield
    logger.info("Agent-Service wird beendet.")


app = FastAPI(
    title="KI-Telefon-Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(call_router.router, tags=["Telephonie"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
