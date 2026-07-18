"""iter140 — Routes /social/member/* + /social/invisible/* (Phase 2 & 3).

Phase 2 — 6 actions par membre (dans groupes + messages privés) :
  - mute        : mute la personne pour l'appelant uniquement (impossible
                  sur un supérieur hiérarchique — sauf notif OFF).
  - notif_off   : coupe les notifs (fonctionne aussi sur supérieurs).
  - block       : bloque les demandes d'ami / messages entrants.
  - report      : signale la personne (log dans db.reports).
  - friend_req  : envoie une demande de clé en ami (délègue à /friends/request).
  - delete_msg  : supprime un message (le message reste visible côté créa).

Phase 3 — Mode invisible admin/créa :
  - PUT /social/invisible : bascule le mode invisible pour un group_type
                            donné (staff = interdit sauf pour admin, créa
                            reste toujours visible dans staff).
  - GET /social/invisible : renvoie l'état courant pour l'appelant.

Toutes les routes signées ECDSA. Stockage :
  db.social_prefs { key_id, target_key_id, mutes:[], notif_off:[], blocks:[] }
  db.reports      { report_id, actor_key_id, target_key_id, reason, ts }
  db.invisible_flags { key_id, group_type, enabled, ts }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


# Ordre hiérarchique : utilisateurs < privé < modo < admin < créa
# Invités hors classement (ils sont en lecture seule, ne participent pas).
HIERARCHY = {"users": 1, "private": 2, "modo": 3, "admin": 4, "creator": 5}


def _tier(dev: dict) -> int:
    if not dev:
        return 0
    if dev.get("role") == "creator":
        return HIERARCHY["creator"]
    sk = dev.get("staff_kind")
    if sk == "admin":
        return HIERARCHY["admin"]
    if sk == "modo":
        return HIERARCHY["modo"]
    if dev.get("role") == "approved":
        return HIERARCHY["private"]
    if dev.get("role") == "pending":
        return HIERARCHY["users"]
    return 0  # guest / unknown


class _SignedIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class MemberActionIn(_SignedIn):
    target_key_id: str
    action: str  # mute | unmute | notif_off | notif_on | block | unblock | report | friend_req
    reason: Optional[str] = None


class InvisibleToggleIn(_SignedIn):
    group_type: str
    enabled: bool


class AnonymousToggleIn(_SignedIn):
    enabled: bool


class SunModeToggleIn(_SignedIn):
    enabled: bool  # true = Soleil (voit tout), false = Nuit (respecte anonymat)


def build_social_member_router(db, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Social-Members"])

    async def _get_dev(key_id: str) -> dict:
        d = await db.device_keys.find_one({"key_id": key_id}, {"_id": 0})
        if not d:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        return d

    @router.post("/social/member/action")
    async def member_action(payload: MemberActionIn):
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        target = await _get_dev(payload.target_key_id)
        if me["key_id"] == target["key_id"]:
            raise HTTPException(status_code=400, detail="Auto-action interdite.")

        action = payload.action
        if action == "mute":
            # iter140 — mute impossible sur un supérieur hiérarchique.
            if _tier(target) > _tier(me):
                raise HTTPException(status_code=403, detail="Impossible de mute un supérieur hiérarchique (utilise 'notif_off' à la place).")
            await db.social_prefs.update_one(
                {"key_id": payload.key_id},
                {"$addToSet": {"mutes": payload.target_key_id}},
                upsert=True,
            )
            return {"ok": True, "action": "mute"}

        if action == "unmute":
            await db.social_prefs.update_one(
                {"key_id": payload.key_id}, {"$pull": {"mutes": payload.target_key_id}}, upsert=True,
            )
            return {"ok": True, "action": "unmute"}

        if action in ("notif_off", "notif_on"):
            op = "$addToSet" if action == "notif_off" else "$pull"
            await db.social_prefs.update_one(
                {"key_id": payload.key_id}, {op: {"notif_off": payload.target_key_id}}, upsert=True,
            )
            return {"ok": True, "action": action}

        if action in ("block", "unblock"):
            op = "$addToSet" if action == "block" else "$pull"
            await db.social_prefs.update_one(
                {"key_id": payload.key_id}, {op: {"blocks": payload.target_key_id}}, upsert=True,
            )
            return {"ok": True, "action": action}

        if action == "report":
            await db.reports.insert_one({
                "report_id": f"rp_{uuid.uuid4().hex[:12]}",
                "actor_key_id": payload.key_id,
                "target_key_id": payload.target_key_id,
                "reason": (payload.reason or "")[:500],
                "ts": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            })
            return {"ok": True, "action": "report"}

        if action == "friend_req":
            # Délègue à /friends/request logique.
            existing = await db.friend_requests.find_one(
                {"from_key_id": payload.key_id, "to_key_id": payload.target_key_id, "status": "pending"},
                {"_id": 0},
            )
            if existing:
                return {"ok": True, "action": "friend_req", "already_pending": True}
            await db.friend_requests.insert_one({
                "request_id": f"fr_{uuid.uuid4().hex[:12]}",
                "from_key_id": payload.key_id,
                "to_key_id": payload.target_key_id,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"ok": True, "action": "friend_req"}

        raise HTTPException(status_code=400, detail="Action inconnue.")

    @router.post("/social/member/prefs")
    async def member_prefs(payload: _SignedIn):
        """Retourne les listes mutes / notif_off / blocks de l'appelant."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        p = await db.social_prefs.find_one({"key_id": payload.key_id}, {"_id": 0}) or {}
        return {
            "mutes": p.get("mutes", []),
            "notif_off": p.get("notif_off", []),
            "blocks": p.get("blocks", []),
        }

    # ---- Phase 3 — Mode invisible admin/créa ----

    @router.put("/social/invisible")
    async def invisible_toggle(payload: InvisibleToggleIn):
        """iter140 Phase 3 — Bascule mode invisible pour un group_type.

        Règles :
          - Seuls admins + créa peuvent activer le mode invisible.
          - Créa dans le groupe 'staff' : REFUSÉ (présence obligatoire).
          - Le mode est par (key_id, group_type) — on peut être invisible
            dans un groupe et visible dans un autre.
        """
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if not (me.get("role") == "creator" or me.get("staff_kind") == "admin"):
            raise HTTPException(status_code=403, detail="Mode invisible réservé aux admins et à la créa.")
        if me.get("role") == "creator" and payload.group_type == "staff":
            raise HTTPException(status_code=403, detail="La créa doit rester visible dans le tchat Staff (présence obligatoire).")
        await db.invisible_flags.update_one(
            {"key_id": payload.key_id, "group_type": payload.group_type},
            {"$set": {"enabled": bool(payload.enabled),
                      "ts": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "group_type": payload.group_type, "enabled": bool(payload.enabled)}

    @router.post("/social/invisible/state")
    async def invisible_state(payload: _SignedIn):
        """Retourne les group_types dans lesquels l'appelant est invisible."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        rows = await db.invisible_flags.find(
            {"key_id": payload.key_id, "enabled": True}, {"_id": 0, "group_type": 1},
        ).to_list(length=50)
        return {"invisible_in": [r["group_type"] for r in rows]}

    @router.post("/social/invisible/present")
    async def invisible_present(payload: _SignedIn):
        """Renvoie true si des admins invisibles sont présents dans un groupe
        (l'appelant fournit implicitement le contexte via son propre role).
        Cette API prend en fait le group_type en query — voir GET-like via body."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        # Comme on veut lister des group_types, on renvoie un dict.
        rows = await db.invisible_flags.find(
            {"enabled": True}, {"_id": 0, "group_type": 1, "key_id": 1},
        ).to_list(length=500)
        # Groupe → nb d'admins/créas invisibles (sans exposer key_id aux non-créa).
        counts: dict = {}
        for r in rows:
            counts[r["group_type"]] = counts.get(r["group_type"], 0) + 1
        return {"invisible_counts": counts}

    # ---- iter141 — Mode Anonyme (tout le monde) + Sun/Night Mode (staff) ----

    @router.put("/social/anonymous")
    async def anonymous_toggle(payload: AnonymousToggleIn):
        """iter141 — Bascule le Mode Anonyme (disponible pour tous).
        Masque pseudo, public_handle et couleur du rôle dans les groupes,
        listes de membres et messages privés (pour tous sauf le staff en
        mode Soleil).
        """
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        await db.social_prefs.update_one(
            {"key_id": payload.key_id},
            {"$set": {"anonymous": bool(payload.enabled),
                      "anonymous_ts": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "anonymous": bool(payload.enabled)}

    @router.put("/social/sun-mode")
    async def sun_mode_toggle(payload: SunModeToggleIn):
        """iter141 — Bascule Sun/Night Mode (modo/admin/créa seulement).
        Mode Soleil (enabled=true) : révèle les pseudos/couleurs des
        utilisateurs anonymes au staff.
        Mode Nuit (enabled=false) : respecte l'anonymat, comme les autres.
        """
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        me = await _get_dev(payload.key_id)
        if not (me.get("role") == "creator" or me.get("staff_kind") in ("admin", "modo")):
            raise HTTPException(status_code=403, detail="Réservé au staff (modo/admin/créa).")
        await db.social_prefs.update_one(
            {"key_id": payload.key_id},
            {"$set": {"sun_mode": bool(payload.enabled),
                      "sun_mode_ts": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "sun_mode": bool(payload.enabled)}

    @router.post("/social/modes/state")
    async def modes_state(payload: _SignedIn):
        """iter141 — Retourne l'état des toggles Anonyme + Sun/Night."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        p = await db.social_prefs.find_one({"key_id": payload.key_id}, {"_id": 0}) or {}
        return {
            "anonymous": bool(p.get("anonymous", False)),
            "sun_mode": bool(p.get("sun_mode", False)),
        }

    return router
