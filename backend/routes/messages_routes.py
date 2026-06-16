"""iter94 — Refacto slice 4c : routes /messages/* extraites de server.py.

Factory pattern `build_messages_router(...)` qui injecte toutes les dépendances
nécessaires (db, helpers, constantes). server.py inclut le router via
`app.include_router(..., prefix='/api')` après définition des helpers.
"""
from __future__ import annotations

import uuid
import random
from datetime import datetime, timezone
from typing import Any, Optional, Callable, Awaitable

from fastapi import APIRouter, HTTPException

from models.auth_signatures import SignedIn


class MessageSendIn(SignedIn):
    content: str
    target_key_id: Optional[str] = None
    # iter128.5 — Persona override créa-only. Le backend valide via la
    # signature ECDSA que l'appelant est bien la créatrice avant
    # d'appliquer les overrides ; ignoré pour tout autre rôle.
    persona_override: Optional[dict] = None  # {id, customPseudo, customAvatar, aiReplies, visible}


class MessagesInboxIn(SignedIn):
    pass


class MessagesThreadIn(SignedIn):
    thread_key_id: Optional[str] = None


class MessagesDeleteIn(SignedIn):
    thread_key_id: str


class MessagesRenameIn(SignedIn):
    thread_key_id: str
    new_label: str


class MessageToStaffIn(SignedIn):
    content: str


