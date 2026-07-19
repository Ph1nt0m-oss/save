"""iter144 — Founder creators protection.

Les 2 créas fondatrices sont intouchables : aucune action administrative
(bannir, exclure, déconnecter, retirer rôle, changer permissions, etc.)
ne peut être exécutée sur leurs `key_id`. Cette liste est chargée depuis
`FOUNDER_CREATOR_KEYS` (env ou fichier `founder_creators.json`).

Note importante : au premier boot où aucun founder n'est enregistré,
`register_current_creators_as_founders` scanne `device_keys` et fige les
`role='creator'` existants comme fondateurs. Une fois figés, aucune
modification n'est possible sans intervention manuelle sur le fichier
config (protection anti-usurpation).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Set

_CONFIG_PATH = Path(__file__).resolve().parent / "founder_creators.json"


def _load_from_env() -> Set[str]:
    raw = os.environ.get("FOUNDER_CREATOR_KEYS", "").strip()
    if not raw:
        return set()
    return {k.strip() for k in raw.split(",") if k.strip()}


def _load_from_file() -> Set[str]:
    if not _CONFIG_PATH.exists():
        return set()
    try:
        data = json.loads(_CONFIG_PATH.read_text())
        return set(data.get("key_ids") or [])
    except Exception:
        return set()


def get_founder_key_ids() -> Set[str]:
    """Union env + fichier."""
    return _load_from_env() | _load_from_file()


def is_founder(key_id: str | None) -> bool:
    if not key_id:
        return False
    return key_id in get_founder_key_ids()


async def register_current_creators_as_founders(db) -> Set[str]:
    """Idempotent — fige les créas existantes comme fondatrices SI aucune
    n'est encore enregistrée. Écrit dans founder_creators.json. Renvoie la
    liste courante des fondatrices."""
    current = get_founder_key_ids()
    if current:
        return current
    creators = await db.device_keys.find(
        {"role": "creator"}, {"_id": 0, "key_id": 1},
    ).to_list(length=10)
    key_ids = sorted({c["key_id"] for c in creators if c.get("key_id")})
    if not key_ids:
        return set()
    _CONFIG_PATH.write_text(json.dumps({"key_ids": key_ids, "frozen_at": None}, indent=2))
    return set(key_ids)


def assert_not_founder(target_key_id: str | None, action: str = "action") -> None:
    """Lève HTTPException 403 si la cible est une créa fondatrice."""
    from fastapi import HTTPException
    if is_founder(target_key_id):
        raise HTTPException(
            status_code=403,
            detail=f"Créa fondatrice — {action} interdite.",
        )
