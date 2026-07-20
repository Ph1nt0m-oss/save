"""iter150 — Compteurs de messages non lus par conversation.

Chaque device stocke un last_read_ts par salon (`group_type`) et par DM
thread (`dm_thread_id`). Endpoints signés ECDSA :
  - POST /api/social/unread-counts     → dict complet
  - POST /api/social/mark-read         → marque une conversation comme lue

Format des compteurs :
  {
    "groups": { "public": 3, "modo": 0, ... },
    "dms":    { "<thread_id>": 5, ... }
  }

Stockage MongoDB :
  db.conversation_read_state :
    { key_id, scope: 'group'|'dm', conv_id: group_type|thread_id, last_read_ts }

`last_read_ts` = ISO datetime UTC du dernier message lu.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class _Signed(BaseModel):
    key_id: str
    nonce: str
    signature: str


class MarkReadIn(_Signed):
    scope: str  # 'group' | 'dm'
    conv_id: str
    at_ts: Optional[str] = None  # ISO ; défaut = maintenant


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_unread_router(db, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Unread"])

    @router.post("/social/unread-counts")
    async def unread_counts(payload: _Signed):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        # 1) Lit tous les states de lecture du device.
        rows = await db.conversation_read_state.find(
            {"key_id": payload.key_id}, {"_id": 0}
        ).to_list(length=500)
        last_by_group: Dict[str, str] = {}
        last_by_dm: Dict[str, str] = {}
        for r in rows:
            if r.get("scope") == "group":
                last_by_group[r["conv_id"]] = r.get("last_read_ts", "")
            elif r.get("scope") == "dm":
                last_by_dm[r["conv_id"]] = r.get("last_read_ts", "")
        # 2) Compte les messages postés APRES last_read_ts pour chaque groupe.
        groups: Dict[str, int] = {}
        # On énumère les groupes présents en DB — puis compte via aggregation.
        group_names = await db.group_messages.distinct("group_type")
        for gname in group_names:
            q: Dict[str, Any] = {
                "group_type": gname,
                # Ne compte pas les messages écrits par l'appareil lui-même.
                "key_id": {"$ne": payload.key_id},
            }
            cutoff = last_by_group.get(gname)
            if cutoff:
                q["ts"] = {"$gt": cutoff}
            n = await db.group_messages.count_documents(q)
            if n > 0:
                groups[gname] = int(n)
        # 3) DMs (collection direct_messages, thread_id partagé pour 2 clefs).
        dms: Dict[str, int] = {}
        if hasattr(db, "direct_messages"):
            # thread_ids où ce device participe.
            threads = await db.direct_messages.distinct(
                "thread_id",
                {"$or": [{"from_key_id": payload.key_id}, {"to_key_id": payload.key_id}]},
            )
            for tid in threads:
                q2: Dict[str, Any] = {
                    "thread_id": tid,
                    "to_key_id": payload.key_id,  # messages reçus uniquement
                }
                cutoff = last_by_dm.get(tid)
                if cutoff:
                    q2["ts"] = {"$gt": cutoff}
                n = await db.direct_messages.count_documents(q2)
                if n > 0:
                    dms[tid] = int(n)
        total = sum(groups.values()) + sum(dms.values())
        return {"groups": groups, "dms": dms, "total": int(total)}

    @router.post("/social/mark-read")
    async def mark_read(payload: MarkReadIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        scope = payload.scope
        if scope not in ("group", "dm"):
            raise HTTPException(status_code=400, detail="scope invalide")
        conv_id = (payload.conv_id or "").strip()
        if not conv_id:
            raise HTTPException(status_code=400, detail="conv_id requis")
        ts = payload.at_ts or _now_iso()
        await db.conversation_read_state.update_one(
            {"key_id": payload.key_id, "scope": scope, "conv_id": conv_id},
            {"$set": {"last_read_ts": ts, "updated_at": _now_iso()}},
            upsert=True,
        )
        return {"ok": True, "scope": scope, "conv_id": conv_id, "last_read_ts": ts}

    return router