def build_messages_router(
    db,
    *,
    device_by_key: Callable[[str], Awaitable[Optional[dict]]],
    consume_nonce: Callable[[str, str], Awaitable[bool]],
    verify_signature: Callable[[dict, str, str], bool],
    verify_signed: Callable[[str, str, str], Awaitable[dict]],
    require_creator_signature: Callable[[str, str, str], Awaitable[Any]],
    max_message_len: int,
    message_cooldown_seconds: int,
):
    router = APIRouter()

    @router.post("/messages/send")
    async def messages_send(payload: MessageSendIn):
        content = (payload.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="Message vide.")
        if len(content) > max_message_len:
            raise HTTPException(status_code=400, detail=f"Message trop long ({max_message_len} max).")
        sender = await device_by_key(payload.key_id)
        if not sender:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        if sender.get("role") == "blocked":
            raise HTTPException(
                status_code=403,
                detail="Votre demande a été formulée de nombreuses fois. Veuillez contacter le créateur.",
            )
        last_msg_iso = sender.get("last_message_at")
        is_creator_sender_quick = sender.get("role") == "creator"
        if last_msg_iso and not is_creator_sender_quick:
            try:
                last_msg = datetime.fromisoformat(last_msg_iso)
                elapsed = (datetime.now(timezone.utc) - last_msg).total_seconds()
                if elapsed < message_cooldown_seconds:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Patiente {int(message_cooldown_seconds - elapsed)}s avant d'envoyer un autre message.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass
        if not await consume_nonce(payload.key_id, payload.nonce):
            raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
        if not verify_signature(sender.get("public_key_jwk") or {}, payload.nonce, payload.signature):
            raise HTTPException(status_code=403, detail="Signature invalide.")
        is_creator_sender = sender.get("role") == "creator"
        if is_creator_sender:
            if not payload.target_key_id:
                raise HTTPException(status_code=400, detail="target_key_id requis pour les créateurs.")
            thread_key_id = payload.target_key_id
            target = await device_by_key(thread_key_id)
            if not target:
                raise HTTPException(status_code=404, detail="Destinataire inconnu.")
        else:
            thread_key_id = payload.key_id
        now = datetime.now(timezone.utc)
        msg_id = f"msg_{uuid.uuid4().hex[:16]}"
        sender_label = sender.get("label") or sender.get("pseudo") or None
        # iter128.5 — Persona override créa : seul un sender créateur peut
        # spécifier un pseudo/avatar customs et un flag de visibilité.
        persona = (payload.persona_override or {}) if is_creator_sender else {}
        custom_pseudo = (persona.get("customPseudo") or "").strip() or None
        custom_avatar = (persona.get("customAvatar") or "").strip() or None
        persona_id = persona.get("id") or None  # 'ai' | 'owner' | 'creator'
        visible_to_target = persona.get("visible", True) if persona else True
        ai_replies = persona.get("aiReplies", True) if persona else True
        await db.messages.insert_one({
            "message_id": msg_id,
            "thread_key_id": thread_key_id,
            "from_key_id": payload.key_id,
            "is_from_creator": bool(is_creator_sender),
            "content": content,
            "sender_label": sender_label,
            "ts": now.isoformat(),
            "read_by_creator": bool(is_creator_sender),
            "read_by_user": not bool(is_creator_sender) and bool(visible_to_target),
            # iter128.5 — Métadonnées persona (uniquement si créa). Permettront
            # au front de rendre le message avec l'icône/pseudo customs et de
            # masquer les messages "fantômes" du fil côté cible.
            "persona_id": persona_id,
            "persona_pseudo": custom_pseudo,
            "persona_avatar": custom_avatar,
            "visible_to_target": bool(visible_to_target),
            "ai_replies": bool(ai_replies),
        })
        await db.device_keys.update_one(
            {"key_id": payload.key_id},
            {"$set": {"last_message_at": now.isoformat()}},
        )
        return {"sent": True, "message_id": msg_id, "ts": now.isoformat()}

    @router.post("/messages/inbox")
    async def messages_inbox(payload: MessagesInboxIn):
        dev = await device_by_key(payload.key_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Clé inconnue.")
        if not await consume_nonce(payload.key_id, payload.nonce):
            raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
        if not verify_signature(dev.get("public_key_jwk") or {}, payload.nonce, payload.signature):
            raise HTTPException(status_code=403, detail="Signature invalide.")
        role = dev.get("role")
        sk = dev.get("staff_kind")
        is_creator = role == "creator"
        is_admin = sk == "admin"
        is_modo = sk == "modo"
        if not (is_creator or is_admin or is_modo):
            raise HTTPException(status_code=403, detail="Accès réservé staff.")
        match = {} if (is_creator or is_admin) else {"to_key_id": payload.key_id}
        pipeline = [
            {"$match": match},
            {"$sort": {"ts": -1}},
            {"$group": {
                "_id": "$thread_key_id",
                "last_ts": {"$first": "$ts"},
                "last_content": {"$first": "$content"},
                "last_is_from_creator": {"$first": "$is_from_creator"},
                "last_sender_label": {"$first": "$sender_label"},
                "recipient_kind": {"$first": "$recipient_kind"},
                "to_key_id": {"$first": "$to_key_id"},
                "unread": {
                    "$sum": {
                        "$cond": [{"$and": [
                            {"$eq": ["$is_from_creator", False]},
                            {"$eq": ["$read_by_creator", False]},
                        ]}, 1, 0]
                    }
                },
                "total": {"$sum": 1},
            }},
            {"$sort": {"last_ts": -1}},
            {"$limit": 100},
        ]
        rows = await db.messages.aggregate(pipeline).to_list(length=100)
        out = []
        for r in rows:
            d = await device_by_key(r["_id"]) or {}
            out.append({
                "thread_key_id": r["_id"],
                "label": d.get("label"),
                "pseudo": d.get("pseudo"),
                "role": d.get("role"),
                "last_ts": r["last_ts"],
                "last_content": r["last_content"][:140],
                "last_is_from_creator": r["last_is_from_creator"],
                "last_sender_label": r.get("last_sender_label"),
                "recipient_kind": r.get("recipient_kind"),
                "to_key_id": r.get("to_key_id"),
                "unread": r["unread"],
                "total": r["total"],
            })
        return {"threads": out}

    @router.post("/messages/thread")
    async def messages_thread(payload: MessagesThreadIn):
        sender = await device_by_key(payload.key_id)
        if not sender:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        if not await consume_nonce(payload.key_id, payload.nonce):
            raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
        if not verify_signature(sender.get("public_key_jwk") or {}, payload.nonce, payload.signature):
            raise HTTPException(status_code=403, detail="Signature invalide.")
        is_creator_caller = sender.get("role") == "creator"
        if is_creator_caller:
            thread_key_id = payload.thread_key_id
            if not thread_key_id:
                raise HTTPException(status_code=400, detail="thread_key_id requis.")
            await db.messages.update_many(
                {"thread_key_id": thread_key_id, "is_from_creator": False, "read_by_creator": False},
                {"$set": {"read_by_creator": True}},
            )
        else:
            thread_key_id = payload.key_id
            await db.messages.update_many(
                {"thread_key_id": thread_key_id, "is_from_creator": True, "read_by_user": False},
                {"$set": {"read_by_user": True}},
            )
        rows = await db.messages.find(
            {"thread_key_id": thread_key_id}, {"_id": 0},
        ).sort("ts", 1).to_list(length=500)
        return {"thread_key_id": thread_key_id, "messages": rows}

    @router.post("/messages/unread-count")
    async def messages_unread_count(payload: MessagesThreadIn):
        sender = await device_by_key(payload.key_id)
        if not sender:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        if not await consume_nonce(payload.key_id, payload.nonce):
            raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
        if not verify_signature(sender.get("public_key_jwk") or {}, payload.nonce, payload.signature):
            raise HTTPException(status_code=403, detail="Signature invalide.")
        if sender.get("role") == "creator":
            muted_ids = [d["key_id"] async for d in db.device_keys.find({"muted": True}, {"_id": 0, "key_id": 1})]
            q = {"is_from_creator": False, "read_by_creator": False}
            if muted_ids:
                q["thread_key_id"] = {"$nin": muted_ids}
            n = await db.messages.count_documents(q)
        else:
            n = await db.messages.count_documents({
                "thread_key_id": payload.key_id,
                "is_from_creator": True,
                "read_by_user": False,
            })
        return {"unread": n}

    @router.post("/messages/rename-contact")
    async def messages_rename_contact(payload: MessagesRenameIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        new_label = (payload.new_label or "").strip()
        if not new_label:
            raise HTTPException(status_code=400, detail="Nom requis.")
        if len(new_label) > 40:
            raise HTTPException(status_code=400, detail="Nom trop long (40 max).")
        target = await device_by_key(payload.thread_key_id)
        if not target:
            raise HTTPException(status_code=404, detail="Destinataire inconnu.")
        await db.device_keys.update_one(
            {"key_id": payload.thread_key_id}, {"$set": {"label": new_label}},
        )
        return {"success": True, "label": new_label}

    @router.post("/messages/delete-thread")
    async def messages_delete_thread(payload: MessagesDeleteIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        res = await db.messages.delete_many({"thread_key_id": payload.thread_key_id})
        return {"deleted": res.deleted_count}

    @router.post("/messages/send-to-staff")
    async def messages_send_to_staff(payload: MessageToStaffIn):
        sender = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        content = (payload.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="Message vide.")
        if len(content) > max_message_len:
            raise HTTPException(status_code=400, detail=f"Message trop long ({max_message_len} max).")
        modos = await db.device_keys.find(
            {"staff_kind": "modo", "role": {"$in": ["approved", "creator"]}},
            {"_id": 0, "key_id": 1, "pseudo": 1, "label": 1},
        ).to_list(length=50)
        if not modos:
            modos = await db.device_keys.find(
                {"staff_kind": "admin", "role": {"$in": ["approved", "creator"]}},
                {"_id": 0, "key_id": 1, "pseudo": 1, "label": 1},
            ).to_list(length=50)
        recipient_kind = "modo" if modos else "creator"
        if not modos:
            modos = await db.device_keys.find(
                {"role": "creator"}, {"_id": 0, "key_id": 1, "pseudo": 1, "label": 1},
            ).to_list(length=10)
        if not modos:
            raise HTTPException(status_code=503, detail="Aucun destinataire staff disponible.")
        target = random.choice(modos)
        target_key_id = target["key_id"]
        now = datetime.now(timezone.utc)
        msg_id = f"msg_{uuid.uuid4().hex[:16]}"
        await db.messages.insert_one({
            "message_id": msg_id,
            "thread_key_id": payload.key_id,
            "from_key_id": payload.key_id,
            "to_key_id": target_key_id,
            "is_from_creator": False,
            "recipient_kind": recipient_kind,
            "content": content,
            "sender_label": sender.get("pseudo") or sender.get("label"),
            "ts": now.isoformat(),
            "read_by_creator": False,
            "read_by_user": True,
        })
        return {"sent": True, "message_id": msg_id,
                "assigned_to": target.get("pseudo") or target.get("label") or target_key_id[:10],
                "recipient_kind": recipient_kind}

    return router
