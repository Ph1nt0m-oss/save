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
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils import bot_analyzer


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


def _groups_for_device(dev: Dict[str, Any], view_mode: Optional[str] = None) -> List[str]:
    """iter86/140/141 — Retourne la liste des groupes auxquels ce device a accès.

    Règles précises (iter141, matrice utilisateur) :
      - Créa RÉELLE (view_mode == None ou 'creator') : voit TOUT.
      - Créa SIMULÉE (view_mode != creator/None) : la simulation applique
        les règles du rôle simulé (user/modo/admin/guest).
      - Admin : public, staff, admin, modo, public_staff, private_staff,
        users_staff.
      - Modo : public, modo, public_staff, private_staff, users_staff
        (PAS le groupe 'staff' général, PAS 'admin').
      - Privé (approved non-staff) : public, private, users_private,
        public_staff, private_staff.
      - Utilisateurs (pending) : public, users, users_staff, users_private.
      - Invité (guest / unknown / no account) : public uniquement.
    """
    role = dev.get("role")
    sk = dev.get("staff_kind")
    if role == "blocked":
        return []
    # Créa réelle → tout.
    if role == "creator" and view_mode in (None, "", "creator"):
        return list(GROUP_TYPES)
    # Créa en simulation → on résout le rôle effectif via view_mode.
    if role == "creator" and view_mode:
        vm = view_mode.lower()
        if vm == "admin":
            # iter142 — Admin ne voit PAS le tchat 'modo' (privé aux modos).
            return ["public", "staff", "admin",
                    "public_staff", "private_staff", "users_staff"]
        if vm == "modo":
            return ["public", "modo",
                    "public_staff", "private_staff", "users_staff"]
        if vm == "user":
            return ["public", "users", "users_staff", "users_private"]
        if vm == "guest":
            # iter142 — Invité voit aussi 'public_staff' (mais l'historique
            # est bloqué au niveau du rendu par view_mode==guest côté back).
            return ["public", "public_staff"]
        # creator ou inconnu → tout.
        return list(GROUP_TYPES)
    # Non-créa : on suit le rôle réel.
    is_modo = sk == "modo"
    is_admin = sk == "admin"
    is_private = role == "approved" and not (is_modo or is_admin)
    is_users = role == "pending"
    if is_admin:
        # iter142 — Admin ne voit PAS 'modo' (chat privé des modos).
        return ["public", "staff", "admin",
                "public_staff", "private_staff", "users_staff"]
    if is_modo:
        return ["public", "modo",
                "public_staff", "private_staff", "users_staff"]
    if is_private:
        return ["public", "private", "users_private",
                "public_staff", "private_staff"]
    if is_users:
        return ["public", "users", "users_staff", "users_private"]
    # guest / inconnu : public + public_staff (historique bloqué au render).
    return ["public", "public_staff"]


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
    view_mode: Optional[str] = None  # iter141 — Créa simule un rôle


class GroupMessagesIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    group_type: str
    limit: int = 200
    view_mode: Optional[str] = None  # iter141


class GroupSendIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    group_type: str
    content: str
    view_mode: Optional[str] = None  # iter141


