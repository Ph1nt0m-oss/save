"""iter158 — Gestion centralisée des sanctions (durée + expiration auto).

Unifie les DEUX schémas de nommage historiques :
  - legacy (accounts_routes) : `excluded_until`, `force_visitor`
  - unifié (staff_actions)    : `exclude_until`, `force_visitor_until`,
                                `disconnect_until`, `muted`

Règles :
  - Une sanction temporisée expirée est AUTOMATIQUEMENT levée (unset en DB) →
    retour à l'état normal sans intervention.
  - `banned` (booléen) et rôles `blocked`/`revoked` restent persistants.
  - `muted` est persistant jusqu'à `unmute` (pas de durée par défaut) sauf si
    `muted_until` est présent (alors temporisé).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

# Champs "…_until" temporisés → clé d'état exposée au front.
_TIMED_FIELDS = {
    "exclude_until": "excluded",
    "excluded_until": "excluded",   # legacy
    "force_visitor_until": "force_visitor",
    "disconnect_until": "disconnected",
    "muted_until": "muted",
    "mute_until": "muted",
}


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


async def evaluate_sanctions(db, dev: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-expire les sanctions temporisées en DB et renvoie l'état courant.

    Retourne un dict :
      { banned, blocked, revoked, excluded, force_visitor, muted, disconnected,
        exclude_until, force_visitor_until, disconnect_until }
    """
    now = datetime.now(timezone.utc)
    key_id = dev.get("key_id")
    unset: Dict[str, str] = {}
    active: Dict[str, str] = {}

    for field, state in _TIMED_FIELDS.items():
        val = dev.get(field)
        if not val:
            continue
        exp = _parse(val)
        if exp is None or exp <= now:
            # expiré ou illisible → on lève la sanction
            unset[field] = ""
            unset[field.replace("_until", "_reason")] = ""
        else:
            active[state] = val

    if unset and key_id:
        await db.device_keys.update_one({"key_id": key_id}, {"$unset": unset})

    role = dev.get("role")
    # `force_visitor` peut aussi être un simple booléen legacy persistant.
    force_visitor_bool = bool(dev.get("force_visitor", False))

    return {
        "banned": bool(dev.get("banned")) or role == "banned",
        "blocked": role == "blocked",
        "revoked": role == "revoked",
        "excluded": "excluded" in active,
        "muted": bool(dev.get("muted")) or "muted" in active,
        "force_visitor": force_visitor_bool or "force_visitor" in active,
        "disconnected": "disconnected" in active,
        "exclude_until": active.get("excluded"),
        "force_visitor_until": active.get("force_visitor"),
        "disconnect_until": active.get("disconnected"),
    }
