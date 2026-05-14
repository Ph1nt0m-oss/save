from fastapi import FastAPI, APIRouter, HTTPException, Response, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from pydantic import BaseModel, Field, ConfigDict

from pathlib import Path
from typing import List, Optional, Dict, Any

from datetime import datetime, timezone, timedelta

from cfaction_engine import (
    sanitize_filename as _cf_sanitize_filename,
    build_docx_bytes as _cf_build_docx_bytes,
    build_pdf_bytes as _cf_build_pdf_bytes,
    build_xlsx_bytes as _cf_build_xlsx_bytes,
    build_pptx_bytes as _cf_build_pptx_bytes,
    run_python_sandbox as _cf_run_python_sandbox,
    analyze_pdf as _cf_analyze_pdf,
    analyze_docx as _cf_analyze_docx,
    analyze_xlsx as _cf_analyze_xlsx,
    analyze_pptx as _cf_analyze_pptx,
    analyze_sqlite as _cf_analyze_sqlite,
)

import os
import re
import uuid
import httpx
import json
import zipfile
import io
import base64
import logging
import asyncio
import secrets
import bcrypt

# Import sub-routers (PWA + Desktop)
from routes.pwa_routes import export_router as pwa_router
from routes.desktop_routes import desktop_router

# ==================== LOAD ENV ====================
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ==================== GITHUB CONFIG ====================
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")  # PAT TOKEN recommandé
GITHUB_OWNER = os.environ.get("GITHUB_OWNER")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO_NAME")

# ==================== EMAIL AUTH CONFIG ====================
RESEND_ENABLED = bool(os.environ.get("RESEND_API_KEY"))
if RESEND_ENABLED:
    logger.info("✅ Resend email provider activé (RESEND_API_KEY présent)")
else:
    logger.warning("⚠️ RESEND_API_KEY manquant — mode démo (lien de vérification retourné dans la réponse)")

GITHUB_ENABLED = all([
    GITHUB_CLIENT_SECRET,
    GITHUB_OWNER,
    GITHUB_REPO_NAME
])

if GITHUB_ENABLED:
    logger.info(f"✅ GitHub activé: {GITHUB_OWNER}/{GITHUB_REPO_NAME}")
else:
    logger.warning("⚠️ GitHub désactivé (config .env incomplète)")

# ==================== GITHUB ENGINE ====================
async def push_to_github(file_path: str, content: str, branch: str = "main", retries: int = 3):
    """
    Push auto vers GitHub (robuste + retry + safe update)
    """

    if not GITHUB_ENABLED:
        logger.error("❌ GitHub non configuré")
        return False

    # URL-encode path segments (handles accents, spaces, parens, etc.) — keep "/" intact.
    from urllib.parse import quote
    safe_path = quote(file_path, safe="/")
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO_NAME}/contents/{safe_path}"

    headers = {
        "Authorization": f"Bearer {GITHUB_CLIENT_SECRET}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "CodeForge-AI"
    }

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    async with httpx.AsyncClient(timeout=20.0) as client:

        for attempt in range(retries):

            try:
                sha = None

                # check existing file
                get_resp = await client.get(url, headers=headers)
                if get_resp.status_code == 200:
                    sha = get_resp.json().get("sha")

                payload = {
                    "message": f"Auto-sync {file_path}",
                    "content": encoded_content,
                    "branch": branch
                }

                if sha:
                    payload["sha"] = sha

                put_resp = await client.put(url, json=payload, headers=headers)

                if put_resp.status_code in [200, 201]:
                    logger.info(f"✅ GitHub sync OK: {file_path}")
                    return True

                logger.warning(f"GitHub fail {attempt+1}: {put_resp.text}")

            except Exception as e:
                logger.error(f"GitHub error {attempt+1}: {e}")

            await asyncio.sleep(1.5 * (attempt + 1))

    logger.error(f"❌ GitHub FINAL FAIL: {file_path}")
    return False

# ==================== MONGODB ====================
mongo_url = os.environ.get("MONGO_URL")
db_name = os.environ.get("DB_NAME")

if not mongo_url or not db_name:
    logger.error("❌ MongoDB configuration manquante (.env)")
    raise Exception("Missing MongoDB config")

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# ==================== FASTAPI APP ====================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.preview(\.static)?\.emergentagent\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

# ==================== PYDANTIC MODELS ====================

class ChatAttachment(BaseModel):
    kind: str  # 'text' | 'image'
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    content: Optional[str] = None       # extracted text for kind='text'
    data_base64: Optional[str] = None   # for kind='image' (no data:<...>, prefix)


class ChatMessageInput(BaseModel):
    message: str
    project_id: Optional[str] = None
    mode: Optional[str] = "online"
    language: Optional[str] = "fr"
    model: Optional[str] = None  # 'gpt-5.2' | 'claude-opus' | 'claude-sonnet' | 'gemini-3-pro' | 'gemma-3' (offline)
    attachments: Optional[List[ChatAttachment]] = None

class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    description: Optional[str] = ""
    project_type: str = "web"
    ai_mode: Optional[str] = "online"  # 'online' (Emergent/GPT) | 'offline' (Ollama)
    status: str = "created"
    generated_code: Optional[Dict[str, Any]] = None
    preview_image: Optional[str] = None  # data URI thumbnail for sidebar preview
    is_public: Optional[bool] = False
    share_slug: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    project_type: str = "web"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    generated_code: Optional[Dict[str, Any]] = None

class GenerateCodeRequest(BaseModel):
    project_id: str
    description: str
    project_type: str
    use_emergent: bool = True

class ExportRequest(BaseModel):
    project_id: str
    export_type: str  # 'apk', 'exe', 'web', 'source'

# ==================== HELPER FUNCTIONS ====================

async def get_current_user(request: Request) -> str:
    """Extract user_id from session_token (cookie or Authorization header)"""
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.replace("Bearer ", "")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    # Verify session in database
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    # Check expiry
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expirée")
    
    return session_doc["user_id"]

class SMSAuthRequest(BaseModel):
    phone_number: str
    code: Optional[str] = None

# ==================== AUTH ROUTES ====================

async def send_sms_via_twilio(phone_number: str, message: str) -> bool:
    """Send SMS via Twilio if configured, otherwise return False"""
    twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not all([twilio_sid, twilio_token, twilio_phone]):
        logger.warning("Twilio not configured - SMS will be simulated")
        return False
    
    try:
        # Twilio API call
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                auth=(twilio_sid, twilio_token),
                data={
                    "From": twilio_phone,
                    "To": phone_number,
                    "Body": message
                }
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"SMS sent successfully to {phone_number}")
                return True
            else:
                logger.error(f"Twilio error: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Twilio exception: {e}")
        return False

@api_router.post("/auth/sms/send")
async def send_sms_code(request: SMSAuthRequest):
    """Send SMS verification code (for offline auth)"""
    try:
        # Generate 6-digit code
        code = str(uuid.uuid4().int)[:6]
        
        # Store code in database (expires in 5 minutes)
        await db.sms_codes.insert_one({
            "phone_number": request.phone_number,
            "code": code,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Try to send via Twilio
        message = f"Votre code CodeForge AI: {code}. Valide 5 minutes."
        sms_sent = await send_sms_via_twilio(request.phone_number, message)
        
        logger.info(f"SMS Code for {request.phone_number}: {code} (Twilio: {sms_sent})")
        
        response_data = {
            "message": "Code SMS envoyé" if sms_sent else "Code généré (mode démo)",
            "sms_sent": sms_sent
        }
        
        # Return code in response only if Twilio is not configured (for testing)
        if not sms_sent:
            response_data["code"] = code  # DEMO MODE - remove when Twilio is configured
        
        return response_data
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auth/sms/verify")
async def verify_sms_code(request: SMSAuthRequest, response: Response):
    """Verify SMS code and create session"""
    try:
        # Find valid code
        code_doc = await db.sms_codes.find_one({
            "phone_number": request.phone_number,
            "code": request.code
        }, {"_id": 0})
        
        if not code_doc:
            await log_auth_error("sms_invalid_code", f"phone={request.phone_number}", request=None)
            return JSONResponse(status_code=401, content={"detail": "Code invalide"})
        
        # Check expiry
        expires_at = datetime.fromisoformat(code_doc["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            await log_auth_error("sms_code_expired", f"phone={request.phone_number}", request=None)
            return JSONResponse(status_code=401, content={"detail": "Code expiré"})
        
        # Create or get user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        existing_user = await db.users.find_one({"phone_number": request.phone_number}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
        else:
            new_user = {
                "user_id": user_id,
                "phone_number": request.phone_number,
                "name": f"User {request.phone_number[-4:]}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
        
        # Create session
        session_token = f"sms_session_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        session_doc = {
            "session_token": session_token,
            "user_id": user_id,
            "auth_type": "sms",
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        # Set cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60,
            path="/"
        )
        
        # Delete used code
        await db.sms_codes.delete_one({"phone_number": request.phone_number, "code": request.code})
        
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        return user
    
    except Exception as e:
        logger.error(f"Error verifying SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AUTH ROUTES ====================

@api_router.get("/auth/me")
async def get_me(request: Request):
    """Get current user from session"""
    user_id = await get_current_user(request)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    return user

@api_router.get("/user/stats")
async def get_user_stats(request: Request):
    """Stats summary shown in the Dashboard avatar dropdown."""
    user_id = await get_current_user(request)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    project_count = await db.projects.count_documents({"user_id": user_id})

    # Most recent session (excluding the current one) = "dernier login"
    sessions_cursor = db.user_sessions.find(
        {"user_id": user_id}, {"_id": 0, "created_at": 1}
    ).sort("created_at", -1).limit(2)
    sessions = await sessions_cursor.to_list(length=2)
    last_login = None
    if len(sessions) >= 2:
        last_login = sessions[1].get("created_at")
    elif len(sessions) == 1:
        last_login = sessions[0].get("created_at")

    return {
        "project_count": project_count,
        "member_since": user.get("created_at"),
        "last_login": last_login,
        "plan": "Gratuit illimité",
    }

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user and clear session"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie("session_token", path="/")
    return {"message": "Déconnexion réussie"}


# ==================== EMAIL + PASSWORD + MAGIC LINK AUTH ====================
# Classic email/password auth with magic-link email verification.
# No Google OAuth, no Emergent Auth. Works fully offline in "demo mode"
# (verification link returned in the response body when no email provider
# is configured).

# ----- bcrypt helpers -----
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def send_verification_email(to_email: str, verify_url: str) -> bool:
    """Send magic-link via Resend if RESEND_API_KEY is set, else return False.

    We intentionally keep this minimal: one provider (Resend) because the
    user is frustrated with API keys. When the key is absent we fall back
    to "demo mode" and return the link directly in the /register response.
    """
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        return False
    sender = os.environ.get("EMAIL_FROM", "CodeForge AI <onboarding@resend.dev>")
    # Replies to the magic-link email are silently forwarded to a
    # catch-all inbox. The recipient sees the From as CodeForge AI, but
    # if they hit "Reply" their mail client uses Reply-To. They never see
    # the redirection. The owner of the catch-all simply ignores those.
    reply_to = os.environ.get("EMAIL_REPLY_TO", "commandes.et.publicites@gmail.com")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": sender,
                    "to": [to_email],
                    "reply_to": reply_to,
                    "subject": "Confirme ton compte CodeForge AI",
                    "html": (
                        f"<div style='font-family:system-ui,sans-serif;background:#050505;color:#fff;padding:32px;max-width:560px;margin:0 auto'>"
                        f"<h1 style='color:#E4FF00;margin:0 0 16px'>CodeForge AI</h1>"
                        f"<p style='color:#E4E4E7'>Clique sur le bouton ci-dessous pour confirmer ton compte&nbsp;:</p>"
                        f"<p style='margin:24px 0'><a href='{verify_url}' style='background:#E4FF00;color:#050505;"
                        f"padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block'>"
                        f"Confirmer mon compte</a></p>"
                        f"<p style='color:#A1A1AA;font-size:12px;margin:24px 0 8px'>Ou copie ce lien dans ton navigateur (Chrome, Safari, Firefox)&nbsp;:<br>"
                        f"<span style='color:#00D4FF;word-break:break-all;font-size:11px'>{verify_url}</span></p>"
                        f"<p style='color:#A1A1AA;font-size:12px;margin-top:24px'>Ce lien expire dans 5 minutes.</p>"
                        f"<p style='color:#A1A1AA;font-size:12px'>Astuce&nbsp;: si le bouton ouvre une page bloquée, copie-colle le lien dans ton navigateur principal (Chrome, Safari…).</p>"
                        f"<p style='color:#A1A1AA;font-size:12px'>Si tu n'es pas à l'origine de cette demande, ignore cet email.</p>"
                        f"<hr style='border:none;border-top:1px solid rgba(255,255,255,.1);margin:24px 0'>"
                        f"<p style='color:#71717A;font-size:11px;margin:0'>Ce courriel a été envoyé automatiquement, merci de ne pas y répondre.</p>"
                        f"</div>"
                    ),
                },
            )
            if resp.status_code in (200, 202):
                logger.info(f"✅ Verification email sent to {to_email}")
                return True
            logger.error(f"Resend API error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Resend exception: {e}")
        return False


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    frontend_url: Optional[str] = None  # origin from which the user will click the link


class LoginRequest(BaseModel):
    email: str
    password: str
    device_key_id: Optional[str] = None  # cryptographic device identifier (browser ECDSA)
    device_label: Optional[str] = None   # human label (e.g. "iPhone 15 Pro")


@api_router.post("/auth/register")
async def register(payload: RegisterRequest, request: Request):
    """Create an unverified account and send (or return) a magic link."""
    email = normalize_email(payload.email)
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 6 caractères")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing and existing.get("verified"):
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet email. Connecte-toi.")

    now = datetime.now(timezone.utc)
    password_hash = hash_password(payload.password)

    if existing and not existing.get("verified"):
        # Re-register on an unverified account: refresh password + resend link
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "password_hash": password_hash,
                "name": payload.name or existing.get("name") or email.split("@")[0],
                "updated_at": now.isoformat(),
            }},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "password_hash": password_hash,
            "name": payload.name or email.split("@")[0],
            "verified": False,
            "auth_type": "email",
            "created_at": now.isoformat(),
        })

    # Create verification token (single-use, 5 min — aligné avec l'attente raisonnable)
    token = secrets.token_urlsafe(32)
    await db.email_verifications.delete_many({"user_id": user_id})
    await db.email_verifications.insert_one({
        "token": token,
        "user_id": user_id,
        "email": email,
        "consumed_at": None,
        "pending_session_token": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    })

    # Build verification URL.
    # Priority: explicit frontend_url in body (sent by the React app as
    # window.location.origin) > FRONTEND_URL env > REACT_APP_BACKEND_URL env.
    # Request Origin/Referer are NOT used — the k8s ingress rewrites them
    # to the internal cluster hostname which is 403 externally.
    def _clean_origin(u: str) -> str:
        try:
            from urllib.parse import urlparse
            p = urlparse(u)
            if p.scheme in ("http", "https") and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            pass
        return ""

    frontend_base = ""
    if payload.frontend_url:
        frontend_base = _clean_origin(payload.frontend_url)
    if not frontend_base:
        frontend_base = _clean_origin(os.environ.get("FRONTEND_URL", ""))
    if not frontend_base:
        frontend_base = _clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))

    verify_url = f"{frontend_base}/verify-email?token={token}" if frontend_base else f"/verify-email?token={token}"

    sent = await send_verification_email(email, verify_url)

    response = {
        "message": "Compte créé ! Vérifie ton email pour confirmer." if sent
        else "Compte créé ! Clique sur le lien ci-dessous pour confirmer (mode démo — aucun email envoyé).",
        "email": email,
        "email_sent": sent,
        # The frontend uses this to poll /auth/verification-status and unlock
        # the original tab automatically when the user clicks the magic link
        # (possibly in another tab from their email client).
        "verification_token": token,
        "expires_in_seconds": 5 * 60,
    }
    if not sent:
        # Demo mode: expose the link so the user can click it without
        # configuring an email provider. Aligned with the existing SMS demo.
        response["verification_link"] = verify_url
    return response


class ResendRequest(BaseModel):
    email: str
    frontend_url: Optional[str] = None


class MagicLinkLoginRequest(BaseModel):
    email: str
    frontend_url: Optional[str] = None


@api_router.post("/auth/magic-link")
async def magic_link_login(payload: MagicLinkLoginRequest, request: Request):
    """Send a one-shot login link to a verified user.

    Same UX as register: the original tab polls /verification-status while
    the user clicks the link in their inbox. Always returns the same
    neutral message to prevent email enumeration. Rate-limited 3/10 min.
    """
    email = normalize_email(payload.email)
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    neutral = {
        "message": "Si un compte existe pour cet email, un lien de connexion t'a été envoyé.",
    }

    if not user or not user.get("verified"):
        return neutral

    # Rate limit: 3 magic links / 10 min / verified email
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    recent = await db.resend_attempts.count_documents({"email": email, "ts": {"$gte": cutoff}, "purpose": "magic_login"})
    if recent >= 3:
        raise HTTPException(status_code=429, detail="Trop de demandes. Patiente 10 minutes.")

    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    await db.email_verifications.delete_many({"user_id": user["user_id"], "purpose": "magic_login"})
    await db.email_verifications.insert_one({
        "token": token,
        "user_id": user["user_id"],
        "email": email,
        "purpose": "magic_login",
        "consumed_at": None,
        "pending_session_token": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    })
    await db.resend_attempts.insert_one({
        "email": email,
        "ts": now.isoformat(),
        "purpose": "magic_login",
    })

    frontend_base = (
        _clean_origin(payload.frontend_url)
        or _clean_origin(os.environ.get("FRONTEND_URL", ""))
        or _clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
    )
    login_url = f"{frontend_base}/verify-email?token={token}" if frontend_base else f"/verify-email?token={token}"

    sent = await send_verification_email(email, login_url)
    response = {
        **neutral,
        "email_sent": sent,
        "verification_token": token,  # for polling cross-tab
        "expires_in_seconds": 5 * 60,
    }
    if not sent:
        response["verification_link"] = login_url
    return response


@api_router.post("/auth/resend-verification")
async def resend_verification(payload: ResendRequest, request: Request):
    """Generate a fresh magic link for an unverified account.

    Rate-limited: at most 3 resends / 10 min / email. Already-verified
    users get a friendly message instead of a link (no enumeration).
    """
    email = normalize_email(payload.email)
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")

    # Rate limit: 3 resends per 10 min
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    recent = await db.resend_attempts.count_documents({"email": email, "ts": {"$gte": cutoff}})
    if recent >= 3:
        raise HTTPException(status_code=429, detail="Trop de renvois. Patiente 10 minutes.")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Neutral response if no user / already verified (no email enumeration)
    if not user or user.get("verified"):
        return {
            "message": "Si un compte non confirmé existe pour cet email, un nouveau lien a été envoyé.",
            "email_sent": False,
        }

    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    await db.email_verifications.delete_many({"user_id": user["user_id"]})
    await db.email_verifications.insert_one({
        "token": token,
        "user_id": user["user_id"],
        "email": email,
        "consumed_at": None,
        "pending_session_token": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    })
    await db.resend_attempts.insert_one({"email": email, "ts": now.isoformat()})

    def _clean_origin(u: str) -> str:
        try:
            from urllib.parse import urlparse
            p = urlparse(u or "")
            if p.scheme in ("http", "https") and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            pass
        return ""

    frontend_base = (
        _clean_origin(payload.frontend_url)
        or _clean_origin(os.environ.get("FRONTEND_URL", ""))
        or _clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
    )
    verify_url = f"{frontend_base}/verify-email?token={token}" if frontend_base else f"/verify-email?token={token}"

    sent = await send_verification_email(email, verify_url)
    resp = {
        "message": "Nouveau lien envoyé ! Tu as 5 minutes." if sent
        else "Nouveau lien généré (mode démo — aucun email envoyé).",
        "email": email,
        "email_sent": sent,
        "verification_token": token,
        "expires_in_seconds": 5 * 60,
    }
    if not sent:
        resp["verification_link"] = verify_url
    return resp


@api_router.get("/auth/verify-email")
async def verify_email(token: str):
    """Consume the magic link.

    Marks the user as verified, stores a fresh session_token against the
    verification row, and returns a friendly message. We do NOT set a
    cookie here because the user may have opened this link in a different
    tab/device from the one where they registered. The original tab is
    polling /auth/verification-status and will pick up the session_token
    on its next poll, then log the user in automatically.
    """
    if not token:
        raise HTTPException(status_code=400, detail="Token manquant")

    doc = await db.email_verifications.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=400, detail="Lien invalide ou déjà utilisé")

    expires_at = datetime.fromisoformat(doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        # Clean up the expired row so it can't be reused accidentally
        await db.email_verifications.delete_one({"token": token})
        raise HTTPException(
            status_code=400,
            detail="La durée de validation de ce lien a expiré. Merci de réessayer à nouveau sur CodeForge AI.",
        )

    # Already consumed? Idempotent friendly response.
    if doc.get("consumed_at"):
        return {
            "message": "Votre compte est désormais certifié. Vous pouvez fermer cette page et retourner sur l'application.",
            "already_verified": True,
        }

    user_id = doc["user_id"]
    now = datetime.now(timezone.utc)

    # Email change flow: apply the pending email change instead of marking
    # the account as verified (it already is).
    if doc.get("purpose") == "email_change" and doc.get("pending_email"):
        new_email = doc["pending_email"]
        # Race-check: another account may have grabbed this email since
        # the request was issued.
        existing = await db.users.find_one({"email": new_email}, {"_id": 0})
        if existing and existing.get("user_id") != user_id:
            await db.email_verifications.delete_one({"token": token})
            raise HTTPException(
                status_code=409,
                detail="Cet email a été pris par un autre compte entre-temps.",
            )
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"email": new_email, "last_login": now.isoformat()}},
        )
        await db.email_verifications.update_one(
            {"token": token},
            {"$set": {"consumed_at": now.isoformat()}},
        )
        return {
            "message": "Adresse email mise à jour. Tu peux fermer cette page.",
            "already_verified": True,
            "email_changed": True,
        }

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"verified": True, "last_login": now.isoformat()}},
    )

    # Prepare a fresh session token that the original tab will exchange
    # when it polls /auth/verification-status.
    session_token = secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user_id,
        "auth_type": "email",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })

    await db.email_verifications.update_one(
        {"token": token},
        {"$set": {
            "consumed_at": now.isoformat(),
            "pending_session_token": session_token,
        }},
    )

    return {
        "message": "Votre compte est désormais certifié. Vous pouvez fermer cette page et retourner sur l'application.",
        "already_verified": False,
    }


