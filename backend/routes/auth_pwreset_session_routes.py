"""iter120 — Routes /auth/* password-reset + session-request extraites de server.py.

6 endpoints :
  - POST /auth/forgot-password
  - GET  /auth/confirm-password-reset
  - POST /auth/reset-password
  - POST /auth/session-request-status
  - GET  /auth/session-pending
  - POST /auth/session-decide

Helpers injectés (passés explicitement pour éviter les imports circulaires) :
  - normalize_email, EMAIL_RE, _clean_origin
  - hash_password, send_reset_email
  - get_current_user
"""
from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


class ForgotPasswordRequest(BaseModel):
    email: str
    password: Optional[str] = None  # NEW flow: user supplies the new password upfront
    frontend_url: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class SessionRequestStatusIn(BaseModel):
    request_id: str


class SessionDecideIn(BaseModel):
    request_id: str
    decision: str  # 'approve' | 'deny'


def build_auth_pwreset_session_router(
    db,
    *,
    normalize_email,
    email_re,
    clean_origin,
    hash_password,
    send_reset_email,
    get_current_user,
):
    router = APIRouter()

    @router.post("/auth/forgot-password")
    async def forgot_password(payload: ForgotPasswordRequest, request: Request):
        """Step 1 of the "set then confirm" reset flow.

        The user enters their email + a NEW password (twice, validated by frontend).
        We store the new hash on a pending token, then email a confirmation link.
        Always returns the same neutral message to prevent email enumeration.
        Rate-limited: 3 requests / 10 min / email.
        """
        email = normalize_email(payload.email)
        if not email or not email_re.match(email):
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
            clean_origin(payload.frontend_url)
            or clean_origin(os.environ.get("FRONTEND_URL", ""))
            or clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
        )
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

    @router.get("/auth/confirm-password-reset")
    async def confirm_password_reset(request: Request, token: str):
        """Step 2: user clicks the email link → apply the pending password.

        Returns a small HTML success page that auto-redirects to /login after 3s.
        """
        frontend_base = (
            clean_origin(os.environ.get("FRONTEND_URL", ""))
            or clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
            or ""
        )

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

    @router.post("/auth/reset-password")
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
        # Invalidate all existing sessions for this user (defense in depth).
        await db.user_sessions.delete_many({"user_id": doc["user_id"]})
        # Clear failed-login counters
        await db.login_attempts.delete_many({"identifier": doc["email"]})

        return {"message": "Mot de passe mis à jour. Tu peux te reconnecter."}

    @router.post("/auth/session-request-status")
    async def session_request_status(payload: SessionRequestStatusIn, response: Response):
        """Polled by the requesting device until the connected device decides
        (approve/deny) or the request expires (15 min).

        Idempotent: once approved, the session token is persisted on the request
        and returned on every subsequent poll until the requesting device clears it.
        """
        now = datetime.now(timezone.utc)
        req = await db.session_requests.find_one({"request_id": payload.request_id}, {"_id": 0})
        if not req:
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
                "last_seen_at": now.isoformat(),  # iter66
                "expires_at": (now + timedelta(days=7)).isoformat(),
            })
            # Tiny read-after-write check (max 3 attempts × 50ms) — paranoia for
            # hosted MongoDB clusters with secondary read preference.
            for _ in range(3):
                check = await db.user_sessions.find_one(
                    {"session_token": session_token}, {"_id": 0, "session_token": 1}
                )
                if check:
                    break
                await asyncio.sleep(0.05)
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"last_login": now.isoformat()}})
            await db.session_requests.update_one(
                {"request_id": payload.request_id},
                {"$set": {
                    "issued_session_token": session_token,
                    "consumed_at": now.isoformat(),
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

    @router.get("/auth/session-pending")
    async def list_pending_session_requests(request: Request):
        """Listed by the currently-connected user — pending requests on their
        account from other devices.

        iter83 — auto-expire requests pending de plus de 90 secondes (fix
        "demande fantôme récurrente").
        """
        user_id = await get_current_user(request)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        stale_threshold = (now - timedelta(seconds=90)).isoformat()
        # Auto-expire stale pending requests.
        await db.session_requests.update_many(
            {"user_id": user_id, "status": "pending", "created_at": {"$lt": stale_threshold}},
            {"$set": {"status": "expired", "expired_at": now_iso}},
        )
        rows = await db.session_requests.find(
            {"user_id": user_id, "status": "pending",
             "expires_at": {"$gt": now_iso}, "created_at": {"$gte": stale_threshold}},
            {"_id": 0},
        ).sort("created_at", -1).to_list(length=50)
        # iter146 — Filtre défensif : la validation doit se déclencher UNIQUEMENT
        # sur le premier appareil déjà connecté, JAMAIS sur le nouvel appareil
        # qui a lancé la demande. On exclut toute requête dont le
        # `requesting_key_id` correspond à un device_key du caller.
        try:
            caller_devices = [
                d["key_id"] async for d in db.device_keys.find(
                    {"user_id": user_id}, {"_id": 0, "key_id": 1},
                )
            ]
            # user_id → email lookup si nécessaire (device_keys est ancré email).
            if not caller_devices:
                u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1})
                if u and u.get("email"):
                    caller_devices = [
                        d["key_id"] async for d in db.device_keys.find(
                            {"email": u["email"]}, {"_id": 0, "key_id": 1},
                        )
                    ]
            # Récupère le device_key actuellement authentifié depuis le cookie/session.
            sess = await db.user_sessions.find_one(
                {"user_id": user_id, "expires_at": {"$gt": now_iso}},
                {"_id": 0, "device_key_id": 1},
                sort=[("last_seen_at", -1)],
            )
            active_dev = (sess or {}).get("device_key_id")
            if active_dev:
                rows = [r for r in rows if r.get("requesting_key_id") != active_dev]
        except Exception:
            pass
        return {"requests": rows}

    @router.post("/auth/session-decide")
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

    return router
