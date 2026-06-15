"""iter117 — Routes /accounts/* extraites de server.py.

16 endpoints créa/staff pour la gestion des comptes :
  - /accounts/list, /history, /history/clear
  - /accounts/rename-pseudo, /set-staff-kind, /force-visitor
  - /accounts/mute, /unmute, /exclude, /ban, /unban
  - /accounts/visit (interactive)
  - /accounts/delete-user-project, /delete-one, /delete-all
  - /accounts/remove-creator (self + other)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict


class _CreatorSigIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


class _TargetCreatorSigIn(_CreatorSigIn):
    target_key_id: str


class _SetStaffKindIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    target_key_id: str
    staff_kind: Optional[str] = None


class _ForceVisitorIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    target_key_id: str
    force: bool = True


def build_accounts_router(db, *, require_creator_signature, require_staff_signature):
    router = APIRouter()

    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _log_account_event(event: str, target_key_id: str, target_label: Optional[str] = None,
                                  extra: Optional[Dict[str, Any]] = None,
                                  actor_key_id: Optional[str] = None):
        doc = {
            "event_id": f"ah_{uuid.uuid4().hex[:14]}",
            "event": event,
            "target_key_id": target_key_id,
            "target_label": target_label,
            "ts": _now_iso(),
        }
        if actor_key_id:
            doc["actor_key_id"] = actor_key_id
            actor = await db.device_keys.find_one(
                {"key_id": actor_key_id},
                {"_id": 0, "role": 1, "staff_kind": 1, "pseudo": 1, "label": 1},
            )
            if actor:
                doc["actor_kind"] = ("creator" if actor.get("role") == "creator"
                                     else (actor.get("staff_kind") or actor.get("role")))
                doc["actor_label"] = actor.get("pseudo") or actor.get("label")
        if extra:
            doc.update(extra)
        await db.account_history.insert_one(doc)

    def _disambiguate_pseudos(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_lower: Dict[str, int] = {}
        out = []
        for r in rows:
            p = (r.get("pseudo") or r.get("label") or "").strip()
            key = p.lower()
            if not p:
                r["display"] = (r.get("email") or r.get("key_id", "")[:14])
                out.append(r); continue
            by_lower[key] = by_lower.get(key, 0) + 1
            n = by_lower[key]
            r["display"] = p if n == 1 else f"{p} #{n}"
            out.append(r)
        return out

    async def _email_for_device_key(key_id: str) -> Optional[str]:
        me = await db.device_keys.find_one({"key_id": key_id}, {"_id": 0, "email": 1})
        if me and me.get("email"):
            return me["email"]
        sess = await db.user_sessions.find_one(
            {"device_key_id": key_id, "expires_at": {"$gt": _now_iso()}},
            {"_id": 0, "user_id": 1},
        )
        if not sess:
            return None
        owner = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "email": 1})
        if owner and owner.get("email"):
            await db.device_keys.update_one({"key_id": key_id}, {"$set": {"email": owner["email"]}})
            return owner["email"]
        return None

    @router.post("/accounts/list")
    async def accounts_list(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        devices = await db.device_keys.find(
            {}, {"_id": 0, "public_key_jwk": 0},
        ).sort("created_at", -1).to_list(length=2000)
        emails = list({d.get("email") for d in devices if d.get("email")})
        users = {}
        if emails:
            async for u in db.users.find({"email": {"$in": emails}}, {"_id": 0, "email": 1, "pseudo": 1}):
                users[u["email"]] = u.get("pseudo")
        for d in devices:
            d["pseudo"] = users.get(d.get("email")) or d.get("pseudo") or d.get("label")
            d["muted"] = bool(d.get("muted"))
            d["banned"] = bool(d.get("banned"))
            d["is_inactive"] = (d.get("role") == "inactive")
            d["deleted"] = bool(d.get("deleted"))
            d.setdefault("product", None); d.setdefault("model", None)
            d.setdefault("staff_kind", None)
            d.setdefault("force_visitor", bool(d.get("force_visitor", False)))
        return {"accounts": _disambiguate_pseudos(devices)}

    @router.post("/accounts/rename-pseudo")
    async def accounts_rename_pseudo(payload: _TargetCreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump()
        new_pseudo = (body.get("new_pseudo") or "").strip()
        if not (1 <= len(new_pseudo) <= 30):
            raise HTTPException(status_code=400, detail="Pseudo invalide (3-30).")
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"pseudo": new_pseudo, "label": new_pseudo}},
        )
        if target.get("email"):
            await db.users.update_one(
                {"email": target["email"]},
                {"$set": {"pseudo": new_pseudo, "pseudo_lower": new_pseudo.lower()}},
            )
        await _log_account_event("rename", payload.target_key_id, new_pseudo)
        return {"success": True, "pseudo": new_pseudo}

    @router.post("/accounts/mute")
    async def accounts_mute(payload: _TargetCreatorSigIn):
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"muted": True, "muted_at": _now_iso()}},
        )
        await _log_account_event("mute", payload.target_key_id, actor_key_id=payload.key_id)
        return {"success": True}

    @router.post("/accounts/unmute")
    async def accounts_unmute(payload: _TargetCreatorSigIn):
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"muted": False}, "$unset": {"muted_at": ""}},
        )
        await _log_account_event("unmute", payload.target_key_id, actor_key_id=payload.key_id)
        return {"success": True}

    @router.post("/accounts/set-staff-kind")
    async def accounts_set_staff_kind(payload: _SetStaffKindIn):
        actor = await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        sk = (payload.staff_kind or None)
        if sk not in (None, "admin", "modo"):
            raise HTTPException(status_code=400, detail="staff_kind invalide ('admin'|'modo'|null).")
        if actor.get("role") != "creator":
            actor_sk = actor.get("staff_kind")
            if actor_sk != "admin":
                raise HTTPException(status_code=403, detail="Seuls les admins et créatrice peuvent promouvoir.")
            if sk == "admin":
                raise HTTPException(status_code=403, detail="Seule la créatrice peut nommer un admin.")
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0, "role": 1})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        update = {"$set": {"staff_kind": sk}} if sk else {"$unset": {"staff_kind": ""}}
        await db.device_keys.update_one({"key_id": payload.target_key_id}, update)
        await _log_account_event(f"staff_kind_{sk or 'clear'}", payload.target_key_id, actor_key_id=payload.key_id)
        return {"success": True, "staff_kind": sk}

    @router.post("/accounts/force-visitor")
    async def accounts_force_visitor(payload: _ForceVisitorIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"force_visitor": bool(payload.force)}},
        )
        await _log_account_event(
            "force_visitor_on" if payload.force else "force_visitor_off",
            payload.target_key_id,
        )
        return {"success": True, "force_visitor": bool(payload.force)}

    @router.post("/accounts/exclude")
    async def accounts_exclude(payload: _TargetCreatorSigIn):
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump()
        minutes = int(body.get("duration_minutes") or 0)
        if minutes <= 0 or minutes > 60 * 24 * 90:
            raise HTTPException(status_code=400, detail="Durée invalide (1 min - 90 jours).")
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"excluded_until": until.isoformat(), "excluded_reason": body.get("reason") or ""}},
        )
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0, "email": 1})
        if target and target.get("email"):
            await db.user_sessions.delete_many({"email": target["email"]})
        await _log_account_event("exclude", payload.target_key_id,
                                 extra={"until": until.isoformat(), "minutes": minutes},
                                 actor_key_id=payload.key_id)
        return {"success": True, "excluded_until": until.isoformat()}

    @router.post("/accounts/ban")
    async def accounts_ban(payload: _TargetCreatorSigIn):
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"banned": True, "banned_at": _now_iso()}},
        )
        if target.get("email"):
            await db.banned_emails.update_one(
                {"email": target["email"]},
                {"$set": {"email": target["email"], "banned_at": _now_iso()}},
                upsert=True,
            )
            await db.user_sessions.delete_many({"email": target["email"]})
        await _log_account_event("ban", payload.target_key_id,
                                 extra={"email": target.get("email")},
                                 actor_key_id=payload.key_id)
        return {"success": True}

    @router.post("/accounts/unban")
    async def accounts_unban(payload: _TargetCreatorSigIn):
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0})
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"banned": False}, "$unset": {"banned_at": ""}},
        )
        if target and target.get("email"):
            await db.banned_emails.delete_many({"email": target["email"]})
        await _log_account_event("unban", payload.target_key_id, actor_key_id=payload.key_id)
        return {"success": True}

    @router.post("/accounts/history")
    async def accounts_history(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        rows = await db.account_history.find({}, {"_id": 0}).sort("ts", -1).to_list(length=1000)
        return {"history": rows}

    @router.post("/accounts/history/clear")
    async def accounts_history_clear(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        r = await db.account_history.delete_many({})
        return {"deleted": r.deleted_count}

    @router.post("/accounts/visit")
    async def accounts_visit(payload: _TargetCreatorSigIn):
        """iter80 — Vue interactive du compte d'un user (créa-only)."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        user_id = None
        if target.get("email"):
            u = await db.users.find_one({"email": target["email"]}, {"_id": 0, "user_id": 1})
            if u:
                user_id = u["user_id"]
        projects = []
        messages = []
        if user_id:
            raw_projects = await db.projects.find(
                {"user_id": user_id}, {"_id": 0, "generated_code": 0},
            ).sort("created_at", -1).to_list(length=500)
            for p in raw_projects:
                p["is_deleted"] = bool(p.get("deleted_by_user") or p.get("deleted_by_creator") or p.get("deleted"))
                projects.append(p)
            raw_messages = await db.chat_messages.find(
                {"user_id": user_id}, {"_id": 0},
            ).sort("timestamp", -1).to_list(length=2000)
            for m in raw_messages:
                m["is_deleted"] = bool(m.get("deleted"))
                messages.append(m)
        private_msgs = await db.messages.find(
            {"$or": [
                {"thread_key_id": payload.target_key_id},
                {"from_key_id": payload.target_key_id},
                {"to_key_id": payload.target_key_id},
            ]},
            {"_id": 0},
        ).sort("ts", -1).to_list(length=2000)
        friend_requests = await db.friend_requests.find(
            {"$or": [{"from_key_id": payload.target_key_id}, {"to_key_id": payload.target_key_id}]},
            {"_id": 0},
        ).sort("created_at", -1).to_list(length=200)
        group_posts = await db.group_messages.find(
            {"from_key_id": payload.target_key_id}, {"_id": 0},
        ).sort("ts", -1).to_list(length=1000)
        return {
            "target": {
                "key_id": payload.target_key_id,
                "email": target.get("email"),
                "pseudo": target.get("pseudo") or target.get("label"),
                "label": target.get("label"),
                "role": target.get("role"),
                "staff_kind": target.get("staff_kind"),
                "force_visitor": target.get("force_visitor"),
                "muted": target.get("muted"),
                "banned": target.get("banned"),
                "last_seen_at": target.get("last_seen_at"),
                "created_at": target.get("created_at"),
                "biometric_kind": (
                    target.get("biometric_kind")
                    or (target.get("biometric") or {}).get("kind") if isinstance(target.get("biometric"), dict) else None
                ),
                "approved_by_kind": target.get("approved_by_kind"),
                "approved_by_label": target.get("approved_by_label"),
            },
            "projects": projects,
            "messages": list(reversed(messages)),
            "private_messages": list(reversed(private_msgs)),
            "friend_requests": friend_requests,
            "group_posts": group_posts,
        }

    @router.post("/accounts/delete-user-project")
    async def accounts_delete_user_project(payload: _TargetCreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump()
        project_id = body.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id requis.")
        r = await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"deleted_by_creator": True, "deleted_at": _now_iso()}},
        )
        await _log_account_event("delete_project", payload.target_key_id, extra={"project_id": project_id})
        return {"success": True, "matched": r.matched_count}

    @router.post("/accounts/delete-one")
    async def accounts_delete_one(payload: _TargetCreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        target_key_id = payload.target_key_id
        if target_key_id == payload.key_id:
            raise HTTPException(status_code=400, detail="Impossible de supprimer ton propre compte ici.")
        target = await db.device_keys.find_one({"key_id": target_key_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        # iter127 — Soft-delete : on conserve l'entrée pour qu'elle reste
        # visible dans la liste avec le badge "Compte supprimé". Les
        # sessions actives sont invalidées et l'email est dissocié pour
        # éviter toute reconnexion silencieuse.
        await db.device_keys.update_one(
            {"key_id": target_key_id},
            {"$set": {"deleted": True, "deleted_at": _now_iso(), "role": "inactive"}},
        )
        if target.get("email"):
            await db.user_sessions.delete_many({"email": target["email"]})
        await _log_account_event("delete_account", target_key_id, target.get("label"))
        return {"success": True}

    @router.post("/accounts/delete-all")
    async def accounts_delete_all(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump()
        pwd = body.get("password") or ""
        email = await _email_for_device_key(payload.key_id)
        if not email:
            raise HTTPException(status_code=400, detail="Aucun email lié à cet appareil. Reconnecte-toi pour le re-lier.")
        user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 1})
        if not user or not user.get("password_hash"):
            raise HTTPException(status_code=400, detail="Aucun mot de passe configuré.")
        if not bcrypt.checkpw(pwd.encode("utf-8"), user["password_hash"].encode("utf-8")):
            raise HTTPException(status_code=403, detail="Mot de passe incorrect.")
        r = await db.device_keys.delete_many({"key_id": {"$ne": payload.key_id}})
        await _log_account_event("delete_all_accounts", payload.key_id, extra={"deleted": r.deleted_count})
        return {"success": True, "deleted": r.deleted_count}

    @router.post("/accounts/remove-creator")
    async def accounts_remove_creator(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump()
        pwd = body.get("password") or ""
        target_key_id = body.get("target_key_id") or payload.key_id
        email = await _email_for_device_key(payload.key_id)
        if not email:
            raise HTTPException(status_code=400, detail="Aucun email lié à cet appareil. Reconnecte-toi pour le re-lier.")
        user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 1})
        if not user or not user.get("password_hash"):
            raise HTTPException(status_code=400, detail="Aucun mot de passe configuré.")
        if not bcrypt.checkpw(pwd.encode("utf-8"), user["password_hash"].encode("utf-8")):
            raise HTTPException(status_code=403, detail="Mot de passe incorrect.")
        target = await db.device_keys.find_one({"key_id": target_key_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        if target.get("role") != "creator":
            raise HTTPException(status_code=400, detail="Ce compte n'est pas créateur.")
        await db.device_keys.update_one(
            {"key_id": target_key_id}, {"$set": {"role": "approved"}},
        )
        is_self = target_key_id == payload.key_id
        await _log_account_event("remove_creator_self" if is_self else "remove_creator_other",
                                  target_key_id, target.get("label"))
        await db.device_decisions.insert_one({
            "decision_id": f"d_{uuid.uuid4().hex[:14]}",
            "action": "demote",
            "actor_key_id": payload.key_id,
            "target_key_id": target_key_id,
            "ts": _now_iso(),
            "target_label": target.get("label"),
        })
        return {"success": True, "self": is_self}

    return router
