"""iter120 — Routes /auth/* signup/verification extraites de server.py.

4 endpoints liés au cycle "magic link + verify email" :
  - POST /auth/magic-link
  - POST /auth/resend-verification
  - GET  /auth/verify-email
  - GET  /auth/verification-status

Helpers injectés (passés explicitement pour éviter les imports circulaires) :
  - normalize_email, EMAIL_RE, _clean_origin
  - send_verification_email (Resend / SMTP pipeline)
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel


class ResendRequest(BaseModel):
    email: str
    frontend_url: Optional[str] = None


class MagicLinkLoginRequest(BaseModel):
    email: str
    frontend_url: Optional[str] = None


def build_auth_signup_verify_router(
    db,
    *,
    normalize_email,
    email_re,
    clean_origin,
    send_verification_email,
):
    router = APIRouter()

    @router.post("/auth/magic-link")
    async def magic_link_login(payload: MagicLinkLoginRequest, request: Request):
        """Send a one-shot login link to a verified user.

        Always returns a neutral message to prevent email enumeration.
        Rate-limited 3/10 min.
        """
        email = normalize_email(payload.email)
        if not email or not email_re.match(email):
            raise HTTPException(status_code=400, detail="Adresse email invalide")

        user = await db.users.find_one({"email": email}, {"_id": 0})
        neutral = {
            "message": "Si un compte existe pour cet email, un lien de connexion t'a été envoyé.",
        }

        if not user or not user.get("verified"):
            return neutral

        # Rate limit: 3 magic links / 10 min / verified email
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        recent = await db.resend_attempts.count_documents(
            {"email": email, "ts": {"$gte": cutoff}, "purpose": "magic_login"}
        )
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
            clean_origin(payload.frontend_url)
            or clean_origin(os.environ.get("FRONTEND_URL", ""))
            or clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
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

    @router.post("/auth/resend-verification")
    async def resend_verification(payload: ResendRequest, request: Request):
        """Generate a fresh magic link for an unverified account.

        Rate-limited: at most 3 resends / 10 min / email. Already-verified
        users get a friendly message instead of a link (no enumeration).
        """
        email = normalize_email(payload.email)
        if not email or not email_re.match(email):
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

        frontend_base = (
            clean_origin(payload.frontend_url)
            or clean_origin(os.environ.get("FRONTEND_URL", ""))
            or clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
        )
        verify_url = f"{frontend_base}/verify-email?token={token}" if frontend_base else f"/verify-email?token={token}"

        sent = await send_verification_email(email, verify_url)
        resp = {
            "message": "Nouveau lien envoyé ! Tu as 5 minutes." if sent
            else "Nouveau lien généré. L'e-mail n'a pas pu être envoyé automatiquement — utilise le lien ci-dessous.",
            "email": email,
            "email_sent": sent,
            "verification_token": token,
            "expires_in_seconds": 5 * 60,
            # iter59: always expose the link as a copy/open fallback
            "verification_link": verify_url,
        }
        return resp

    @router.get("/auth/verify-email")
    async def verify_email(token: str):
        """Consume the magic link.

        Marks the user as verified, stores a fresh session_token against the
        verification row, and returns a friendly message. We do NOT set a
        cookie here because the user may have opened this link in a different
        tab/device from the one where they registered.
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

    @router.get("/auth/verification-status")
    async def verification_status(token: str, response: Response):
        """Polled by the original registration tab every ~2 seconds.

        Returns one of:
          - {status: "pending"}
          - {status: "expired"}
          - {status: "verified", session_token, user}
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

    return router
