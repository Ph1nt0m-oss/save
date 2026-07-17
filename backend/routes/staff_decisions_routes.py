"""iter133 — Routes /staff-decisions/* (Créa-only).

Les décisions prises par modos/admins sont marquées "validation temporaire"
(champ `pending_creator_review` sur device_keys + doc dans `staff_decisions`
avec status='pending'). La créa peut :
  - Lister les décisions en attente
  - Les VALIDER (persistent définitivement)
  - Les ANNULER (revert : rollback de la modif appliquée)

Actions supportées : staff_kind_admin/modo/clear, mute/unmute, exclude,
ban/unban, force_visitor_on/off, rename_pseudo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from models.auth_signatures import CreatorSigIn as _CreatorSigIn


class _DecisionActionIn(_CreatorSigIn):
    decision_id: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_staff_decisions_router(db, *, require_creator_signature):
    router = APIRouter()

    @router.post("/staff-decisions/list")
    async def staff_decisions_list(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        rows = await db.staff_decisions.find(
            {"status": "pending"}, {"_id": 0},
        ).sort("ts", -1).to_list(length=500)
        return {"decisions": rows, "count": len(rows)}

    @router.post("/staff-decisions/validate")
    async def staff_decisions_validate(payload: _DecisionActionIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        dec = await db.staff_decisions.find_one({"decision_id": payload.decision_id, "status": "pending"}, {"_id": 0})
        if not dec:
            raise HTTPException(status_code=404, detail="Décision introuvable ou déjà traitée.")
        await db.staff_decisions.update_one(
            {"decision_id": payload.decision_id},
            {"$set": {"status": "validated", "reviewed_at": _now_iso(), "reviewed_by": payload.key_id}},
        )
        # Si plus aucune décision pending pour ce target, on retire le flag.
        remaining = await db.staff_decisions.count_documents(
            {"target_key_id": dec["target_key_id"], "status": "pending"},
        )
        if remaining == 0:
            await db.device_keys.update_one(
                {"key_id": dec["target_key_id"]},
                {"$unset": {"pending_creator_review": ""}},
            )
        return {"validated": True, "decision_id": payload.decision_id}

    @router.post("/staff-decisions/revert")
    async def staff_decisions_revert(payload: _DecisionActionIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        dec = await db.staff_decisions.find_one({"decision_id": payload.decision_id, "status": "pending"}, {"_id": 0})
        if not dec:
            raise HTTPException(status_code=404, detail="Décision introuvable ou déjà traitée.")

        # Rollback selon le type d'action.
        event = dec.get("event")
        tkid = dec["target_key_id"]
        rollback_applied = False

        if event == "staff_kind_admin" or event == "staff_kind_modo":
            # On annule la promotion → staff_kind = None.
            await db.device_keys.update_one({"key_id": tkid}, {"$unset": {"staff_kind": ""}})
            rollback_applied = True
        elif event == "staff_kind_clear":
            # On restaurerait l'ancien staff_kind si stocké dans extra.previous.
            prev = (dec.get("extra") or {}).get("previous_staff_kind")
            if prev in ("admin", "modo"):
                await db.device_keys.update_one({"key_id": tkid}, {"$set": {"staff_kind": prev}})
                rollback_applied = True
        elif event == "mute":
            await db.device_keys.update_one({"key_id": tkid}, {"$set": {"muted": False}, "$unset": {"muted_at": ""}})
            rollback_applied = True
        elif event == "unmute":
            await db.device_keys.update_one({"key_id": tkid}, {"$set": {"muted": True, "muted_at": _now_iso()}})
            rollback_applied = True
        elif event == "exclude":
            await db.device_keys.update_one({"key_id": tkid}, {"$unset": {"excluded_until": "", "excluded_reason": ""}})
            rollback_applied = True
        elif event == "ban":
            await db.device_keys.update_one({"key_id": tkid}, {"$set": {"banned": False}, "$unset": {"banned_at": ""}})
            rollback_applied = True
        elif event == "unban":
            await db.device_keys.update_one({"key_id": tkid}, {"$set": {"banned": True, "banned_at": _now_iso()}})
            rollback_applied = True
        elif event == "force_visitor_on":
            await db.device_keys.update_one({"key_id": tkid}, {"$set": {"force_visitor": False}})
            rollback_applied = True
        elif event == "force_visitor_off":
            await db.device_keys.update_one({"key_id": tkid}, {"$set": {"force_visitor": True}})
            rollback_applied = True
        elif event == "rename_pseudo":
            prev = (dec.get("extra") or {}).get("previous_pseudo")
            if prev:
                await db.device_keys.update_one({"key_id": tkid}, {"$set": {"pseudo": prev, "label": prev}})
                rollback_applied = True

        await db.staff_decisions.update_one(
            {"decision_id": payload.decision_id},
            {"$set": {"status": "reverted", "reviewed_at": _now_iso(), "reviewed_by": payload.key_id,
                      "rollback_applied": rollback_applied}},
        )
        # Nettoie le flag si plus aucune pending.
        remaining = await db.staff_decisions.count_documents(
            {"target_key_id": tkid, "status": "pending"},
        )
        if remaining == 0:
            await db.device_keys.update_one({"key_id": tkid}, {"$unset": {"pending_creator_review": ""}})

        return {"reverted": True, "decision_id": payload.decision_id, "rollback_applied": rollback_applied}

    return router
