"""iter118 — Routes /ideas/* extraites de server.py.

7 endpoints (feedback/idées/bugs envoyés à la créatrice) :
  - /ideas/send (public — anonyme ou signé)
  - /ideas/mine (signé — items envoyés par ce device)
  - /ideas/inbox (créa + admin + modo)
  - /ideas/clear (créa — vide tout/résolus/non-résolus)
  - /ideas/mark-read (créa + admin + modo)
  - /ideas/delete (créa — supprime une idée)
  - /ideas/set-state (créa + admin + modo — validé/refusé/orange/reset)
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from models.auth_signatures import CreatorSigIn as _CreatorSigIn, SignedIn


class IdeasSendIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: Optional[str] = None
    nonce: Optional[str] = None
    signature: Optional[str] = None
    content: str = ""
    kind: str = "idea"


class IdeasClearIn(_CreatorSigIn):
    scope: str
    password: Optional[str] = None


class IdeaSetStateIn(SignedIn):
    idea_id: str
    state: str


def _idea_is_resolved(idea: Dict[str, Any]) -> bool:
    return idea.get("state") == "validated"


def build_ideas_router(db, *, verify_signed, require_creator_signature):
    router = APIRouter()

    @router.post("/ideas/send")
    async def ideas_send(request: Request, payload: IdeasSendIn):
        sender_label = "Anonyme"
        sender_key_id = None
        sender_email = None
        if payload.key_id and payload.nonce and payload.signature:
            try:
                dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
                sender_label = dev.get("pseudo") or dev.get("label") or payload.key_id[:14]
                sender_key_id = payload.key_id
                sender_email = dev.get("email")
            except HTTPException:
                pass
        content = (payload.content or "").strip()
        kind = payload.kind if payload.kind in ("idea", "bug", "report", "other") else "idea"
        ip = request.client.host if request and request.client else None
        await db.ideas.insert_one({
            "idea_id": f"idea_{uuid.uuid4().hex[:14]}",
            "sender_key_id": sender_key_id,
            "sender_label": sender_label,
            "sender_email": sender_email,
            "sender_ip_hash": hashlib.sha256((ip or "").encode()).hexdigest()[:16] if ip else None,
            "kind": kind,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
            "read": False,
            "page": getattr(payload, "page", None) or "/",
        })
        return {"success": True}

    @router.post("/ideas/mine")
    async def ideas_mine(payload: _CreatorSigIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        rows = await db.ideas.find({"sender_key_id": payload.key_id}, {"_id": 0}).sort("ts", -1).to_list(length=500)
        return {"ideas": rows}

    @router.post("/ideas/inbox")
    async def ideas_inbox(payload: _CreatorSigIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if role != "creator" and sk not in ("admin", "modo"):
            raise HTTPException(status_code=403, detail="Réservé staff (admin/modo) et créatrice.")
        rows = await db.ideas.find({}, {"_id": 0}).sort("ts", -1).to_list(length=500)
        return {"ideas": rows}

    @router.post("/ideas/clear")
    async def ideas_clear(payload: IdeasClearIn):
        dev = await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        scope = payload.scope
        if scope not in ("all", "resolved", "unresolved"):
            raise HTTPException(status_code=400, detail="scope invalide.")
        rows = await db.ideas.find({}, {"_id": 0}).to_list(length=2000)
        unresolved_ids = [i["idea_id"] for i in rows if not _idea_is_resolved(i)]
        resolved_ids = [i["idea_id"] for i in rows if _idea_is_resolved(i)]
        if scope in ("all", "unresolved") and unresolved_ids:
            if not payload.password:
                raise HTTPException(status_code=428, detail="Mot de passe requis pour effacer des retours non-traités.")
            user = await db.users.find_one({"email": dev.get("email")}, {"_id": 0, "password_hash": 1})
            if not user or not user.get("password_hash"):
                raise HTTPException(status_code=412,
                    detail="Ton compte n'a pas de mot de passe configuré. Crée-en un dans Profil → Sécurité avant d'utiliser cette action.")
            try:
                ok = bcrypt.checkpw(payload.password.encode("utf-8"), user["password_hash"].encode("utf-8"))
            except Exception:
                ok = False
            if not ok:
                raise HTTPException(status_code=403, detail="Mot de passe incorrect. Veuillez réessayer.")
        if scope == "all":
            await db.ideas.delete_many({})
            deleted = len(rows)
        elif scope == "resolved":
            await db.ideas.delete_many({"idea_id": {"$in": resolved_ids}})
            deleted = len(resolved_ids)
        else:
            await db.ideas.delete_many({"idea_id": {"$in": unresolved_ids}})
            deleted = len(unresolved_ids)
        return {"success": True, "deleted": deleted, "scope": scope}

    @router.post("/ideas/mark-read")
    async def ideas_mark_read(payload: _CreatorSigIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if role != "creator" and sk not in ("admin", "modo"):
            raise HTTPException(status_code=403, detail="Réservé staff (admin/modo) et créatrice.")
        await db.ideas.update_many({"read": False}, {"$set": {"read": True}})
        return {"success": True}

    @router.post("/ideas/delete")
    async def ideas_delete(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        idea_id = body.get("idea_id")
        if not idea_id:
            raise HTTPException(status_code=400, detail="idea_id requis.")
        await db.ideas.delete_one({"idea_id": idea_id})
        return {"success": True}

    @router.post("/ideas/set-state")
    async def ideas_set_state(payload: IdeaSetStateIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if role != "creator" and sk not in ("admin", "modo"):
            raise HTTPException(status_code=403, detail="Réservé au staff (admin/modo) et créatrice.")
        if payload.state not in ("validated", "refused", "orange", "reset"):
            raise HTTPException(status_code=400, detail="État invalide.")
        if payload.state == "reset":
            await db.ideas.update_one(
                {"idea_id": payload.idea_id},
                {"$unset": {"state": "", "state_by": "", "state_at": ""}},
            )
        else:
            await db.ideas.update_one(
                {"idea_id": payload.idea_id},
                {"$set": {
                    "state": payload.state,
                    "state_by": payload.key_id,
                    "state_actor": "creator" if role == "creator" else sk,
                    "state_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        return {"success": True}

    return router