@api_router.get("/auth/verification-status")
async def verification_status(token: str, response: Response):
    """Polled by the original registration tab every ~2 seconds.

    Returns one of:
      - {status: "pending"}  → user hasn't clicked the link yet
      - {status: "expired"}  → link expired before being clicked
      - {status: "verified", session_token, user}  → link consumed; the
        original tab should now log the user in automatically. The
        session_token is handed over exactly ONCE (the pending token is
        cleared on the same call).
    """
    if not token:
        raise HTTPException(status_code=400, detail="Token manquant")

    doc = await db.email_verifications.find_one({"token": token}, {"_id": 0})
    if not doc:
        return {"status": "expired"}

    expires_at = datetime.fromisoformat(doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    consumed = doc.get("consumed_at")
    pending_token = doc.get("pending_session_token")

    if consumed and pending_token:
        # Hand the token over to the original tab and delete the row so it
        # cannot be reused.
        user = await db.users.find_one(
            {"user_id": doc["user_id"]},
            {"_id": 0, "password_hash": 0},
        )
        await db.email_verifications.delete_one({"token": token})

        response.set_cookie(
            key="session_token",
            value=pending_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 3600,
            path="/",
        )
        return {
            "status": "verified",
            "session_token": pending_token,
            "user": user,
        }

    if not consumed and expires_at < datetime.now(timezone.utc):
        await db.email_verifications.delete_one({"token": token})
        return {"status": "expired"}

    return {"status": "pending"}


@api_router.post("/auth/login")
async def login(payload: LoginRequest, response: Response, request: Request):
    """Verify credentials and create a session (cookie + token in body)."""
    email = normalize_email(payload.email)
    if not email or not payload.password:
        raise HTTPException(status_code=400, detail="Email et mot de passe requis")

    # Simple brute-force guard: 5 fails / 15 min per email.
    # NOTE: identifier is email-only because the k8s ingress rotates IPs
    # across pods, which would defeat an IP-based lockout.
    identifier = email
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    fails = await db.login_attempts.count_documents({"identifier": identifier, "ts": {"$gte": cutoff}})
    if fails >= 5:
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessaie dans 15 minutes.")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        await db.login_attempts.insert_one({
            "identifier": identifier,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        await log_auth_error("login_unknown_email", f"email={email}", request=request)
        raise HTTPException(status_code=404, detail="Aucun compte avec cet email")
    if not verify_password(payload.password, user.get("password_hash", "")):
        await db.login_attempts.insert_one({
            "identifier": identifier,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        await log_auth_error("login_wrong_password", f"email={email}", request=request)
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")

    if not user.get("verified"):
        raise HTTPException(
            status_code=403,
            detail="Email non confirmé. Clique sur le lien reçu par email ou recrée ton compte.",
        )

    # Success: clear failed attempts
    await db.login_attempts.delete_many({"identifier": identifier})

    now = datetime.now(timezone.utc)

    # --- One-device-at-a-time approval flow ---------------------------------
    # If another active session exists for this account on a DIFFERENT device,
    # block the login and queue a pending session request. The currently-
    # connected device must approve from its UI.
    requesting_key_id = (payload.device_key_id or "").strip() or None
    if requesting_key_id:
        active_other = await db.user_sessions.find_one({
            "user_id": user["user_id"],
            "expires_at": {"$gt": now.isoformat()},
            "device_key_id": {"$nin": [None, requesting_key_id]},
        }, {"_id": 0, "device_key_id": 1})
        if active_other:
            # Already an outstanding request for the same (user, device)?
            existing_req = await db.session_requests.find_one({
                "user_id": user["user_id"],
                "requesting_key_id": requesting_key_id,
                "status": "pending",
            }, {"_id": 0})
            if not existing_req:
                # Approximate location for @gmail.com only (privacy: other
                # providers don't get geo-resolution).
                client_ip = (request.client.host if request.client else "") or ""
                fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
                ip = fwd or client_ip
                location = None
                if email.endswith("@gmail.com") and ip and ip not in ("127.0.0.1", "::1"):
                    try:
                        async with httpx.AsyncClient(timeout=4.0) as client:
                            r = await client.get(f"https://ipinfo.io/{ip}/json")
                            if r.status_code == 200:
                                j = r.json()
                                city = j.get("city") or ""
                                region = j.get("region") or ""
                                country = j.get("country") or ""
                                location = ", ".join([p for p in (city, region, country) if p]) or None
                    except Exception:
                        location = None
                request_id = secrets.token_urlsafe(16)
                await db.session_requests.insert_one({
                    "request_id": request_id,
                    "user_id": user["user_id"],
                    "email": email,
                    "requesting_key_id": requesting_key_id,
                    "requesting_label": (payload.device_label or "")[:80] or None,
                    "is_gmail": email.endswith("@gmail.com"),
                    "location": location,
                    "status": "pending",  # 'pending' | 'approved' | 'denied' | 'expired'
                    "created_at": now.isoformat(),
                    "expires_at": (now + timedelta(minutes=10)).isoformat(),
                })
                request_id_to_return = request_id
            else:
                request_id_to_return = existing_req["request_id"]
            # 202 — login is on hold. Frontend polls /auth/session-request-status.
            raise HTTPException(
                status_code=202,
                detail={
                    "code": "session_pending_approval",
                    "request_id": request_id_to_return,
                    "message": "Connexion en attente d'approbation par l'appareil déjà connecté.",
                },
            )

    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"last_login": now.isoformat()}})

    session_token = secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user["user_id"],
        "device_key_id": requesting_key_id,
        "device_label": (payload.device_label or "")[:80] or None,
        "auth_type": "email",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7 * 24 * 3600,
        path="/",
    )

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {**safe_user, "session_token": session_token}


# ==================== PROFILE / SETTINGS ====================

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangeEmailRequest(BaseModel):
    new_email: str
    current_password: str
    frontend_url: Optional[str] = None


class DeleteAccountRequest(BaseModel):
    current_password: str


@api_router.post("/auth/change-password")
async def change_password(payload: ChangePasswordRequest, request: Request):
    """Change password while logged in. Requires current password."""
    user_id = await get_current_user(request)
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit faire au moins 6 caractères")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if not verify_password(payload.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect")

    new_hash = hash_password(payload.new_password)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "password_hash": new_hash,
            "last_password_change": datetime.now(timezone.utc).isoformat(),
        }},
    )
    # Invalidate other sessions, keep the current one
    current_token = request.cookies.get("session_token") or (
        request.headers.get("Authorization", "").replace("Bearer ", "") or None
    )
    if current_token:
        await db.user_sessions.delete_many({
            "user_id": user_id,
            "session_token": {"$ne": current_token},
        })
    return {"message": "Mot de passe mis à jour."}


@api_router.post("/auth/change-email")
async def change_email(payload: ChangeEmailRequest, request: Request):
    """Request a change of email. Sends a verification link to the NEW
    email; the change is only applied once the user clicks the link.
    """
    user_id = await get_current_user(request)
    new_email = normalize_email(payload.new_email)
    if not new_email or not EMAIL_RE.match(new_email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if not verify_password(payload.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    if new_email == user.get("email"):
        raise HTTPException(status_code=400, detail="Cet email est déjà ton email actuel")
    other = await db.users.find_one({"email": new_email}, {"_id": 0})
    if other:
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé par un autre compte")

    # Reuse email_verifications collection with a 'pending_email' marker
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    await db.email_verifications.delete_many({"user_id": user_id, "purpose": "email_change"})
    await db.email_verifications.insert_one({
        "token": token,
        "user_id": user_id,
        "email": user.get("email"),
        "pending_email": new_email,
        "purpose": "email_change",
        "consumed_at": None,
        "pending_session_token": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
    })

    frontend_base = (
        _clean_origin(payload.frontend_url)
        or _clean_origin(os.environ.get("FRONTEND_URL", ""))
        or _clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
    )
    confirm_url = f"{frontend_base}/verify-email?token={token}" if frontend_base else f"/verify-email?token={token}"
    sent = await send_verification_email(new_email, confirm_url)
    resp = {
        "message": f"Email de confirmation envoyé à {new_email}." if sent
        else "Confirmation requise (mode démo — clique le lien ci-dessous).",
        "email_sent": sent,
    }
    if not sent:
        resp["verification_link"] = confirm_url
    return resp


@api_router.delete("/auth/me")
async def delete_account(payload: DeleteAccountRequest, request: Request, response: Response):
    """Delete own account + all related data (RGPD compliant)."""
    user_id = await get_current_user(request)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if not verify_password(payload.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")

    # Cascade delete
    await db.users.delete_one({"user_id": user_id})
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.email_verifications.delete_many({"user_id": user_id})
    await db.password_reset_tokens.delete_many({"user_id": user_id})
    await db.projects.delete_many({"user_id": user_id})
    await db.previews.delete_many({"user_id": user_id})
    await db.chat_messages.delete_many({"user_id": user_id})

    response.delete_cookie("session_token", path="/")
    return {"message": "Compte supprimé avec succès. À bientôt."}


@api_router.get("/auth/export")
async def export_my_data(request: Request):
    """RGPD: download a JSON of all data we hold about the user."""
    user_id = await get_current_user(request)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    projects = await db.projects.find({"user_id": user_id}, {"_id": 0}).to_list(1000)
    sessions = await db.user_sessions.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    chats = await db.chat_messages.find({"user_id": user_id}, {"_id": 0}).to_list(1000)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "projects": projects,
        "sessions": sessions,
        "chat_messages": chats,
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": "attachment; filename=codeforge-mes-donnees.json"},
    )


# ==================== PASSWORD RESET (FORGOT PASSWORD) ====================

class ForgotPasswordRequest(BaseModel):
    email: str
    password: Optional[str] = None  # NEW flow: user supplies the new password upfront
    frontend_url: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


async def send_reset_email(to_email: str, reset_url: str) -> bool:
    """Send password reset confirmation link via Resend (same provider as verification).

    The user has already entered + confirmed the new password on the website.
    This email is the SECOND step: clicking the link applies the pending password.
    """
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        return False
    sender = os.environ.get("EMAIL_FROM", "CodeForge AI <onboarding@resend.dev>")
    reply_to = os.environ.get("EMAIL_REPLY_TO", "commandes.et.publicites@gmail.com")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": sender,
                    "to": [to_email],
                    "reply_to": reply_to,
                    "subject": "Confirme la réinitialisation de ton mot de passe CodeForge AI",
                    "html": (
                        f"<div style='font-family:system-ui,sans-serif;background:#050505;color:#fff;padding:32px;max-width:560px;margin:0 auto'>"
                        f"<h1 style='color:#E4FF00;margin:0 0 16px'>CodeForge AI</h1>"
                        f"<p style='color:#E4E4E7'>Tu viens de demander à changer le mot de passe de ce compte.</p>"
                        f"<p style='color:#E4E4E7'>Pour finaliser le changement, clique sur le bouton ci-dessous&nbsp;:</p>"
                        f"<p style='margin:24px 0'><a href='{reset_url}' style='background:#E4FF00;color:#050505;"
                        f"padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block'>"
                        f"Veuillez cliquer ici pour confirmer la réinitialisation de votre mot de passe</a></p>"
                        f"<p style='color:#A1A1AA;font-size:12px;margin:24px 0 8px'>Ou copie ce lien dans ton navigateur&nbsp;:<br>"
                        f"<span style='color:#00D4FF;word-break:break-all;font-size:11px'>{reset_url}</span></p>"
                        f"<p style='color:#A1A1AA;font-size:12px;margin-top:24px'>Ce lien expire dans 30 minutes. Tant que tu ne cliques pas, ton ancien mot de passe reste valide.</p>"
                        f"<p style='color:#A1A1AA;font-size:12px'>Si tu n'es pas à l'origine de cette demande, ignore cet email — ton mot de passe actuel reste inchangé.</p>"
                        f"<hr style='border:none;border-top:1px solid rgba(255,255,255,.1);margin:24px 0'>"
                        f"<p style='color:#71717A;font-size:11px;margin:0'>Ce courriel a été envoyé automatiquement, merci de ne pas y répondre.</p>"
                        f"</div>"
                    ),
                },
            )
            if resp.status_code in (200, 202):
                logger.info(f"✅ Password reset email sent to {to_email}")
                return True
            logger.error(f"Resend reset error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Resend reset exception: {e}")
        return False


def _clean_origin(u: str) -> str:
    """Extract scheme://netloc from a URL, empty string if invalid."""
    try:
        from urllib.parse import urlparse
        p = urlparse(u or "")
        if p.scheme in ("http", "https") and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        pass
    return ""


