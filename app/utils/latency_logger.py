# app/utils/latency_logger.py
"""
Latenz-Messung für den KI-Telefon-Agent.
Schreibt strukturierte JSON-Logs in Google Cloud Logging,
die per Log-Explorer oder Log Analytics ausgewertet werden können.

Verwendung:
    from app.utils.latency_logger import LatencyLogger

    logger = LatencyLogger(call_sid)
    logger.mark("stt_done")
    logger.mark("rag_done")
    logger.mark("llm_done")
    logger.mark("tts_done")
    logger.finish()   # schreibt Summary-Log mit allen Deltas
"""

import sys
import time
import logging
import json
from typing import Optional

# Cloud Logging strukturiertes JSON-Format:
# stderr wird von Cloud Run zuverlässiger als structured log indexiert als stdout.
_cloud_logger = logging.getLogger("latency")
_cloud_logger.setLevel(logging.INFO)
_cloud_logger.propagate = False

# Nur einen Handler hinzufügen (verhindert Doppel-Logs beim Reload)
if not _cloud_logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _cloud_logger.addHandler(handler)


class LatencyLogger:
    """
    Misst Zeitabschnitte innerhalb eines Anruf-Flows.

    Checkpoints (empfohlen):
        call_start      → /call/incoming erreicht
        stt_done        → SpeechResult empfangen in /call/transcribe
        firestore_write → pending/{CallSid} geschrieben
        process_start   → /call/process erreicht
        firestore_read  → SpeechResult aus Firestore gelesen
        rag_start       → Vertex AI Search aufgerufen
        rag_done        → Vertex AI Search Antwort erhalten
        llm_start       → Gemini API aufgerufen
        llm_done        → Gemini Antwort vollständig
        tts_ready       → TwiML mit Antwort fertig gebaut
    """

    def __init__(self, call_sid: str, flow: str = "call"):
        self.call_sid = call_sid
        self.flow = flow
        self.start_time = time.time()
        self.marks: list[dict] = []
        self._last_time = self.start_time

    def mark(self, checkpoint: str, extra: Optional[dict] = None):
        """Zeitstempel für einen Checkpoint setzen."""
        now = time.time()
        delta_from_start = now - self.start_time
        delta_from_last = now - self._last_time

        entry = {
            "checkpoint": checkpoint,
            "elapsed_ms": round(delta_from_start * 1000),
            "delta_ms": round(delta_from_last * 1000),
        }
        if extra:
            entry.update(extra)

        self.marks.append(entry)
        self._last_time = now

        # Sofort-Log für Live-Debugging im Log Explorer
        self._emit({
            "severity": "INFO",
            "message": f"[LATENCY] {self.call_sid} | {checkpoint} | "
                       f"+{entry['delta_ms']}ms | gesamt {entry['elapsed_ms']}ms",
            "call_sid": self.call_sid,
            "flow": self.flow,
            "checkpoint": checkpoint,
            "elapsed_ms": entry["elapsed_ms"],
            "delta_ms": entry["delta_ms"],
            **(extra or {}),
        })

    def finish(self):
        """Summary-Log mit allen Segmenten — für Log Analytics Queries."""
        total_ms = round((time.time() - self.start_time) * 1000)

        # Segmente als Key-Value für einfache Auswertung
        segments = {}
        for m in self.marks:
            segments[f"seg_{m['checkpoint']}_ms"] = m["delta_ms"]

        self._emit({
            "severity": "INFO",
            "message": f"[LATENCY_SUMMARY] {self.call_sid} | gesamt {total_ms}ms",
            "call_sid": self.call_sid,
            "flow": self.flow,
            "total_ms": total_ms,
            "checkpoints": self.marks,
            **segments,
        })

        return total_ms

    @staticmethod
    def _emit(payload: dict):
        """JSON-Log ausgeben — Cloud Run indexiert stderr als structured log."""
        _cloud_logger.info(json.dumps(payload, ensure_ascii=False))
