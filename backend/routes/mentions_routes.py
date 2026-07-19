"""iter147 — Notifications de mentions @handle anonymous-safe.

RÈGLE ABSOLUE (spec utilisateur) : lorsqu'un message contient une mention
`@handle`, le destinataire reçoit une notification. Si l'auteur est en
mode ANONYME (social_prefs.anonymous=True), la notification ne révèle
JAMAIS l'identité de l'auteur (ni pseudo, ni public_handle, ni rôle).

Le message d'affichage est alors neutre :
  - "Quelqu'un t'a mentionné dans le tchat #<group_type>"

Endpoints :
  - POST /api/mentions/list    → liste des notifs (non lues + récentes)
  - POST /api/mentions/mark-read → marque N notifs comme lues
  - POST /api/mentions/unread-count → compteur uniquement

Stockage : db.mention_notifications (inséré par /groups/send).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class _SignedIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class MentionsListIn(_SignedIn):
    limit: int = 50
    only_unread: bool = False


class MentionsMarkReadIn(_SignedIn):
    notification_ids: List[str]


def _sanitize(row: Dict[str, Any]) -> Dict[str, Any]:
    """Filtre défensif : jamais exposer key_id de l'auteur si notif marquée
    author_hidden. En pratique, le champ from_key_id n'est déjà stocké
    que quand l'auteur n'est pas anonyme, mais on double-check ici."""
    hidden = bool(row.get("author_hidden"))
    out = {
        "notification_id": row.get("notification_id"),
        "type": row.get("type") or "mention",
        "group_type": row.get("group_type"),
        "message_id": row.get("message_id"),
        "ts": row.get("ts"),
        "read": bool(row.get("read", False)),
        "author_hidden": hidden,
    }
    if not hidden:
        out["from_pseudo"] = row.get("from_pseudo") or ""
        out["from_public_handle"] = row.get("from_public_handle") or ""
        out["from_role"] = row.get("from_role")
    return out


def build_mentions_router(db, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Mentions"])

    @router.post("/mentions/list")
    async def mentions_list(payload: MentionsListIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        q: Dict[str, Any] = {"to_key_id": payload.key_id}
        if payload.only_unread:
            q["read"] = False
        limit = min(max(payload.limit, 1), 200)
        rows = await db.mention_notifications.find(q, {"_id": 0}).sort(
            "ts", -1,
        ).limit(limit).to_list(length=limit)
        return {"notifications": [_sanitize(r) for r in rows]}

    @router.post("/mentions/unread-count")
    async def mentions_unread_count(payload: _SignedIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        n = await db.mention_notifications.count_documents(
            {"to_key_id": payload.key_id, "read": False},
        )
        return {"unread": int(n)}

    @router.post("/mentions/mark-read")
    async def mentions_mark_read(payload: MentionsMarkReadIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        ids = [i for i in (payload.notification_ids or []) if isinstance(i, str)]
        if not ids:
            return {"updated": 0}
        result = await db.mention_notifications.update_many(
            {"to_key_id": payload.key_id, "notification_id": {"$in": ids}},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"updated": int(result.modified_count)}

    @router.post("/mentions/mark-all-read")
    async def mentions_mark_all_read(payload: _SignedIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        result = await db.mention_notifications.update_many(
            {"to_key_id": payload.key_id, "read": False},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"updated": int(result.modified_count)}

    return router
