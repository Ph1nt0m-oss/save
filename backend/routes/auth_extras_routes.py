"""iter119 — Routes /auth/* extras extraites de server.py.

7 endpoints "satellites" auth (les plus isolés en termes de helpers) :
  - GET  /auth/preferences (user prefs read)
  - PUT  /auth/preferences (user prefs write)
  - POST /auth/update-pseudo
  - POST /auth/theft-email-request
  - GET  /auth/theft-email-confirm
  - POST /auth/theft-iris-verify

Les endpoints /auth/* "lourds" (register, login, magic-link, verify-email,
reset-password, sms, session-*) restent dans server.py car leurs helpers
(email pipeline, password strength, session creation, cookies) sont
imbriqués dans des dizaines d'autres routes.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class UserPreferences(BaseModel):
    theme: Optional[str] = "dark"
    contrast: Optional[str] = "normal"
    accent: Optional[str] = "#E4FF00"
    notifications_email: Optional[bool] = True
    notifications_push: Optional[bool] = False


class UpdatePseudoIn(BaseModel):
    new_pseudo: str


class TheftEmailIn(BaseModel):
    email: str


class TheftIrisVerifyIn(BaseModel):
    token: Optional[str] = None
    email: Optional[str] = None
    hashes: List[str]


def build_auth_extras_router(db, *, get_current_user, send_email, clean_origin, logger):
    router = APIRouter()

    @router.get("/auth/preferences")
    async def get_user_preferences(request: Request):
        user_id = await get_current_user(request)
        doc = await db.user_preferences.find_one({"user_id": user_id}, {"_id": 0, "user_id": 0}) or {}
        base = UserPreferences().model_dump()
        base.update({k: v for k, v in doc.items() if k in base})
        return base

    @router.put("/auth/preferences")
    async def put_user_preferences(request: Request, prefs: UserPreferences):
        user_id = await get_current_user(request)
        payload = prefs.model_dump()
        await db.user_preferences.update_one(
            {"user_id": user_id},
            {"$set": {**payload, "user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return payload

    @router.post("/auth/update-pseudo")
    async def auth_update_pseudo(request: Request, payload: UpdatePseudoIn):
        user_id = await get_current_user(request)
        p = (payload.new_pseudo or "").strip()
        if not (1 <= len(p) <= 30):
            raise HTTPException(status_code=400, detail="Pseudo invalide (1-30).")
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1})
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        await db.users.update_one({"user_id": user_id}, {"$set": {"pseudo": p, "pseudo_lower": p.lower()}})
        if user.get("email"):
            await db.device_keys.update_many(
                {"email": user["email"]},
                {"$set": {"pseudo": p, "label": p}},
            )
        return {"success": True, "pseudo": p}

    @router.post("/auth/theft-email-request")
    async def auth_theft_email_request(payload: TheftEmailIn):
        email = (payload.email or "").strip().lower()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="Email invalide.")
        user = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        if user:
            token = uuid.uuid4().hex
            await db.theft_email_tokens.insert_one({
                "token": token, "email": email,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "used": False,
            })
            frontend_base = (
                clean_origin(os.environ.get("FRONTEND_URL", ""))
                or clean_origin(os.environ.get("REACT_APP_BACKEND_URL", ""))
                or ""
            )
            link = f"{frontend_base}/theft-confirm?token={token}" if frontend_base else f"/theft-confirm?token={token}"
            try:
                html = (
                    "<div style='font-family:system-ui,sans-serif;background:#050505;color:#fff;padding:32px;max-width:560px;margin:0 auto'>"
                    "<h1 style='color:#E4FF00;margin:0 0 16px'>CodeForge AI</h1>"
                    "<p style='color:#E4E4E7'>Tu reçois ce mail parce qu'une procédure de récupération en cas de vol a été demandée depuis un nouvel appareil.</p>"
                    "<p style='color:#FF6B6B'><strong>Si ce n'est pas toi, ignore ce message.</strong></p>"
                    "<p style='color:#E4E4E7'>Sinon, clique ci-dessous pour révoquer tous les anciens appareils enregistrés sous ton compte :</p>"
                    f"<p style='margin:24px 0'><a href='{link}' style='background:#E4FF00;color:#050505;padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block'>Confirmer la récupération</a></p>"
                    f"<p style='color:#A1A1AA;font-size:12px'>Ou copie ce lien : <span style='color:#00D4FF;word-break:break-all'>{link}</span></p>"
                    "<p style='color:#A1A1AA;font-size:12px'>Ce lien expire dans 30 minutes.</p>"
                    "</div>"
                )
                await send_email(email, "CodeForge AI — Récupération en cas de vol", html)
            except Exception as e:
                logger.warning(f"theft-email send failed: {e}")
        return {"success": True}

    @router.get("/auth/theft-email-confirm")
    async def auth_theft_email_confirm(token: str):
        row = await db.theft_email_tokens.find_one({"token": token}, {"_id": 0})
        if not row or row.get("used"):
            raise HTTPException(status_code=404, detail="Lien invalide ou déjà utilisé.")
        try:
            created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - created).total_seconds() > 1800:
                raise HTTPException(status_code=410, detail="Lien expiré.")
        except (KeyError, ValueError):
            raise HTTPException(status_code=410, detail="Lien expiré.")
        email = row["email"]
        r = await db.device_keys.update_many(
            {"email": email, "role": {"$in": ["creator", "approved"]}},
            {"$set": {"role": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat(),
                      "revoked_reason": "theft_email_recovery"}},
        )
        await db.theft_email_tokens.update_one({"token": token}, {"$set": {"used": True}})
        return {"success": True, "revoked_count": r.modified_count}

    @router.post("/auth/theft-iris-verify")
    async def auth_theft_iris_verify(payload: TheftIrisVerifyIn):
        if not isinstance(payload.hashes, list) or len(payload.hashes) < 3:
            raise HTTPException(status_code=400, detail="3 captures iris sont requises.")
        if any((not isinstance(h, str)) or len(h) < 20 or len(h) > 128 for h in payload.hashes[:3]):
            raise HTTPException(status_code=400, detail="Empreintes iris invalides.")
        email = (payload.email or "").strip().lower() or None
        if not email and payload.token:
            row = await db.theft_email_tokens.find_one({"token": payload.token}, {"_id": 0, "email": 1})
            if row:
                email = row.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email du compte requis.")
        user = await db.users.find_one({"email": email}, {"_id": 0, "biometric": 1})
        if not user or (user.get("biometric") or {}).get("kind") != "iris":
            logger.info(f"theft-iris-verify: no iris baseline for {email}, accepting capture as observation only")
        await db.theft_iris_attempts.insert_one({
            "email": email, "hashes": payload.hashes[:3], "token": payload.token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "verified": False,
        })
        return {"success": True, "revoked_count": 0}

    return router
