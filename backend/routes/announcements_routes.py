"""iter91 — Refacto slice 4a : routes /announcements/* extraites de server.py.

Comme social_routes.py, on définit une factory `build_announcements_router(...)`
qui injecte les dépendances (db, verify_signed, require_creator_signature,
audience_matches). server.py appelle build_announcements_router puis
app.include_router(router, prefix='/api').
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict


VALID_AUDIENCE_GROUPS = {"all", "approved", "creator", "admin", "modo", "pending", "non_validated"}


class AnnounceCreateIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    title: str
    body: str = ""
    audience: Any = "all"


class AnnounceEditIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    announce_id: str
    title: Optional[str] = None
    body: Optional[str] = None
    audience: Any = None


class AnnStateIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    announce_id: str
    state: str  # validated / refused / orange / reset


class _CreatorSigIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


class _AnnounceDeleteIn(_CreatorSigIn):
    announce_id: str


def build_announcements_router(
    db,
    verify_signed,
    require_creator_signature,
    audience_matches,
):
    """Construct an APIRouter with /announcements/* routes wired to injected deps."""
    router = APIRouter()

    @router.post("/announcements/create")
    async def announcements_create(payload: AnnounceCreateIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="Titre requis.")
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        raw_aud = body.get("audience")
        audience = raw_aud if isinstance(raw_aud, list) else [raw_aud or "all"]
        audience = [g for g in audience if g in VALID_AUDIENCE_GROUPS] or ["all"]
        doc = {
            "announce_id": f"ann_{uuid.uuid4().hex[:12]}",
            "title": payload.title.strip()[:200],
            "body": (payload.body or "").strip()[:5000],
            "audience": audience,
            "ts": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        await db.announcements.insert_one(doc)
        return {"success": True, "announce_id": doc["announce_id"]}

    @router.get("/announcements/list")
    async def announcements_list(key_id: Optional[str] = None):
        rows = await db.announcements.find({}, {"_id": 0}).sort("ts", -1).to_list(length=50)
        dev = None
        role = "public"
        if key_id:
            dev = await db.device_keys.find_one(
                {"key_id": key_id},
                {"_id": 0, "role": 1, "staff_kind": 1},
            )
            role = (dev or {}).get("role") or "public"
        filtered = []
        for r in rows:
            if not audience_matches(r.get("audience"), dev):
                continue
            my_state = None
            if key_id:
                ms = await db.announcement_states.find_one(
                    {"announce_id": r["announce_id"], "key_id": key_id},
                    {"_id": 0, "state": 1, "actor": 1, "ts": 1},
                )
                if ms:
                    my_state = ms.get("state")
            if role == "creator":
                states = await db.announcement_states.find(
                    {"announce_id": r["announce_id"], "key_id": {"$ne": key_id}},
                    {"_id": 0, "key_id": 1, "state": 1, "actor": 1, "ts": 1},
                ).to_list(length=200)
                r["staff_states"] = states
            r["my_state"] = my_state
            if role != "creator" and my_state == "validated":
                continue
            filtered.append(r)
        return {"announcements": filtered}

    @router.post("/announcements/edit")
    async def announcements_edit(payload: AnnounceEditIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        upd: Dict[str, Any] = {}
        if body.get("title") is not None:
            title = (body.get("title") or "").strip()
            if not title:
                raise HTTPException(status_code=400, detail="Titre requis.")
            upd["title"] = title[:200]
        if body.get("body") is not None:
            upd["body"] = (body.get("body") or "").strip()[:5000]
        if body.get("audience") is not None:
            raw_aud = body.get("audience")
            aud = raw_aud if isinstance(raw_aud, list) else [raw_aud]
            aud = [g for g in aud if g in VALID_AUDIENCE_GROUPS] or ["all"]
            upd["audience"] = aud
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = await db.announcements.update_one({"announce_id": payload.announce_id}, {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Annonce introuvable.")
        await db.announcement_states.delete_many({"announce_id": payload.announce_id})
        return {"success": True, "updated_at": upd["updated_at"]}

    @router.post("/announcements/delete")
    async def announcements_delete(payload: _AnnounceDeleteIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        if not payload.announce_id:
            raise HTTPException(status_code=400, detail="announce_id requis.")
        await db.announcements.delete_one({"announce_id": payload.announce_id})
        return {"success": True}

    @router.post("/announcements/set-state")
    async def announcements_set_state(payload: AnnStateIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        state = (payload.state or "").strip().lower()
        if state not in ("validated", "refused", "orange", "reset"):
            raise HTTPException(status_code=400, detail="État invalide.")
        ann = await db.announcements.find_one({"announce_id": payload.announce_id}, {"_id": 0, "announce_id": 1})
        if not ann:
            raise HTTPException(status_code=404, detail="Annonce introuvable.")
        role = dev.get("role") or "public"
        actor = "creator" if role == "creator" else ("staff" if role == "approved" else "user")

        if state == "reset":
            if role == "creator":
                await db.announcement_states.delete_many({"announce_id": payload.announce_id})
            else:
                await db.announcement_states.delete_one({"announce_id": payload.announce_id, "key_id": payload.key_id})
            return {"success": True, "reset": True}

        await db.announcement_states.update_one(
            {"announce_id": payload.announce_id, "key_id": payload.key_id},
            {"$set": {
                "announce_id": payload.announce_id,
                "key_id": payload.key_id,
                "state": state,
                "actor": actor,
                "ts": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"success": True, "state": state, "actor": actor}

    @router.post("/announcements/clear-history")
    async def announcements_clear_history(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        res_ann = await db.announcements.delete_many({})
        res_st = await db.announcement_states.delete_many({})
        return {"success": True, "deleted_announcements": res_ann.deleted_count, "deleted_states": res_st.deleted_count}

    return router