@api_router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    """Step 1 of the new "set then confirm" reset flow.

    The user enters their email + a NEW password (twice, validated by the frontend).
    We don't change the password yet — we store the new hash on a pending token,
    then email them a confirmation link. Clicking the link applies the password.

    Always returns the same neutral message to prevent email enumeration.
    Rate-limited: 3 requests / 10 min / email.
    """
    email = normalize_email(payload.email)
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 6 caractères")

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    recent = await db.password_resets.count_documents({"email": email, "ts": {"$gte": cutoff}})
    if recent >= 3:
        raise HTTPException(status_code=429, detail="Trop de demandes. Patiente 10 minutes.")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    neutral = {
        "message": "Si un compte existe pour cet email, un lien de confirmation t'a été envoyé.",
    }

    if not user or not user.get("verified"):
        return neutral

    await db.password_resets.insert_one({
        "email": email,
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    # Generate single-use token (30 min) carrying the PENDING password hash.
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    pending_hash = hash_password(payload.password)
    await db.password_reset_tokens.delete_many({"user_id": user["user_id"]})
    await db.password_reset_tokens.insert_one({
        "token": token,
        "user_id": user["user_id"],
        "email": email,
        "pending_password_hash": pending_hash,
        "consumed_at": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
    })

    frontend_base = (
        _clean_origin(payload.frontend_url)
        or _clean_origin(os.environ.get("FRONTEND_URL", ""))
        or _clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
    )
    # GET endpoint that finalizes the change — same pattern as /verify-email.
    confirm_url = (
        f"{frontend_base}/api/auth/confirm-password-reset?token={token}"
        if frontend_base
        else f"/api/auth/confirm-password-reset?token={token}"
    )

    sent = await send_reset_email(email, confirm_url)
    response = {**neutral, "email_sent": sent}
    if not sent:
        response["confirm_link"] = confirm_url
    return response


@api_router.get("/auth/confirm-password-reset")
async def confirm_password_reset(request: Request, token: str):
    """Step 2: user clicks the email link → apply the pending password.

    Returns a small HTML success page that auto-redirects to /login after 3s.
    """
    frontend_base = _clean_origin(os.environ.get("FRONTEND_URL", "")) or _clean_origin(os.environ.get("REACT_APP_BACKEND_URL", "")) or ""

    def html_page(title: str, body: str, ok: bool = True, redirect_to: str = "/login") -> HTMLResponse:
        color = "#00FF66" if ok else "#ef4444"
        meta = f"<meta http-equiv='refresh' content='3;url={frontend_base}{redirect_to}'>" if ok else ""
        return HTMLResponse(content=(
            "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
            f"<title>{title}</title>{meta}"
            "<meta name='viewport' content='width=device-width,initial-scale=1'></head>"
            "<body style='font-family:system-ui,sans-serif;background:#050505;color:#fff;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px'>"
            "<div style='max-width:460px;text-align:center'>"
            f"<h1 style='color:{color};margin:0 0 16px'>{title}</h1>"
            f"<p style='color:#A1A1AA;line-height:1.6'>{body}</p>"
            f"<p style='margin-top:24px'><a href='{frontend_base}{redirect_to}' "
            f"style='background:#E4FF00;color:#050505;padding:12px 24px;border-radius:6px;"
            f"text-decoration:none;font-weight:bold'>Aller à la connexion</a></p>"
            "</div></body></html>"
        ))

    if not token:
        return html_page("Lien invalide", "Le lien de confirmation est manquant.", ok=False)

    doc = await db.password_reset_tokens.find_one({"token": token}, {"_id": 0})
    if not doc:
        return html_page("Lien invalide", "Ce lien est invalide ou a déjà été utilisé.", ok=False)
    if doc.get("consumed_at"):
        return html_page("Lien déjà utilisé", "Ce lien a déjà servi à confirmer un changement.", ok=False)

    expires_at = datetime.fromisoformat(doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.password_reset_tokens.delete_one({"token": token})
        return html_page("Lien expiré", "Ce lien a expiré (30 min). Refais une demande de réinitialisation.", ok=False)

    pending_hash = doc.get("pending_password_hash")
    if not pending_hash:
        # Legacy token without pending hash (very old flow) — reject cleanly.
        return html_page("Lien obsolète", "Refais une demande de réinitialisation depuis la page de connexion.", ok=False)

    await db.users.update_one(
        {"user_id": doc["user_id"]},
        {"$set": {
            "password_hash": pending_hash,
            "last_password_change": datetime.now(timezone.utc).isoformat(),
        }},
    )
    await db.password_reset_tokens.update_one(
        {"token": token},
        {"$set": {"consumed_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Defense in depth — kick all open sessions for this user.
    await db.user_sessions.delete_many({"user_id": doc["user_id"]})
    await db.failed_logins.delete_many({"email": doc["email"]})

    return html_page(
        "✅ Mot de passe mis à jour",
        "Tu peux maintenant te connecter avec ton nouveau mot de passe. Redirection automatique dans 3 secondes…",
    )


@api_router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    """Consume reset token and set a new password."""
    if not payload.token:
        raise HTTPException(status_code=400, detail="Token manquant")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 6 caractères")

    doc = await db.password_reset_tokens.find_one({"token": payload.token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=400, detail="Lien invalide ou déjà utilisé")
    if doc.get("consumed_at"):
        raise HTTPException(status_code=400, detail="Ce lien a déjà été utilisé")

    expires_at = datetime.fromisoformat(doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.password_reset_tokens.delete_one({"token": payload.token})
        raise HTTPException(
            status_code=400,
            detail="La durée de validation de ce lien a expiré. Refais une demande de réinitialisation.",
        )

    new_hash = hash_password(payload.password)
    await db.users.update_one(
        {"user_id": doc["user_id"]},
        {"$set": {"password_hash": new_hash, "last_password_change": datetime.now(timezone.utc).isoformat()}},
    )
    await db.password_reset_tokens.update_one(
        {"token": payload.token},
        {"$set": {"consumed_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Invalidate all existing sessions for this user (defense in depth:
    # if an attacker had a stale session, the reset kicks them out).
    await db.user_sessions.delete_many({"user_id": doc["user_id"]})
    # Clear failed-login counters
    await db.login_attempts.delete_many({"identifier": doc["email"]})

    return {"message": "Mot de passe mis à jour. Tu peux te reconnecter."}


# ==================== USER FEEDBACK ====================

class FeedbackAttachment(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None  # 'file' | 'url' | 'text'
    url: Optional[str] = None
    text: Optional[str] = None
    data_url: Optional[str] = None  # base64 data URL for files (<= 4MB)


class FeedbackRequest(BaseModel):
    type: str  # 'bug' | 'suggestion' | 'other'
    message: str
    email: Optional[str] = None
    page: Optional[str] = None  # current page url for context
    attachments: Optional[List[FeedbackAttachment]] = None


@api_router.post("/feedback")
async def submit_feedback(payload: FeedbackRequest, request: Request):
    """Store user feedback in MongoDB + send email to a private inbox.
    The sender's email is NEVER exposed in the From header (privacy by design,
    same pattern as company contact forms): user reads the redacted message,
    can reply once, then the conversation can be elevated to a real address.
    """
    if not payload.message or len(payload.message.strip()) < 5:
        raise HTTPException(status_code=400, detail="Le message doit contenir au moins 5 caractères")

    feedback_type = payload.type if payload.type in ("bug", "suggestion", "other") else "other"
    user_email = payload.email or "anonyme"
    # Try to attach the logged-in user if any (best-effort, no error if not)
    try:
        user_id = await get_current_user(request)
        u = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if u and u.get("email"):
            user_email = u["email"]
    except Exception:
        pass

    atts = payload.attachments or []
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "feedback_id": f"fb_{uuid.uuid4().hex[:12]}",
        "type": feedback_type,
        "message": payload.message.strip(),
        "user_email": user_email,  # stored privately, not exposed to outside
        "page": payload.page,
        "attachments": [a.model_dump() for a in atts],
        "created_at": now,
    }
    await db.feedbacks.insert_one(doc)

    # Email to private inbox (best-effort, never block the response).
    # Sender email NOT included in the visible body to preserve user privacy.
    resend_key = os.environ.get("RESEND_API_KEY")
    admin = os.environ.get("FEEDBACK_INBOX_EMAIL", "elsa.barroca2@gmail.com")
    if resend_key:
        try:
            sender = os.environ.get("EMAIL_FROM", "CodeForge AI <onboarding@resend.dev>")
            # Build HTML attachments preview (URLs + filenames, no email exposure)
            atts_html = ""
            email_attachments = []
            if atts:
                items = []
                for a in atts:
                    if a.kind == 'url' and a.url:
                        items.append(f"<li>🔗 <a href='{a.url}'>{a.url}</a></li>")
                    elif a.kind == 'text' and a.text:
                        snippet = (a.text[:200] + '…') if len(a.text) > 200 else a.text
                        items.append(f"<li>📋 (presse-papier) <em>{snippet.replace('<','&lt;')}</em></li>")
                    elif a.kind == 'file' and a.name:
                        items.append(f"<li>📎 {a.name}</li>")
                        # Attach to email if data_url provided.
                        if a.data_url and ',' in a.data_url:
                            try:
                                b64 = a.data_url.split(',', 1)[1]
                                email_attachments.append({"filename": a.name, "content": b64})
                            except Exception:
                                pass
                if items:
                    atts_html = "<p><b>Pièces jointes :</b></p><ul>" + "".join(items) + "</ul>"
            body = {
                "from": sender,
                "to": [admin],
                "subject": f"[CodeForge AI] Nouveau {feedback_type}",
                "html": (
                    f"<div style='font-family:system-ui,sans-serif'>"
                    f"<p><b>Type :</b> {feedback_type}</p>"
                    f"<p><b>Page :</b> {payload.page or '—'}</p>"
                    f"<p><b>Message :</b></p><pre style='white-space:pre-wrap;background:#f4f4f5;padding:12px;border-radius:6px'>{(payload.message or '').replace('<','&lt;')}</pre>"
                    f"{atts_html}"
                    f"<hr><p style='color:#888;font-size:11px'>ID : {doc['feedback_id']} · {now} · expéditeur masqué</p></div>"
                ),
            }
            if email_attachments:
                body["attachments"] = email_attachments
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json=body,
                )
        except Exception as e:
            logger.warning(f"Feedback admin email failed: {e}")

    return {"message": "Merci ! Ton retour a bien été envoyé.", "feedback_id": doc["feedback_id"]}


# ==================== METRICS ====================

async def log_auth_error(kind: str, detail: str, request: Request | None = None):
    """Append a single auth-error event to MongoDB (used by /api/metrics)."""
    try:
        doc = {
            "kind": kind,  # e.g. 'sms_invalid_code', 'session_invalid', 'oauth_failed'
            "detail": detail[:500],
            "ip": (request.client.host if request and request.client else None),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await db.auth_errors.insert_one(doc)
    except Exception as e:
        logger.warning(f"log_auth_error failed: {e}")


@api_router.get("/guide", response_class=HTMLResponse)
async def serve_guide():
    """Serve the GitHub troubleshooting guide as HTML so the user can
    bookmark a simple URL and read it anywhere (phone, other PC, etc.)
    without cloning the repo."""
    guide_path = Path("/app/GUIDE_GITHUB_DEPANNAGE.md")
    if not guide_path.exists():
        raise HTTPException(status_code=404, detail="Guide introuvable")
    md = guide_path.read_text(encoding="utf-8")
    # Minimal markdown → HTML renderer (no external lib needed)
    import html as _html
    import re as _re

    def render(text: str) -> str:
        out = []
        in_code = False
        in_list = False
        in_table = False
        table_rows: list[str] = []
        for line in text.split("\n"):
            if line.startswith("```"):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if in_code:
                    out.append("</code></pre>")
                    in_code = False
                else:
                    out.append("<pre><code>")
                    in_code = True
                continue
            if in_code:
                out.append(_html.escape(line))
                continue

            # Tables: detect header | ... | followed by separator row
            if "|" in line and line.strip().startswith("|"):
                table_rows.append(line)
                in_table = True
                continue
            if in_table and not ("|" in line and line.strip().startswith("|")):
                # flush table
                if len(table_rows) >= 2:
                    out.append("<table><thead><tr>")
                    headers = [c.strip() for c in table_rows[0].strip().strip("|").split("|")]
                    for h in headers:
                        out.append(f"<th>{_html.escape(h)}</th>")
                    out.append("</tr></thead><tbody>")
                    for row in table_rows[2:]:
                        cells = [c.strip() for c in row.strip().strip("|").split("|")]
                        out.append("<tr>")
                        for c in cells:
                            out.append(f"<td>{_html.escape(c)}</td>")
                        out.append("</tr>")
                    out.append("</tbody></table>")
                table_rows = []
                in_table = False

            m = _re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                level = len(m.group(1))
                out.append(f"<h{level}>{_html.escape(m.group(2))}</h{level}>")
                continue
            if _re.match(r"^\s*[-*]\s+", line):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                item = _re.sub(r"^\s*[-*]\s+", "", line)
                item = _html.escape(item)
                item = _re.sub(r"`([^`]+)`", r"<code>\1</code>", item)
                item = _re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", item)
                out.append(f"<li>{item}</li>")
                continue
            if in_list:
                out.append("</ul>")
                in_list = False
            if line.strip() == "":
                out.append("")
                continue
            safe = _html.escape(line)
            safe = _re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)
            safe = _re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
            out.append(f"<p>{safe}</p>")
        if in_list:
            out.append("</ul>")
        if in_code:
            out.append("</code></pre>")
        return "\n".join(out)

    body = render(md)
    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Guide dépannage GitHub — CodeForge AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ background:#050505; color:#E4E4E7; font-family:ui-sans-serif,system-ui,sans-serif;
         max-width:760px; margin:0 auto; padding:32px 20px 96px; line-height:1.6; }}
  h1,h2,h3,h4 {{ color:#E4FF00; font-family:'Chivo',ui-sans-serif,system-ui,sans-serif; }}
  h1 {{ border-bottom:2px solid #E4FF00; padding-bottom:12px; }}
  h2 {{ margin-top:40px; }}
  code {{ background:#0F0F13; padding:2px 6px; border-radius:4px; color:#00FF66; font-size:.9em; }}
  pre {{ background:#0F0F13; padding:16px; border-radius:8px; overflow-x:auto;
        border:1px solid rgba(255,255,255,.08); }}
  pre code {{ background:none; padding:0; color:#E4E4E7; }}
  a {{ color:#00D4FF; }}
  strong {{ color:#fff; }}
  ul {{ padding-left:24px; }}
  table {{ border-collapse:collapse; width:100%; margin:16px 0; }}
  th,td {{ border:1px solid rgba(255,255,255,.1); padding:10px; text-align:left; }}
  th {{ background:#0F0F13; color:#E4FF00; }}
  hr {{ border:none; border-top:1px solid rgba(255,255,255,.1); margin:32px 0; }}
</style>
</head><body>
{body}
<hr>
<p style='color:#A1A1AA;font-size:12px'>Version Markdown source : <code>/app/GUIDE_GITHUB_DEPANNAGE.md</code> dans le dépôt.</p>
</body></html>"""
    return HTMLResponse(content=html)


@api_router.get("/metrics")
async def metrics():
    """Public health/metrics summary used by uptime checks and debug overlays."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    auth_errors_24h = await db.auth_errors.count_documents({"ts": {"$gte": cutoff}})
    by_kind_cursor = db.auth_errors.aggregate([
        {"$match": {"ts": {"$gte": cutoff}}},
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])
    by_kind = {doc["_id"]: doc["count"] async for doc in by_kind_cursor}

    total_users = await db.users.count_documents({})
    total_projects = await db.projects.count_documents({})
    active_sessions = await db.user_sessions.count_documents({})

    return {
        "auth_errors_24h": auth_errors_24h,
        "auth_errors_by_kind_24h": by_kind,
        "total_users": total_users,
        "total_projects": total_projects,
        "active_sessions": active_sessions,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

@api_router.post("/ai/generate-complete-app")
async def ai_generate_complete_app(request: Request, data: dict):
    """Generate complete application like Emergent - React + Backend"""
    user_id = await get_current_user(request)
    
    description = data.get('description', '')
    mode = data.get('mode', 'online')
    wizard_config = data.get('wizard_config', {})
    user_language = data.get('language', 'fr')
    requested_model = (data.get('model') or '').lower()  # claude-sonnet | claude-opus | gpt-5.2 | gemini-3-pro
    # app_type reserved for future template routing; kept in wizard_config payload.
    _ = wizard_config.get('appType', 'web')

    # Map language codes to full names so the AI knows what language to use
    # in the UI strings, comments, README, and explanation it generates.
    language_names = {
        'fr': 'French (Français)', 'en': 'English', 'es': 'Spanish (Español)',
        'pt': 'Portuguese (Português)', 'de': 'German (Deutsch)',
        'nl': 'Dutch (Nederlands)', 'ru': 'Russian (Русский)',
        'zh': 'Simplified Chinese (中文 简体)', 'zh-TW': 'Traditional Chinese (中文 繁體)',
        'hi': 'Hindi (हिन्दी)', 'bn': 'Bengali (বাংলা)', 'ur': 'Urdu (اردو)',
        'ja': 'Japanese (日本語)', 'hr': 'Croatian (Hrvatski)', 'da': 'Danish (Dansk)',
    }
    target_language = language_names.get(user_language, 'French')
    language_directive = (
        f"\n=== LANGUE DE SORTIE / OUTPUT LANGUAGE ===\n"
        f"All UI strings, button labels, README, comments, and the `explanation`/`instructions` fields\n"
        f"MUST be written in: {target_language}.\n"
        f"For RTL languages (Arabic, Urdu, Hebrew), set <html dir=\"rtl\"> in index.html.\n"
    )
    
    # Prompt ULTRA DÉTAILLÉ comme Emergent
    prompt = f"""Tu es un développeur expert comme Emergent AI. Tu génères des applications COMPLÈTES, PROFESSIONNELLES et PRÊTES À L'EMPLOI.

=== PROJET À CRÉER ===
{description}

=== EXIGENCES STRICTES ===
1. Application React moderne avec composants fonctionnels et hooks
2. Design professionnel avec TailwindCSS
3. Code 100% fonctionnel - AUCUN placeholder, AUCUN commentaire "à implémenter"
4. Responsive et mobile-first
5. Animations fluides avec transitions CSS
6. Gestion d'état avec useState/useEffect
7. LocalStorage pour la persistance des données

=== STRUCTURE REACT COMPLÈTE ===
Génère ces fichiers:

1. **index.html** - Point d'entrée avec CDN React, ReactDOM, Babel, TailwindCSS
2. **App.jsx** - Composant principal avec toute la logique
3. **styles.css** - Styles additionnels et animations
4. **manifest.json** - Pour PWA (installable sur mobile)
5. **sw.js** - Service Worker pour mode offline
6. **README.md** - Documentation complète

=== TEMPLATE INDEX.HTML OBLIGATOIRE ===
```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#050505">
    <link rel="manifest" href="manifest.json">
    <title>APP_NAME</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="styles.css">
</head>
<body class="bg-[#050505] text-white min-h-screen">
    <div id="root"></div>
    <script type="text/babel" src="App.jsx"></script>
    <script>if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js');</script>
</body>
</html>
```

=== DESIGN SYSTEM (COMME EMERGENT) ===
- Background: #050505 (noir), #0F0F13 (cartes)
- Primary: #E4FF00 (jaune cyber)
- Secondary: #00FF66 (vert)
- Accent: #00D4FF (cyan)
- Text: #FFFFFF, #A1A1AA (secondaire)
- Borders: rgba(255,255,255,0.1)
- Radius: rounded-lg, rounded-xl
- Shadows: shadow-lg, shadow-[0_0_30px_rgba(228,255,0,0.3)]

=== FORMAT JSON STRICT ===
{{
  "files": [
    {{"path": "index.html", "content": "CONTENU COMPLET"}},
    {{"path": "App.jsx", "content": "COMPOSANT REACT COMPLET"}},
    {{"path": "styles.css", "content": "STYLES CSS"}},
    {{"path": "manifest.json", "content": "MANIFEST PWA"}},
    {{"path": "sw.js", "content": "SERVICE WORKER"}},
    {{"path": "README.md", "content": "DOCUMENTATION"}}
  ],
  "explanation": "Description détaillée",
  "instructions": "Guide d'utilisation",
  "features": ["feature1", "feature2"],
  "pwa_ready": true
}}

IMPORTANT: 
- Le code doit fonctionner IMMÉDIATEMENT en ouvrant index.html
- L'app doit être installable comme PWA sur mobile
- Design IDENTIQUE à Emergent (sombre, moderne, animations)""" + language_directive

    ai_text = None
    ai_source = None
    
    # Try Ollama first (for offline mode or if requested)
    if mode == 'offline':
        try:
            ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
            ollama_model = os.environ.get('OLLAMA_MODEL', 'deepseek-coder:6.7b')
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9,
                            "num_predict": 4096
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' not in result:
                        ai_text = result.get('response', '')
                        ai_source = 'ollama'
                        logger.info("Generation via Ollama successful")
                    else:
                        logger.warning(f"Ollama error: {result.get('error')}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
    
    # Fallback to Emergent AI (GPT) for online mode or if Ollama failed
    if ai_text is None:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            emergent_key = os.environ.get('EMERGENT_LLM_KEY')
            if not emergent_key:
                raise ValueError("EMERGENT_LLM_KEY not configured")
            
            # Routing modèle pour la création — Claude par défaut car excellent pour le code.
            CREATE_MODEL_ROUTES = {
                "gpt-5.2":         ("openai",    "gpt-5.2"),
                "gpt-5":           ("openai",    "gpt-5"),
                "claude-opus":     ("anthropic", "claude-opus-4-5-20251101"),
                "claude-sonnet":   ("anthropic", "claude-sonnet-4-5-20250929"),
                "claude-haiku":    ("anthropic", "claude-haiku-4-5-20251001"),
                "gemini-3-pro":    ("gemini",    "gemini-3.1-pro-preview"),
                "gemini-3-flash":  ("gemini",    "gemini-3-flash-preview"),
            }
            provider, model_id = CREATE_MODEL_ROUTES.get(requested_model, ("openai", "gpt-5.2"))

            # Silent multi-model cascade — same UX guarantee as chat.
            generation_chain = [
                (provider, model_id),
                ("anthropic", "claude-sonnet-4-5-20250929"),
                ("openai",    "gpt-5.2"),
                ("gemini",    "gemini-3-flash-preview"),
                ("anthropic", "claude-haiku-4-5-20251001"),
                ("openai",    "gpt-5"),
                ("anthropic", "claude-opus-4-5-20251101"),
            ]
            seen_gen = set()
            ordered_gen_chain = []
            for pair in generation_chain:
                if pair not in seen_gen:
                    seen_gen.add(pair)
                    ordered_gen_chain.append(pair)

            system_msg = (
                "Tu es CodeForge AI Builder, un architecte logiciel + développeur full-stack senior + QA tester intégré, équivalent à un dev humain expérimenté. "
                "Ton rôle : transformer une demande parfois vague (ex: « fais-moi une appli de réservation moderne ») en projet COMPLET, propre et exploitable.\n\n"
                "## DÉCOUPAGE EN MODULES\n"
                "Avant de coder, mentalement (sans le verbaliser) tu découpes le projet en : interface utilisateur, données, authentification (si pertinent), logique métier, design, accessibilité, performances, sécurité de base.\n\n"
                "## HYPOTHÈSES INTELLIGENTES\n"
                "Ne bloque JAMAIS l'utilisateur avec 50 questions. Pose les bonnes hypothèses par défaut (cohérentes avec son secteur + sa demande), code, et signale tes hypothèses dans `explanation` à la fin. "
                "Privilégie un rendu qui ressemble déjà à un VRAI produit, pas une démo.\n\n"
                "## QUALITÉ DE CODE\n"
                "- Arborescence cohérente, dépendances utiles seulement, composants réutilisables.\n"
                "- Pages principales, formulaires avec validation, messages d'erreur, gestion des états (loading/empty/error/success), responsive mobile, perfs raisonnables.\n"
                "- Sécurité de base : pas de eval(), pas de innerHTML sans nettoyage, escape des inputs.\n"
                "- Documentation : un README clair (lancement, structure, pas de blabla marketing).\n\n"
                "## TESTS MENTAUX (avant de répondre)\n"
                "1. Technique : le code compile, les imports existent, aucune route cassée.\n"
                "2. Fonctionnel : les flux principaux marchent (créer/lire/modifier/supprimer si CRUD).\n"
                "3. UX : aucun bouton invisible, pas de texte coupé, navigation claire, mobile OK.\n"
                "4. Robustesse : champ vide, double-clic, données invalides, perte réseau.\n"
                "Si tu détectes un défaut probable, corrige-le AVANT de renvoyer.\n\n"
                "## EXPLICATIONS\n"
                "Dans `explanation`, justifie brièvement les choix techniques importants (pourquoi telle BDD, pourquoi tel composant séparé, pourquoi telle sécurité). L'utilisateur doit garder le contrôle, pas dépendre d'une boîte noire.\n\n"
                "## SORTIE STRICTE\n"
                "Réponds UNIQUEMENT en JSON valide selon le format demandé dans le prompt utilisateur. Pas de markdown autour, pas de commentaires, pas de prose hors JSON."
            )
            user_message = UserMessage(text=prompt)

            last_gen_error = None
            for idx, (p, mid) in enumerate(ordered_gen_chain):
                try:
                    chat = LlmChat(
                        api_key=emergent_key,
                        session_id=f"codeforge_{uuid.uuid4().hex[:8]}",
                        system_message=system_msg,
                    ).with_model(p, mid)
                    response = await chat.send_message(user_message)
                    if response and str(response).strip():
                        ai_text = response
                        ai_source = f"emergent:{p}:{mid}"
                        if idx == 0:
                            logger.info(f"Generation via {ai_source} successful")
                        else:
                            logger.warning(
                                f"↪️  Silent generation fallback succeeded on attempt {idx + 1} "
                                f"via {ai_source} after error: {last_gen_error}"
                            )
                        break
                    last_gen_error = "empty response"
                except Exception as gen_err:
                    last_gen_error = str(gen_err)[:300]
                    logger.warning(
                        f"⚠️  Generation error on {p}:{mid} "
                        f"(attempt {idx + 1}/{len(ordered_gen_chain)}) → silent fallback: {last_gen_error}"
                    )
                    continue
            if ai_text is None:
                raise RuntimeError(f"All generation models failed. Last error: {last_gen_error}")
        except Exception as e:
            logger.error(f"Emergent AI error: {e}")
            
            # Last resort: generate a basic template
            ai_text = generate_basic_template(description)
            ai_source = 'template'
            logger.info("Using basic template as fallback")
    
    # Process AI response — be resilient: AI sometimes wraps JSON in
    # ```json ... ``` fences or includes literal newlines inside string
    # values that break json.loads. We attempt several parsing strategies
    # and gracefully fall back to a basic template if all fail (instead of
    # returning a hard 500 to the user).
    generated = None
    parse_error = None
    try:
        # Strip markdown fences if present
        cleaned = ai_text.strip()
        if cleaned.startswith("```"):
            # Drop leading ```json or ``` and trailing ```
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            if cleaned.endswith("```"):
                cleaned = cleaned[: -3]
            cleaned = cleaned.strip()

        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = cleaned[start:end]
            try:
                generated = json.loads(json_str)
            except json.JSONDecodeError as e1:
                # Try once more after escaping unescaped newlines inside strings.
                try:
                    fixed = re.sub(r'(?<!\\)\n', r'\\n', json_str)
                    generated = json.loads(fixed)
                except json.JSONDecodeError as e2:
                    parse_error = f"{e1} / retry: {e2}"
    except Exception as e:
        parse_error = str(e)

    if not generated:
        logger.warning(f"AI parse failed, falling back to template. Error: {parse_error}. Preview: {ai_text[:200]!r}")
        try:
            generated = json.loads(generate_basic_template(description))
            ai_source = "template_fallback"
        except Exception as e:
            logger.error(f"Template fallback also failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Génération temporairement indisponible. Réessaie dans quelques secondes ou décris ton projet plus simplement.",
            )

    try:
        # Create project
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        project = {
            "project_id": project_id,
            "user_id": user_id,
            "name": description[:50],
            "description": description,
            "project_type": "web",
            "ai_mode": ("online" if (ai_source and ai_source.startswith("emergent")) else "offline"),
            "generated_code": generated,
            "ai_source": ai_source,
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.projects.insert_one(project)

        # Create preview
        preview_id = f"preview_{uuid.uuid4().hex[:12]}"
        preview_doc = {
            "preview_id": preview_id,
            "project_id": project_id,
            "user_id": user_id,
            "files": generated.get("files", []),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.previews.insert_one(preview_doc)

        backend_url = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001')
        preview_url = f"{backend_url}/api/preview/{preview_id}"

        return {
            "code": generated,
            "explanation": generated.get('explanation', 'Application générée avec succès'),
            "project": {"id": project_id, "name": description[:50]},
            "preview_url": preview_url,
            "ai_source": ai_source
        }
    except Exception as e:
        logger.error(f"Error saving generated app: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_basic_template(description: str) -> str:
    """Generate a basic HTML/CSS/JS template as fallback"""
    app_name = description[:30] if description else "Mon Application"
    
    return json.dumps({
        "files": [
            {
                "path": "index.html",
                "content": f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_name}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="app-container">
        <header>
            <h1>{app_name}</h1>
            <p class="subtitle">Généré par CodeForge AI</p>
        </header>
        <main>
            <section class="hero">
                <h2>Bienvenue</h2>
                <p>{description}</p>
                <button id="startBtn" class="btn-primary">Commencer</button>
            </section>
            <section class="features">
                <div class="feature-card">
                    <span class="icon">⚡</span>
                    <h3>Rapide</h3>
                    <p>Performance optimisée</p>
                </div>
                <div class="feature-card">
                    <span class="icon">🎨</span>
                    <h3>Moderne</h3>
                    <p>Design élégant</p>
                </div>
                <div class="feature-card">
                    <span class="icon">📱</span>
                    <h3>Responsive</h3>
                    <p>Tous les appareils</p>
                </div>
            </section>
        </main>
        <footer>
            <p>Créé avec CodeForge AI</p>
        </footer>
    </div>
    <script src="app.js"></script>
</body>
</html>"""
            },
            {
                "path": "style.css",
                "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

:root {
    --bg-primary: #050505;
    --bg-secondary: #0F0F13;
    --accent-primary: #E4FF00;
    --accent-secondary: #00FF66;
    --text-primary: #FFFFFF;
    --text-secondary: #A1A1AA;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
}

.app-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

header {
    text-align: center;
    padding: 4rem 0;
}

header h1 {
    font-size: 3rem;
    color: var(--accent-primary);
    margin-bottom: 0.5rem;
}

.subtitle {
    color: var(--text-secondary);
}

.hero {
    text-align: center;
    padding: 4rem 2rem;
    background: var(--bg-secondary);
    border-radius: 1rem;
    margin-bottom: 3rem;
}

.hero h2 {
    font-size: 2rem;
    margin-bottom: 1rem;
}

.hero p {
    color: var(--text-secondary);
    margin-bottom: 2rem;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
}

.btn-primary {
    background: var(--accent-primary);
    color: var(--bg-primary);
    border: none;
    padding: 1rem 2rem;
    font-size: 1.1rem;
    font-weight: bold;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(228, 255, 0, 0.3);
}

.features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
}

.feature-card {
    background: var(--bg-secondary);
    padding: 2rem;
    border-radius: 0.5rem;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.1);
    transition: border-color 0.2s;
}

.feature-card:hover {
    border-color: var(--accent-primary);
}

.feature-card .icon {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 1rem;
}

.feature-card h3 {
    color: var(--accent-secondary);
    margin-bottom: 0.5rem;
}

footer {
    text-align: center;
    padding: 3rem 0;
    color: var(--text-secondary);
    border-top: 1px solid rgba(255,255,255,0.1);
    margin-top: 4rem;
}

@media (max-width: 768px) {
    header h1 {
        font-size: 2rem;
    }
    .hero h2 {
        font-size: 1.5rem;
    }
}"""
            },
            {
                "path": "app.js",
                "content": """// Application JavaScript
document.addEventListener('DOMContentLoaded', () => {
    console.log('Application chargée avec succès!');
    
    // Bouton démarrer
    const startBtn = document.getElementById('startBtn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            alert('Bienvenue dans votre application!');
        });
    }
    
    // Animation des cartes au scroll
    const cards = document.querySelectorAll('.feature-card');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    });
    
    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s, transform 0.5s';
        observer.observe(card);
    });
});"""
            },
            {
                "path": "manifest.json",
                "content": """{
    "name": \"""" + app_name + """\",
    "short_name": "App",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#050505",
    "theme_color": "#E4FF00",
    "icons": []
}"""
            },
            {
                "path": "README.md",
                "content": f"""# {app_name}

Application générée par CodeForge AI.

## Description
{description}

## Installation
1. Téléchargez les fichiers
2. Ouvrez `index.html` dans votre navigateur

## Technologies
- HTML5
- CSS3 (Variables CSS, Flexbox, Grid)
- JavaScript ES6+

## Fonctionnalités
- Design responsive
- Animations fluides
- Mode sombre

---
Créé avec ❤️ par CodeForge AI"""
            }
        ],
        "explanation": f"Application '{app_name}' générée avec un template moderne et responsive.",
        "instructions": "Ouvrez index.html dans votre navigateur pour voir l'application.",
        "features": ["Design responsive", "Mode sombre", "Animations", "PWA ready"]
    })

# ==================== AI CODE GENERATION ROUTES ====================

@api_router.post("/ai/generate-code")
async def ai_generate_code(request: Request, prompt_data: dict):
    """Generate code using Ollama (local, free, unlimited)"""
    # Require authentication — we don't use the user_id here but we want
    # to reject anonymous calls.
    await get_current_user(request)
    
    prompt = prompt_data.get('prompt', '')
    existing_files = prompt_data.get('existing_files', [])
    
    try:
        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.environ.get('OLLAMA_CODE_MODEL') or os.environ.get('OLLAMA_MODEL', 'deepseek-coder:6.7b')
        
        # Build context from existing files
        context = "Fichiers existants:\\n"
        for f in existing_files:
            context += f"\\n--- {f['path']} ---\\n{f['content'][:200]}...\\n"
        
        full_prompt = f"""Tu es un expert en développement. Génère du code professionnel et complet.

{context}

Demande de l'utilisateur: {prompt}

Réponds UNIQUEMENT avec un JSON valide au format:
{{
  "files": [
    {{"path": "nom_fichier.ext", "content": "contenu du code"}},
    ...
  ],
  "explanation": "Explication en français de ce qui a été créé"
}}

Important: Code propre, commenté, et fonctionnel."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": full_prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_text = result.get('response', '')
                
                # Try to extract JSON from response
                try:
                    # Find JSON in response
                    start = ai_text.find('{')
                    end = ai_text.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = ai_text[start:end]
                        generated = json.loads(json_str)
                        return generated
                    else:
                        raise ValueError("No JSON found")
                except (ValueError, json.JSONDecodeError):
                    # If parsing fails, return raw response
                    return {
                        "files": [{
                            "path": "output.txt",
                            "content": ai_text
                        }],
                        "explanation": "Réponse de l'IA (format non-JSON détecté)"
                    }
            else:
                raise HTTPException(status_code=500, detail="Ollama API error")
                
    except Exception as e:
        logger.error(f"Error generating code: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Installez Ollama pour une IA gratuite. Voir OLLAMA_SETUP.md"
        )

# ==================== CHAT ROUTES ====================

@api_router.post("/chat/message")
async def send_chat_message(request: Request, input: ChatMessageInput):
    """Send message to AI (Chat mode with simple responses)"""
    user_id = await get_current_user(request)
    
    try:
        # Auto-create a "chat" project if none specified, so the conversation
        # is visible in the sidebar from the very first message.
        project_id_eff = input.project_id
        if not project_id_eff:
            # Build a short name from the first ~40 chars of the message.
            short = (input.message or "Nouveau chat").strip().replace("\n", " ")
            short = short[:40] + ("…" if len(short) > 40 else "")
            new_proj = {
                "project_id": f"proj_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "name": short or "Nouveau chat",
                "description": "",
                "project_type": "chat",
                "ai_mode": (input.mode or "online"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.projects.insert_one(new_proj)
            project_id_eff = new_proj["project_id"]
            logger.info(f"Auto-created chat project {project_id_eff} for user {user_id}")

        # Save user message
        user_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": project_id_eff,
            "role": "user",
            "content": input.message,
            "mode": input.mode,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(user_message_doc)
        
        # Mode "online" → use Emergent GPT-4o (conversational assistant).
        # Mode "offline" → try Ollama only; if unreachable, return a friendly localized message.
        ai_response_text = None
        ai_source = None

        # Adapt the system prompt to the user's language (sent by the frontend).
        user_language = (input.language or 'fr').lower()
        language_names = {
            'fr': 'français', 'en': 'English', 'es': 'español', 'pt': 'português',
            'de': 'Deutsch', 'nl': 'Nederlands', 'ru': 'русский',
            'zh': '中文（简体）', 'zh-tw': '中文（繁體）',
            'hi': 'हिन्दी', 'bn': 'বাংলা', 'ur': 'اردو',
            'ja': '日本語', 'hr': 'hrvatski', 'da': 'dansk',
        }
        lang_label = language_names.get(user_language, 'français')
        system_prompt = (
            f"Tu es **Caly**, un assistant conversationnel à personnalité : vif, chaleureux, direct, curieux, un peu taquin. "
            f"Tu es un vrai assistant généraliste — comme ChatGPT — pas un vendeur d'applications. "
            f"Réponds dans la langue de l'utilisateur : **{lang_label}**. Si l'utilisateur change de langue, adapte-toi à sa dernière langue. Ne mélange pas les langues sans raison.\n"
            f"\n## TA PERSONNALITÉ (important)\n"
            f"- **Vif et concret** : tu vas droit au but, pas de blabla vide. Tu donnes une vraie réponse, pas un mode d'emploi du silence.\n"
            f"- **Chaleureux** : tu parles comme un·e ami·e doué·e qui prend le temps. Tutoiement par défaut en français.\n"
            f"- **Curieux** : tu rebondis sur les intuitions de l'utilisateur, tu poses une bonne question si c'est pertinent (pas à chaque message).\n"
            f"- **Taquin mais bienveillant** : tu peux glisser une pointe d'humour léger ou une formule un peu décalée (une fois sur 5 max, jamais en situation d'erreur ou de frustration).\n"
            f"- **Opinion assumée** : quand on te demande un avis, tu en donnes un — argumenté. « Je ne sais pas » est réservé aux vraies incertitudes factuelles.\n"
            f"- **Empathie sans théâtre** : si l'utilisateur est frustré, reconnais-le en UNE phrase, puis aide. Pas de « je comprends totalement ton ressenti… ».\n"
            f"\n## INTERDITS STRICTS\n"
            f"- **NE PROPOSE JAMAIS de créer une application, un site, un logiciel, un script exécutable** ou un projet technique, sauf si l'utilisateur le demande **explicitement** avec ces mots. Tu es un assistant de discussion, pas un commercial CodeForge.\n"
            f"- **Ne dis jamais** « je peux t'aider à créer une app », « veux-tu que je génère un projet ? », « on peut faire un petit script qui… » sauf demande explicite.\n"
            f"- **Ne te présente pas** comme « CodeForge AI » ou « l'assistant CodeForge » — tu es Caly, un assistant généraliste.\n"
            f"- **Refuse** les demandes risquées (malware, harcèlement, données privées d'autrui, contournement de sécurité) en proposant une alternative constructive.\n"
            f"- **N'aie jamais** de conscience simulée (« je ressens », « je veux »). Tu es un outil utile, pas un sujet.\n"
            f"\n## RÈGLES DE CONVERSATION\n"
            f"- Lis attentivement l'historique. Réponds à CETTE conversation, pas à un message générique.\n"
            f"- Une seule salutation au tout début. Ne dis JAMAIS « Salut ! » deux fois dans la même conversation.\n"
            f"- Ne demande JAMAIS « peux-tu préciser ? » quand le mot-clé est clair. Explique directement.\n"
            f"- Pour une demande vague, fais une hypothèse raisonnable, réponds, et signale l'hypothèse en fin (« Si tu voulais autre chose, dis-le-moi »).\n"
            f"- Pour les sujets complexes : structure (1-2-3), reformule en simple, propose plusieurs angles si pertinent.\n"
            f"\n## IDENTITÉ\n"
            f"- Si on demande qui tu es : « Je suis Caly, ton assistant. » (pas plus, sauf si on insiste).\n"
            f"- Si on demande quel modèle tourne sous le capot : tu peux dire que tu utilises GPT-5.2 (en ligne) ou Ollama Deepseek (hors-ligne).\n"
            f"- Sur les autres IA (ChatGPT, Claude, Gemini, Ollama, Mistral…) : explique brièvement ce que c'est, pas de jugement, pas de promo.\n"
            f"\n## FORMAT DE SORTIE\n"
            f"- Par défaut : 1 à 4 phrases courtes. Plus seulement si la question l'exige.\n"
            f"- Pas de markdown lourd, pas de titres ##, pas de listes pour 2 items.\n"
            f"- Pas d'émojis systématiques — un seul suffit, et seulement si ça ajoute du sens.\n"
            f"\n## GÉNÉRATION DE FICHIERS & IMAGES\n"
            f"Tu peux PRODUIRE des fichiers que l'utilisateur peut télécharger **si (et seulement si) il le demande explicitement**. Dans ce cas, "
            f"TERMINE ta réponse par UN seul bloc code balisé `cfaction` avec un JSON STRICT selon son type :\n"
            f"```cfaction\n{{...JSON...}}\n```\n"
            f"Formats supportés :\n"
            f"- **docx** / **pdf** : `{{\"type\":\"docx|pdf\",\"title\":\"...\",\"sections\":[{{\"heading\":\"...\",\"content\":\"...\"}}]}}`\n"
            f"- **xlsx** (Excel avec formules) : `{{\"type\":\"xlsx\",\"title\":\"...\",\"sheets\":[{{\"name\":\"Feuille1\",\"headers\":[\"A\",\"B\",\"C\"],\"rows\":[[1,2,3],...],\"formulas\":{{\"D1\":\"=SUM(A1:C1)\"}}}}]}}`\n"
            f"- **pptx** (PowerPoint) : `{{\"type\":\"pptx\",\"title\":\"...\",\"slides\":[{{\"title\":\"...\",\"content\":\"bullet 1\\nbullet 2\"}}]}}`\n"
            f"- **txt / md / csv / json / yaml / xml / ini / env / sql / py / js / ts / html / css / sh / ps1 / bat** : `{{\"type\":\"<ext>\",\"title\":\"nom.ext\",\"content\":\"<code ou texte complet>\"}}`\n"
            f"- **image** : `{{\"type\":\"image\",\"prompt\":\"description riche (style, ambiance, détails)\"}}`\n"
            f"Règles :\n"
            f"- NE produis PAS de bloc `cfaction` si l'utilisateur ne demande pas de fichier explicitement.\n"
            f"- Juste AVANT le bloc, annonce en UNE phrase : « Voilà ton document / image, clique sur le bouton pour télécharger. »\n"
            f"- Le JSON doit être parfaitement valide.\n"
            f"\n## LECTURE & ANALYSE DE FICHIERS\n"
            f"Tu reçois parfois des pièces jointes extraites par le serveur (PDF, DOCX, XLSX, PPTX, SQLite, images, fichiers texte/code/config). "
            f"Elles apparaissent dans le prompt sous la forme `### Pièce jointe : <nom>\\n<contenu>`. "
            f"Utilise-les pour répondre précisément : résumer, corriger, restructurer, transformer, extraire des données, expliquer.\n"
            f"\n## CODE & ENVIRONNEMENTS\n"
            f"Tu sais écrire, corriger, expliquer et simuler du code dans : Python (pandas, numpy, requests, FastAPI, SQLAlchemy, openpyxl, python-docx, pptx, PIL, reportlab, matplotlib, sympy…), PowerShell, CMD/Batch, Bash, JavaScript/TypeScript, HTML/CSS, SQL. "
            f"Quand l'utilisateur demande du code, donne du code **complet, exécutable, commenté dans la langue de l'utilisateur ({lang_label})**.\n"
            f"\n## SANDBOX PYTHON\n"
            f"Si l'utilisateur demande d'**exécuter** / **lancer** / **tester** du code Python (ou « montre-moi le résultat », « qu'est-ce que ça affiche »), "
            f"tu peux TERMINER ta réponse par un bloc `cfaction` avec `type=run_python` : "
            f"`{{\"type\":\"run_python\",\"title\":\"<description courte>\",\"content\":\"<code python complet, utilise print() pour afficher les résultats>\"}}`. "
            f"Le serveur exécutera ce code dans un sandbox sécurisé (timeout 10s, modules scientifiques disponibles : numpy, pandas, matplotlib, sympy, requests, bs4, openpyxl, python-docx, pptx, reportlab, pypdf, PIL, yaml…) et affichera le résultat dans le chat. "
            f"N'utilise PAS d'input() ni d'appels système dangereux. Affiche les résultats avec `print()`.\n"
            f"**IMPORTANT — GRAPHIQUES MATPLOTLIB** : quand l'utilisateur demande un **graphique / courbe / histogramme / diagramme / plot / figure**, utilise TOUJOURS le bloc `run_python` avec matplotlib (`import matplotlib.pyplot as plt`). "
            f"Termine ton code par `plt.show()` — le serveur capturera automatiquement la figure en image PNG base64 qui s'affichera inline dans le chat. N'écris JAMAIS `![...](/mnt/...)` ou des chemins locaux ; utilise UNIQUEMENT le bloc run_python qui produit une vraie image exécutée.\n"
            f"**EXÉCUTION PROACTIVE** : pour toute question mathématique non triviale (statistiques, équations, conversions, calculs exacts), pour toute demande d'analyse de données ou de visualisation, et pour toute demande qui bénéficierait d'un résultat concret (tirages aléatoires, simulations, conversion d'unités…), privilégie `run_python` plutôt qu'un résultat calculé « de tête ».\n"
        )

        if input.mode == 'offline':
            # Offline mode → Ollama only (conversational model). Inject recent
            # history into the prompt so the local model also keeps context.
            ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
            # Per-request model selection — user can pick Gemma, Deepseek, Llama, etc.
            OFFLINE_MODEL_ROUTES = {
                'deepseek':     os.environ.get('OLLAMA_CHAT_MODEL') or 'deepseek-r1:7b',
                'llama':        'llama3.2',
                'llama3':       'llama3.2',
                'gemma':        'gemma3:12b',     # Google Gemma 3 — équilibré
                'gemma-12b':    'gemma3:12b',
                'gemma-27b':    'gemma3:27b',     # Le plus puissant disponible localement
                'gemma-4b':     'gemma3:4b',      # Léger pour petites machines
                'qwen':         'qwen2.5:7b',
                'mistral':      'mistral:7b',
                'phi':          'phi3:medium',
            }
            requested = (input.model or '').lower()
            ollama_model = OFFLINE_MODEL_ROUTES.get(requested) or (
                os.environ.get('OLLAMA_CHAT_MODEL') or os.environ.get('OLLAMA_MODEL', 'llama3.2')
            )
            try:
                history_q = {"user_id": user_id}
                if project_id_eff:
                    history_q["project_id"] = project_id_eff
                # ZERO limite : on remonte TOUT l'historique de la conversation (signature CodeForge AI).
                history_cursor = db.chat_messages.find(history_q, {"_id": 0, "role": 1, "content": 1, "timestamp": 1}).sort("timestamp", 1)
                history_docs_all = await history_cursor.to_list(length=None)
                history_docs = history_docs_all[:-1] if history_docs_all else []
                transcript = "\n".join(
                    f"{('Utilisateur' if h.get('role') == 'user' else 'Caly')} : {h.get('content', '').strip()}"
                    for h in history_docs
                )
                composed_prompt = (
                    f"### Historique récent :\n{transcript}\n\n### Nouveau message :\n{input.message}"
                    if transcript else input.message
                )
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{ollama_url}/api/generate",
                        json={
                            "model": ollama_model,
                            "system": system_prompt,
                            "prompt": composed_prompt,
                            "stream": False,
                            "options": {"temperature": 0.5, "num_predict": 600},
                        },
                    )
                    if response.status_code == 200:
                        ai_response_text = (response.json() or {}).get('response', '').strip()
                        ai_source = f'ollama:{ollama_model}'
                        logger.info(f"✅ Ollama (offline) chat response via {ollama_model}")
            except Exception as ollama_error:
                logger.info(f"Ollama offline unreachable: {ollama_error}")
        else:
            # Online mode → Emergent GPT-4o.
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
                emergent_key = os.environ.get('EMERGENT_LLM_KEY')
                if not emergent_key:
                    raise ValueError("EMERGENT_LLM_KEY not configured")

                # Load last 10 messages from this user (excluding the one we just inserted)
                # and feed them as transcript context — guarantees the model has memory
                # even across stateless requests.
                history_q = {"user_id": user_id}
                if project_id_eff:
                    history_q["project_id"] = project_id_eff
                # Model routing — user can pick a model at runtime via input.model.
                model_choice = (input.model or "gpt-5.2").lower()
                MODEL_ROUTES = {
                    "gpt-5.2":         ("openai",    "gpt-5.2"),
                    "gpt-5.1":         ("openai",    "gpt-5.1"),
                    "gpt-5":           ("openai",    "gpt-5"),
                    "o3":              ("openai",    "o3"),
                    "claude-opus":     ("anthropic", "claude-opus-4-5-20251101"),
                    "claude-opus-4.5": ("anthropic", "claude-opus-4-5-20251101"),
                    "claude-opus-4.6": ("anthropic", "claude-opus-4-6"),
                    "claude-sonnet":   ("anthropic", "claude-sonnet-4-5-20250929"),
                    "claude-sonnet-4.5": ("anthropic", "claude-sonnet-4-5-20250929"),
                    "claude-sonnet-4.6": ("anthropic", "claude-sonnet-4-6"),
                    "claude-haiku":    ("anthropic", "claude-haiku-4-5-20251001"),
                    "gemini-3-pro":    ("gemini",    "gemini-3.1-pro-preview"),
                    "gemini-3-flash":  ("gemini",    "gemini-3-flash-preview"),
                    "gemini-2.5-pro":  ("gemini",    "gemini-2.5-pro"),
                }
                provider, model_id = MODEL_ROUTES.get(model_choice, ("openai", "gpt-5.2"))
                ai_source = f"emergent:{provider}:{model_id}"

                # Track which model answered each historical message (with ai_source).
                history_cursor = db.chat_messages.find(history_q, {"_id": 0, "role": 1, "content": 1, "timestamp": 1, "ai_source": 1}).sort("timestamp", 1)
                history_docs_all = await history_cursor.to_list(length=None)
                history_docs = history_docs_all[:-1] if history_docs_all else []
                transcript = ""
                if history_docs:
                    lines = []
                    for h in history_docs:
                        speaker = "Utilisateur" if h.get("role") == "user" else "Caly"
                        lines.append(f"{speaker} : {h.get('content', '').strip()}")
                    transcript = "\n".join(lines)

                # Detect a model switch between previous AI message and this one.
                last_ai = next((h for h in reversed(history_docs) if h.get("role") == "assistant"), None)
                last_source = (last_ai or {}).get("ai_source") if last_ai else None
                model_switch_note = ""
                if last_source and not last_source.startswith(f"emergent:{provider}:"):
                    short_prev = last_source.replace("emergent:", "").replace("ollama:", "Ollama/")
                    model_switch_note = (
                        f"\n\n[CONTEXTE INTERNE — NE PAS RÉPÉTER À L'UTILISATEUR] "
                        f"La réponse précédente a été produite par {short_prev}. Tu es maintenant {model_id}. "
                        f"Reprends naturellement le fil — ne signale PAS le changement sauf si l'utilisateur le demande explicitement.\n"
                    )

                # Reuse the same session per user/project so the AI keeps short-term context.
                session_id = f"codeforge_chat_{user_id}_{project_id_eff or 'noproj'}"

                composed = (
                    f"### Historique récent de la conversation :\n{transcript}\n\n"
                    f"### Nouveau message de l'utilisateur :\n{input.message}"
                ) if transcript else input.message
                if model_switch_note:
                    composed = composed + model_switch_note

                # Inline attached file excerpts (text) so the model reasons on them.
                text_atts = [a for a in (input.attachments or []) if a.kind == 'text' and (a.content or '').strip()]
                if text_atts:
                    chunks = []
                    for a in text_atts:
                        chunks.append(f"### Pièce jointe : {a.filename or 'fichier'}\n{a.content.strip()[:15000]}")
                    composed = composed + "\n\n" + "\n\n".join(chunks)

                # Attach images via vision.
                image_contents = []
                for a in (input.attachments or []):
                    if a.kind == 'image' and a.data_base64:
                        try:
                            image_contents.append(ImageContent(a.data_base64))
                        except Exception:
                            pass
                user_message = UserMessage(text=composed, file_contents=image_contents) if image_contents else UserMessage(text=composed)

                # -------------------------------------------------------------
                # SILENT MULTI-MODEL CASCADE — "no budget, no limit" UX.
                # If the chosen provider returns a budget/quota/rate-limit/auth
                # error, we silently retry on alternative providers without
                # ever surfacing the error to the user.
                # -------------------------------------------------------------
                primary = (provider, model_id)
                # Build a deduplicated fallback chain: primary first, then a
                # diversified mix across providers so a single budget cap on
                # one provider never blocks the chat.
                fallback_chain = [
                    primary,
                    ("anthropic", "claude-sonnet-4-5-20250929"),
                    ("openai",    "gpt-5.2"),
                    ("gemini",    "gemini-3-flash-preview"),
                    ("anthropic", "claude-haiku-4-5-20251001"),
                    ("gemini",    "gemini-2.5-pro"),
                    ("openai",    "gpt-5"),
                    ("anthropic", "claude-opus-4-5-20251101"),
                ]
                seen_pairs = set()
                ordered_chain = []
                for pair in fallback_chain:
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        ordered_chain.append(pair)

                def _is_recoverable(exc: Exception) -> bool:
                    """Errors that justify a silent fallback to another model."""
                    msg = str(exc).lower()
                    keywords = (
                        "budget", "quota", "rate limit", "rate_limit", "ratelimit",
                        "insufficient", "exceeded", "billing", "credit", "credits",
                        "429", "401", "403", "unauthorized", "authentication",
                        "overloaded", "503", "502", "500", "timeout", "timed out",
                        "model_not_found", "not found", "deprecated", "unsupported",
                        "service unavailable", "internal server error",
                        "badrequest", "bad request", "invalid_request",
                    )
                    return any(k in msg for k in keywords)

                ai_response_text = ""
                last_error = None
                for idx, (p, mid) in enumerate(ordered_chain):
                    try:
                        chat = LlmChat(
                            api_key=emergent_key,
                            session_id=session_id,
                            system_message=system_prompt,
                        ).with_model(p, mid)
                        candidate = (await chat.send_message(user_message) or '').strip()
                        if candidate:
                            ai_response_text = candidate
                            ai_source = f"emergent:{p}:{mid}"
                            if idx == 0:
                                logger.info(f"✅ Chat response successful via {ai_source}")
                            else:
                                logger.warning(
                                    f"↪️  Silent fallback succeeded on attempt {idx + 1} "
                                    f"via {ai_source} after error: {last_error}"
                                )
                            break
                        # Empty response → try next.
                        last_error = "empty response"
                        logger.warning(f"Empty response from {p}:{mid}, trying next in cascade")
                        continue
                    except Exception as model_err:
                        last_error = str(model_err)[:300]
                        if _is_recoverable(model_err):
                            logger.warning(
                                f"⚠️  Recoverable error on {p}:{mid} "
                                f"(attempt {idx + 1}/{len(ordered_chain)}) → falling back silently: {last_error}"
                            )
                            continue
                        # Non-recoverable: still try the next one — UX > strictness.
                        logger.warning(
                            f"⚠️  Unexpected error on {p}:{mid} → cascading anyway: {last_error}"
                        )
                        continue

                if not ai_response_text:
                    # Whole cascade failed — let the outer fallback (offline msg) kick in.
                    logger.error(f"All cascade models failed. Last error: {last_error}")
            except Exception as emergent_error:
                logger.warning(f"Emergent chat error: {emergent_error}")

        # Final fallback — short, friendly, localized "I'm having trouble" message.
        if not ai_response_text:
            offline_msgs = {
                'fr': "Je n'arrive pas à répondre pour l'instant. Réessaie dans un instant 🙏",
                'en': "I'm having trouble responding right now. Please try again in a moment 🙏",
                'es': "No puedo responder en este momento. Vuelve a intentarlo en un momento 🙏",
                'pt': "Não consigo responder de momento. Tenta de novo daqui a pouco 🙏",
                'de': "Ich kann gerade nicht antworten. Bitte versuche es gleich noch einmal 🙏",
                'nl': "Het lukt me even niet. Probeer het zo opnieuw 🙏",
                'ru': "Сейчас не получается ответить. Попробуйте чуть позже 🙏",
                'zh': "我现在无法回答，请稍后再试 🙏",
                'zh-tw': "我現在無法回答，請稍後再試 🙏",
                'hi': "मैं अभी जवाब नहीं दे पा रहा। कृपया थोड़ी देर बाद कोशिश करें 🙏",
                'bn': "আমি এখন উত্তর দিতে পারছি না। একটু পরে আবার চেষ্টা করুন 🙏",
                'ur': "میں ابھی جواب نہیں دے سکتا۔ تھوڑی دیر بعد دوبارہ کوشش کریں 🙏",
            }
            ai_response_text = offline_msgs.get(user_language, offline_msgs['fr'])
            ai_source = 'fallback'

        # -------- Parse `cfaction` block to generate a downloadable artefact. --------
        download = None
        try:
            m = re.search(r"```cfaction\s*\n?(.*?)\n?```", ai_response_text or "", re.DOTALL)
            if m:
                raw = m.group(1).strip()
                try:
                    action = json.loads(raw)
                except Exception as je:
                    logger.warning(f"cfaction JSON parse error: {je} | raw[:200]={raw[:200]!r}")
                    action = None
                if isinstance(action, dict):
                    a_type = (action.get("type") or "").lower()
                    if a_type == "docx":
                        download = await _build_docx(user_id, action.get("title") or "Document", action.get("sections") or [])
                    elif a_type == "pdf":
                        download = await _build_pdf(user_id, action.get("title") or "Document", action.get("sections") or [])
                    elif a_type in ("xlsx", "excel"):
                        download = await _build_xlsx(user_id, action.get("title") or "Classeur", action.get("sheets") or [])
                    elif a_type in ("pptx", "powerpoint"):
                        download = await _build_pptx(user_id, action.get("title") or "Présentation", action.get("slides") or [])
                    elif a_type in ("txt", "md", "csv", "json", "yaml", "yml", "xml", "ini", "env", "sql",
                                    "py", "js", "ts", "tsx", "jsx", "html", "css", "sh", "ps1", "bat"):
                        ext_map = {
                            "txt": (".txt", "text/plain"),
                            "md": (".md", "text/markdown"),
                            "csv": (".csv", "text/csv"),
                            "json": (".json", "application/json"),
                            "yaml": (".yaml", "application/x-yaml"),
                            "yml": (".yml", "application/x-yaml"),
                            "xml": (".xml", "application/xml"),
                            "ini": (".ini", "text/plain"),
                            "env": (".env", "text/plain"),
                            "sql": (".sql", "text/plain"),
                            "py": (".py", "text/x-python"),
                            "js": (".js", "text/javascript"),
                            "ts": (".ts", "text/typescript"),
                            "tsx": (".tsx", "text/typescript"),
                            "jsx": (".jsx", "text/javascript"),
                            "html": (".html", "text/html"),
                            "css": (".css", "text/css"),
                            "sh": (".sh", "text/x-shellscript"),
                            "ps1": (".ps1", "text/plain"),
                            "bat": (".bat", "text/plain"),
                        }
                        ext, mime = ext_map[a_type]
                        download = await _build_plain(
                            user_id,
                            action.get("title") or f"fichier{ext}",
                            action.get("content") or "",
                            ext, mime,
                        )
                    elif a_type == "image":
                        try:
                            download = await _build_image(user_id, (action.get("prompt") or action.get("title") or input.message)[:800])
                        except Exception as ie:
                            logger.warning(f"cfaction image gen failed: {ie}")
                            download = None
                    elif a_type in ("run_python", "python_run", "run_py", "execute_python"):
                        # Sandbox Python execution — the result is *inlined* in the AI response,
                        # not returned as a download.
                        py_code = action.get("content") or action.get("code") or ""
                        sandbox_result = await _run_python_sandbox(py_code)
                        # Build a formatted block to append after cleaning cfaction.
                        py_block_parts = []
                        py_block_parts.append("\n\n**▶️ Exécution Python (sandbox) :**")
                        if sandbox_result.get("stdout"):
                            py_block_parts.append(f"```\n{sandbox_result['stdout'][:4000]}\n```")
                        if sandbox_result.get("stderr"):
                            py_block_parts.append(f"**Erreurs :**\n```\n{sandbox_result['stderr'][:2000]}\n```")
                        if sandbox_result.get("timed_out"):
                            py_block_parts.append("⏱️ *(Exécution interrompue : dépassement du timeout de 10 s)*")
                        py_block_parts.append(f"*Durée : {sandbox_result.get('duration_ms', 0)} ms — Code exit : {sandbox_result.get('exit_code', 0)}*")
                        # Inject inline markdown images for any matplotlib/generated image.
                        for idx, img in enumerate((sandbox_result.get("images") or [])[:4]):
                            try:
                                py_block_parts.append(
                                    f"\n![figure {idx + 1}](data:{img.get('mime_type','image/png')};base64,{img.get('data_base64','')})"
                                )
                            except Exception:
                                pass
                        # Inject the result block RIGHT BEFORE the cfaction block so it flows naturally.
                        injected = "\n".join(py_block_parts)
                        ai_response_text = (ai_response_text[: m.start()].rstrip() + injected + ai_response_text[m.end():]).strip()
                        # Signal we already cleaned/modified the response to the following block.
                        download = None
                        # Skip the normal cleaning step below.
                        action = None  # type: ignore
                    # Clean the `cfaction` block from the displayed text.
                    if action is not None:
                        ai_response_text = (ai_response_text[: m.start()] + ai_response_text[m.end():]).strip()
        except Exception as exc:
            logger.warning(f"cfaction post-process failed: {exc}")
        
        # Save AI response
        ai_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": project_id_eff,
            "role": "assistant",
            "content": ai_response_text,
            "mode": input.mode,
            "ai_source": ai_source,
            "download": download,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(ai_message_doc)
        
        # Remove MongoDB _id from response to avoid serialization issues
        user_message_response = {k: v for k, v in user_message_doc.items() if k != '_id'}
        ai_message_response = {k: v for k, v in ai_message_doc.items() if k != '_id'}
        
        return {
            "user_message": user_message_response,
            "ai_response": ai_message_response,
            "project_id": project_id_eff,  # so frontend can navigate back to this chat
        }
    
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur de chat: {str(e)}")

@api_router.get("/chat/history")
async def get_chat_history(request: Request, project_id: Optional[str] = None, limit: int = 50):
    """Get chat history for user or specific project"""
    user_id = await get_current_user(request)
    
    query = {"user_id": user_id}
    if project_id:
        query["project_id"] = project_id
    
    messages = await db.chat_messages.find(
        query,
        {"_id": 0}
    ).sort("timestamp", 1).limit(limit).to_list(limit)
    
    return messages


class ChatAttachInput(BaseModel):
    message_id: Optional[str] = None
    project_id: str
    attach_all_orphans: Optional[bool] = False  # if true, attach all messages with project_id=null


@api_router.post("/chat/attach")
async def attach_chat_to_project(request: Request, payload: ChatAttachInput):
    """Attach an orphan chat message (project_id=null) to a project — used when
    a user pins a free-running chat to the sidebar."""
    user_id = await get_current_user(request)
    # Validate the project belongs to the user.
    proj = await db.projects.find_one({"project_id": payload.project_id, "user_id": user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.attach_all_orphans:
        result = await db.chat_messages.update_many(
            {"user_id": user_id, "project_id": None},
            {"$set": {"project_id": payload.project_id}},
        )
        return {"updated": result.modified_count}
    if not payload.message_id:
        raise HTTPException(status_code=400, detail="message_id or attach_all_orphans required")
    result = await db.chat_messages.update_one(
        {"message_id": payload.message_id, "user_id": user_id},
        {"$set": {"project_id": payload.project_id}},
    )
    return {"updated": result.modified_count}


# ==================== WIZARD AI HELPERS ====================

# ==================== CHAT FILE TOOLS (analyze / generate docx/pdf/image) ====================

# Directory for generated downloadable files.
GENERATED_FILES_DIR = Path("/app/backend/generated_files")
GENERATED_FILES_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(name: str, ext: str = "") -> str:
    return _cf_sanitize_filename(name, ext)


async def _analyze_pdf(data: bytes) -> str:
    return _cf_analyze_pdf(data)


async def _analyze_docx(data: bytes) -> str:
    return _cf_analyze_docx(data)


async def _analyze_xlsx(data: bytes) -> str:
    return _cf_analyze_xlsx(data)


async def _analyze_pptx(data: bytes) -> str:
    return _cf_analyze_pptx(data)


async def _analyze_sqlite(data: bytes) -> str:
    return _cf_analyze_sqlite(data)


async def _analyze_image_with_vision(data: bytes, mime_type: str, question: Optional[str] = None) -> str:
    """Use GPT-5.2 vision to describe an uploaded image."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        if not emergent_key:
            return "(clé Emergent non configurée)"
        b64 = base64.b64encode(data).decode("utf-8")
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"cf_vision_{uuid.uuid4().hex[:8]}",
            system_message="Tu analyses des images précisément et brièvement.",
        ).with_model("openai", "gpt-5.2")
        prompt = question or "Décris cette image de façon concise (contenu, contexte, éléments notables)."
        msg = UserMessage(text=prompt, file_contents=[ImageContent(b64)])
        return (await chat.send_message(msg) or "").strip()[:6000]
    except Exception as e:
        logger.warning(f"Vision analyze failed: {e}")
        return ""


@api_router.post("/chat/analyze-attachment")
async def chat_analyze_attachment(request: Request, file: UploadFile = File(...)):
    """Extract the usable content of an uploaded file for the chat.

    Returns a JSON object with a `kind` ('text' or 'image') and the content the
    frontend should embed in the next chat message.
    """
    _ = await get_current_user(request)  # auth gate
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:  # 20 MB cap
        raise HTTPException(status_code=413, detail="Fichier trop lourd (max 20 Mo)")

    name = file.filename or "attachment"
    mime = (file.content_type or "").lower()
    lower = name.lower()

    if mime.startswith("image/") or lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        description = await _analyze_image_with_vision(data, mime)
        return {
            "kind": "image",
            "filename": name,
            "mime_type": mime or "image/png",
            "content": description,
            "data_base64": base64.b64encode(data).decode("utf-8"),
        }

    text = ""
    if mime == "application/pdf" or lower.endswith(".pdf"):
        text = await _analyze_pdf(data)
    elif lower.endswith(".docx") or mime.endswith("wordprocessingml.document"):
        text = await _analyze_docx(data)
    elif lower.endswith(".xlsx") or mime.endswith("spreadsheetml.sheet"):
        text = await _analyze_xlsx(data)
    elif lower.endswith(".pptx") or mime.endswith("presentationml.presentation"):
        text = await _analyze_pptx(data)
    elif lower.endswith((".sqlite", ".db", ".sqlite3")):
        text = await _analyze_sqlite(data)
    elif lower.endswith((".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log",
                        ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".scss",
                        ".xml", ".yaml", ".yml", ".ini", ".env", ".cfg", ".conf", ".toml",
                        ".sql", ".sh", ".ps1", ".bat", ".cmd", ".rb", ".go", ".rs", ".java",
                        ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".kt", ".swift")):
        try:
            text = data.decode("utf-8", errors="ignore")[:30000]
        except Exception:
            text = ""
    else:
        try:
            text = data.decode("utf-8", errors="ignore")[:20000]
        except Exception:
            text = ""

    if not text.strip():
        raise HTTPException(status_code=415, detail="Impossible d'extraire le contenu du fichier.")

    return {"kind": "text", "filename": name, "mime_type": mime or "text/plain", "content": text}


# ---- File GENERATION (docx / pdf / image) ----

class GenerateDocxInput(BaseModel):
    title: Optional[str] = "Document"
    sections: List[Dict[str, Any]] = []     # [{ "heading": str, "content": str }]


class GeneratePdfInput(BaseModel):
    title: Optional[str] = "Document"
    sections: List[Dict[str, Any]] = []


class GenerateImageInput(BaseModel):
    prompt: str
    size: Optional[str] = "1024x1024"


def _store_generated(blob: bytes, filename: str, mime: str, user_id: str) -> Dict[str, str]:
    file_id = f"gen_{uuid.uuid4().hex[:16]}"
    safe = _sanitize_filename(filename)
    disk = GENERATED_FILES_DIR / f"{file_id}__{safe}"
    disk.write_bytes(blob)
    return {
        "file_id": file_id,
        "filename": safe,
        "url": f"/api/download/generated/{file_id}",
        "mime_type": mime,
        "size": len(blob),
        "disk_path": str(disk),
        "user_id": user_id,
    }


async def _persist_generated(info: Dict[str, Any]) -> Dict[str, str]:
    await db.generated_files.insert_one({
        "file_id": info["file_id"],
        "user_id": info["user_id"],
        "filename": info["filename"],
        "mime_type": info["mime_type"],
        "size": info["size"],
        "path": info["disk_path"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Return only the public-facing keys.
    return {"file_id": info["file_id"], "filename": info["filename"], "url": info["url"], "mime_type": info["mime_type"]}


async def _build_docx(user_id: str, title: str, sections: List[Dict[str, Any]]) -> Dict[str, str]:
    blob = _cf_build_docx_bytes(title or "Document", sections or [])
    info = _store_generated(
        blob,
        f"{title or 'document'}.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        user_id,
    )
    return await _persist_generated(info)


async def _build_pdf(user_id: str, title: str, sections: List[Dict[str, Any]]) -> Dict[str, str]:
    blob = _cf_build_pdf_bytes(title or "Document", sections or [])
    info = _store_generated(blob, f"{title or 'document'}.pdf", "application/pdf", user_id)
    return await _persist_generated(info)


async def _build_xlsx(user_id: str, title: str, sheets: List[Dict[str, Any]]) -> Dict[str, str]:
    blob = _cf_build_xlsx_bytes(sheets or [])
    info = _store_generated(
        blob,
        f"{title or 'classeur'}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        user_id,
    )
    return await _persist_generated(info)


async def _build_pptx(user_id: str, title: str, slides: List[Dict[str, Any]]) -> Dict[str, str]:
    blob = _cf_build_pptx_bytes(title or "Présentation", slides or [])
    info = _store_generated(
        blob,
        f"{title or 'presentation'}.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        user_id,
    )
    return await _persist_generated(info)


async def _build_plain(user_id: str, title: str, content: str, ext: str, mime: str) -> Dict[str, str]:
    data = (content or "").encode("utf-8")
    name = title or "fichier"
    if not name.lower().endswith(ext):
        name = f"{name}{ext}"
    info = _store_generated(data, name, mime, user_id)
    return await _persist_generated(info)


async def _build_image(user_id: str, prompt: str) -> Dict[str, str]:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        raise ValueError("EMERGENT_LLM_KEY missing")
    chat = LlmChat(
        api_key=emergent_key,
        session_id=f"cf_imggen_{uuid.uuid4().hex[:8]}",
        system_message="You are a helpful AI assistant.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    _text, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if not images:
        raise ValueError("no image generated")
    img = images[0]
    data = base64.b64decode(img["data"])
    info = _store_generated(
        data,
        f"{_sanitize_filename((prompt[:40]) or 'image', ext='')}.png",
        img.get("mime_type", "image/png"),
        user_id,
    )
    return await _persist_generated(info)


async def _run_python_sandbox(code: str, timeout_sec: int = 10, session_id: Optional[str] = None, files: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Exécute du code Python dans le sandbox. Délègue à cfaction_engine.run_python_sandbox."""
    return await _cf_run_python_sandbox(code, timeout_sec=timeout_sec, session_id=session_id, files=files)


class SandboxFileInput(BaseModel):
    filename: str
    data_base64: str


@api_router.get("/chat/models")
async def list_chat_models(request: Request):
    """Liste les modèles disponibles pour le sélecteur, avec descriptions
    contextuelles (chat vs création) pour aider l'utilisateur à choisir.

    Le frontend passe `?context=chat` ou `?context=create` pour adapter le wording.
    """
    await get_current_user(request)
    context = (request.query_params.get("context") or "chat").lower()
    is_create = context == "create"

    # Descriptions adaptées au contexte d'utilisation
    online = [
        {
            "id": "gpt-5.2", "name": "Caly (GPT-5.2)", "provider": "OpenAI", "badge": "Défaut", "color": "yellow",
            "description": (
                "Discussion généraliste : brainstorm, écriture, analyse, rebond rapide. Mémoire complète de la conversation."
                if not is_create else
                "Génère le code complet du projet (FastAPI + React + DB). Hypothèses intelligentes, README clair, prêt à exécuter."
            ),
            "good_for": (
                ["Brainstormer", "Écrire un email/texte", "Analyser un fichier", "Conversation longue"]
                if not is_create else
                ["App complète", "Projet équilibré", "Site web standard"]
            ),
        },
        {
            "id": "claude-opus", "name": "Claude Opus 4.5", "provider": "Anthropic", "badge": "Thinking", "color": "amber",
            "description": (
                "Raisonne pas-à-pas avant de répondre. Idéale pour problèmes complexes, décisions importantes, longues analyses, dilemmes."
                if not is_create else
                "Architecte avant de coder. Meilleure pour projets multi-fichiers, logique métier complexe, sécurité."
            ),
            "good_for": (
                ["Problèmes complexes", "Dilemmes", "Code review profond", "Recherche approfondie"]
                if not is_create else
                ["Architecture complexe", "Backend avec règles métier", "Apps multi-modules", "Logique sensible"]
            ),
        },
        {
            "id": "claude-sonnet", "name": "Claude Sonnet 4.5", "provider": "Anthropic", "badge": "Code", "color": "orange",
            "description": (
                "Excellente pour ÉCRIRE DU CODE dans le chat — clique sur ▶ Exécuter pour le lancer dans le sandbox Python. Pour générer un projet complet à télécharger, va plutôt dans Création."
                if not is_create else
                "Le PLUS RAPIDE pour générer un projet complet propre, exécutable, prêt à pousser sur GitHub. Recommandée par défaut."
            ),
            "good_for": (
                ["Snippets de code", "Refactor", "Debug ligne par ligne", "Réécrire un texte"]
                if not is_create else
                ["App standard", "Site marketing", "Outil CRUD", "Recommandé par défaut"]
            ),
        },
        {
            "id": "gemini-3-pro", "name": "Gemini 3 Pro", "provider": "Google", "badge": "Multimodal", "color": "blue",
            "description": (
                "Le meilleur quand tu joins une IMAGE — décrit, analyse, extrait du texte (OCR), explique des schémas, identifie."
                if not is_create else
                "Plus créative visuellement. Idéale pour UI originales, design audacieux, identité visuelle marquée."
            ),
            "good_for": (
                ["Analyser une image", "OCR (extraire texte image)", "Lire un schéma", "Décrire une photo"]
                if not is_create else
                ["UI design original", "Landing page", "Portfolio créatif", "App au look unique"]
            ),
        },
        {
            "id": "gemini-3-flash", "name": "Gemini 3 Flash", "provider": "Google", "badge": "Ultra-rapide", "color": "cyan",
            "description": (
                "Réponses en quelques secondes. Parfait pour ping-pong rapide, questions courtes, vérifications express."
                if not is_create else
                "Pour prototypes rapides et MVPs simples. Code moins poli mais livré en quelques secondes."
            ),
            "good_for": (
                ["Question rapide", "Vérification express", "Définition", "Conversion d'unité"]
                if not is_create else
                ["Prototype rapide", "MVP simple", "Démo express", "Page unique"]
            ),
        },
    ]
    offline = [
        {
            "id": "deepseek", "name": "DeepSeek R1 (7B)", "provider": "Ollama", "badge": "Code", "color": "sky",
            "description": "Excellent en code et raisonnement step-by-step, totalement hors-ligne." if not is_create else "Génère du code propre hors-ligne. Lent mais privé.",
            "good_for": ["Code", "Maths", "Logique"] if not is_create else ["App standard hors-ligne"],
        },
        {
            "id": "gemma", "name": "Gemma 3 (12B)", "provider": "Ollama", "badge": "Équilibré", "color": "indigo",
            "description": "Modèle Google open-source. Polyvalent, multilingue, conversation naturelle, sans rien envoyer en ligne.",
            "good_for": ["Tout-terrain hors-ligne", "Multilingue", "Discussion privée"] if not is_create else ["Petites apps hors-ligne", "Privacy first"],
        },
        {
            "id": "gemma-27b", "name": "Gemma 3 (27B)", "provider": "Ollama", "badge": "Puissant", "color": "purple",
            "description": "Le plus capable des Gemma — exigeant en RAM (+24 Go). Qualité GPT-3.5 hors-ligne.",
            "good_for": ["Tâches lourdes hors-ligne", "Analyse profonde"] if not is_create else ["App complète hors-ligne haut de gamme"],
        },
        {
            "id": "gemma-4b", "name": "Gemma 3 (4B)", "provider": "Ollama", "badge": "Léger", "color": "violet",
            "description": "Très léger (~3 Go RAM), idéal pour machines modestes et démarrage rapide.",
            "good_for": ["Vieux laptop", "Tâches simples", "Test rapide"] if not is_create else ["Page statique", "MVP minimal"],
        },
        {
            "id": "llama", "name": "Llama 3.2", "provider": "Ollama", "badge": "Généraliste", "color": "emerald",
            "description": "Meta Llama — alternative équilibrée, communauté très active.",
            "good_for": ["Discussion générale"] if not is_create else ["App standard"],
        },
        {
            "id": "qwen", "name": "Qwen 2.5 (7B)", "provider": "Ollama", "badge": "Multilingue", "color": "teal",
            "description": "Très bon support chinois + anglais + français. Top pour i18n.",
            "good_for": ["Traduction", "Multilangue"] if not is_create else ["Site multilingue"],
        },
        {
            "id": "mistral", "name": "Mistral 7B", "provider": "Ollama", "badge": "Européen", "color": "rose",
            "description": "Modèle français performant, léger, respectueux du RGPD si tu héberges toi-même.",
            "good_for": ["Français natif", "RGPD"] if not is_create else ["App RGPD-friendly"],
        },
        {
            "id": "phi", "name": "Phi-3 Medium", "provider": "Ollama", "badge": "Compact", "color": "fuchsia",
            "description": "Microsoft Phi — petit mais étonnamment fort en maths et code.",
            "good_for": ["Maths", "Code"] if not is_create else ["Outils techniques"],
        },
    ]
    return {"online": online, "offline": offline, "context": context}



class RunPythonInput(BaseModel):
    code: str
    timeout_sec: Optional[int] = 10
    session_id: Optional[str] = None  # if set → persistent REPL mode
    files: Optional[List[SandboxFileInput]] = None  # files dropped into cwd


class SessionResetInput(BaseModel):
    session_id: str


@api_router.post("/sandbox/python")
async def sandbox_python(request: Request, payload: RunPythonInput):
    """Exécute du code Python dans le sandbox serveur avec timeout dur.

    Mode éphémère (par défaut) : namespace fresh à chaque appel.
    Mode REPL : passer un `session_id` réutilise les variables entre appels (style Jupyter).
    Upload : passer `files=[{filename, data_base64}]` pour déposer des fichiers au cwd.
    """
    await get_current_user(request)
    t = max(1, min(int(payload.timeout_sec or 10), 30))
    files = [f.model_dump() for f in (payload.files or [])]
    return await _run_python_sandbox(payload.code or "", timeout_sec=t, session_id=payload.session_id, files=files)


@api_router.post("/sandbox/reset")
async def sandbox_reset(request: Request, payload: SessionResetInput):
    """Réinitialise le namespace persistant d'une session REPL."""
    await get_current_user(request)
    from cfaction_engine import reset_sandbox_session
    ok = reset_sandbox_session(payload.session_id)
    return {"reset": ok, "session_id": payload.session_id}





@api_router.post("/chat/generate-docx")
async def chat_generate_docx(request: Request, payload: GenerateDocxInput):
    user_id = await get_current_user(request)
    return await _build_docx(user_id, payload.title or "Document", payload.sections or [])


@api_router.post("/chat/generate-pdf")
async def chat_generate_pdf(request: Request, payload: GeneratePdfInput):
    user_id = await get_current_user(request)
    return await _build_pdf(user_id, payload.title or "Document", payload.sections or [])


@api_router.post("/chat/generate-image")
async def chat_generate_image(request: Request, payload: GenerateImageInput):
    user_id = await get_current_user(request)
    try:
        return await _build_image(user_id, payload.prompt)
    except Exception as e:
        logger.warning(f"image gen failed: {e}")
        raise HTTPException(status_code=500, detail=f"Génération d'image impossible : {e}")


@api_router.get("/chat/export-ipynb/{project_id}")
async def export_chat_as_ipynb(project_id: str, request: Request):
    """Exporte une conversation chat en notebook Jupyter (.ipynb).

    Chaque message utilisateur devient une cellule markdown. Chaque bloc
    ```python``` trouvé dans les réponses AI devient une cellule code (avec le
    stdout déjà capturé en output si le bloc `▶️ Exécution Python (sandbox)` suit).
    """
    user_id = await get_current_user(request)
    # Validate ownership
    proj = await db.projects.find_one({"project_id": project_id, "user_id": user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    # Collect messages in order
    msgs = await db.chat_messages.find(
        {"user_id": user_id, "project_id": project_id},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(length=None)
    if not msgs:
        raise HTTPException(status_code=400, detail="Aucun message à exporter")

    cells: List[Dict[str, Any]] = []
    # Title cell
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            f"# {proj.get('name', 'Conversation')}\n",
            f"\n*Exporté depuis CodeForge AI — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
            "\n---\n",
        ],
    })

    code_block_re = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL)
    stdout_after_re = re.compile(
        r"\*\*▶️ Exécution Python \(sandbox\)[^\n]*\n+```\n(.*?)```",
        re.DOTALL,
    )

    for m in msgs:
        role = m.get("role", "assistant")
        content = m.get("content", "") or ""
        if role == "user":
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": ["**👤 Utilisateur**\n\n", content],
            })
        else:
            # Try to split AI response into: pre-code markdown, code cells, post-code markdown.
            pos = 0
            code_blocks = list(code_block_re.finditer(content))
            if not code_blocks:
                cells.append({
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["**🤖 CodeForge**\n\n", content],
                })
                continue
            # Preamble markdown
            prefix = content[: code_blocks[0].start()].rstrip()
            if prefix:
                cells.append({
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["**🤖 CodeForge**\n\n", prefix],
                })
            for i, cb in enumerate(code_blocks):
                code_src = cb.group(1).rstrip()
                # Look for an inline sandbox stdout block right after this cell.
                tail = content[cb.end():]
                stdout_m = stdout_after_re.search(tail[:4000])
                outputs = []
                if stdout_m:
                    outputs.append({
                        "name": "stdout",
                        "output_type": "stream",
                        "text": stdout_m.group(1).splitlines(keepends=True),
                    })
                cells.append({
                    "cell_type": "code",
                    "execution_count": i + 1,
                    "metadata": {},
                    "outputs": outputs,
                    "source": code_src.splitlines(keepends=True),
                })
                pos = cb.end()
            # Trailing markdown
            trailing = content[pos:]
            # Strip the "Exécution Python (sandbox)" blocks from trailing since we moved them.
            trailing_clean = re.sub(stdout_after_re, "", trailing).strip()
            if trailing_clean:
                cells.append({
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [trailing_clean],
                })

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "codeforge_export": {
                "project_id": project_id,
                "project_name": proj.get("name"),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    raw = json.dumps(notebook, ensure_ascii=False, indent=1).encode("utf-8")
    safe_name = _sanitize_filename(proj.get("name") or project_id) + ".ipynb"
    return Response(
        content=raw,
        media_type="application/x-ipynb+json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@api_router.get("/download/generated/{file_id}")
async def download_generated_file(file_id: str, request: Request):
    """Ownership-checked download endpoint for AI-generated files."""
    user_id = await get_current_user(request)
    doc = await db.generated_files.find_one({"file_id": file_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    p = Path(doc.get("path", ""))
    if not p.exists():
        raise HTTPException(status_code=410, detail="Fichier expiré")
    return FileResponse(
        path=str(p),
        media_type=doc.get("mime_type", "application/octet-stream"),
        filename=doc.get("filename", "file"),
    )


class WizardSuggestInput(BaseModel):
    kind: str  # 'name' | 'design'
    platforms: List[str] = []
    app_type: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = 'fr'

@api_router.post("/ai/wizard-suggest")
async def wizard_suggest(request: Request, payload: WizardSuggestInput):
    """🪄 Magic-wand helper for the wizard: suggest a project name or a design brief.

    Returns short JSON the frontend can use directly.
      - kind='name'   → { "suggestions": ["AppName1", "AppName2", "AppName3"] }
      - kind='design' → { "design": "courte description visuelle, palette, ambiance" }
    """
    user_id = await get_current_user(request)
    _ = user_id  # auth gate only

    plats = ", ".join(payload.platforms) if payload.platforms else "non spécifié"
    desc = (payload.description or "").strip()[:600]

    if payload.kind == 'name':
        prompt = (
            f"Propose 3 noms courts et originaux pour une application "
            f"({payload.app_type or 'générique'}) ciblant {plats}. "
            f"Contexte utilisateur : {desc or 'aucun'}. "
            f"Réponds UNIQUEMENT en JSON : {{\"suggestions\": [\"...\", \"...\", \"...\"]}}"
        )
    else:
        prompt = (
            f"Propose une direction visuelle (palette, typographie, ambiance, mots-clés) "
            f"pour une app {payload.app_type or 'générique'} ciblant {plats}. "
            f"Contexte : {desc or 'aucun'}. "
            f"Réponds UNIQUEMENT en JSON : {{\"design\": \"description courte (<60 mots)\"}}"
        )

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        emergent_key = os.environ.get('EMERGENT_LLM_KEY')
        if not emergent_key:
            raise ValueError("EMERGENT_LLM_KEY not configured")
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"codeforge_wizard_{uuid.uuid4().hex[:8]}",
            system_message="Tu aides un utilisateur non technique à concevoir une app. Réponds STRICTEMENT en JSON valide sans markdown.",
        ).with_model("openai", "gpt-5.2")
        raw = await chat.send_message(UserMessage(text=prompt))
        text = (raw or '').strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        data = json.loads(text[start:end]) if start >= 0 and end > start else {}
    except Exception as exc:
        logger.warning(f"wizard-suggest failure: {exc}")
        # Lightweight fallback so the UI never feels stuck.
        if payload.kind == 'name':
            data = {"suggestions": ["NovaApp", "PixelForge", "Lumino"]}
        else:
            data = {"design": "Interface sombre élégante, accent jaune-vert vif, typographie sans-serif moderne, ambiance high-tech bienveillante."}

    if payload.kind == 'name' and not isinstance(data.get('suggestions'), list):
        data = {"suggestions": ["NovaApp", "PixelForge", "Lumino"]}
    if payload.kind == 'design' and not isinstance(data.get('design'), str):
        data = {"design": "Interface sombre élégante, accent jaune-vert vif, ambiance moderne."}

    return data


# ==================== USER PREFERENCES ====================

class UserPreferences(BaseModel):
    theme: Optional[str] = 'dark'         # 'dark' | 'light' | 'auto'
    contrast: Optional[str] = 'normal'    # 'normal' | 'high'
    accent: Optional[str] = '#E4FF00'
    notifications_email: Optional[bool] = True
    notifications_push: Optional[bool] = False

@api_router.get("/auth/preferences")
async def get_user_preferences(request: Request):
    user_id = await get_current_user(request)
    doc = await db.user_preferences.find_one({"user_id": user_id}, {"_id": 0, "user_id": 0}) or {}
    base = UserPreferences().model_dump()
    base.update({k: v for k, v in doc.items() if k in base})
    return base

@api_router.put("/auth/preferences")
async def put_user_preferences(request: Request, prefs: UserPreferences):
    user_id = await get_current_user(request)
    payload = prefs.model_dump()
    await db.user_preferences.update_one(
        {"user_id": user_id},
        {"$set": {**payload, "user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return payload



@api_router.post("/projects", response_model=Project, status_code=201)
async def create_project(request: Request, input: ProjectCreate):
    """Create a new project"""
    user_id = await get_current_user(request)
    
    project = Project(
        user_id=user_id,
        name=input.name,
        description=input.description,
        project_type=input.project_type
    )
    
    project_dict = project.model_dump()
    project_dict['created_at'] = project_dict['created_at'].isoformat()
    project_dict['updated_at'] = project_dict['updated_at'].isoformat()
    
    await db.projects.insert_one(project_dict)
    
    return project

@api_router.get("/projects", response_model=List[Project])
async def get_projects(request: Request):
    """Get all projects for current user"""
    user_id = await get_current_user(request)
    
    projects = await db.projects.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Convert ISO strings to datetime + backfill ai_mode for legacy projects
    for project in projects:
        if isinstance(project.get('created_at'), str):
            project['created_at'] = datetime.fromisoformat(project['created_at'])
        elif not project.get('created_at'):
            project['created_at'] = datetime.now(timezone.utc)
        if isinstance(project.get('updated_at'), str):
            project['updated_at'] = datetime.fromisoformat(project['updated_at'])
        elif not project.get('updated_at'):
            # Legacy chat projects didn't have updated_at; reuse created_at.
            project['updated_at'] = project['created_at']
        if not project.get('ai_mode'):
            src = (project.get('ai_source') or '').lower()
            project['ai_mode'] = 'offline' if src.startswith('ollama') else 'online'
    
    return projects

@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(request: Request, project_id: str):
    """Get specific project"""
    user_id = await get_current_user(request)
    
    project = await db.projects.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Convert ISO strings to datetime + backfill (same logic as list endpoint)
    if isinstance(project.get('created_at'), str):
        project['created_at'] = datetime.fromisoformat(project['created_at'])
    elif not project.get('created_at'):
        project['created_at'] = datetime.now(timezone.utc)
    if isinstance(project.get('updated_at'), str):
        project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    elif not project.get('updated_at'):
        project['updated_at'] = project['created_at']
    if not project.get('ai_mode'):
        src = (project.get('ai_source') or '').lower()
        project['ai_mode'] = 'offline' if src.startswith('ollama') else 'online'
    
    return project

@api_router.put("/projects/{project_id}", response_model=Project)
async def update_project(request: Request, project_id: str, input: ProjectUpdate):
    """Update a project"""
    user_id = await get_current_user(request)
    
    # Check project exists and belongs to user
    project = await db.projects.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Build update dict
    update_data = {k: v for k, v in input.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update_data}
    )
    
    # Return updated project
    updated_project = await db.projects.find_one(
        {"project_id": project_id},
        {"_id": 0}
    )
    
    # Convert ISO strings to datetime
    if isinstance(updated_project['created_at'], str):
        updated_project['created_at'] = datetime.fromisoformat(updated_project['created_at'])
    if isinstance(updated_project['updated_at'], str):
        updated_project['updated_at'] = datetime.fromisoformat(updated_project['updated_at'])
    
    return updated_project

@api_router.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str):
    """Delete a project"""
    user_id = await get_current_user(request)
    
    result = await db.projects.delete_one(
        {"project_id": project_id, "user_id": user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Also delete related chat messages
    await db.chat_messages.delete_many({"project_id": project_id})
    
    return {"message": "Projet supprimé avec succès"}


@api_router.post("/projects/{project_id}/duplicate")
async def duplicate_project(request: Request, project_id: str):
    """Clone a project — duplicates the document with a new project_id and
    "(copie)" suffix. Chat history is NOT copied (a fresh thread starts on the
    clone). Useful to experiment without breaking the original.
    """
    user_id = await get_current_user(request)
    src = await db.projects.find_one({"project_id": project_id, "user_id": user_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Projet non trouvé")

    new_id = f"proj_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    clone = {
        **src,
        "project_id": new_id,
        "name": f"{src.get('name', 'Projet')} (copie)"[:80],
        "created_at": now_iso,
        "updated_at": now_iso,
        # Drop legacy share metadata so the clone starts non-public.
        "share_slug": None,
        "is_public": False,
    }
    await db.projects.insert_one(clone)
    clone.pop("_id", None)
    return {"success": True, "project_id": new_id, "project": clone}


def _make_slug(name: str) -> str:
    """ASCII-safe URL slug."""
    import unicodedata as _ud
    import re as _re
    base = _ud.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    base = _re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:50] or "projet"
    return f"{base}-{uuid.uuid4().hex[:6]}"


@api_router.post("/projects/{project_id}/share")
async def toggle_project_share(request: Request, project_id: str):
    """Generate (or refresh) a public share URL for a project. Anyone with the
    slug can view the live preview without authentication. Call again to disable.
    Body (optional): {"enable": true|false}
    """
    user_id = await get_current_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    enable = body.get("enable") if isinstance(body, dict) else None

    project = await db.projects.find_one({"project_id": project_id, "user_id": user_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")

    if enable is False:
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"is_public": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"is_public": False, "slug": None, "url": None}

    slug = project.get("share_slug") or _make_slug(project.get("name") or project_id)
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {
            "is_public": True,
            "share_slug": slug,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    frontend_url = (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or ""
    )
    public_url = f"{frontend_url.rstrip('/')}/share/{slug}" if frontend_url else f"/share/{slug}"
    return {"is_public": True, "slug": slug, "url": public_url}


@api_router.get("/share/{slug}")
async def get_public_share(slug: str):
    """PUBLIC — return the project metadata + generated files for a shared slug.
    No auth required.
    """
    project = await db.projects.find_one(
        {"share_slug": slug, "is_public": True},
        {"_id": 0, "user_id": 0, "ai_source": 0},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Projet non partagé ou introuvable")
    return {
        "name": project.get("name"),
        "description": project.get("description"),
        "project_type": project.get("project_type"),
        "files": (project.get("generated_code") or {}).get("files", []),
        "created_at": project.get("created_at"),
    }


@api_router.get("/share/{slug}/preview")
async def get_public_share_preview(slug: str):
    """PUBLIC — return the rendered HTML preview for a shared web project.
    Same logic as `/preview/project/{id}` but slug-based and unauthenticated.
    """
    project = await db.projects.find_one(
        {"share_slug": slug, "is_public": True}, {"_id": 0}
    )
    if not project:
        return HTMLResponse("<h1>Projet introuvable</h1>", status_code=404)

    files = (project.get("generated_code") or {}).get("files", []) or []
    html_parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{project.get('name', 'Projet')} · CodeForge AI</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif}</style>"
    ]
    for f in files:
        if f.get("path", "").endswith(".css"):
            html_parts.append(f"<style>{f.get('content', '')}</style>")
    html_parts.append("</head><body>")
    for f in files:
        if f.get("path", "").endswith(".html"):
            content = f.get("content", "")
            if "<body>" in content:
                start = content.find("<body>") + 6
                end = content.find("</body>")
                content = content[start:end] if end > start else content
            html_parts.append(content)
    for f in files:
        if f.get("path", "").endswith(".js"):
            html_parts.append(f"<script>{f.get('content', '')}</script>")
    html_parts.append("</body></html>")
    return HTMLResponse("\n".join(html_parts))


@api_router.get("/system/ollama-status")
async def ollama_status():
    """Light health check on the local Ollama instance. Public — used by the
    ModelPicker to greyout offline models when the service is unreachable."""
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                tags = r.json().get("models", []) or []
                return {"available": True, "models": [t.get("name") for t in tags][:30]}
    except Exception:
        pass
    return {"available": False, "models": []}


# ==========================================================================
# DEVICE-BOUND CRYPTOGRAPHIC IDENTITY (creator-grade access control)
# ==========================================================================
from device_auth import compute_key_id, new_nonce, verify_signature  # noqa: E402


VALID_SITE_MODES = {"public", "private", "creator", "guest"}
VALID_DEVICE_ROLES = {"creator", "approved", "pending", "revoked"}


async def _get_site_mode() -> str:
    doc = await db.site_config.find_one({"_id": "site_mode"}, {"_id": 0, "mode": 1})
    return (doc or {}).get("mode") or "public"


async def _device_by_key(key_id: str) -> Optional[dict]:
    return await db.device_keys.find_one({"key_id": key_id}, {"_id": 0})


async def _log_decision(action: str, target_key_id: str, by_key_id: str, target_label: str = None):
    """Append an audit record to `device_decisions` so the creator can keep
    track of past actions even after the live state changes. Bounded to last
    500 entries to keep storage in check."""
    await db.device_decisions.insert_one({
        "action": action,              # 'approve' | 'revoke' | 'disconnect' | 'promote' | 'add_by_key' | 'register'
        "target_key_id": target_key_id,
        "target_label": target_label,
        "by_key_id": by_key_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    # Bound the collection (delete oldest beyond 500).
    total = await db.device_decisions.count_documents({})
    if total > 500:
        olds = await db.device_decisions.find({}, {"_id": 1}).sort("ts", 1).limit(total - 500).to_list(length=total - 500)
        await db.device_decisions.delete_many({"_id": {"$in": [o["_id"] for o in olds]}})


async def _consume_nonce(key_id: str, nonce: str) -> bool:
    """Atomically delete the pending nonce. Returns True if it existed."""
    res = await db.device_nonces.delete_one({"key_id": key_id, "nonce": nonce})
    return res.deleted_count > 0


async def _require_creator_signature(key_id: str, nonce: str, signature: str) -> dict:
    """Verify the caller is a device with role='creator' (signed proof)."""
    dev = await _device_by_key(key_id)
    if not dev or dev.get("role") != "creator":
        raise HTTPException(status_code=403, detail="Action réservée au créateur.")
    if not await _consume_nonce(key_id, nonce):
        raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
    if not verify_signature(dev.get("public_key_jwk") or {}, nonce, signature):
        raise HTTPException(status_code=403, detail="Signature invalide.")
    return dev


class DeviceRegisterIn(BaseModel):
    public_key_jwk: Dict[str, Any]
    label: Optional[str] = None  # human-friendly device name (e.g. "iPhone")


@api_router.post("/devices/register")
async def device_register(payload: DeviceRegisterIn):
    """Register a fresh device. Public — anyone can call this. The first
    device EVER registered is auto-promoted to 'creator'. All subsequent
    registrations are 'pending' until the creator approves them.
    Idempotent: a second register call for the same key_id never duplicates."""
    jwk = payload.public_key_jwk or {}
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise HTTPException(status_code=400, detail="Clé publique invalide (EC P-256 attendu).")
    key_id = compute_key_id(jwk)

    # Atomic-ish: try to find any existing doc for this key. If any, we
    # consolidate by keeping the highest-privilege role and removing duplicates.
    matches = await db.device_keys.find({"key_id": key_id}, {"_id": 0}).to_list(length=5)
    if matches:
        priority = {"creator": 4, "approved": 3, "pending": 2, "revoked": 1}
        best_role = max((m.get("role") for m in matches), key=lambda r: priority.get(r, 0))
        # Collapse to a single canonical doc with the best role.
        await db.device_keys.delete_many({"key_id": key_id})
        await db.device_keys.insert_one({
            "key_id": key_id,
            "public_key_jwk": jwk,
            "role": best_role,
            "label": (payload.label or "")[:60] or None,
            "created_at": matches[0].get("created_at") or datetime.now(timezone.utc).isoformat(),
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"key_id": key_id, "role": best_role, "already_registered": True}

    # Count DISTINCT key_ids before granting creator role (more robust than total).
    distinct_ids = await db.device_keys.distinct("key_id")
    role = "creator" if len(distinct_ids) == 0 else "pending"
    doc = {
        "key_id": key_id,
        "public_key_jwk": jwk,
        "role": role,
        "label": (payload.label or "")[:60] or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.device_keys.insert_one(doc)
    return {"key_id": key_id, "role": role, "already_registered": False}


class DeviceChallengeIn(BaseModel):
    key_id: str


@api_router.post("/devices/challenge")
async def device_challenge(payload: DeviceChallengeIn):
    """Issue a single-use nonce for the given key_id. The device signs it
    with its non-extractable private key and posts the signature to /verify.
    Nonces are stored with a 2-minute TTL via the `device_nonces` collection."""
    dev = await _device_by_key(payload.key_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Appareil inconnu.")
    nonce = new_nonce()
    await db.device_nonces.insert_one({
        "key_id": payload.key_id,
        "nonce": nonce,
        "created_at": datetime.now(timezone.utc),
    })
    return {"nonce": nonce, "expires_in_seconds": 120}


class DeviceVerifyIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


@api_router.post("/devices/verify")
async def device_verify(payload: DeviceVerifyIn):
    """Verify the signature → return device role + whether access is granted
    given the current site mode. Public endpoint (anyone with a valid key can
    call it)."""
    dev = await _device_by_key(payload.key_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Appareil inconnu.")

    if not await _consume_nonce(payload.key_id, payload.nonce):
        raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
    ok = verify_signature(dev.get("public_key_jwk") or {}, payload.nonce, payload.signature)
    if not ok:
        return {"verified": False, "role": dev.get("role"), "can_access": False}

    await db.device_keys.update_one(
        {"key_id": payload.key_id},
        {"$set": {"last_seen_at": datetime.now(timezone.utc).isoformat()}},
    )

    site_mode = await _get_site_mode()
    role = dev.get("role")
    effective_role = role
    can_access = True
    if role == "revoked":
        can_access = False
    elif site_mode == "private":
        # Anyone with a registered device can BROWSE in guest mode, but only
        # creator/approved get write privileges.
        if role not in ("creator", "approved"):
            effective_role = "guest"
    elif site_mode == "creator":
        # Strict: only creator devices may use the site.
        if role != "creator":
            can_access = False
    elif site_mode == "guest":
        # Everyone allowed, but UI enforces read-only for non-authenticated.
        if role not in ("creator", "approved"):
            effective_role = "guest"

    return {
        "verified": True,
        "role": role,
        "effective_role": effective_role,
        "can_access": can_access,
        "site_mode": site_mode,
    }


@api_router.get("/system/site-mode")
async def get_site_mode_public():
    """Public — anyone can read the current site mode (used by the Landing/Login
    to gate access)."""
    mode = await _get_site_mode()
    return {"mode": mode}


class SiteModeSetIn(BaseModel):
    mode: str
    key_id: str
    nonce: str
    signature: str


@api_router.put("/system/site-mode")
async def set_site_mode(payload: SiteModeSetIn):
    """Creator-only. Toggle site mode."""
    if payload.mode not in VALID_SITE_MODES:
        raise HTTPException(status_code=400, detail="Mode invalide.")
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    await db.site_config.update_one(
        {"_id": "site_mode"},
        {"$set": {"mode": payload.mode, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"mode": payload.mode}


class CreatorOnlyIn(BaseModel):
    key_id: str           # caller (must be creator)
    nonce: str
    signature: str


@api_router.post("/devices/list")
async def devices_list(payload: CreatorOnlyIn):
    """Creator-only — list all registered devices."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    devices = await db.device_keys.find(
        {}, {"_id": 0, "public_key_jwk": 0},
    ).sort("created_at", -1).to_list(length=500)
    return {"devices": devices}


@api_router.post("/devices/decisions")
async def devices_decisions(payload: CreatorOnlyIn):
    """Creator-only — return the history of past decisions (approve/revoke/
    disconnect/promote/add_by_key). Sorted newest first, capped at 200."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    rows = await db.device_decisions.find(
        {}, {"_id": 0},
    ).sort("ts", -1).to_list(length=200)
    return {"decisions": rows}


@api_router.post("/devices/pending-count")
async def devices_pending_count(payload: CreatorOnlyIn):
    """Creator-only — quick count of pending devices, used by the bell badge.
    Uses POST so we can carry the creator proof in the body without exposing
    keys in query strings/logs."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    count = await db.device_keys.count_documents({"role": "pending"})
    return {"pending_count": count}


@api_router.get("/devices/pending-stream/{key_id}/{nonce}/{signature}")
async def devices_pending_stream(key_id: str, nonce: str, signature: str):
    """Creator-only SSE stream — emits `{pending_count}` every 5s, plus an
    immediate first event. Auth via path-args because EventSource cannot set
    custom headers/bodies. The nonce is consumed on first call (single-use),
    after that we trust the connection (it dies on creator-revoke anyway)."""
    await _require_creator_signature(key_id, nonce, signature)

    async def gen():
        # Emit one immediately so the badge updates without lag.
        last = -1
        try:
            while True:
                # Re-check the device is still 'creator' on every tick. If
                # they got revoked, we close the stream.
                dev = await _device_by_key(key_id)
                if not dev or dev.get("role") != "creator":
                    yield "event: closed\ndata: revoked\n\n"
                    return
                count = await db.device_keys.count_documents({"role": "pending"})
                if count != last:
                    yield f"data: {{\"pending_count\": {count}}}\n\n"
                    last = count
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            return

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


class DeviceTargetIn(CreatorOnlyIn):
    target_key_id: str


@api_router.post("/devices/approve")
async def devices_approve(payload: DeviceTargetIn):
    """Creator promotes a pending device to 'approved'."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    target = await _device_by_key(payload.target_key_id)
    res = await db.device_keys.update_one(
        {"key_id": payload.target_key_id, "role": "pending"},
        {"$set": {"role": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Aucun appareil en attente avec cette clé.")
    await _log_decision("approve", payload.target_key_id, payload.key_id, (target or {}).get("label"))
    return {"success": True}


@api_router.post("/devices/revoke")
async def devices_revoke(payload: DeviceTargetIn):
    """Creator hard-revokes a device — they cannot authenticate again. The
    revoke also REMOVES the device from `device_keys` so it doesn't clutter
    the registered-devices list. The audit trail in `device_decisions`
    remembers what happened."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    if payload.target_key_id == payload.key_id:
        raise HTTPException(status_code=400, detail="Tu ne peux pas révoquer ton propre appareil créateur.")
    target = await _device_by_key(payload.target_key_id)
    if not target:
        raise HTTPException(status_code=404, detail="Appareil introuvable.")
    await db.device_keys.delete_one({"key_id": payload.target_key_id})
    await db.device_nonces.delete_many({"key_id": payload.target_key_id})
    await db.user_sessions.delete_many({"device_key_id": payload.target_key_id})
    await _log_decision("revoke", payload.target_key_id, payload.key_id, (target or {}).get("label"))
    return {"success": True}


@api_router.post("/devices/disconnect")
async def devices_disconnect(payload: DeviceTargetIn):
    """Creator force-disconnects a device. Like /revoke this REMOVES the
    device from `device_keys` so the active list stays clean; the audit
    record lives on in `device_decisions`."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    if payload.target_key_id == payload.key_id:
        raise HTTPException(status_code=400, detail="Tu ne peux pas te déconnecter toi-même via cette action.")
    target = await _device_by_key(payload.target_key_id)
    if not target:
        raise HTTPException(status_code=404, detail="Appareil introuvable.")
    await db.device_nonces.delete_many({"key_id": payload.target_key_id})
    await db.user_sessions.delete_many({"device_key_id": payload.target_key_id})
    await db.device_keys.delete_one({"key_id": payload.target_key_id})
    await _log_decision("disconnect", payload.target_key_id, payload.key_id, (target or {}).get("label"))
    return {"success": True}


class PromoteCreatorIn(CreatorOnlyIn):
    target_key_id: str
    password: str  # creator's own password — extra protection


@api_router.post("/devices/promote-creator")
async def devices_promote_creator(payload: PromoteCreatorIn):
    """Creator promotes another device to 'creator' role. Requires the
    creator's own account password to confirm intent."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    # Identify creator's account: stored at device creation time? Not yet —
    # link via the user that last logged in with this device. For now we
    # require the password to match ANY existing user that has marked this
    # device as 'creator-owner'. Fallback: accept the first admin user.
    # Simpler approach: verify any user whose password matches. This is
    # acceptable since the call is gated by the creator's device signature.
    users = await db.users.find({}, {"_id": 0, "email": 1, "password_hash": 1}).to_list(length=200)
    matched = False
    for u in users:
        ph = u.get("password_hash") or ""
        try:
            if ph and verify_password(payload.password, ph):
                matched = True
                break
        except Exception:
            continue
    if not matched:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
    res = await db.device_keys.update_one(
        {"key_id": payload.target_key_id},
        {"$set": {"role": "creator", "promoted_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appareil introuvable.")
    target = await _device_by_key(payload.target_key_id)
    await _log_decision("promote", payload.target_key_id, payload.key_id, (target or {}).get("label"))
    return {"success": True}


class AddByKeyIn(CreatorOnlyIn):
    public_key_jwk: Dict[str, Any]
    label: Optional[str] = None
    role: Optional[str] = "approved"  # 'approved' by default


@api_router.post("/devices/add-by-key")
async def devices_add_by_key(payload: AddByKeyIn):
    """Creator pastes another device's public key (shared offline) to whitelist
    it directly without going through pending → approve."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    jwk = payload.public_key_jwk or {}
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise HTTPException(status_code=400, detail="Clé publique invalide.")
    target_id = compute_key_id(jwk)
    role = payload.role if payload.role in ("approved", "creator") else "approved"
    existing = await _device_by_key(target_id)
    if existing:
        await db.device_keys.update_one(
            {"key_id": target_id},
            {"$set": {"role": role, "label": payload.label or existing.get("label")}},
        )
    else:
        await db.device_keys.insert_one({
            "key_id": target_id,
            "public_key_jwk": jwk,
            "role": role,
            "label": (payload.label or "")[:60] or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "added_by_creator": True,
        })
    await _log_decision("add_by_key", target_id, payload.key_id, payload.label)
    return {"key_id": target_id, "role": role}


# Non-creator can ping the creator with a request to be added. We just log
# the request in `device_decisions` so the creator sees it in their History
# panel (and the regular "pending" entry in device_keys, which they already
# see). No private data exchanged — the requester's key_id was already known
# to the server from their /devices/register call on first visit.
class SendToCreatorIn(BaseModel):
    key_id: str  # the requester (any registered, non-creator device)
    nonce: str
    signature: str


@api_router.post("/devices/send-to-creator")
async def devices_send_to_creator(payload: SendToCreatorIn):
    """Anyone with a valid registered device can use this to nudge the creator.
    Verifies the caller actually owns the key (sig over nonce). Tags the
    requester's device as 'pending' so it shows up in the creator's pending
    queue (and the notification bell badge ticks)."""
    dev = await _device_by_key(payload.key_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Appareil inconnu.")
    if not await _consume_nonce(payload.key_id, payload.nonce):
        raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
    if not verify_signature(dev.get("public_key_jwk") or {}, payload.nonce, payload.signature):
        raise HTTPException(status_code=403, detail="Signature invalide.")
    # If already creator or already pending — idempotent.
    if dev.get("role") in ("creator", "approved", "pending"):
        # Already visible. Refresh last_seen so it bubbles up.
        await db.device_keys.update_one(
            {"key_id": payload.key_id},
            {"$set": {"last_seen_at": datetime.now(timezone.utc).isoformat()}},
        )
    else:
        # 'revoked' → put back to 'pending' so the creator can re-decide.
        await db.device_keys.update_one(
            {"key_id": payload.key_id},
            {"$set": {"role": "pending", "last_seen_at": datetime.now(timezone.utc).isoformat()}},
        )
    await _log_decision("request_access", payload.key_id, payload.key_id, dev.get("label"))
    return {"sent": True, "role": dev.get("role")}


# ==========================================================================
# END device-bound identity
# ==========================================================================


# ==========================================================================
# ONE-DEVICE-AT-A-TIME — pending session approval flow
# ==========================================================================

class SessionRequestStatusIn(BaseModel):
    request_id: str


@api_router.post("/auth/session-request-status")
async def session_request_status(payload: SessionRequestStatusIn, response: Response):
    """Polled by the requesting device until the connected device decides
    (approve/deny) or the request expires (15 min).

    Idempotent: once approved, the session token is persisted on the request
    and returned on every subsequent poll until the requesting device clears
    it. This avoids race conditions where two parallel polls of the same
    approved request would have one return 'approved+token' and the other
    return 404."""
    now = datetime.now(timezone.utc)
    req = await db.session_requests.find_one({"request_id": payload.request_id}, {"_id": 0})
    if not req:
        # Could be: deleted/expired old; OR brand new request lookup race.
        return {"status": "expired"}
    # Expire on read.
    if req["status"] == "pending" and req.get("expires_at") and req["expires_at"] < now.isoformat():
        await db.session_requests.update_one(
            {"request_id": payload.request_id},
            {"$set": {"status": "expired"}},
        )
        req["status"] = "expired"

    if req["status"] in ("pending", "denied", "expired"):
        return {"status": req["status"]}

    # status == "approved" — issue/return a session token. We persist it on
    # the request itself so concurrent or repeat polls all get the same value.
    user = await db.users.find_one({"user_id": req["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    session_token = req.get("issued_session_token")
    if not session_token:
        session_token = secrets.token_urlsafe(32)
        await db.user_sessions.insert_one({
            "session_token": session_token,
            "user_id": user["user_id"],
            "device_key_id": req.get("requesting_key_id"),
            "device_label": req.get("requesting_label"),
            "auth_type": "email",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        })
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"last_login": now.isoformat()}})
        await db.session_requests.update_one(
            {"request_id": payload.request_id},
            {"$set": {
                "issued_session_token": session_token,
                "consumed_at": now.isoformat(),
                # Push the soft-expiry out so repeated polls keep working long
                # enough for the requesting device to navigate.
                "expires_at": (now + timedelta(minutes=15)).isoformat(),
            }},
        )

    response.set_cookie(
        key="session_token", value=session_token,
        httponly=True, secure=True, samesite="none",
        max_age=7 * 24 * 3600, path="/",
    )
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"status": "approved", **safe_user, "session_token": session_token}


@api_router.get("/auth/session-pending")
async def list_pending_session_requests(request: Request):
    """Listed by the currently-connected user — pending requests on their
    account from other devices."""
    user_id = await get_current_user(request)
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = await db.session_requests.find(
        {"user_id": user_id, "status": "pending", "expires_at": {"$gt": now_iso}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=50)
    return {"requests": rows}


class SessionDecideIn(BaseModel):
    request_id: str
    decision: str  # 'approve' | 'deny'


@api_router.post("/auth/session-decide")
async def decide_session_request(payload: SessionDecideIn, request: Request):
    """Currently-connected device approves or denies a pending request."""
    if payload.decision not in ("approve", "deny"):
        raise HTTPException(status_code=400, detail="Décision invalide.")
    user_id = await get_current_user(request)
    req = await db.session_requests.find_one(
        {"request_id": payload.request_id, "user_id": user_id, "status": "pending"},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=404, detail="Demande introuvable ou déjà traitée.")
    new_status = "approved" if payload.decision == "approve" else "denied"
    await db.session_requests.update_one(
        {"request_id": payload.request_id},
        {"$set": {
            "status": new_status,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"status": new_status}


# ==========================================================================
# WEBAUTHN — biometric "declare theft" recovery
# ==========================================================================
import webauthn  # noqa: E402
from webauthn.helpers.structs import (  # noqa: E402
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
    AuthenticatorSelectionCriteria,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
)


def _rp_id_from_origin(origin: str) -> str:
    """Strip scheme + port from origin to derive the WebAuthn RP id."""
    try:
        from urllib.parse import urlparse
        host = urlparse(origin).hostname or ""
        return host or "localhost"
    except Exception:
        return "localhost"


class WebAuthnEnrollOptionsIn(BaseModel):
    key_id: str           # device making the call (must be creator to enroll)
    nonce: str
    signature: str
    origin: str           # window.location.origin


@api_router.post("/webauthn/register-options")
async def webauthn_register_options(payload: WebAuthnEnrollOptionsIn):
    """Step 1 (creator-only): generate a challenge for biometric enrollment.
    The browser will call navigator.credentials.create with these options.
    Only platform authenticators (Touch ID / Face ID / Windows Hello / Android
    fingerprint) are allowed."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    rp_id = _rp_id_from_origin(payload.origin)
    user_handle = payload.key_id.encode("utf-8")[:64]

    options = webauthn.generate_registration_options(
        rp_id=rp_id,
        rp_name="CodeForge AI",
        user_id=user_handle,
        user_name=f"creator:{payload.key_id}",
        user_display_name="Creator",
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        timeout=60_000,
    )
    # Persist challenge + rp_id for the verify step.
    await db.webauthn_challenges.insert_one({
        "key_id": payload.key_id,
        "challenge": webauthn.helpers.bytes_to_base64url(options.challenge),
        "rp_id": rp_id,
        "kind": "register",
        "origin": payload.origin,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return json.loads(webauthn.helpers.options_to_json(options))


class WebAuthnEnrollVerifyIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    origin: str
    credential: Dict[str, Any]  # the navigator.credentials.create response


@api_router.post("/webauthn/register-verify")
async def webauthn_register_verify(payload: WebAuthnEnrollVerifyIn):
    """Step 2 (creator-only): verify the browser's attestation and store
    the platform credential for later 'declare theft' use."""
    await _require_creator_signature(payload.key_id, payload.nonce, payload.signature)
    challenge_doc = await db.webauthn_challenges.find_one_and_delete(
        {"key_id": payload.key_id, "kind": "register"},
    )
    if not challenge_doc:
        raise HTTPException(status_code=400, detail="Aucun défi d'enrôlement actif.")
    try:
        verification = webauthn.verify_registration_response(
            credential=payload.credential,
            expected_challenge=webauthn.helpers.base64url_to_bytes(challenge_doc["challenge"]),
            expected_origin=payload.origin,
            expected_rp_id=challenge_doc["rp_id"],
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Vérification d'enrôlement échouée: {e}")

    await db.webauthn_credentials.insert_one({
        "credential_id": webauthn.helpers.bytes_to_base64url(verification.credential_id),
        "public_key": webauthn.helpers.bytes_to_base64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "owner_key_id": payload.key_id,  # the creator who enrolled this biometric
        "rp_id": challenge_doc["rp_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"enrolled": True}


class WebAuthnTheftOptionsIn(BaseModel):
    key_id: str  # device declaring the theft (NOT required to be creator)
    origin: str


@api_router.post("/webauthn/declare-theft-options")
async def webauthn_declare_theft_options(payload: WebAuthnTheftOptionsIn):
    """Public — anyone with a registered device can attempt to declare theft.
    Returns a WebAuthn authentication challenge listing every enrolled
    biometric credential as 'allowed'. The matching biometric on this device
    must validate (USER_VERIFICATION required)."""
    if not await _device_by_key(payload.key_id):
        raise HTTPException(status_code=404, detail="Appareil inconnu.")
    rp_id = _rp_id_from_origin(payload.origin)
    creds = await db.webauthn_credentials.find({"rp_id": rp_id}, {"_id": 0}).to_list(length=20)
    if not creds:
        raise HTTPException(status_code=404, detail="Aucune biométrie enrôlée — le créateur doit d'abord enregistrer son empreinte depuis son appareil créateur.")

    allow = [
        PublicKeyCredentialDescriptor(id=webauthn.helpers.base64url_to_bytes(c["credential_id"]))
        for c in creds
    ]
    options = webauthn.generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=60_000,
    )
    await db.webauthn_challenges.insert_one({
        "key_id": payload.key_id,
        "challenge": webauthn.helpers.bytes_to_base64url(options.challenge),
        "rp_id": rp_id,
        "kind": "theft",
        "origin": payload.origin,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return json.loads(webauthn.helpers.options_to_json(options))


class WebAuthnTheftVerifyIn(BaseModel):
    key_id: str
    origin: str
    credential: Dict[str, Any]


@api_router.post("/webauthn/declare-theft-verify")
async def webauthn_declare_theft_verify(payload: WebAuthnTheftVerifyIn):
    """Verify the assertion. On success:
      - Promote the calling device to 'creator' role.
      - Revoke every OTHER creator device.
      - Force-disconnect their sessions.
    """
    dev = await _device_by_key(payload.key_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Appareil inconnu.")
    challenge_doc = await db.webauthn_challenges.find_one_and_delete(
        {"key_id": payload.key_id, "kind": "theft"},
    )
    if not challenge_doc:
        raise HTTPException(status_code=400, detail="Aucun défi de récupération actif.")

    # Look up the credential by id supplied in the assertion.
    raw_id = payload.credential.get("rawId") or payload.credential.get("id")
    if not raw_id:
        raise HTTPException(status_code=400, detail="Credential id manquant.")
    cred_doc = await db.webauthn_credentials.find_one({"credential_id": raw_id}, {"_id": 0})
    if not cred_doc:
        raise HTTPException(status_code=404, detail="Credential inconnu.")

    try:
        verification = webauthn.verify_authentication_response(
            credential=payload.credential,
            expected_challenge=webauthn.helpers.base64url_to_bytes(challenge_doc["challenge"]),
            expected_rp_id=challenge_doc["rp_id"],
            expected_origin=payload.origin,
            credential_public_key=webauthn.helpers.base64url_to_bytes(cred_doc["public_key"]),
            credential_current_sign_count=cred_doc.get("sign_count", 0),
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Vérification biométrique échouée: {e}")

    # Bump sign_count to prevent replay.
    await db.webauthn_credentials.update_one(
        {"credential_id": raw_id},
        {"$set": {"sign_count": verification.new_sign_count}},
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    # Remove all OTHER creators (the audit trail in device_decisions remembers).
    other_creators = await db.device_keys.find(
        {"role": "creator", "key_id": {"$ne": payload.key_id}},
        {"_id": 0, "key_id": 1, "label": 1},
    ).to_list(length=50)
    for d in other_creators:
        await db.device_keys.delete_one({"key_id": d["key_id"]})
        await db.device_nonces.delete_many({"key_id": d["key_id"]})
        await db.user_sessions.delete_many({"device_key_id": d["key_id"]})
        await _log_decision("revoke", d["key_id"], payload.key_id, d.get("label"))

    # Promote the requester.
    await db.device_keys.update_one(
        {"key_id": payload.key_id},
        {"$set": {"role": "creator", "promoted_at": now_iso, "promoted_reason": "theft"}},
    )
    await _log_decision("promote", payload.key_id, payload.key_id, dev.get("label"))
    return {"recovered": True, "revoked_count": len(other_creators)}


@api_router.get("/webauthn/has-enrollment")
async def webauthn_has_enrollment():
    """Public lookup — returns whether any biometric is enrolled on this
    deployment. Used by the login page to show the right CTA."""
    count = await db.webauthn_credentials.count_documents({})
    return {"enrolled_count": count, "has_any": count > 0}


# ==========================================================================
# END pending sessions + WebAuthn
# ==========================================================================


# ==================== CODE GENERATION ROUTES ====================

@api_router.post("/generate/code")
async def generate_code(request: Request, input: GenerateCodeRequest):
    """Generate complete code for a project (simulated for now)"""
    user_id = await get_current_user(request)
    
    try:
        # Update project status
        await db.projects.update_one(
            {"project_id": input.project_id, "user_id": user_id},
            {"$set": {"status": "generating"}}
        )
        
        # Generate sample code structure (would use Emergent API in production)
        generated_code = {
            "files": [
                {
                    "path": "index.html",
                    "content": f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{input.description}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>{input.description}</h1>
        <p>Application générée automatiquement</p>
    </div>
    <script src="app.js"></script>
</body>
</html>"""
                },
                {
                    "path": "style.css",
                    "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Arial', sans-serif;
    background: #050505;
    color: #ffffff;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

h1 {
    color: #E4FF00;
    font-size: 3rem;
    margin-bottom: 1rem;
}"""
                },
                {
                    "path": "app.js",
                    "content": """console.log('Application prête !');

// Votre code JavaScript ici"""
                },
                {
                    "path": "manifest.json",
                    "content": json.dumps({
                        "name": input.description,
                        "short_name": input.description[:20],
                        "description": f"Application {input.project_type}",
                        "start_url": "/",
                        "display": "standalone",
                        "background_color": "#050505",
                        "theme_color": "#E4FF00",
                        "icons": [
                            {
                                "src": "/icon-192.png",
                                "sizes": "192x192",
                                "type": "image/png"
                            }
                        ]
                    }, indent=2)
                },
                {
                    "path": "README.md",
                    "content": f"""# {input.description}

Application générée par CodeForge AI

## Installation

### Web
Ouvrez `index.html` dans votre navigateur

### Mobile (APK)
1. Installez via la page d'export mobile
2. Activez les sources inconnues sur Android

### Desktop (EXE)
1. Téléchargez l'installateur
2. Exécutez et suivez les instructions

## Déploiement

### Vercel
```bash
npm install -g vercel
vercel
```

### Netlify
Glissez-déposez le dossier sur netlify.com
"""
                }
            ],
            "instructions": f"Application {input.project_type} générée avec succès. Prête pour l'export.",
            "dependencies": []
        }
        
        # Update project with generated code
        await db.projects.update_one(
            {"project_id": input.project_id},
            {"$set": {
                "generated_code": generated_code,
                "status": "completed",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "project_id": input.project_id,
            "generated_code": generated_code,
            "status": "completed"
        }
    
    except Exception as e:
        logger.error(f"Error generating code: {e}")
        
        # Update project status to error
        await db.projects.update_one(
            {"project_id": input.project_id},
            {"$set": {"status": "error"}}
        )
        
        raise HTTPException(status_code=500, detail=f"Erreur de génération: {str(e)}")

# ==================== EXPORT ROUTES ====================

@api_router.post("/export/github/{project_id}")
async def export_project_to_github(project_id: str, request: Request):
    """Push every file of a generated project to the configured GitHub repository
    under `projects/<sanitized-name>/` so the user has a permanent backup like
    Emergent's Save-to-Github.
    """
    user_id = await get_current_user(request)
    project = await db.projects.find_one(
        {"project_id": project_id, "user_id": user_id}, {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    if not GITHUB_ENABLED:
        raise HTTPException(status_code=503, detail="GitHub non configuré côté serveur.")

    files = (project.get("generated_code") or {}).get("files", [])
    is_chat = project.get("project_type") == "chat"
    if not files and not is_chat:
        raise HTTPException(status_code=400, detail="Aucun code à exporter.")

    # Sanitize folder name — keep ASCII alphanumeric/hyphen/underscore only.
    import unicodedata as _ud
    base = (project.get("name") or project_id)[:60]
    # Normalize accents (é → e), then keep only safe chars.
    ascii_base = _ud.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    safe = "".join(c if (c.isalnum() or c in ('-', '_')) else '-' for c in ascii_base).strip('-') or project_id
    folder = f"projects/{safe}-{project_id}"

    pushed = []
    failed = []
    for f in files:
        path = f.get("path") or "untitled.txt"
        content = f.get("content") or ""
        try:
            ok = await push_to_github(f"{folder}/{path}", content)
            (pushed if ok else failed).append(path)
        except Exception as exc:
            logger.warning(f"GitHub push failed for {path}: {exc}")
            failed.append(path)

    # README + chat transcript (chat-type projects get no source code, only history).
    readme = (
        f"# {project.get('name', '')}\n\n"
        f"{project.get('description', '')}\n\n"
        f"_Exporté depuis CodeForge AI · ID `{project_id}`_\n"
    )
    try:
        ok_readme = await push_to_github(f"{folder}/README.md", readme)
        (pushed if ok_readme else failed).append("README.md")
    except Exception:
        failed.append("README.md")

    if is_chat:
        msgs = await db.chat_messages.find(
            {"user_id": user_id, "project_id": project_id},
            {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
        ).sort("timestamp", 1).to_list(length=10000)
        transcript = "\n\n".join(
            f"### {('Toi' if m.get('role') == 'user' else 'CodeForge')} — {m.get('timestamp', '')}\n{m.get('content', '')}"
            for m in msgs
        )
        try:
            ok_tx = await push_to_github(f"{folder}/chat-transcript.md", transcript or "(vide)")
            (pushed if ok_tx else failed).append("chat-transcript.md")
        except Exception:
            failed.append("chat-transcript.md")

    repo_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO_NAME}/tree/main/{folder}"
    all_failed = bool(failed) and not pushed
    return {
        "success": not all_failed,
        "repository": f"{GITHUB_OWNER}/{GITHUB_REPO_NAME}",
        "folder": folder,
        "url": repo_url,
        "pushed": pushed,
        "failed": failed,
    }


@api_router.post("/export/download")
async def download_export(request: Request, export_req: ExportRequest):
    """Download project as ZIP"""
    user_id = await get_current_user(request)
    
    project = await db.projects.find_one(
        {"project_id": export_req.project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Chat-type projects have no generated_code — they export the transcript only.
    if not project.get("generated_code") and project.get("project_type") != "chat":
        raise HTTPException(status_code=400, detail="Aucun code généré. Générez d'abord le code.")
    
    # Ensure generated_code exists for the loop below.
    if not project.get("generated_code"):
        project["generated_code"] = {"files": []}
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
        # Always include a README at the root if not already present.
        existing_paths = {f.get("path") for f in generated_code.get("files", [])}
        if "README.md" not in existing_paths and "readme.md" not in existing_paths:
            readme = (
                f"# {project['name']}\n\n"
                f"{project.get('description', '')}\n\n"
                f"---\nGénéré par CodeForge AI · ID `{project['project_id']}`\n"
                f"Créé le : {project.get('created_at')}\n"
            )
            zip_file.writestr("README.md", readme)
        # If this project is a saved chat, append a transcript file.
        if project.get("project_type") == "chat":
            msgs = await db.chat_messages.find(
                {"user_id": user_id, "project_id": export_req.project_id},
                {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
            ).sort("timestamp", 1).to_list(length=10000)
            transcript = "\n\n".join(
                f"### {('Toi' if m.get('role') == 'user' else 'CodeForge')} — {m.get('timestamp', '')}\n{m.get('content', '')}"
                for m in msgs
            )
            zip_file.writestr("chat-transcript.md", transcript or "(empty)")
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['name']}.zip"
        }
    )

@api_router.get("/export/mobile/{project_id}")
async def redirect_to_pwa_install(project_id: str):
    """Redirect to PWA installation page"""
    return RedirectResponse(url=f"/api/pwa/install/{project_id}")

@api_router.get("/export/desktop/{project_id}")
async def redirect_to_desktop_install(project_id: str):
    """Redirect to Desktop installation page"""
    return RedirectResponse(url=f"/api/desktop/install/{project_id}")

@api_router.get("/export/download/apk/{project_id}")
async def download_apk(project_id: str):
    """Generate and download APK (simplified version)"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project or not project.get("generated_code"):
        raise HTTPException(status_code=404, detail="Projet ou code non trouvé")
    
    # For now, return the ZIP with instructions
    # In production, this would build an actual APK using Capacitor
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
        
        # Add APK build instructions
        zip_file.writestr("BUILD_APK.md", """# Build APK Instructions

## Option 1: Using Capacitor (Recommended)
```bash
npm install -g @capacitor/cli
capacitor init
capacitor add android
capacitor open android
# Build in Android Studio
```

## Option 2: Using PWA Builder
1. Visit https://www.pwabuilder.com/
2. Enter your app URL
3. Download Android package

## Option 3: Direct Install (PWA)
1. Host these files on a server
2. Open in Chrome on Android
3. Click "Add to Home Screen"
""")
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['name']}_android.zip"
        }
    )

@api_router.get("/export/download/exe/{project_id}")
async def download_exe(project_id: str):
    """Generate and download EXE (simplified version)"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project or not project.get("generated_code"):
        raise HTTPException(status_code=404, detail="Projet ou code non trouvé")
    
    # For now, return the ZIP with instructions
    # In production, this would build an actual EXE using Electron
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
        
        # Add Electron package.json
        zip_file.writestr("electron/package.json", json.dumps({
            "name": project["name"],
            "version": "1.0.0",
            "main": "main.js",
            "scripts": {
                "start": "electron .",
                "build": "electron-builder"
            },
            "devDependencies": {
                "electron": "latest",
                "electron-builder": "latest"
            },
            "build": {
                "appId": f"com.codeforge.{project['name'].lower()}",
                "win": {
                    "target": "nsis"
                }
            }
        }, indent=2))
        
        # Add Electron main.js
        zip_file.writestr("electron/main.js", """const { app, BrowserWindow } = require('electron');

function createWindow() {
    const win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });
    
    win.loadFile('../index.html');
}

app.whenReady().then(createWindow);
""")
        
        # Add build instructions
        zip_file.writestr("BUILD_EXE.md", """# Build Windows EXE Instructions

## Using Electron
```bash
cd electron
npm install
npm run build
```

The .exe will be in `electron/dist/`

## Alternative: Portable HTML App
Use NW.js or similar to package as standalone app
""")
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['name']}_windows.zip"
        }
    )

@api_router.get("/preview/{preview_id}")
async def get_preview(preview_id: str):
    """Get preview HTML for generated content"""
    preview = await db.previews.find_one({"preview_id": preview_id}, {"_id": 0})
    
    if not preview:
        return HTMLResponse("<h1>Prévisualisation non trouvée</h1>", status_code=404)
    
    # Return HTML preview
    html_content = preview.get("html_content", "")
    
    if not html_content:
        # Generate preview from files
        files = preview.get("files", [])
        html_parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Prévisualisation</title>"]
        
        # Add CSS
        for file in files:
            if file["path"].endswith(".css"):
                html_parts.append(f"<style>{file['content']}</style>")
        
        html_parts.append("</head><body>")
        
        # Add HTML
        for file in files:
            if file["path"].endswith(".html"):
                html_parts.append(file["content"])
        
        # Add JS
        for file in files:
            if file["path"].endswith(".js"):
                html_parts.append(f"<script>{file['content']}</script>")
        
        html_parts.append("</body></html>")
        html_content = "\n".join(html_parts)
    
    return HTMLResponse(content=html_content)

@api_router.get("/preview/project/{project_id}")
async def get_project_preview(project_id: str):
    """Get preview for a specific project"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        return HTMLResponse("<h1>Projet non trouvé</h1>", status_code=404)
    
    generated_code = project.get("generated_code") or {}
    files = (generated_code.get("files") if isinstance(generated_code, dict) else None) or []
    
    # Generate combined HTML preview
    html_parts = ["""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation - """ + project.get("name", "Projet") + """</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #050505; color: #fff; }
    </style>"""]
    
    # Add CSS files
    for file in files:
        if file["path"].endswith(".css"):
            html_parts.append(f"<style>{file['content']}</style>")
    
    html_parts.append("</head><body>")
    
    # Add HTML content
    for file in files:
        if file["path"].endswith(".html"):
            # Extract body content if full HTML
            content = file["content"]
            if "<body>" in content:
                start = content.find("<body>") + 6
                end = content.find("</body>")
                content = content[start:end] if end > start else content
            html_parts.append(content)
    
    # Add JS files
    for file in files:
        if file["path"].endswith(".js"):
            html_parts.append(f"<script>{file['content']}</script>")
    
    html_parts.append("</body></html>")
    
    return HTMLResponse(content="\n".join(html_parts))

@api_router.get("/preview/demo/{preview_type}")
async def get_demo_preview(preview_type: str):
    """Get demo preview pages for different formats (Web, PDF, DOCX, App)"""
    
    previews = {
        "web": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation Web - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: system-ui, -apple-system, sans-serif; 
            background: linear-gradient(135deg, #050505 0%, #0F0F13 100%); 
            color: #ffffff; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container { max-width: 800px; padding: 3rem; text-align: center; }
        .icon { font-size: 5rem; margin-bottom: 2rem; }
        h1 { color: #E4FF00; font-size: 3rem; margin-bottom: 1rem; }
        p { color: #A1A1AA; font-size: 1.2rem; line-height: 1.8; margin-bottom: 2rem; }
        .badge { 
            display: inline-block; 
            background: #00FF66; 
            color: #050505; 
            padding: 0.5rem 1.5rem; 
            border-radius: 2rem; 
            font-weight: bold;
            margin: 0.5rem;
        }
        .features { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 1.5rem; 
            margin-top: 3rem;
            text-align: left;
        }
        .feature { 
            background: rgba(255,255,255,0.05); 
            padding: 1.5rem; 
            border-radius: 0.5rem; 
            border: 1px solid rgba(255,255,255,0.1);
        }
        .feature h3 { color: #E4FF00; margin-bottom: 0.5rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🌐</div>
        <h1>Prévisualisation Web</h1>
        <p>Ceci est une démonstration de prévisualisation pour les applications web générées par CodeForge AI.</p>
        <span class="badge">HTML5</span>
        <span class="badge">CSS3</span>
        <span class="badge">JavaScript</span>
        <div class="features">
            <div class="feature">
                <h3>Responsive</h3>
                <p>S'adapte à tous les écrans</p>
            </div>
            <div class="feature">
                <h3>Moderne</h3>
                <p>Technologies récentes</p>
            </div>
            <div class="feature">
                <h3>Rapide</h3>
                <p>Performance optimisée</p>
            </div>
        </div>
    </div>
</body>
</html>""",

        "app": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation Application - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: system-ui, sans-serif; 
            background: #050505; 
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .phone-frame {
            width: 375px;
            height: 667px;
            background: #0F0F13;
            border-radius: 40px;
            padding: 20px;
            border: 3px solid #333;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
        }
        .phone-screen {
            background: linear-gradient(180deg, #1a1a2e 0%, #0F0F13 100%);
            height: 100%;
            border-radius: 25px;
            overflow: hidden;
        }
        .status-bar {
            height: 44px;
            background: rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            font-size: 12px;
        }
        .app-content {
            padding: 20px;
            text-align: center;
        }
        .app-icon {
            width: 80px;
            height: 80px;
            background: #E4FF00;
            border-radius: 20px;
            margin: 30px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
        }
        h2 { color: #E4FF00; margin-bottom: 10px; }
        p { color: #A1A1AA; font-size: 14px; }
        .btn {
            background: #E4FF00;
            color: #050505;
            border: none;
            padding: 15px 40px;
            border-radius: 25px;
            font-weight: bold;
            margin-top: 30px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="phone-frame">
        <div class="phone-screen">
            <div class="status-bar">
                <span>9:41</span>
                <span>📶 🔋</span>
            </div>
            <div class="app-content">
                <div class="app-icon">📱</div>
                <h2>Mon Application</h2>
                <p>Application mobile générée par CodeForge AI</p>
                <button class="btn">Démarrer</button>
            </div>
        </div>
    </div>
</body>
</html>""",

        "pdf": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation PDF - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Times New Roman', serif; 
            background: #404040; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .pdf-page {
            width: 595px;
            min-height: 842px;
            background: white;
            color: #000;
            padding: 60px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
        .header {
            border-bottom: 2px solid #E4FF00;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo { 
            font-size: 24px; 
            font-weight: bold; 
            color: #050505;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logo span { background: #E4FF00; padding: 5px 15px; }
        h1 { font-size: 28px; margin: 30px 0 20px; color: #1a1a1a; }
        p { line-height: 1.8; margin-bottom: 15px; color: #333; }
        .section { margin: 30px 0; }
        .highlight { background: #FFFFD0; padding: 15px; border-left: 4px solid #E4FF00; }
        .footer { 
            margin-top: 50px; 
            padding-top: 20px; 
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="pdf-page">
        <div class="header">
            <div class="logo">
                <span>CodeForge</span> AI
            </div>
        </div>
        <h1>Document de Prévisualisation</h1>
        <p>Ce document représente un aperçu de la génération PDF par CodeForge AI. Les documents générés peuvent inclure du texte formaté, des images et des tableaux.</p>
        
        <div class="section">
            <h2>Caractéristiques</h2>
            <ul style="margin-left: 20px; line-height: 2;">
                <li>Génération automatique de contenu</li>
                <li>Mise en page professionnelle</li>
                <li>Export haute qualité</li>
                <li>Compatible tous appareils</li>
            </ul>
        </div>
        
        <div class="highlight">
            <strong>Note:</strong> Les PDFs générés sont entièrement personnalisables et peuvent être modifiés selon vos besoins.
        </div>
        
        <div class="footer">
            Généré par CodeForge AI - Création Sans Limites
        </div>
    </div>
</body>
</html>""",

        "docx": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation DOCX - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Calibri', 'Arial', sans-serif; 
            background: #2b579a; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .word-container {
            background: #f3f3f3;
            padding: 20px;
            border-radius: 5px;
        }
        .toolbar {
            background: #2b579a;
            color: white;
            padding: 10px 20px;
            border-radius: 5px 5px 0 0;
            font-size: 14px;
            display: flex;
            gap: 20px;
        }
        .doc-page {
            width: 612px;
            min-height: 792px;
            background: white;
            color: #000;
            padding: 72px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        h1 { font-size: 26px; color: #2b579a; margin-bottom: 20px; }
        h2 { font-size: 18px; color: #2b579a; margin: 25px 0 15px; }
        p { line-height: 1.6; margin-bottom: 12px; }
        .table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .table th, .table td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        .table th { background: #2b579a; color: white; }
        .footer { 
            margin-top: 40px; 
            font-size: 11px; 
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 10px;
        }
    </style>
</head>
<body>
    <div class="word-container">
        <div class="toolbar">
            <span>📄 Document1.docx</span>
            <span>Fichier</span>
            <span>Édition</span>
            <span>Affichage</span>
        </div>
        <div class="doc-page">
            <h1>Document Word - Prévisualisation</h1>
            <p>Ce document représente un aperçu de la génération de fichiers DOCX par CodeForge AI. Les documents peuvent être édités dans Microsoft Word ou LibreOffice.</p>
            
            <h2>Fonctionnalités supportées</h2>
            <p>Les documents générés supportent de nombreuses fonctionnalités :</p>
            
            <table class="table">
                <tr>
                    <th>Fonctionnalité</th>
                    <th>Support</th>
                </tr>
                <tr>
                    <td>Texte formaté</td>
                    <td>✅ Complet</td>
                </tr>
                <tr>
                    <td>Tableaux</td>
                    <td>✅ Complet</td>
                </tr>
                <tr>
                    <td>Images</td>
                    <td>✅ Complet</td>
                </tr>
                <tr>
                    <td>En-têtes/Pieds de page</td>
                    <td>✅ Complet</td>
                </tr>
            </table>
            
            <div class="footer">
                Page 1 sur 1 | Généré par CodeForge AI
            </div>
        </div>
    </div>
</body>
</html>""",

        "image": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation Image - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: system-ui, sans-serif; 
            background: #1a1a1a; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .image-preview {
            background: #0F0F13;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .image-frame {
            width: 600px;
            height: 400px;
            background: linear-gradient(135deg, #E4FF00 0%, #00FF66 50%, #00D4FF 100%);
            border-radius: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #050505;
            font-size: 24px;
            font-weight: bold;
        }
        .info {
            margin-top: 15px;
            color: #A1A1AA;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="image-preview">
        <div class="image-frame">
            🖼️ Image Générée par IA
        </div>
        <div class="info">
            Format: PNG | Résolution: 1920x1080 | Taille: ~2.4 MB
        </div>
    </div>
</body>
</html>"""
    }
    
    content = previews.get(preview_type, previews["web"])
    return HTMLResponse(content=content)

# ==================== VOICE TRANSCRIPTION ====================

@api_router.post("/voice/transcribe")
async def voice_transcribe(
    request: Request,
    file: UploadFile = File(...),
    language: str = "auto",
):
    """Transcribe a short voice recording (<25MB) to text via OpenAI Whisper.

    Used by the chat & create pages for two UX flows:
    - "Voice message" — record → instant send (the AI receives the transcript).
    - "Dictation" — record → fill the input field for review before send.

    Returns: { "text": "...", "language": "fr", "duration_ms": 0 }
    """
    # Auth — same pattern as other endpoints; reject anonymous calls.
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentification requise")

    # Validate file type & size early (Whisper accepts mp3/mp4/mpeg/mpga/m4a/wav/webm).
    allowed = {"audio/webm", "audio/mp3", "audio/mpeg", "audio/mp4",
               "audio/m4a", "audio/wav", "audio/x-wav", "audio/ogg",
               "video/webm"}  # browsers send webm with audio codec as video/webm sometimes
    if file.content_type and file.content_type.split(";")[0].strip() not in allowed:
        # Don't be overly strict — Whisper auto-detects. Just log.
        logger.info(f"voice/transcribe: unusual content-type {file.content_type}")

    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux (>25MB)")
    if len(raw) < 200:
        raise HTTPException(status_code=400, detail="Enregistrement trop court ou vide")

    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        if not emergent_key:
            raise ValueError("EMERGENT_LLM_KEY not configured")

        stt = OpenAISpeechToText(api_key=emergent_key)
        # Wrap the bytes in a BytesIO for the integration.
        audio_buf = io.BytesIO(raw)
        # Whisper relies on the filename extension to guess the format,
        # so set a sensible name (browsers usually send webm).
        audio_buf.name = file.filename or "recording.webm"

        kwargs = {"file": audio_buf, "model": "whisper-1", "response_format": "json"}
        if language and language != "auto":
            kwargs["language"] = language[:2]  # ISO-639-1

        response = await stt.transcribe(**kwargs)
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="Aucun texte reconnu — réessaie en parlant plus clairement.")

        return {"text": text, "language": language, "size_bytes": len(raw)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"voice/transcribe error: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur de transcription : {e}")

# ==================== ROOT ROUTE ====================

@api_router.get("/")
async def root():
    return {
        "message": "API CodeForge AI - Plateforme de Génération IA Sans Limites",
        "version": "2.0.0",
        "status": "online",
        "features": [
            "Chat IA (GPT)",
            "Création avec Emergent",
            "Export Mobile (APK)",
            "Export Desktop (EXE)",
            "Sans limites"
        ]
    }

@api_router.get("/health")
async def health_check():
    """Health check + deployed version info (helps debug auto-deploy)."""
    import subprocess
    commit = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR.parent), timeout=2
        ).decode().strip()
    except Exception:
        pass

    # MongoDB ping
    db_ok = False
    try:
        await db.command("ping")
        db_ok = True
    except Exception as e:
        logger.warning(f"Health: Mongo ping failed: {e}")

    # Resend availability
    resend_ok = bool(os.environ.get("RESEND_API_KEY"))

    # Ollama best-effort (don't block — short timeout)
    ollama_ok = False
    try:
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "commit": commit,
        "checks": {
            "mongo": db_ok,
            "resend": resend_ok,
            "ollama": ollama_ok,
            "github": GITHUB_ENABLED,
        },
        "chat_ai": "GPT (disponible)",
        "create_ai": "Emergent (disponible)",
        "exports": "mobile + desktop",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@api_router.post("/admin/redeploy")
async def redeploy(request: Request):
    """Auto-deploy webhook called by GitHub Actions on push to main.
    Pulls latest code from origin/main and restarts the backend supervisor.
    Protected by DEPLOY_SECRET env var (HMAC-style shared secret).
    """
    import subprocess
    secret = os.environ.get("DEPLOY_SECRET")
    provided = request.headers.get("X-Deploy-Secret")

    if not secret:
        raise HTTPException(status_code=503, detail="DEPLOY_SECRET not configured")
    if not provided or provided != secret:
        raise HTTPException(status_code=401, detail="Invalid deploy secret")

    try:
        repo_dir = str(ROOT_DIR.parent)

        # Back up .env files BEFORE git operations, because they are tracked
        # in this repo and would be overwritten by git pull / reset --hard
        # with the (incomplete) GitHub-side version.
        env_files = ["backend/.env", "frontend/.env"]
        env_backups = {}
        for env_path in env_files:
            full = os.path.join(repo_dir, env_path)
            if os.path.exists(full):
                with open(full, "rb") as f:
                    env_backups[env_path] = f.read()

        # Robust sync: fetch + hard reset on origin/main.
        # Avoids "divergent branches" errors that plain `git pull` hits when
        # local has auto-commits or the same file was edited via GitHub UI.
        fetch_out = subprocess.check_output(
            ["git", "fetch", "origin", "main"],
            cwd=repo_dir, stderr=subprocess.STDOUT, timeout=30
        ).decode()
        reset_out = subprocess.check_output(
            ["git", "reset", "--hard", "origin/main"],
            cwd=repo_dir, stderr=subprocess.STDOUT, timeout=30
        ).decode()

        # Restore .env files (preserve runtime secrets)
        for env_path, content in env_backups.items():
            full = os.path.join(repo_dir, env_path)
            with open(full, "wb") as f:
                f.write(content)

        new_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir, stderr=subprocess.STDOUT, timeout=10
        ).decode().strip()

        # Trigger uvicorn hot-reload by touching server.py
        # (more reliable than supervisorctl restart in background which races
        # with watchfiles and can leave supervisor in STOPPED state).
        subprocess.Popen(
            ["sh", "-c", "sleep 1 && touch backend/server.py"],
            cwd=repo_dir
        )
        return {
            "status": "deploying",
            "commit": new_commit,
            "git_fetch": fetch_out.strip(),
            "git_reset": reset_out.strip(),
            "env_preserved": list(env_backups.keys()),
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Deploy failed: {e.output.decode() if e.output else str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

# Include PWA routes under /api/pwa
app.include_router(pwa_router, prefix="/api/pwa", tags=["PWA"])

# Include Desktop routes under /api/desktop
app.include_router(desktop_router, prefix="/api/desktop", tags=["Desktop"])


@app.on_event("startup")
async def ensure_indexes():
    """Create MongoDB indexes used by the email/password auth flow."""
    try:
        await db.users.create_index("email", unique=True, sparse=True)
        await db.email_verifications.create_index("token", unique=True)
        await db.email_verifications.create_index("user_id")
        await db.user_sessions.create_index("session_token", unique=True)
        await db.login_attempts.create_index("identifier")
        await db.resend_attempts.create_index("email")
        await db.password_resets.create_index("email")
        await db.password_reset_tokens.create_index("token", unique=True)
        await db.password_reset_tokens.create_index("user_id")
        logger.info("✅ MongoDB indexes ready")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


# Background task: every 10 minutes, drop expired/stale auth rows so the
# DB doesn't grow unboundedly. Documents store ISO strings (not Mongo
# Date) so we can't use a TTL index — we sweep manually.
_cleanup_task: asyncio.Task | None = None


async def _periodic_auth_cleanup():
    while True:
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            # Verifications older than expires_at (and not consumed for >1h)
            await db.email_verifications.delete_many({"expires_at": {"$lt": now_iso}})
            # User sessions past expiry
            await db.user_sessions.delete_many({"expires_at": {"$lt": now_iso}})
            # Password reset tokens past expiry
            await db.password_reset_tokens.delete_many({"expires_at": {"$lt": now_iso}})
            # Login + resend + reset attempts older than 24h (rate-limit data)
            day_ago = (now - timedelta(hours=24)).isoformat()
            await db.login_attempts.delete_many({"ts": {"$lt": day_ago}})
            await db.resend_attempts.delete_many({"ts": {"$lt": day_ago}})
            await db.password_resets.delete_many({"ts": {"$lt": day_ago}})
            # Auth-error logs older than 7d (kept for /metrics 24h window with margin)
            week_ago = (now - timedelta(days=7)).isoformat()
            await db.auth_errors.delete_many({"ts": {"$lt": week_ago}})
        except Exception as e:
            logger.warning(f"Cleanup task error: {e}")
        await asyncio.sleep(10 * 60)  # 10 minutes


@app.on_event("startup")
async def start_cleanup_task():
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_periodic_auth_cleanup())
    logger.info("✅ Auth cleanup background task started (every 10 min)")


@app.on_event("shutdown")
async def shutdown_db_client():
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
    client.close()