def build_groups_router(db, verify_signed, max_message_len: int = 2000) -> APIRouter:
    """Construit un APIRouter pour /groups/list, /groups/messages, /groups/send."""
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    router = APIRouter(tags=["Social"])

    async def _sun_mode_active(key_id: str) -> bool:
        """iter141/iter142 — True si le staff (modo/admin/créa) a activé le
        mode Soleil : il voit à travers l'anonymat des autres."""
        row = await db.social_prefs.find_one({"key_id": key_id}, {"_id": 0, "sun_mode": 1}) or {}
        return bool(row.get("sun_mode"))

    async def _is_anonymous(target_key_id: str) -> bool:
        row = await db.social_prefs.find_one({"key_id": target_key_id}, {"_id": 0, "anonymous": 1}) or {}
        return bool(row.get("anonymous"))

    async def _sender_is_creator(target_key_id: str) -> bool:
        d = await db.device_keys.find_one({"key_id": target_key_id}, {"_id": 0, "role": 1}) or {}
        return d.get("role") == "creator"

    async def _render_sender(msg: dict, caller_dev: dict) -> dict:
        """iter141/iter142 — Masque pseudo/rôle/couleur si l'expéditeur est en
        mode Anonyme. Le staff en Sun mode révèle. EXCEPTION iter142 : si
        l'expéditeur est la Créa en anonyme, son identité N'EST JAMAIS
        révélée, même à un staff en Sun mode (protection absolue Créa)."""
        out = dict(msg)
        sender_key = msg.get("from_key_id")
        if not sender_key or sender_key == caller_dev.get("key_id"):
            return out
        anon = await _is_anonymous(sender_key)
        if not anon:
            return out
        # Anonyme : décider si on révèle (staff en Sun mode) ou on masque.
        caller_is_staff = (
            caller_dev.get("role") == "creator"
            or caller_dev.get("staff_kind") in ("admin", "modo")
        )
        # iter142 — Protection Créa : si l'expéditeur est la Créa en anonyme,
        # son identité N'EST JAMAIS révélée (elle reste au-dessus du système
        # de bots et Sun mode).
        if await _sender_is_creator(sender_key):
            out["from_pseudo"] = "Anonyme"
            out["from_public_handle"] = ""
            out["from_role"] = "anon"
            out["from_staff_kind"] = None
            return out
        if caller_is_staff and await _sun_mode_active(caller_dev.get("key_id")):
            # Sun mode : révèle tout.
            out["_revealed_from_anonymous"] = True
            return out
        # Masqué.
        out["from_pseudo"] = "Anonyme"
        out["from_public_handle"] = ""
        out["from_role"] = "anon"
        out["from_staff_kind"] = None
        return out

    @router.post("/groups/list")
    async def groups_list(payload: GroupListIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        return {"groups": sorted(_groups_for_device(dev, view_mode=payload.view_mode))}

    @router.post("/groups/messages")
    async def groups_messages(payload: GroupMessagesIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.group_type not in GROUP_TYPES:
            raise _HTTPException(status_code=400, detail="Type de groupe inconnu.")
        allowed = _groups_for_device(dev, view_mode=payload.view_mode)
        if payload.group_type not in allowed:
            raise _HTTPException(status_code=403, detail="Tu n'as pas accès à ce groupe.")
        # iter142 — Invité (guest, ou Créa en simulation guest) : accès au
        # groupe accordé mais historique bloqué. Idem pour toute simulation.
        effective_vm = (payload.view_mode or "").lower()
        is_guest_effective = (
            dev.get("role") in ("guest", "unknown", None)
            or effective_vm == "guest"
        )
        if is_guest_effective and payload.group_type == "public_staff":
            return {"messages": []}
        cursor = db.group_messages.find(
            {"group_type": payload.group_type}, {"_id": 0},
        ).sort("ts", -1).limit(max(1, min(payload.limit, 500)))
        rows = await cursor.to_list(length=500)
        rows_ordered = list(reversed(rows))
        # iter141 — Anonymat : masque le pseudo/couleur si l'expéditeur est
        # anonyme, sauf pour un staff en mode Soleil.
        rendered = [await _render_sender(m, dev) for m in rows_ordered]
        return {"messages": rendered}

    @router.post("/groups/send")
    async def groups_send(payload: GroupSendIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.group_type not in GROUP_TYPES:
            raise _HTTPException(status_code=400, detail="Type de groupe inconnu.")
        allowed = _groups_for_device(dev, view_mode=payload.view_mode)
        if payload.group_type not in allowed:
            raise _HTTPException(status_code=403, detail="Tu n'as pas accès à ce groupe.")
        content = (payload.content or "").strip()
        if not content:
            raise _HTTPException(status_code=400, detail="Message vide.")
        if len(content) > max_message_len:
            raise _HTTPException(status_code=400, detail=f"Message trop long ({max_message_len} max).")
        now = datetime.now(timezone.utc)
        # iter141 — Lookup public_handle depuis users (mirror via email lookup)
        # ou depuis device_keys si déjà mirroré.
        public_handle = dev.get("public_handle") or ""
        if not public_handle:
            u = await db.users.find_one({"pseudo": dev.get("pseudo")}, {"_id": 0, "public_handle": 1}) if dev.get("pseudo") else None
            public_handle = (u or {}).get("public_handle", "") if u else ""
        doc = {
            "message_id": f"gm_{_uuid.uuid4().hex[:16]}",
            "group_type": payload.group_type,
            "from_key_id": payload.key_id,
            "from_pseudo": dev.get("pseudo") or dev.get("label"),
            "from_public_handle": public_handle,
            "from_role": dev.get("role"),
            "from_staff_kind": dev.get("staff_kind"),
            "content": content,
            "ts": now.isoformat(),
        }
        await db.group_messages.insert_one(doc)
        # iter142 Batch 3 — Analyse locale du message par les bots.
        # Si suspicion → marque le groupe, notifie les membres du groupe
        # (via un événement bot), autorise le staff à activer Sun Mode.
        try:
            analysis = bot_analyzer.analyze_message(
                group_type=payload.group_type,
                key_id=payload.key_id,
                content=content,
            )
            if analysis.get("suspicion"):
                await bot_analyzer.mark_group_suspicion(
                    db, group_type=payload.group_type,
                    analysis=analysis, sender_key_id=payload.key_id,
                )
                # Injecte un "message système" du bot dans le groupe si
                # aucun staff n'y est présent (héritage règle utilisateur).
                staff_present = await db.device_keys.count_documents({
                    "$or": [
                        {"role": "creator"},
                        {"staff_kind": {"$in": ["admin", "modo"]}},
                    ],
                    "last_seen_at": {"$exists": True},
                }, limit=1)
                if not staff_present:
                    await db.group_messages.insert_one({
                        "message_id": f"gm_bot_{_uuid.uuid4().hex[:12]}",
                        "group_type": payload.group_type,
                        "from_key_id": "bot_moderator",
                        "from_pseudo": "Modérateur automatique",
                        "from_public_handle": "moderation_bot",
                        "from_role": "bot",
                        "from_staff_kind": None,
                        "content": (
                            "⚠ Surveillance déclenchée par le système. "
                            "Un membre du staff va être notifié pour "
                            "examiner la conversation."
                        ),
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
        except Exception:
            # Non-critical: bot analysis errors never block message send.
            pass
        return {"sent": True, "message_id": doc["message_id"], "ts": doc["ts"]}

    # iter141 — Liste des membres du groupe (pour l'UI listing).
    class GroupMembersIn(BaseModel):
        key_id: str
        nonce: str
        signature: str
        group_type: str
        view_mode: Optional[str] = None

    @router.post("/groups/members")
    async def groups_members(payload: GroupMembersIn):
        """iter141 — Retourne la liste des membres visibles d'un groupe.

        Règle spéciale Créa (iter141) :
          - Le Créateur est INVISIBLE dans les listes de tous les groupes
            SAUF 'staff'.
          - EXCEPTION : les Admins voient TOUJOURS le Créateur dans les
            listes (pour ne pas éveiller les soupçons).
          - Le Créateur se voit toujours lui-même.
        """
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.group_type not in GROUP_TYPES:
            raise _HTTPException(status_code=400, detail="Type de groupe inconnu.")
        allowed = _groups_for_device(dev, view_mode=payload.view_mode)
        if payload.group_type not in allowed:
            raise _HTTPException(status_code=403, detail="Tu n'as pas accès à ce groupe.")
        # On liste les devices dont l'accès inclut ce groupe.
        cursor = db.device_keys.find(
            {"role": {"$nin": ["blocked", "inactive"]}},
            {"_id": 0, "key_id": 1, "pseudo": 1, "label": 1, "role": 1,
             "staff_kind": 1, "public_handle": 1, "deleted": 1},
        )
        rows = await cursor.to_list(length=1000)
        caller_is_admin = dev.get("staff_kind") == "admin"
        caller_is_creator = dev.get("role") == "creator"
        me_key = dev.get("key_id")
        members: List[Dict[str, Any]] = []
        # Précharge état invisible + anonymat via 1 query.
        invisible_rows = await db.invisible_flags.find(
            {"group_type": payload.group_type, "enabled": True},
            {"_id": 0, "key_id": 1},
        ).to_list(length=500)
        invisible_set = {r["key_id"] for r in invisible_rows}
        anon_rows = await db.social_prefs.find(
            {"anonymous": True}, {"_id": 0, "key_id": 1},
        ).to_list(length=1000)
        anon_set = {r["key_id"] for r in anon_rows}
        sun_active = await _sun_mode_active(me_key) if (caller_is_creator or dev.get("staff_kind") in ("admin", "modo")) else False
        for r in rows:
            if r.get("deleted"):
                continue
            if r["key_id"] not in [me_key]:  # skip filter for self
                # Filtre : ce membre a-t-il accès à ce groupe ?
                target_allowed = _groups_for_device(r, view_mode=None)
                if payload.group_type not in target_allowed:
                    continue
                # Mode invisible admin/créa : masqué sauf pour soi-même.
                if r["key_id"] in invisible_set:
                    continue
                # Règle iter141 — Créa invisible dans TOUS les groupes
                # SAUF 'staff'. Exception : les Admins voient toujours.
                if r.get("role") == "creator" and payload.group_type != "staff":
                    if not caller_is_admin:
                        continue
            # Anonymat : masque pseudo/handle/rôle sauf pour soi ou Sun mode.
            entry = {
                "key_id": r["key_id"],
                "pseudo": r.get("pseudo") or r.get("label") or "",
                "public_handle": r.get("public_handle") or "",
                "role": r.get("role"),
                "staff_kind": r.get("staff_kind"),
            }
            if r["key_id"] != me_key and r["key_id"] in anon_set and not sun_active:
                entry["pseudo"] = "Anonyme"
                entry["public_handle"] = ""
                entry["role"] = "anon"
                entry["staff_kind"] = None
                entry["anonymous"] = True
            members.append(entry)
        return {"members": members}

    return router