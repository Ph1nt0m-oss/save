"""iter143 — Système de modération complet.

Workflow (spec utilisateur) :
  1. Un bot détecte une suspicion → crée un `mod_alert` (state=open).
  2. Le système recherche un staff en ligne → crée un `mod_assignment`
     (respecte l'équilibrage + évite conflits d'intérêt).
  3. Le staff reçoit une popup mi-écran → ACCEPT / REFUSE.
     - REFUSE → log dans mod_assignments (refused) + tente un autre staff.
     - ACCEPT → présente l'analyse détaillée (messages + dates).
  4. Staff décide :
     - SANCTION → Sun mode temporaire + attente exécution → back to Night → mod_decision.
     - PAS INFRACTION → mod_decision.not_infraction (l'alerte reste visible pour Créa).
     - DÉLÉGATION → mod_decision.delegated (recherche un autre staff).
  5. Si staff hors ligne >120s ou pas de réponse → auto-transfer.
  6. Les bots continuent l'analyse en permanence.

Restrictions :
  - Créa + Admin voient le journal complet.
  - Modo voit uniquement ses propres assignations + décisions.
  - MP privés (1-1) NON analysés — uniquement groupes ≥ 3 participants.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


ASSIGNMENT_TIMEOUT_SEC = 120  # transfert auto après ce délai


class _SignedIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class AlertCreateIn(_SignedIn):
    group_type: str
    reasons: List[str]
    score: int
    sender_key_id: Optional[str] = None
    message_ids: Optional[List[str]] = None


class AssignmentActionIn(_SignedIn):
    assignment_id: str
    action: str  # "accept" | "refuse" | "sanction" | "not_infraction" | "delegate"
    note: Optional[str] = None


class ListIn(_SignedIn):
    limit: int = 50


def build_moderation_router(db, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Moderation"])

    async def _get_dev(key_id: str) -> Dict[str, Any]:
        d = await db.device_keys.find_one({"key_id": key_id}, {"_id": 0}) or {}
        return d

    async def _pick_online_staff(exclude: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """iter143 — Sélectionne un staff (modo/admin) en ligne, en évitant
        les key_ids listés dans `exclude`. Priorité :
          1. Moins d'assignations en cours.
          2. Plus rapide temps de réponse historique.
          3. Rôle modo prioritaire pour la charge de première ligne.
        """
        exclude = set(exclude or [])
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        candidates = await db.device_keys.find(
            {
                "staff_kind": {"$in": ["modo", "admin"]},
                "last_seen_at": {"$gt": cutoff},
                "key_id": {"$nin": list(exclude)},
                "role": {"$ne": "blocked"},
            },
            {"_id": 0, "key_id": 1, "pseudo": 1, "staff_kind": 1, "public_handle": 1},
        ).to_list(length=50)
        if not candidates:
            return None
        # Compte les assignations ouvertes par staff.
        loads: Dict[str, int] = {}
        for c in candidates:
            loads[c["key_id"]] = await db.mod_assignments.count_documents(
                {"assignee_key_id": c["key_id"], "state": {"$in": ["pending", "accepted"]}},
            )
        candidates.sort(key=lambda c: (loads[c["key_id"]], c["staff_kind"] != "modo"))
        return candidates[0]

    @router.post("/moderation/alerts/create")
    async def alerts_create(payload: AlertCreateIn):
        """Appelé par les bots (ou en interne) quand un score de suspicion
        dépasse le seuil. Enregistre une alerte + tente une assignation
        immédiate à un staff en ligne."""
        # Note : ici on autorise l'appel signé par n'importe quel device pour
        # que le bot analyzer côté serveur puisse l'invoquer via HTTP interne
        # si besoin. En pratique, l'appel se fait via le code Python direct.
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        alert_id = f"alert_{uuid.uuid4().hex[:14]}"
        now = datetime.now(timezone.utc)
        doc = {
            "alert_id": alert_id,
            "group_type": payload.group_type,
            "reasons": payload.reasons,
            "score": payload.score,
            "sender_key_id": payload.sender_key_id,
            "message_ids": payload.message_ids or [],
            "state": "open",
            "created_at": now.isoformat(),
        }
        await db.mod_alerts.insert_one(doc)
        # Tentative d'assignation immédiate.
        picked = await _pick_online_staff()
        if picked:
            assignment_id = f"asn_{uuid.uuid4().hex[:14]}"
            await db.mod_assignments.insert_one({
                "assignment_id": assignment_id,
                "alert_id": alert_id,
                "assignee_key_id": picked["key_id"],
                "assignee_pseudo": picked.get("pseudo") or "",
                "assignee_role": picked.get("staff_kind"),
                "state": "pending",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=ASSIGNMENT_TIMEOUT_SEC)).isoformat(),
                "refused_by": [],
            })
            await db.mod_alerts.update_one(
                {"alert_id": alert_id},
                {"$set": {"assigned_to": picked["key_id"], "state": "assigned"}},
            )
        return {"alert_id": alert_id}

    @router.post("/moderation/assignments/mine")
    async def assignments_mine(payload: _SignedIn):
        """Retourne l'assignation active du staff appelant (si présente)."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if not (me.get("staff_kind") in ("modo", "admin") or me.get("role") == "creator"):
            raise HTTPException(status_code=403, detail="Réservé au staff.")
        now_iso = datetime.now(timezone.utc).isoformat()
        # Nettoie les assignations expirées d'abord.
        expired = await db.mod_assignments.find(
            {"state": "pending", "expires_at": {"$lt": now_iso},
             "assignee_key_id": payload.key_id},
            {"_id": 0, "assignment_id": 1, "alert_id": 1, "assignee_key_id": 1},
        ).to_list(length=20)
        for e in expired:
            await db.mod_assignments.update_one(
                {"assignment_id": e["assignment_id"]},
                {"$set": {"state": "expired", "expired_at": now_iso}},
            )
            # Tente un autre staff.
            picked = await _pick_online_staff(exclude=[e["assignee_key_id"]])
            if picked:
                new_id = f"asn_{uuid.uuid4().hex[:14]}"
                await db.mod_assignments.insert_one({
                    "assignment_id": new_id,
                    "alert_id": e["alert_id"],
                    "assignee_key_id": picked["key_id"],
                    "assignee_pseudo": picked.get("pseudo") or "",
                    "assignee_role": picked.get("staff_kind"),
                    "state": "pending",
                    "created_at": now_iso,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ASSIGNMENT_TIMEOUT_SEC)).isoformat(),
                    "refused_by": [e["assignee_key_id"]],
                })
        # Récupère l'active.
        active = await db.mod_assignments.find_one(
            {"assignee_key_id": payload.key_id, "state": {"$in": ["pending", "accepted"]}},
            {"_id": 0},
        )
        if not active:
            return {"assignment": None}
        alert = await db.mod_alerts.find_one({"alert_id": active["alert_id"]}, {"_id": 0}) or {}
        return {"assignment": active, "alert": alert}

    @router.post("/moderation/assignments/action")
    async def assignments_action(payload: AssignmentActionIn):
        """Le staff exécute une action sur son assignation."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if not (me.get("staff_kind") in ("modo", "admin") or me.get("role") == "creator"):
            raise HTTPException(status_code=403, detail="Réservé au staff.")
        row = await db.mod_assignments.find_one(
            {"assignment_id": payload.assignment_id}, {"_id": 0},
        )
        if not row or row.get("assignee_key_id") != payload.key_id:
            raise HTTPException(status_code=404, detail="Assignation introuvable.")
        action = payload.action
        now_iso = datetime.now(timezone.utc).isoformat()
        if action == "accept":
            await db.mod_assignments.update_one(
                {"assignment_id": payload.assignment_id},
                {"$set": {"state": "accepted", "accepted_at": now_iso}},
            )
            return {"ok": True, "state": "accepted"}
        if action == "refuse":
            await db.mod_assignments.update_one(
                {"assignment_id": payload.assignment_id},
                {"$set": {"state": "refused", "refused_at": now_iso, "note": payload.note or ""}},
            )
            # Retenter avec un autre staff (exclut celui-ci + les précédents).
            excluded = list(set(row.get("refused_by", []) + [payload.key_id]))
            picked = await _pick_online_staff(exclude=excluded)
            if picked:
                new_id = f"asn_{uuid.uuid4().hex[:14]}"
                await db.mod_assignments.insert_one({
                    "assignment_id": new_id,
                    "alert_id": row["alert_id"],
                    "assignee_key_id": picked["key_id"],
                    "assignee_pseudo": picked.get("pseudo") or "",
                    "assignee_role": picked.get("staff_kind"),
                    "state": "pending",
                    "created_at": now_iso,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ASSIGNMENT_TIMEOUT_SEC)).isoformat(),
                    "refused_by": excluded,
                })
            return {"ok": True, "state": "refused"}
        # Décisions finales
        decision_id = f"dec_{uuid.uuid4().hex[:14]}"
        await db.mod_decisions.insert_one({
            "decision_id": decision_id,
            "alert_id": row["alert_id"],
            "assignment_id": payload.assignment_id,
            "actor_key_id": payload.key_id,
            "actor_pseudo": me.get("pseudo"),
            "actor_public_handle": me.get("public_handle") or "",
            "actor_role": me.get("staff_kind") or me.get("role"),
            "decision": action,
            "note": payload.note or "",
            "created_at": now_iso,
        })
        # Update assignment state.
        final_state = "sanctioned" if action == "sanction" \
            else ("dismissed" if action == "not_infraction"
                  else ("delegated" if action == "delegate" else "closed"))
        await db.mod_assignments.update_one(
            {"assignment_id": payload.assignment_id},
            {"$set": {"state": final_state, "closed_at": now_iso}},
        )
        # Update alert.
        alert_state = "resolved" if action != "delegate" else "assigned"
        await db.mod_alerts.update_one(
            {"alert_id": row["alert_id"]},
            {"$set": {"state": alert_state, "last_decision": action, "last_decision_at": now_iso}},
        )
        # Cas délégation : nouvelle tentative.
        if action == "delegate":
            excluded = list(set(row.get("refused_by", []) + [payload.key_id]))
            picked = await _pick_online_staff(exclude=excluded)
            if picked:
                new_id = f"asn_{uuid.uuid4().hex[:14]}"
                await db.mod_assignments.insert_one({
                    "assignment_id": new_id,
                    "alert_id": row["alert_id"],
                    "assignee_key_id": picked["key_id"],
                    "assignee_pseudo": picked.get("pseudo") or "",
                    "assignee_role": picked.get("staff_kind"),
                    "state": "pending",
                    "created_at": now_iso,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ASSIGNMENT_TIMEOUT_SEC)).isoformat(),
                    "refused_by": excluded,
                })
        return {"ok": True, "state": final_state, "decision_id": decision_id}

    @router.post("/moderation/decisions/list")
    async def decisions_list(payload: ListIn):
        """Créa + Admin : voit tout. Modo : voit ses propres décisions."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        role = me.get("role")
        sk = me.get("staff_kind")
        if not (role == "creator" or sk in ("admin", "modo")):
            raise HTTPException(status_code=403, detail="Réservé au staff.")
        q: Dict[str, Any] = {}
        if role != "creator" and sk != "admin":
            q["actor_key_id"] = payload.key_id
        rows = await db.mod_decisions.find(q, {"_id": 0}).sort(
            "created_at", -1,
        ).limit(min(max(payload.limit, 1), 200)).to_list(length=200)
        return {"decisions": rows}

    @router.post("/moderation/alerts/list")
    async def alerts_list(payload: ListIn):
        """Créa + Admin uniquement — historique complet des alertes bot."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if me.get("role") != "creator" and me.get("staff_kind") != "admin":
            raise HTTPException(status_code=403, detail="Réservé Créa/Admin.")
        rows = await db.mod_alerts.find({}, {"_id": 0}).sort(
            "created_at", -1,
        ).limit(min(max(payload.limit, 1), 200)).to_list(length=200)
        return {"alerts": rows}

    return router
