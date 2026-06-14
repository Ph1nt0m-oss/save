"""iter121 — Routes /site/issues/* extraites de server.py (3 endpoints).

  - POST /site/issues/create  (créa/admin)
  - GET  /site/issues          (lecture publique, filtrable par status)
  - POST /site/issues/update   (créa/admin)

Helpers injectés : verify_signed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class SiteIssueIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    title: str
    description: Optional[str] = ""
    severity: Optional[str] = "medium"  # low | medium | high | critical
    status: Optional[str] = "open"      # open | in_progress | resolved | wontfix


class SiteIssueUpdateIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    issue_id: str
    status: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None


def build_site_issues_router(db, *, verify_signed):
    router = APIRouter()

    @router.post("/site/issues/create")
    async def site_issues_create(payload: SiteIssueIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role")
        sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="Titre requis.")
        issue_id = f"iss_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "issue_id": issue_id,
            "title": payload.title.strip()[:200],
            "description": (payload.description or "").strip()[:5000],
            "severity": payload.severity if payload.severity in ("low", "medium", "high", "critical") else "medium",
            "status": payload.status if payload.status in ("open", "in_progress", "resolved", "wontfix") else "open",
            "created_at": now,
            "updated_at": now,
            "created_by_key": payload.key_id,
        }
        await db.site_issues.insert_one(doc)
        return {"success": True, "issue_id": issue_id}

    @router.get("/site/issues")
    async def site_issues_list(status: Optional[str] = None, limit: int = 100):
        q = {}
        if status:
            q["status"] = status
        rows = (
            await db.site_issues.find(q, {"_id": 0, "created_by_key": 0})
            .sort("created_at", -1)
            .to_list(length=min(limit, 500))
        )
        return {"issues": rows, "total": len(rows)}

    @router.post("/site/issues/update")
    async def site_issues_update(payload: SiteIssueUpdateIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role")
        sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.status and payload.status in ("open", "in_progress", "resolved", "wontfix"):
            updates["status"] = payload.status
        if payload.severity and payload.severity in ("low", "medium", "high", "critical"):
            updates["severity"] = payload.severity
        if payload.description is not None:
            updates["description"] = payload.description.strip()[:5000]
        res = await db.site_issues.update_one({"issue_id": payload.issue_id}, {"$set": updates})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Issue introuvable.")
        return {"success": True}

    return router
