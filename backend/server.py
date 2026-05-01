from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from pydantic import BaseModel, Field, ConfigDict

from pathlib import Path
from typing import List, Optional, Dict, Any

from datetime import datetime, timezone, timedelta

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

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO_NAME}/contents/{file_path}"

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

class ChatMessageInput(BaseModel):
    message: str
    project_id: Optional[str] = None
    mode: Optional[str] = "online"
    language: Optional[str] = "fr"

class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    description: Optional[str] = ""
    project_type: str = "web"
    status: str = "created"
    generated_code: Optional[Dict[str, Any]] = None
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
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await db.login_attempts.insert_one({
            "identifier": identifier,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        await log_auth_error("login_invalid_credentials", f"email={email}", request=request)
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.get("verified"):
        raise HTTPException(
            status_code=403,
            detail="Email non confirmé. Clique sur le lien reçu par email ou recrée ton compte.",
        )

    # Success: clear failed attempts
    await db.login_attempts.delete_many({"identifier": identifier})

    now = datetime.now(timezone.utc)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"last_login": now.isoformat()}})

    session_token = secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user["user_id"],
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

class FeedbackRequest(BaseModel):
    type: str  # 'bug' | 'suggestion' | 'other'
    message: str
    email: Optional[str] = None
    page: Optional[str] = None  # current page url for context


