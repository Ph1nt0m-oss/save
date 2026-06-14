"""iter117 — Routes /system/* extraites de server.py.

4 endpoints :
  - GET /system/ollama-status (public — health check Ollama)
  - POST /system/schedule-kick (créa)
  - GET  /system/scheduled-kicks (public list)
  - POST /system/cancel-scheduled-kick (créa)

Les endpoints /system/site-mode restent dans server.py (intégration trop
profonde avec _get_site_mode + cache + invalidation pour cette session).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict


class ScheduleKickIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    minutes: int = 5
    note: str = ""
    audience: Any = "all"


class _CreatorSigIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


def build_system_router(db, *, require_creator_signature, valid_audience_groups):
    router = APIRouter()

    @router.get("/system/ollama-status")
    async def ollama_status():
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

    @router.post("/system/schedule-kick")
    async def system_schedule_kick(payload: ScheduleKickIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        try:
            delay = max(0, min(int(payload.minutes or 0), 24 * 60))
        except Exception:
            delay = 5
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        raw_aud = body.get("audience")
        aud = raw_aud if isinstance(raw_aud, list) else [raw_aud or "all"]
        if "staff" in aud:
            aud = [g for g in aud if g != "staff"] + ["admin", "modo"]
        aud = [g for g in aud if g in valid_audience_groups] or ["all"]
        now = datetime.now(timezone.utc)
        execute_at = (now + timedelta(minutes=delay)).isoformat()
        sk_id = f"sk_{uuid.uuid4().hex[:12]}"
        await db.scheduled_kicks.insert_one({
            "kick_id": sk_id,
            "creator_key_id": payload.key_id,
            "minutes": delay,
            "audience": aud,
            "execute_at": execute_at,
            "executed": False,
            "ts": now.isoformat(),
        })
        if (payload.note or "").strip():
            await db.announcements.insert_one({
                "announce_id": f"ann_{uuid.uuid4().hex[:12]}",
                "title": (payload.note.strip())[:200],
                "body": "",
                "audience": aud,
                "ts": now.isoformat(),
                "from_scheduled_kick": sk_id,
            })
        return {"success": True, "kick_id": sk_id, "execute_at": execute_at, "audience": aud}

    @router.get("/system/scheduled-kicks")
    async def system_scheduled_kicks_list(key_id: Optional[str] = None):
        rows = await db.scheduled_kicks.find(
            {"executed": False}, {"_id": 0},
        ).sort("execute_at", 1).to_list(length=50)
        return {"scheduled_kicks": rows}

    @router.post("/system/cancel-scheduled-kick")
    async def system_cancel_scheduled_kick(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        kid = body.get("kick_id")
        if not kid:
            raise HTTPException(status_code=400, detail="kick_id requis.")
        await db.scheduled_kicks.update_one(
            {"kick_id": kid}, {"$set": {"executed": True, "cancelled": True}},
        )
        return {"success": True}

    return router
