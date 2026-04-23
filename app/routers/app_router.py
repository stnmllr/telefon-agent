# ============================================================
# app/routers/app_router.py
# PWA Backend: Google OAuth + Abwesenheits-CRUD
# ============================================================

import logging
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.services.absence_service import (
    create_absence,
    get_all_absences,
    delete_absence,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/app")

# ── Env-Vars ─────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
ALLOWED_EMAIL        = os.getenv("ALLOWED_EMAIL", "stn.mueller@gmail.com")
APP_SECRET_KEY       = os.getenv("APP_SECRET_KEY", secrets.token_hex(32))
BASE_URL             = os.getenv("BASE_URL", "https://telefon-agent-1051648887841.europe-west3.run.app")

REDIRECT_URI         = f"{BASE_URL}/app/auth/callback"
GOOGLE_AUTH_URL      = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL     = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

# Einfacher In-Memory Session Store (reicht für Single-User)
# Key: session_token, Value: email
_sessions: dict[str, str] = {}
# OAuth State Store
_oauth_states: dict[str, str] = {}


# ── Auth Helpers ─────────────────────────────────────────────

def _get_session_email(request: Request) -> Optional[str]:
    token = request.cookies.get("sofia_session")
    if not token:
        return None
    return _sessions.get(token)


def require_auth(request: Request) -> str:
    email = _get_session_email(request)
    if not email:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    return email


# ── OAuth Endpoints ──────────────────────────────────────────

@router.get("/auth/login")
async def auth_login(request: Request):
    """Startet den Google OAuth Flow."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "pending"

    client = AsyncOAuth2Client(
        client_id=GOOGLE_CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope="openid email profile",
    )
    url, _ = client.create_authorization_url(GOOGLE_AUTH_URL, state=state)
    return RedirectResponse(url)


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str, state: str):
    """Google OAuth Callback — tauscht Code gegen Token."""
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Ungültiger State")
    del _oauth_states[state]

    client = AsyncOAuth2Client(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
    )
    token = await client.fetch_token(GOOGLE_TOKEN_URL, code=code)
    userinfo_resp = await client.get(GOOGLE_USERINFO_URL)
    userinfo = userinfo_resp.json()

    email = userinfo.get("email", "")
    if email.lower() != ALLOWED_EMAIL.lower():
        logger.warning("Login abgelehnt für: %s", email)
        raise HTTPException(status_code=403, detail="Zugriff verweigert")

    session_token = secrets.token_urlsafe(32)
    _sessions[session_token] = email
    logger.info("Login erfolgreich: %s", email)

    response = RedirectResponse(url="/app/")
    response.set_cookie(
        key="sofia_session",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 Tage
    )
    return response


@router.get("/auth/logout")
async def auth_logout(request: Request):
    token = request.cookies.get("sofia_session")
    if token and token in _sessions:
        del _sessions[token]
    response = RedirectResponse(url="/app/")
    response.delete_cookie("sofia_session")
    return response


# ── PWA Frontend ─────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def app_index(request: Request):
    """Liefert die PWA HTML-App."""
    from pathlib import Path
    html_path = Path(__file__).parent.parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/manifest.json")
async def manifest():
    from pathlib import Path
    json_path = Path(__file__).parent.parent / "static" / "manifest.json"
    return JSONResponse(content=__import__("json").loads(json_path.read_text()))


@router.get("/sw.js")
async def service_worker():
    from pathlib import Path
    js_path = Path(__file__).parent.parent / "static" / "sw.js"
    from fastapi.responses import Response
    return Response(content=js_path.read_text(), media_type="application/javascript")


# ── Abwesenheits-API ─────────────────────────────────────────

class AbsenceCreate(BaseModel):
    type: str        # urlaub | meeting | abwesend | dienstreise
    start: str       # ISO-8601, z.B. "2026-04-25T09:00"
    end: str         # ISO-8601, z.B. "2026-04-28" oder "2026-04-25T14:00"
    note: str = ""


@router.get("/absence")
async def list_absences(email: str = Depends(require_auth)):
    absences = await get_all_absences()
    return {"absences": absences}


@router.post("/absence")
async def add_absence(body: AbsenceCreate, email: str = Depends(require_auth)):
    result = await create_absence(
        absence_type=body.type,
        start=body.start,
        end=body.end,
        note=body.note,
    )
    return {"success": True, "absence": result}


@router.delete("/absence/{absence_id}")
async def remove_absence(absence_id: str, email: str = Depends(require_auth)):
    deleted = await delete_absence(absence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return {"success": True}


# ── Auth-Status API (für Frontend) ───────────────────────────

@router.get("/auth/me")
async def auth_me(request: Request):
    email = _get_session_email(request)
    if not email:
        return JSONResponse({"authenticated": False}, status_code=401)
    return {"authenticated": True, "email": email}
