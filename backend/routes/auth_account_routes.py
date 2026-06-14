"""iter120 — Routes /auth/* account management extraites de server.py.

4 endpoints liés à la gestion du compte connecté :
  - POST /auth/change-password
  - POST /auth/change-email
  - DELETE /auth/me
  - GET  /auth/export

Helpers injectés explicitement (anti-circular imports).
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangeEmailRequest(BaseModel):
    new_email: str
    current_password: str
    frontend_url: Optional[str] = None


class DeleteAccountRequest(BaseModel):
    current_password: str


def build_auth_account_router(
    db,
    *,
    get_current_user,
    verify_password,
    hash_password,
    normalize_email,
    email_re,
    clean_origin,
    send_verification_email,
):
    router = APIRouter()

    @router.post("/auth/change-password")
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

    @router.post("/auth/change-email")
    async def change_email(payload: ChangeEmailRequest, request: Request):
        """Request a change of email. Sends a verification link to the NEW
        email; the change is only applied once the user clicks the link.
        """
        user_id = await get_current_user(request)
        new_email = normalize_email(payload.new_email)
        if not new_email or not email_re.match(new_email):
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
            clean_origin(payload.frontend_url)
            or clean_origin(os.environ.get("FRONTEND_URL", ""))
            or clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
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

    @router.delete("/auth/me")
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

    @router.get("/auth/export")
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

    return router
