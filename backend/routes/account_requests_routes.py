"""iter158.1 — Demandes entre comptes RÉELLES (non simulées).

Workflow complet initié par le DEMANDEUR :
  create → stockage statut → notification → validation/refus par une personne
  AUTORISÉE → application réelle du changement côté serveur → journalisation.

Types (`kind`) :
  - device_validation : faire valider son appareil (pending → approved)
  - go_private        : passage en clé privée (approved)
  - role_modo         : demande de rôle Modérateur
  - role_admin        : demande de rôle Admin
  - role_creator      : demande de rôle Créa (visible) — approbation PROPRIÉTAIRE requise ;
                        n'accorde JAMAIS la propriété réelle.

Sécurité :
  - Toutes les routes exigent une signature ECDSA valide.
  - L'approbation vérifie CÔTÉ SERVEUR que l'approbateur a le droit d'accorder
    ce rôle précis (matrice). role_creator → appareil propriétaire réel uniquement.
  - Les infos privées (email, clé publique) ne fuient jamais dans /pending ou /mine.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

VALID_KINDS = {"device_validation", "go_private", "role_modo", "role_admin", "role_creator"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _SignedIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


class CreateIn(_SignedIn):
    kind: str
    message: Optional[str] = None


class DecideIn(_SignedIn):
    request_id: str
    decision: str  # approve | refuse


def _can_approve(kind: str, actor_role: str, actor_sk: Optional[str], actor_is_owner: bool) -> bool:
    is_creator = actor_role == "creator"
    is_admin = actor_sk == "admin"
    if kind == "role_creator":
        return actor_is_owner            # propriétaire réel UNIQUEMENT
    if kind == "role_admin":
        return is_creator                # seule une Créa accorde Admin
    if kind in ("device_validation", "go_private", "role_modo"):
        return is_creator or is_admin    # Créa ou Admin
    return False


def _sanitize(req: Dict[str, Any]) -> Dict[str, Any]:
    """N'expose QUE des champs publics — jamais email ni clé publique."""
    return {
        "request_id": req.get("request_id"),
        "kind": req.get("kind"),
        "status": req.get("status"),
        "from_key_id": req.get("from_key_id"),
        "from_pseudo": req.get("from_pseudo"),
        "from_public_handle": req.get("from_public_handle"),
        "from_role": req.get("from_role"),
        "message": req.get("message"),
        "created_at": req.get("created_at"),
        "decided_at": req.get("decided_at"),
        "decided_by_kind": req.get("decided_by_kind"),
    }


def build_account_requests_router(db, *, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Account Requests"])

    async def _dev(key_id: str) -> Dict[str, Any]:
        return await db.device_keys.find_one({"key_id": key_id}, {"_id": 0}) or {}

    @router.post("/requests/create")
    async def create_request(payload: CreateIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.kind not in VALID_KINDS:
            raise HTTPException(status_code=400, detail="Type de demande invalide.")
        # Anti-doublon : une seule demande pending par (from, kind).
        existing = await db.role_requests.find_one(
            {"from_key_id": payload.key_id, "kind": payload.kind, "status": "pending"}, {"_id": 0},
        )
        if existing:
            return {"ok": True, "status": "pending", "request_id": existing["request_id"], "duplicate": True}
        doc = {
            "request_id": f"rr_{uuid.uuid4().hex[:14]}",
            "kind": payload.kind,
            "status": "pending",
            "from_key_id": payload.key_id,
            "from_pseudo": dev.get("pseudo") or dev.get("label"),
            "from_public_handle": dev.get("public_handle"),
            "from_role": dev.get("role"),
            "message": (payload.message or "")[:300],
            "created_at": _now(),
        }
        await db.role_requests.insert_one(doc)
        # Notification côté demandeur = /requests/mine ; côté approbateur = /requests/pending.
        return {"ok": True, "status": "pending", "request_id": doc["request_id"]}

    @router.post("/requests/mine")
    async def my_requests(payload: _SignedIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        rows = await db.role_requests.find(
            {"from_key_id": payload.key_id}, {"_id": 0},
        ).sort("created_at", -1).limit(50).to_list(length=50)
        return {"requests": [_sanitize(r) for r in rows]}

    @router.post("/requests/pending")
    async def pending_requests(payload: _SignedIn):
        actor = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        from utils.ownership_guard import is_owner_device
        actor_is_owner = await is_owner_device(db, payload.key_id)
        actor_role = actor.get("role")
        actor_sk = actor.get("staff_kind")
        rows = await db.role_requests.find({"status": "pending"}, {"_id": 0}).sort("created_at", 1).to_list(length=200)
        # Ne montrer QUE les demandes que cet approbateur a le droit de traiter.
        visible = [r for r in rows if _can_approve(r["kind"], actor_role, actor_sk, actor_is_owner)]
        return {"requests": [_sanitize(r) for r in visible]}

    @router.post("/requests/decide")
    async def decide_request(payload: DecideIn):
        actor = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.decision not in ("approve", "refuse"):
            raise HTTPException(status_code=400, detail="decision doit être 'approve' ou 'refuse'.")
        req = await db.role_requests.find_one({"request_id": payload.request_id, "status": "pending"}, {"_id": 0})
        if not req:
            raise HTTPException(status_code=404, detail="Demande introuvable ou déjà traitée.")
        from utils.ownership_guard import is_owner_device
        actor_is_owner = await is_owner_device(db, payload.key_id)
        if not _can_approve(req["kind"], actor.get("role"), actor.get("staff_kind"), actor_is_owner):
            raise HTTPException(status_code=403, detail="Tu n'es pas autorisé à traiter ce type de demande.")

        new_status = "approved" if payload.decision == "approve" else "refused"
        applied = None
        if payload.decision == "approve":
            kind = req["kind"]
            target = req["from_key_id"]
            if kind in ("device_validation", "go_private"):
                await db.device_keys.update_one({"key_id": target}, {"$set": {"role": "approved", "approved_at": _now()}})
                applied = "approved"
            elif kind == "role_modo":
                await db.device_keys.update_one({"key_id": target}, {"$set": {"role": "approved", "staff_kind": "modo", "promoted_at": _now()}})
                applied = "modo"
            elif kind == "role_admin":
                await db.device_keys.update_one({"key_id": target}, {"$set": {"role": "approved", "staff_kind": "admin", "promoted_at": _now()}})
                applied = "admin"
            elif kind == "role_creator":
                # Rôle VISIBLE creator uniquement — JAMAIS la propriété réelle.
                await db.device_keys.update_one({"key_id": target}, {"$set": {"role": "creator", "is_delegate_creator": True, "promoted_at": _now()}})
                applied = "creator_visible"
        await db.role_requests.update_one(
            {"request_id": payload.request_id},
            {"$set": {"status": new_status, "decided_at": _now(),
                      "decided_by_key_id": payload.key_id,
                      "decided_by_kind": "creator" if actor.get("role") == "creator" else (actor.get("staff_kind") or actor.get("role")),
                      "applied": applied}},
        )
        await db.role_requests_log.insert_one({
            "log_id": f"rrl_{uuid.uuid4().hex[:12]}",
            "request_id": payload.request_id, "kind": req["kind"],
            "target_key_id": req["from_key_id"], "decision": new_status,
            "actor_key_id": payload.key_id, "applied": applied, "ts": _now(),
        })
        return {"ok": True, "status": new_status, "applied": applied}

    return router
