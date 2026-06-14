"""iter118 — Routes /webauthn/* extraites de server.py.

6 endpoints WebAuthn (biométrie enrollment + signup + theft recovery) :
  - /webauthn/enroll-begin (signup-time enrollment options, public)
  - /webauthn/register-options (créa)
  - /webauthn/register-verify (créa)
  - /webauthn/declare-theft-options (public, registered device only)
  - /webauthn/declare-theft-verify (public — recovery)
  - /webauthn/has-enrollment (public)
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import webauthn
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


class WebAuthnSignupEnrollIn(BaseModel):
    email: Optional[str] = None
    origin: Optional[str] = None


class WebAuthnEnrollOptionsIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    origin: str


class WebAuthnEnrollVerifyIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    origin: str
    credential: Dict[str, Any]


class WebAuthnTheftOptionsIn(BaseModel):
    key_id: str
    origin: str


class WebAuthnTheftVerifyIn(BaseModel):
    key_id: str
    origin: str
    credential: Dict[str, Any]


def build_webauthn_router(db, *, require_creator_signature, device_by_key, log_decision, rp_id_from_origin):
    router = APIRouter()

    @router.post("/webauthn/enroll-begin")
    async def webauthn_enroll_begin(payload: WebAuthnSignupEnrollIn, request: Request):
        origin = payload.origin or request.headers.get("origin") or request.headers.get("referer") or ""
        rp_id = rp_id_from_origin(origin) if origin else "localhost"
        user_handle = secrets.token_bytes(16)
        options_token = secrets.token_urlsafe(24)
        options = webauthn.generate_registration_options(
            rp_id=rp_id, rp_name="CodeForge AI",
            user_id=user_handle,
            user_name=(payload.email or f"new_{secrets.token_hex(4)}@codeforge.ai")[:64],
            user_display_name=payload.email or "Nouveau compte",
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
            timeout=120_000,
        )
        await db.webauthn_challenges.insert_one({
            "options_token": options_token,
            "challenge": webauthn.helpers.bytes_to_base64url(options.challenge),
            "rp_id": rp_id, "kind": "signup", "origin": origin,
            "user_handle": webauthn.helpers.bytes_to_base64url(user_handle),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "options": json.loads(webauthn.helpers.options_to_json(options)),
            "options_token": options_token,
        }

    @router.post("/webauthn/register-options")
    async def webauthn_register_options(payload: WebAuthnEnrollOptionsIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        rp_id = rp_id_from_origin(payload.origin)
        user_handle = payload.key_id.encode("utf-8")[:64]
        options = webauthn.generate_registration_options(
            rp_id=rp_id, rp_name="CodeForge AI",
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
        await db.webauthn_challenges.insert_one({
            "key_id": payload.key_id,
            "challenge": webauthn.helpers.bytes_to_base64url(options.challenge),
            "rp_id": rp_id, "kind": "register", "origin": payload.origin,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return json.loads(webauthn.helpers.options_to_json(options))

    @router.post("/webauthn/register-verify")
    async def webauthn_register_verify(payload: WebAuthnEnrollVerifyIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
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
            "owner_key_id": payload.key_id,
            "rp_id": challenge_doc["rp_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"enrolled": True}

    @router.post("/webauthn/declare-theft-options")
    async def webauthn_declare_theft_options(payload: WebAuthnTheftOptionsIn):
        if not await device_by_key(payload.key_id):
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        rp_id = rp_id_from_origin(payload.origin)
        creds = await db.webauthn_credentials.find({"rp_id": rp_id}, {"_id": 0}).to_list(length=20)
        if not creds:
            raise HTTPException(status_code=404, detail="Aucune biométrie enrôlée — le créateur doit d'abord enregistrer son empreinte depuis son appareil créateur.")
        allow = [
            PublicKeyCredentialDescriptor(id=webauthn.helpers.base64url_to_bytes(c["credential_id"]))
            for c in creds
        ]
        options = webauthn.generate_authentication_options(
            rp_id=rp_id, allow_credentials=allow,
            user_verification=UserVerificationRequirement.REQUIRED,
            timeout=60_000,
        )
        await db.webauthn_challenges.insert_one({
            "key_id": payload.key_id,
            "challenge": webauthn.helpers.bytes_to_base64url(options.challenge),
            "rp_id": rp_id, "kind": "theft", "origin": payload.origin,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return json.loads(webauthn.helpers.options_to_json(options))

    @router.post("/webauthn/declare-theft-verify")
    async def webauthn_declare_theft_verify(payload: WebAuthnTheftVerifyIn):
        dev = await device_by_key(payload.key_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        challenge_doc = await db.webauthn_challenges.find_one_and_delete(
            {"key_id": payload.key_id, "kind": "theft"},
        )
        if not challenge_doc:
            raise HTTPException(status_code=400, detail="Aucun défi de récupération actif.")
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
        await db.webauthn_credentials.update_one(
            {"credential_id": raw_id},
            {"$set": {"sign_count": verification.new_sign_count}},
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        other_creators = await db.device_keys.find(
            {"role": "creator", "key_id": {"$ne": payload.key_id}},
            {"_id": 0, "key_id": 1, "label": 1},
        ).to_list(length=50)
        for d in other_creators:
            await db.device_keys.delete_one({"key_id": d["key_id"]})
            await db.device_nonces.delete_many({"key_id": d["key_id"]})
            await db.user_sessions.delete_many({"device_key_id": d["key_id"]})
            await log_decision("revoke", d["key_id"], payload.key_id, d.get("label"))
        await db.device_keys.update_one(
            {"key_id": payload.key_id},
            {"$set": {"role": "creator", "promoted_at": now_iso, "promoted_reason": "theft"}},
        )
        await log_decision("promote", payload.key_id, payload.key_id, dev.get("label"))
        return {"recovered": True, "revoked_count": len(other_creators)}

    @router.get("/webauthn/has-enrollment")
    async def webauthn_has_enrollment():
        count = await db.webauthn_credentials.count_documents({})
        return {"enrolled_count": count, "has_any": count > 0}

    return router
