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

import base64
import json as _json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from models.auth_signatures import CreatorSigIn as _CreatorSigIn, SignedIn, TargetCreatorSigIn as _TargetCreatorSigIn


class _SetStaffKindIn(SignedIn):
    target_key_id: str
    staff_kind: Optional[str] = None


class _ForceVisitorIn(SignedIn):
    target_key_id: str
    force: bool = True


class _AccountsUndoIn(SignedIn):
    event_id: str


class _AccountsUndoMultiIn(SignedIn):
    event_ids: List[str]


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
        actor = None
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

        # iter133 — Décisions de staff NON-créa = "validation temporaire".
        # On persiste dans `staff_decisions` pour que la créa puisse valider
        # ou annuler chaque action prise par les modos/admins.
        is_creator_actor = bool(actor and actor.get("role") == "creator")
        TRACKED_EVENTS = {
            "staff_kind_admin", "staff_kind_modo", "staff_kind_clear",
            "mute", "unmute", "exclude", "ban", "unban",
            "force_visitor_on", "force_visitor_off",
            "rename_pseudo",
        }
        if not is_creator_actor and event in TRACKED_EVENTS and actor_key_id:
            await db.staff_decisions.insert_one({
                "decision_id": f"sd_{uuid.uuid4().hex[:14]}",
                "event": event,
                "target_key_id": target_key_id,
                "target_label": target_label,
                "actor_key_id": actor_key_id,
                "actor_kind": doc.get("actor_kind"),
                "actor_label": doc.get("actor_label"),
                "extra": extra or {},
                "ts": _now_iso(),
                "status": "pending",  # pending | validated | reverted
            })
            # Marque le target pour badge UI "Validation temporaire".
            await db.device_keys.update_one(
                {"key_id": target_key_id},
                {"$set": {"pending_creator_review": True}},
            )

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
        # iter127 — include public_key_jwk so we can derive the share_code
        # (base64 du JWK) que la créa peut copier depuis la liste.
        devices = await db.device_keys.find(
            {}, {"_id": 0},
        ).sort("created_at", -1).to_list(length=2000)
        emails = list({d.get("email") for d in devices if d.get("email")})
        users = {}
        handles = {}
        if emails:
            async for u in db.users.find({"email": {"$in": emails}}, {"_id": 0, "email": 1, "pseudo": 1, "public_handle": 1}):
                users[u["email"]] = u.get("pseudo")
                handles[u["email"]] = u.get("public_handle") or ""
        for d in devices:
            d["pseudo"] = users.get(d.get("email")) or d.get("pseudo") or d.get("label")
            d["public_handle"] = handles.get(d.get("email")) or d.get("public_handle") or ""
            d["muted"] = bool(d.get("muted"))
            d["banned"] = bool(d.get("banned"))
            d["is_inactive"] = (d.get("role") == "inactive")
            d["deleted"] = bool(d.get("deleted"))
            d.setdefault("product", None); d.setdefault("model", None)
            d.setdefault("staff_kind", None)
            d.setdefault("force_visitor", bool(d.get("force_visitor", False)))
            # iter133 — Marqueur "validation temporaire" : une décision non-créa
            # a été prise sur ce compte et attend la confirmation de la créa.
            d["pending_creator_review"] = bool(d.get("pending_creator_review", False))
            # iter127 — share_code = base64(JSON(public_key_jwk)) — identique
            # à `exportPublicKeyShareCode()` côté front. C'est la "clé" que
            # l'utilisateur partage pour ses demandes d'amis / mode privé.
            jwk = d.pop("public_key_jwk", None) or {}
            try:
                if jwk:
                    raw = _json.dumps(jwk, separators=(",", ":")).encode("utf-8")
                    d["share_code"] = base64.b64encode(raw).decode("ascii")
                else:
                    d["share_code"] = ""
            except Exception:
                d["share_code"] = ""
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

    @router.post("/accounts/disconnect")
    async def accounts_disconnect(payload: _TargetCreatorSigIn):
        """iter158.5 — Déconnexion temporaire d'un compte (staff modo+).

        Applique une sanction `disconnect_until` (15 min par défaut) et invalide
        les sessions actives. Le message d'écran affiché à l'utilisateur
        déconnecté est celui du CDC exact — voir i18n `kick_disconnected_body`
        (« Oh oh... on dirait que vous avez un problème de connexion »).
        """
        actor = await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        # Interdit d'agir sur un appareil propriétaire ON (protection).
        try:
            from utils.ownership_guard import assert_not_owner_target
            await assert_not_owner_target(db, payload.target_key_id, payload.key_id, action="disconnect")
        except Exception:
            raise
        body = payload.model_dump()
        minutes = int(body.get("duration_minutes") or 15)
        minutes = max(1, min(minutes, 60 * 24))  # 1 min → 24 h
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"disconnect_until": until.isoformat()}},
        )
        target = await db.device_keys.find_one({"key_id": payload.target_key_id}, {"_id": 0, "email": 1})
        if target and target.get("email"):
            await db.user_sessions.delete_many({"email": target["email"]})
        await _log_account_event(
            "disconnect", payload.target_key_id,
            extra={"until": until.isoformat(), "minutes": minutes,
                   "kick_reason": "kick_disconnected"},
            actor_key_id=payload.key_id,
        )
        return {"success": True, "disconnect_until": until.isoformat()}

    @router.post("/accounts/history")
    async def accounts_history(payload: _CreatorSigIn):
        """iter158.5 — Historique des actions comptes. Ouvert au staff selon
        la matrice de permissions :
          - Créa : voit tout.
          - Admin : voit toutes les décisions (admin + modo).
          - Modo : voit uniquement ses propres décisions.
        """
        actor = await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        role = actor.get("role"); sk = actor.get("staff_kind")
        q: Dict[str, Any] = {}
        if role != "creator":
            if sk == "modo":
                q = {"actor_key_id": payload.key_id}
        rows = await db.account_history.find(q, {"_id": 0}).sort("ts", -1).to_list(length=1000)
        return {"history": rows}

    @router.post("/accounts/history/clear")
    async def accounts_history_clear(payload: _CreatorSigIn):
        """iter158.5 — Fonction retirée par spec CDC. 410 Gone."""
        raise HTTPException(
            status_code=410,
            detail="Fonction retirée : l'historique des comptes ne peut plus être vidé (spec finalisation).",
        )

    # ---------------- UNDO helpers ----------------
    UNDO_MATRIX = {
        # event → (undo_endpoint_or_action, reverse_updates)
        "mute": {"$set": {"muted": False}, "$unset": {"muted_at": ""}},
        "unmute": {"$set": {"muted": True, "muted_at": _now_iso()}},
        "ban": {"$set": {"banned": False}, "$unset": {"banned_at": "", "banned_reason": ""}},
        "unban": {"$set": {"banned": True, "banned_at": _now_iso()}},
        "exclude": {"$unset": {"excluded_until": "", "excluded_reason": ""}},
        "disconnect": {"$unset": {"disconnect_until": ""}},
        "force_visitor_on": {"$set": {"force_visitor": False}},
        "force_visitor_off": {"$set": {"force_visitor": True}},
        "staff_kind_admin": {"$unset": {"staff_kind": ""}},
        "staff_kind_modo": {"$unset": {"staff_kind": ""}},
        "staff_kind_clear": {"$set": {"staff_kind": "modo"}},  # défaut sécurisé
    }

    def _can_undo_event(actor_role: Optional[str], actor_sk: Optional[str],
                        event_actor_kind: Optional[str], event_actor_key_id: Optional[str],
                        me_key_id: str) -> bool:
        if actor_role == "creator":
            return True
        if actor_sk == "admin":
            return event_actor_kind != "creator"
        if actor_sk == "modo":
            return event_actor_key_id == me_key_id
        return False

    async def _apply_undo(event_row: Dict[str, Any]) -> bool:
        ev = event_row.get("event")
        tkid = event_row.get("target_key_id")
        if not tkid or ev not in UNDO_MATRIX:
            return False
        await db.device_keys.update_one({"key_id": tkid}, UNDO_MATRIX[ev])
        return True

    @router.post("/accounts/history/undo")
    async def accounts_history_undo(payload: _AccountsUndoIn):
        """iter158.5 — Annulation d'une action comptes.

        Applique la matrice inverse `UNDO_MATRIX` et logue un événement
        `undo_<event>` pour traçabilité. Refuse si l'événement n'est pas
        annulable (delete_account, delete_all_accounts…) ou hors périmètre
        du rôle acteur.
        """
        actor = await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        row = await db.account_history.find_one({"event_id": payload.event_id}, {"_id": 0})
        if not row:
            raise HTTPException(status_code=404, detail="Événement introuvable.")
        allowed = _can_undo_event(
            actor.get("role"), actor.get("staff_kind"),
            row.get("actor_kind"), row.get("actor_key_id"),
            payload.key_id,
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Cette action n'est pas dans ton périmètre d'annulation.")
        applied = await _apply_undo(row)
        if not applied:
            return {"success": False, "reason": "non_undoable_action"}
        await _log_account_event(f"undo_{row.get('event')}", row.get("target_key_id"),
                                 extra={"original_event_id": payload.event_id},
                                 actor_key_id=payload.key_id)
        return {"success": True}

    @router.post("/accounts/history/undo-multi")
    async def accounts_history_undo_multi(payload: _AccountsUndoMultiIn):
        """iter158.5 — Annulation multiple. Retourne {ok_count, failed[]}."""
        actor = await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        ok = 0
        failed: List[Dict[str, Any]] = []
        for eid in payload.event_ids or []:
            row = await db.account_history.find_one({"event_id": eid}, {"_id": 0})
            if not row:
                failed.append({"event_id": eid, "reason": "not_found"})
                continue
            allowed = _can_undo_event(
                actor.get("role"), actor.get("staff_kind"),
                row.get("actor_kind"), row.get("actor_key_id"),
                payload.key_id,
            )
            if not allowed:
                failed.append({"event_id": eid, "reason": "not_authorized"})
                continue
            applied = await _apply_undo(row)
            if not applied:
                failed.append({"event_id": eid, "reason": "non_undoable_action"})
                continue
            await _log_account_event(f"undo_{row.get('event')}", row.get("target_key_id"),
                                     extra={"original_event_id": eid},
                                     actor_key_id=payload.key_id)
            ok += 1
        return {"success": True, "ok_count": ok, "failed": failed}

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
        # iter158.16 (P1.5) — Protection self-remove d'un créateur verrouillé.
        # Un véritable créateur (délégué avec `locked=true` dans ownership.delegates)
        # ne peut PAS être retiré de son statut créa, ni par lui-même ni par un
        # autre acteur. Cohérent avec /ownership/delegate/revoke (iter158.6).
        # owner_key_ids n'est jamais touché par cet endpoint — la protection est
        # spécifique au flag `locked` du délégué.
        from utils.ownership_guard import get_delegate as _get_delegate
        delegate_row = await _get_delegate(db, target_key_id)
        if delegate_row and delegate_row.get("locked"):
            is_self_attempt = target_key_id == payload.key_id
            raise HTTPException(
                status_code=409,
                detail=(
                    "Créateur verrouillé (véritable créateur) — "
                    + ("retrait volontaire refusé. " if is_self_attempt else "retrait refusé. ")
                    + "Le propriétaire doit d'abord /ownership/delegate/unlock."
                ),
            )
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
