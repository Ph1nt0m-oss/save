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
    # iter140 — Refonte : Public + Privé retiré, ajout de "users" (Utilisateurs
    # = compte non-approuvé mais valide, PAS lecture seule) + 4 nouveaux
    # groupes hybrides. Ordre logique : "users" entre privé et staff.
    "public", "private", "users", "staff", "modo", "admin",
    "public_staff", "private_staff", "users_staff", "users_private",
}


# iter140 — Ordre d'affichage imposé pour le front-end.
GROUP_TYPES_ORDER = [
    "public", "private", "users", "staff", "modo", "admin",
    "public_staff", "private_staff", "users_staff", "users_private",
]


def _groups_for_device(dev: Dict[str, Any]) -> List[str]:
    """iter86/140 — Retourne la liste des groupes auxquels ce device a accès.

    Règles iter140 :
      - Créa : voit TOUT.
      - Staff (admin ou modo) : staff + son propre groupe (modo/admin) +
        les 4 hybrides staff (public_staff, private_staff, users_staff).
      - Privé (approved non-staff) : private + users_private + public_staff +
        private_staff.
      - Utilisateurs (pending) : public + users + users_private +
        users_staff + public_staff.
      - Invité (rôle unknown / no account) : uniquement public (lecture seule
        gérée ailleurs).
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
    is_users = role == "pending"
    out: List[str] = []
    # Public : accessible à tous les rôles non bloqués.
    out.append("public")
    if is_staff:
        out.append("staff")
        out.append("public_staff")
        out.append("private_staff")
        out.append("users_staff")
    if is_admin:
        out.append("admin")
    if is_modo:
        out.append("modo")
    if is_private:
        out.append("private")
        out.append("public_staff")
        out.append("private_staff")
        out.append("users_private")
    if is_users:
        out.append("users")
        out.append("users_private")
        out.append("users_staff")
        out.append("public_staff")
    # Dédup préservant l'ordre.
    seen = set()
    ordered = []
    for g in out:
        if g not in seen:
            seen.add(g)
            ordered.append(g)
    return ordered


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


# ==========================================================================
# iter88 — Slice 3 du refacto : /groups/* extraits
# ==========================================================================

class GroupListIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class GroupMessagesIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    group_type: str
    limit: int = 200


class GroupSendIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    group_type: str
    content: str


def build_groups_router(db, verify_signed, max_message_len: int = 2000) -> APIRouter:
    """Construit un APIRouter pour /groups/list, /groups/messages, /groups/send."""
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    router = APIRouter(tags=["Social"])

    @router.post("/groups/list")
    async def groups_list(payload: GroupListIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        return {"groups": sorted(_groups_for_device(dev))}

    @router.post("/groups/messages")
    async def groups_messages(payload: GroupMessagesIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.group_type not in GROUP_TYPES:
            raise _HTTPException(status_code=400, detail="Type de groupe inconnu.")
        if payload.group_type not in _groups_for_device(dev):
            raise _HTTPException(status_code=403, detail="Tu n'as pas accès à ce groupe.")
        cursor = db.group_messages.find(
            {"group_type": payload.group_type}, {"_id": 0},
        ).sort("ts", -1).limit(max(1, min(payload.limit, 500)))
        rows = await cursor.to_list(length=500)
        return {"messages": list(reversed(rows))}

    @router.post("/groups/send")
    async def groups_send(payload: GroupSendIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.group_type not in GROUP_TYPES:
            raise _HTTPException(status_code=400, detail="Type de groupe inconnu.")
        if payload.group_type not in _groups_for_device(dev):
            raise _HTTPException(status_code=403, detail="Tu n'as pas accès à ce groupe.")
        content = (payload.content or "").strip()
        if not content:
            raise _HTTPException(status_code=400, detail="Message vide.")
        if len(content) > max_message_len:
            raise _HTTPException(status_code=400, detail=f"Message trop long ({max_message_len} max).")
        now = datetime.now(timezone.utc)
        doc = {
            "message_id": f"gm_{_uuid.uuid4().hex[:16]}",
            "group_type": payload.group_type,
            "from_key_id": payload.key_id,
            "from_pseudo": dev.get("pseudo") or dev.get("label"),
            "from_role": dev.get("role"),
            "from_staff_kind": dev.get("staff_kind"),
            "content": content,
            "ts": now.isoformat(),
        }
        await db.group_messages.insert_one(doc)
        return {"sent": True, "message_id": doc["message_id"], "ts": doc["ts"]}

    return router