@api_router.post("/feedback")
async def submit_feedback(payload: FeedbackRequest, request: Request):
    """Store user feedback in MongoDB + send email to admin."""
    if not payload.message or len(payload.message.strip()) < 5:
        raise HTTPException(status_code=400, detail="Le message doit contenir au moins 5 caractères")
    if len(payload.message) > 5000:
        raise HTTPException(status_code=400, detail="Message trop long (max 5000 caractères)")

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

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "feedback_id": f"fb_{uuid.uuid4().hex[:12]}",
        "type": feedback_type,
        "message": payload.message.strip(),
        "user_email": user_email,
        "page": payload.page,
        "created_at": now,
    }
    await db.feedbacks.insert_one(doc)

    # Email to admin (best-effort, never block the response)
    resend_key = os.environ.get("RESEND_API_KEY")
    admin = os.environ.get("EMAIL_REPLY_TO", "commandes.et.publicites@gmail.com")
    if resend_key:
        try:
            sender = os.environ.get("EMAIL_FROM", "CodeForge AI <onboarding@resend.dev>")
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": sender,
                        "to": [admin],
                        "subject": f"[CodeForge AI] Nouveau {feedback_type}",
                        "html": (
                            f"<div style='font-family:system-ui,sans-serif'>"
                            f"<p><b>Type :</b> {feedback_type}</p>"
                            f"<p><b>Email :</b> {user_email}</p>"
                            f"<p><b>Page :</b> {payload.page or '—'}</p>"
                            f"<p><b>Message :</b></p><pre style='white-space:pre-wrap;background:#f4f4f5;padding:12px;border-radius:6px'>{(payload.message or '').replace('<','&lt;')}</pre>"
                            f"<hr><p style='color:#888;font-size:11px'>ID : {doc['feedback_id']} · {now}</p></div>"
                        ),
                    },
                )
        except Exception as e:
            logger.warning(f"Feedback admin email failed: {e}")

    return {"message": "Merci ! Ton retour a bien été enregistré.", "feedback_id": doc["feedback_id"]}


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
            
            # Initialize chat with GPT-4o
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"codeforge_{uuid.uuid4().hex[:8]}",
                system_message="Tu es un expert développeur senior. Tu génères du code complet, fonctionnel et professionnel. Réponds TOUJOURS en JSON valide."
            ).with_model("openai", "gpt-4o")
            
            # Send generation request
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            ai_text = response
            ai_source = 'emergent_gpt4o'
            logger.info("Generation via Emergent GPT-4o successful")
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
        ollama_model = os.environ.get('OLLAMA_MODEL', 'llama3.3')
        
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
        # Save user message
        user_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": input.project_id,
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
        }
        lang_label = language_names.get(user_language, 'français')
        system_prompt = (
            f"Tu es CodeForge AI, un assistant chaleureux et conversationnel. "
            f"Réponds TOUJOURS en {lang_label}, comme un ami qui aide. "
            f"\n\nRÈGLES IMPORTANTES :\n"
            f"- Pour les salutations (« bonjour », « salut », « hello »…) : réponds par UNE phrase courte de salutation et propose ton aide. "
            f"NE PARLE PAS de code, d'apps, de PWA, de React ou de tech tant que l'utilisateur ne le demande pas explicitement.\n"
            f"- Pour les questions courtes ou floues : pose une question de précision plutôt que d'inventer une réponse technique.\n"
            f"- Pour les vraies questions de dev : sois concis, donne l'essentiel, propose un exemple court si c'est utile.\n"
            f"- Ne mentionne JAMAIS Ollama, GPT, OpenAI ni les fournisseurs. Tu es juste « CodeForge AI ».\n"
            f"- Pas d'auto-promotion, pas de bullets de features non demandées."
        )

        if input.mode == 'offline':
            # Offline mode → Ollama only.
            ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
            ollama_model = os.environ.get('OLLAMA_MODEL', 'deepseek-coder:33b')
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{ollama_url}/api/generate",
                        json={
                            "model": ollama_model,
                            "system": system_prompt,
                            "prompt": input.message,
                            "stream": False,
                        },
                    )
                    if response.status_code == 200:
                        ai_response_text = (response.json() or {}).get('response', '').strip()
                        ai_source = 'ollama'
                        logger.info("✅ Ollama (offline) chat response successful")
            except Exception as ollama_error:
                logger.info(f"Ollama offline unreachable: {ollama_error}")
        else:
            # Online mode → Emergent GPT-4o.
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                emergent_key = os.environ.get('EMERGENT_LLM_KEY')
                if not emergent_key:
                    raise ValueError("EMERGENT_LLM_KEY not configured")

                # Reuse the same session per user so the AI keeps short-term context.
                session_id = f"codeforge_chat_{user_id}"
                chat = LlmChat(
                    api_key=emergent_key,
                    session_id=session_id,
                    system_message=system_prompt,
                ).with_model("openai", "gpt-4o")
                user_message = UserMessage(text=input.message)
                ai_response_text = (await chat.send_message(user_message) or '').strip()
                ai_source = 'emergent_gpt4o'
                logger.info("✅ Emergent GPT-4o chat response successful")
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
        
        # Save AI response
        ai_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": input.project_id,
            "role": "assistant",
            "content": ai_response_text,
            "mode": input.mode,
            "ai_source": ai_source,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(ai_message_doc)
        
        # Remove MongoDB _id from response to avoid serialization issues
        user_message_response = {k: v for k, v in user_message_doc.items() if k != '_id'}
        ai_message_response = {k: v for k, v in ai_message_doc.items() if k != '_id'}
        
        return {
            "user_message": user_message_response,
            "ai_response": ai_message_response
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

# ==================== WIZARD AI HELPERS ====================

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
        ).with_model("openai", "gpt-4o")
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
    
    # Convert ISO strings to datetime
    for project in projects:
        if isinstance(project['created_at'], str):
            project['created_at'] = datetime.fromisoformat(project['created_at'])
        if isinstance(project['updated_at'], str):
            project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    
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
    
    # Convert ISO strings to datetime
    if isinstance(project['created_at'], str):
        project['created_at'] = datetime.fromisoformat(project['created_at'])
    if isinstance(project['updated_at'], str):
        project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    
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
    
    if not project.get("generated_code"):
        raise HTTPException(status_code=400, detail="Aucun code généré. Générez d'abord le code.")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
    
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
    
    generated_code = project.get("generated_code", {})
    files = generated_code.get("files", [])
    
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
