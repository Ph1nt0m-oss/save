"""iter86 — Routes sociales (friends + groups + send-to-staff) extraites de
server.py en slices progressives du refacto.

iter85 slice 1 : extraction des helpers (GROUP_TYPES + _groups_for_device).
iter86 slice 2 : routes /api/friends/* déplacées (request, decide, list).

Approche : on définit un APIRouter local et une factory `build_friends_router(...)`
qui injecte les dépendances (db, verify_signed, device_by_key). server.py
appelle build_friends_router puis app.include_router(router, prefix='/api').
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


GROUP_TYPES = {
    "public", "private", "staff", "modo", "admin", "public_staff", "public_private",
}


def _groups_for_device(dev: Dict[str, Any]) -> List[str]:
    """Retourne la liste des groupes auxquels CE device a accès.

    iter86 — Ajout du groupe 'admin' (admin-only) + créa voit TOUT (y compris
    admin chat). Cohérence : staff = admin ∪ modo, donc admin a accès à
    staff + admin + public_staff. Modo a accès à staff + modo + public_staff.
    """
    role = dev.get("role")
    sk = dev.get("staff_kind")
    if role == "creator":
        return list(GROUP_TYPES)
    if role == "blocked":
        return []
    is_modo = sk == "modo"
    is_admin = sk == "admin"
    is_staff = is_modo or is_admin
    is_private = role == "approved" and not is_staff
    is_public = role in ("pending", "approved")
    out = []
    if is_public and not is_staff and not is_private:
        out.append("public")
        out.append("public_staff")
        out.append("public_private")
    if is_private:
        out.append("private")
        out.append("public_staff")
        out.append("public_private")
    if is_staff:
        out.append("staff")
        out.append("public_staff")
    if is_modo:
        out.append("modo")
    if is_admin:
        out.append("admin")
    return list(set(out))


class FriendRequestIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    target_key_id: str


class FriendDecideIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    request_id: str
    accept: bool


class FriendsListIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


def build_friends_router(db, verify_signed, device_by_key) -> APIRouter:
    """Construit un APIRouter pour les endpoints /friends/*. server.py
    importe et inclut via app.include_router(router, prefix='/api')."""
    router = APIRouter(tags=["Social"])

    @router.post("/friends/request")
    async def friends_request(payload: FriendRequestIn):
        sender = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        target = await device_by_key(payload.target_key_id)
        if not target:
            raise HTTPException(status_code=404, detail="Clé destinataire inconnue.")
        if payload.target_key_id == payload.key_id:
            raise HTTPException(status_code=400, detail="On ne se demande pas en ami soi-même.")

        existing = await db.friend_requests.find_one({
            "from_key_id": payload.key_id, "to_key_id": payload.target_key_id,
        })
        is_creator = sender.get("role") == "creator"
        status = "accepted" if is_creator else "pending"
        if existing:
            await db.friend_requests.update_one(
                {"from_key_id": payload.key_id, "to_key_id": payload.target_key_id},
                {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            return {"sent": True, "auto_accepted": is_creator}

        await db.friend_requests.insert_one({
            "request_id": f"fr_{uuid.uuid4().hex[:16]}",
            "from_key_id": payload.key_id,
            "from_pseudo": sender.get("pseudo") or sender.get("label"),
            "to_key_id": payload.target_key_id,
            "to_pseudo": target.get("pseudo") or target.get("label"),
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"sent": True, "auto_accepted": is_creator}

    @router.post("/friends/decide")
    async def friends_decide(payload: FriendDecideIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        req = await db.friend_requests.find_one({"request_id": payload.request_id}, {"_id": 0})
        if not req:
            raise HTTPException(status_code=404, detail="Demande introuvable.")
        if req.get("to_key_id") != payload.key_id and dev.get("role") != "creator":
            raise HTTPException(status_code=403, detail="Tu n'es pas le destinataire.")
        new_status = "accepted" if payload.accept else "refused"
        await db.friend_requests.update_one(
            {"request_id": payload.request_id},
            {"$set": {"status": new_status, "decided_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"status": new_status}

    @router.post("/friends/list")
    async def friends_list(payload: FriendsListIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        sent = await db.friend_requests.find(
            {"from_key_id": payload.key_id}, {"_id": 0},
        ).sort("created_at", -1).to_list(length=200)
        received = await db.friend_requests.find(
            {"to_key_id": payload.key_id}, {"_id": 0},
        ).sort("created_at", -1).to_list(length=200)
        return {"sent": sent, "received": received}

    return router
