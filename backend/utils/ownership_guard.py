"""iter158 — Propriété réelle (Ownership) INDÉPENDANTE des rôles.

Cahier des charges (phase finale) :
  - Séparer strictement « rôle visible », « permissions » et « propriétaire réel ».
  - Le rôle `creator` (visible) ne confère PLUS à lui seul la propriété.
  - La propriété est une entité dédiée (collection `ownership`, _id='root')
    reliant l'espace Créa à des APPAREILS propriétaires (owner_key_ids) et un
    utilisateur propriétaire (owner_user_id).
  - Une Créa déléguée (delegate) administre selon des permissions accordées
    mais ne peut JAMAIS : remplacer le propriétaire, retirer la propriété,
    supprimer un appareil propriétaire, ni bloquer la récupération.
  - Toute action critique est vérifiée CÔTÉ SERVEUR via cette table + une
    authentification renforcée (challenge lié à l'action, double signature).

Ce module ne contient QUE des helpers de lecture/garde. Les endpoints et la
logique de challenge/signature vivent dans `routes/ownership_routes.py`.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException

from utils.founder_guard import get_founder_key_ids

OWNERSHIP_ID = "root"

# Permissions qu'un propriétaire peut déléguer à une Créa déléguée.
DELEGATE_PERMISSIONS = {
    "manage_site",        # config du site, annonces, sondages
    "manage_staff",       # promouvoir/rétrograder modo/admin
    "moderate",           # actions de modération
    "approve_exports",    # valider les demandes d'export
    "manage_bots",        # gérer les bots/IA
}

# Actions critiques qui exigent une auth renforcée liée à l'action.
CRITICAL_ACTIONS = {
    "transfer_ownership",
    "remove_owner_device",
    "add_owner_device",
    "revoke_owner",
    "grant_full_control",
    "rotate_recovery",
}

# Sous-ensemble exigeant une DOUBLE signature (2 appareils propriétaires).
DOUBLE_SIG_ACTIONS = {
    "transfer_ownership",
    "remove_owner_device",
    "revoke_owner",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recovery_pepper() -> bytes:
    """Pepper serveur (env dédiée, fallback stable dérivé de SECRET_KEY)."""
    raw = os.environ.get("OWNERSHIP_RECOVERY_PEPPER") or os.environ.get("SECRET_KEY") or "codeforge-ownership"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def hash_recovery_code(code: str, salt: Optional[str] = None) -> Dict[str, str]:
    """PBKDF2-HMAC-SHA256 (200k) + pepper. Renvoie {salt, hash}."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        (code.strip() + _recovery_pepper().hex()).encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    )
    return {"salt": salt, "hash": dk.hex()}


def verify_recovery_code(code: str, salt: str, expected_hash: str) -> bool:
    got = hash_recovery_code(code, salt)["hash"]
    return hmac.compare_digest(got, expected_hash)


def gen_recovery_code() -> str:
    """Code de récupération lisible : 4 groupes de 5 caractères base32."""
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alpha) for _ in range(5)) for _ in range(4)]
    return "-".join(groups)


async def get_ownership(db) -> Optional[Dict[str, Any]]:
    return await db.ownership.find_one({"_id": OWNERSHIP_ID})


async def ensure_ownership(db) -> Dict[str, Any]:
    """Bootstrap idempotent : crée la propriété racine à partir des créas
    fondatrices figées si elle n'existe pas encore. Ne génère PAS de code de
    récupération ici (fait via /ownership/init pour le renvoyer une seule fois)."""
    doc = await get_ownership(db)
    if doc:
        return doc
    founder_keys = sorted(get_founder_key_ids())
    if not founder_keys:
        # fallback : créas existantes en base
        creators = await db.device_keys.find(
            {"role": "creator"}, {"_id": 0, "key_id": 1},
        ).to_list(length=10)
        founder_keys = sorted({c["key_id"] for c in creators if c.get("key_id")})
    owner_user_id = None
    if founder_keys:
        first = await db.device_keys.find_one({"key_id": founder_keys[0]}, {"_id": 0, "user_id": 1})
        owner_user_id = (first or {}).get("user_id")
    doc = {
        "_id": OWNERSHIP_ID,
        "crea_id": OWNERSHIP_ID,
        "owner_user_id": owner_user_id,
        "owner_key_ids": founder_keys,
        "delegates": [],
        "recovery_code_hash": None,
        "recovery_salt": None,
        "recovery_set_at": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.ownership.update_one(
        {"_id": OWNERSHIP_ID}, {"$setOnInsert": doc}, upsert=True,
    )
    return await get_ownership(db) or doc


async def owner_key_ids(db) -> Set[str]:
    doc = await get_ownership(db)
    keys = set((doc or {}).get("owner_key_ids") or [])
    # Les fondatrices sont TOUJOURS propriétaires (garde-fou anti-usurpation).
    keys |= get_founder_key_ids()
    return keys


async def is_owner_device(db, key_id: Optional[str]) -> bool:
    if not key_id:
        return False
    return key_id in (await owner_key_ids(db))


async def get_delegate(db, key_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not key_id:
        return None
    doc = await get_ownership(db)
    for d in (doc or {}).get("delegates") or []:
        if d.get("key_id") == key_id:
            return d
    return None


async def has_delegate_perm(db, key_id: Optional[str], perm: str) -> bool:
    if await is_owner_device(db, key_id):
        return True
    d = await get_delegate(db, key_id)
    if not d:
        return False
    perms = d.get("perms") or []
    return perm in perms or "full_control" in perms


async def assert_not_owner_target(db, target_key_id: Optional[str], actor_key_id: Optional[str], action: str = "action") -> None:
    """Empêche TOUTE action administrative (ban, demote, delete, revoke...)
    contre un APPAREIL PROPRIÉTAIRE si l'acteur n'est pas lui-même propriétaire.

    → Une Créa déléguée (ou un admin) ne peut jamais toucher un appareil
    propriétaire. Seul un propriétaire peut agir sur un autre propriétaire, et
    uniquement via les endpoints /ownership/* (auth renforcée)."""
    if not await is_owner_device(db, target_key_id):
        return
    # La cible EST un appareil propriétaire.
    if not await is_owner_device(db, actor_key_id):
        raise HTTPException(
            status_code=403,
            detail=f"Appareil propriétaire protégé — {action} interdite (auth propriétaire requise).",
        )
    # Même entre propriétaires, les actions destructives passent par /ownership/*.
    raise HTTPException(
        status_code=403,
        detail="Action sur un appareil propriétaire : utilise le module Propriété (auth renforcée).",
    )


async def log_ownership_event(db, event: str, actor_key_id: Optional[str],
                               detail: Optional[Dict[str, Any]] = None) -> None:
    await db.ownership_audit.insert_one({
        "event": event,
        "actor_key_id": actor_key_id,
        "detail": detail or {},
        "ts": _now_iso(),
    })
