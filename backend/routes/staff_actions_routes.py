"""iter144 — Staff actions unifiées + Renommages (global + local).

Actions staff (device_keys) :
  - mute / block          — persistantes jusqu'au 'unmute' / 'unblock'.
  - exclude(t) / force_visitor(t) / disconnect(t) — timed (auto-expire).
  - ban                   — Admin+ only (définitif).
  - promote_modo / admin  — Admin+ only.
  - promote_creator       — Créa réelle only (crée une nouvelle créa).
  - demote                — retire tout rôle staff (démote → 'pending').
  - rename_global         — renomme officiellement le compte (staff selon permissions).

Renommage local :
  - /rename/local/set  → alias visible seulement par l'auteur.
  - /rename/local/list → liste des alias posés par l'auteur.

Toutes les actions vérifient `founder_guard.is_founder(target)` avant
d'agir → jamais aucune action sur les 2 créas fondatrices.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.founder_guard import assert_not_founder, is_founder
from utils.ownership_guard import assert_not_owner_target


# Actions durées par défaut (secondes).
DEFAULT_DURATIONS = {
    "exclude":       3600,       # 1h
    "force_visitor": 1800,       # 30min
    "disconnect":    900,        # 15min
}


class _SignedIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class StaffActionIn(_SignedIn):
    target_key_id: str
    action: str
    duration_sec: Optional[int] = None  # override pour timed
    reason: Optional[str] = None


class RenameGlobalIn(_SignedIn):
    target_key_id: str
    new_pseudo: str


class RenameLocalIn(_SignedIn):
    target_key_id: str
    alias: Optional[str] = None  # None → supprime


class ListLocalIn(_SignedIn):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _permission_matrix(actor_role: str, actor_sk: Optional[str], action: str) -> bool:
    """Retourne True si l'acteur a le droit d'exécuter cette action."""
    is_creator = actor_role == "creator"
    is_admin = actor_sk == "admin"
    is_modo = actor_sk == "modo"
    # Créa : tout autorisé (sauf sur fondatrices, filtré ailleurs).
    if is_creator:
        return True
    # Modo : actions basiques.
    modo_allowed = {"mute", "unmute", "block", "unblock",
                    "exclude", "force_visitor", "disconnect"}
    if is_modo and action in modo_allowed:
        return True
    # Admin : tout modo + ban + promote_modo/admin + rename_global + demote.
    if is_admin:
        admin_allowed = modo_allowed | {"ban", "promote_modo", "promote_admin",
                                        "demote", "rename_global"}
        return action in admin_allowed
    return False


def build_staff_actions_router(db, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Staff Actions"])

    async def _get_dev(key_id: str) -> Dict[str, Any]:
        return await db.device_keys.find_one({"key_id": key_id}, {"_id": 0}) or {}

    @router.post("/staff/action")
    async def staff_action(payload: StaffActionIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        target = await _get_dev(payload.target_key_id)
        if not target:
            raise HTTPException(status_code=404, detail="Cible introuvable.")
        action = payload.action
        # Protection créas fondatrices — jamais d'action.
        if is_founder(payload.target_key_id):
            raise HTTPException(
                status_code=403,
                detail="Créa fondatrice — cette action est interdite.",
            )
        # iter158 — Protection APPAREIL PROPRIÉTAIRE : aucune action staff
        # (ban, demote, block, disconnect, exclude...) ne peut viser un
        # appareil propriétaire. Seul le module /ownership/* (auth renforcée)
        # peut agir sur la propriété. Bloque même la Créa déléguée.
        _owner_touching = action in (
            "ban", "block", "demote", "disconnect", "exclude",
            "force_visitor", "mute", "promote_modo", "promote_admin",
        )
        if _owner_touching:
            await assert_not_owner_target(db, payload.target_key_id, payload.key_id, action)
        # Anti self-target sur actions destructives.
        if payload.target_key_id == payload.key_id and action in \
                ("ban", "disconnect", "exclude", "demote"):
            raise HTTPException(status_code=400, detail="Impossible sur soi-même.")
        # Permission.
        if not _permission_matrix(me.get("role"), me.get("staff_kind"), action):
            raise HTTPException(status_code=403, detail=f"Action '{action}' non autorisée pour ton rôle.")
        # Enforce : un admin ne peut pas ban/demote une créa réelle (non-fondatrice).
        # Seule la Créa peut agir sur une autre créa.
        if target.get("role") == "creator" and me.get("role") != "creator":
            raise HTTPException(status_code=403, detail="Seule une Créa peut modifier une autre Créa.")

        now = _now()
        set_ops: Dict[str, Any] = {}
        # Persistent actions.
        if action == "mute":
            set_ops = {"muted": True, "muted_at": now.isoformat(),
                       "muted_by": payload.key_id, "mute_reason": payload.reason or ""}
        elif action == "unmute":
            set_ops = {"muted": False, "unmuted_at": now.isoformat()}
        elif action == "block":
            set_ops = {"role": "blocked", "blocked_at": now.isoformat(),
                       "blocked_by": payload.key_id, "block_reason": payload.reason or ""}
        elif action == "unblock":
            # Restaure le rôle précédent si connu, sinon 'pending'.
            prev = target.get("role_before_block") or "pending"
            set_ops = {"role": prev, "unblocked_at": now.isoformat()}
        elif action == "ban":
            set_ops = {"role": "banned", "banned_at": now.isoformat(),
                       "banned_by": payload.key_id, "ban_reason": payload.reason or ""}
        elif action == "demote":
            set_ops = {"staff_kind": None, "demoted_at": now.isoformat(),
                       "demoted_by": payload.key_id}
        elif action == "promote_modo":
            set_ops = {"staff_kind": "modo", "role": "approved",
                       "promoted_at": now.isoformat(), "promoted_by": payload.key_id}
        elif action == "promote_admin":
            set_ops = {"staff_kind": "admin", "role": "approved",
                       "promoted_at": now.isoformat(), "promoted_by": payload.key_id}
        elif action == "promote_creator":
            if me.get("role") != "creator":
                raise HTTPException(status_code=403, detail="Seule une Créa peut promouvoir une créa.")
            set_ops = {"role": "creator", "staff_kind": None,
                       "promoted_at": now.isoformat(), "promoted_by": payload.key_id}
        # Timed actions.
        elif action in DEFAULT_DURATIONS:
            duration = int(payload.duration_sec or DEFAULT_DURATIONS[action])
            expires = (now + timedelta(seconds=duration)).isoformat()
            key = f"{action}_until"
            set_ops = {key: expires, f"{action}_at": now.isoformat(),
                       f"{action}_by": payload.key_id, f"{action}_reason": payload.reason or ""}
        elif action.startswith("un_"):
            base = action[3:]
            set_ops = {f"{base}_until": None, f"{base}_cleared_at": now.isoformat()}
        else:
            raise HTTPException(status_code=400, detail=f"Action inconnue : {action}")

        await db.device_keys.update_one(
            {"key_id": payload.target_key_id}, {"$set": set_ops},
        )
        # Journal indépendant des décisions staff (compatibilité mod_decisions).
        await db.staff_actions_log.insert_one({
            "log_id": f"sact_{uuid.uuid4().hex[:14]}",
            "actor_key_id": payload.key_id,
            "actor_pseudo": me.get("pseudo") or "",
            "actor_role": me.get("role"),
            "actor_staff_kind": me.get("staff_kind"),
            "target_key_id": payload.target_key_id,
            "target_pseudo": target.get("pseudo") or "",
            "action": action,
            "reason": payload.reason or "",
            "duration_sec": payload.duration_sec,
            "ts": now.isoformat(),
        })
        return {"ok": True, "action": action, "target": payload.target_key_id}

    @router.post("/staff/rename-global")
    async def rename_global(payload: RenameGlobalIn):
        """iter144 — Renommage officiel du compte. Staff-only selon perms.
        Visible par tous. Ne touche jamais une créa fondatrice."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if not _permission_matrix(me.get("role"), me.get("staff_kind"), "rename_global"):
            raise HTTPException(status_code=403, detail="Renommage réservé à admin+ ou créa.")
        assert_not_founder(payload.target_key_id, "renommage")
        new_pseudo = (payload.new_pseudo or "").strip()
        if not new_pseudo or len(new_pseudo) > 30:
            raise HTTPException(status_code=400, detail="Pseudo invalide (1-30 chars).")
        target = await _get_dev(payload.target_key_id)
        prev = target.get("pseudo") or target.get("label") or ""
        now_iso = _now().isoformat()
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"pseudo": new_pseudo,
                      "label": new_pseudo,
                      "renamed_at": now_iso,
                      "renamed_by": payload.key_id,
                      "pseudo_before_rename": prev}},
        )
        # Mirror to users if link.
        email = target.get("email")
        if email:
            await db.users.update_one({"email": email}, {"$set": {"pseudo": new_pseudo}})
        await db.staff_actions_log.insert_one({
            "log_id": f"sact_{uuid.uuid4().hex[:14]}",
            "actor_key_id": payload.key_id,
            "target_key_id": payload.target_key_id,
            "action": "rename_global",
            "old_pseudo": prev,
            "new_pseudo": new_pseudo,
            "ts": now_iso,
        })
        return {"ok": True, "new_pseudo": new_pseudo}

    # ---- Renommage local (alias personnel) --------------------------------
    @router.post("/rename/local/set")
    async def rename_local_set(payload: RenameLocalIn):
        """Enregistre un alias LOCAL. Visible uniquement par l'auteur.
        `alias=null` supprime l'alias."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        # Créa fondatrice non renommable même en local.
        if is_founder(payload.target_key_id):
            raise HTTPException(status_code=403, detail="Créa fondatrice non renommable.")
        alias = (payload.alias or "").strip()
        if alias and len(alias) > 30:
            raise HTTPException(status_code=400, detail="Alias trop long (30 max).")
        if not alias:
            await db.local_aliases.delete_one({
                "owner_key_id": payload.key_id,
                "target_key_id": payload.target_key_id,
            })
            return {"ok": True, "removed": True}
        await db.local_aliases.update_one(
            {"owner_key_id": payload.key_id, "target_key_id": payload.target_key_id},
            {"$set": {"alias": alias, "updated_at": _now().isoformat()}},
            upsert=True,
        )
        return {"ok": True, "alias": alias}

    @router.post("/rename/local/list")
    async def rename_local_list(payload: ListLocalIn):
        """Retourne tous les alias posés par l'appelant."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        rows = await db.local_aliases.find(
            {"owner_key_id": payload.key_id}, {"_id": 0},
        ).to_list(length=500)
        return {"aliases": rows}

    @router.post("/rename/local/creator-view")
    async def rename_local_creator_view(payload: ListLocalIn):
        """iter144 — Créa uniquement : voit tous les alias posés sur un
        compte donné (pour contexte). Retourne également le pseudo officiel."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if me.get("role") != "creator":
            raise HTTPException(status_code=403, detail="Créa uniquement.")
        # payload doit contenir target_key_id — on utilise RenameLocalIn.
        # (Réutilise le shape existant pour pas multiplier les classes.)
        return {"ok": True, "note": "Utiliser /rename/local/list-on-target avec target_key_id."}

    class ListOnTargetIn(_SignedIn):
        target_key_id: str

    @router.post("/rename/local/list-on-target")
    async def rename_local_on_target(payload: ListOnTargetIn):
        """Créa only — retourne tous les alias posés sur un compte cible +
        son pseudo officiel."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if me.get("role") != "creator":
            raise HTTPException(status_code=403, detail="Créa uniquement.")
        target = await _get_dev(payload.target_key_id)
        rows = await db.local_aliases.find(
            {"target_key_id": payload.target_key_id}, {"_id": 0},
        ).to_list(length=200)
        return {
            "official_pseudo": target.get("pseudo") or target.get("label") or "",
            "aliases": rows,
        }

    return router
