"""iter158 — Environnement de test Sandbox (multi-rôles / multi-appareils).

Objectif : permettre au PROPRIÉTAIRE réel de tester l'application comme un
utilisateur réel, en incarnant instantanément plusieurs profils fictifs, sans
autres appareils physiques et SANS toucher aux données réelles.

Sécurité :
  - Activable UNIQUEMENT si `CODEFORGE_TEST_MODE` est vrai (dev/préprod).
  - Réservé aux APPAREILS PROPRIÉTAIRES réels (table ownership).
  - Toutes les entités créées portent `sandbox: True` → isolées des vraies
    données ; `POST /sandbox/teardown` les supprime intégralement.
  - Les paires de clés ECDSA fictives sont générées côté serveur et renvoyées
    au navigateur du propriétaire pour l'incarnation (signatures réelles). Ces
    clés n'existent QUE dans le sandbox et n'ont aucune valeur en production.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from device_auth import compute_key_id
from utils.ownership_guard import ensure_ownership, is_owner_device

SANDBOX_TAG = "sandbox"


def sandbox_enabled() -> bool:
    return str(os.environ.get("CODEFORGE_TEST_MODE", "")).strip().lower() in ("1", "true", "yes", "on")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_uint(n: int) -> str:
    length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).decode().rstrip("=")


def _gen_keypair() -> Dict[str, Any]:
    """Génère une paire ECDSA P-256 et exporte les JWK public + privé."""
    priv = ec.generate_private_key(ec.SECP256R1())
    nums = priv.private_numbers()
    pub = nums.public_numbers
    pub_jwk = {"kty": "EC", "crv": "P-256", "x": _b64url_uint(pub.x), "y": _b64url_uint(pub.y)}
    priv_jwk = {**pub_jwk, "d": _b64url_uint(nums.private_value)}
    return {"public_jwk": pub_jwk, "private_jwk": priv_jwk, "key_id": compute_key_id(pub_jwk)}


# Les 9 profils fictifs demandés par le cahier des charges.
SANDBOX_PROFILES = [
    {"slug": "owner",     "pseudo": "SBX Créa Propriétaire", "handle": "sbx_owner",   "role": "creator",  "staff_kind": None,    "is_owner": True},
    {"slug": "delegate",  "pseudo": "SBX Créa Déléguée",     "handle": "sbx_delegue", "role": "creator",  "staff_kind": None,    "is_delegate": True},
    {"slug": "admin",     "pseudo": "SBX Admin",             "handle": "sbx_admin",   "role": "approved", "staff_kind": "admin"},
    {"slug": "modo",      "pseudo": "SBX Modérateur",        "handle": "sbx_modo",    "role": "approved", "staff_kind": "modo"},
    {"slug": "approved",  "pseudo": "SBX Utilisateur Validé","handle": "sbx_valide",  "role": "approved", "staff_kind": None},
    {"slug": "pending",   "pseudo": "SBX Utilisateur",       "handle": "sbx_user",    "role": "pending",  "staff_kind": None},
    {"slug": "guest",     "pseudo": "SBX Invité",            "handle": "sbx_invite",  "role": "inactive", "staff_kind": None},
    {"slug": "muted",     "pseudo": "SBX Sanctionné (mute)", "handle": "sbx_mute",    "role": "approved", "staff_kind": None, "sanction": "muted"},
    {"slug": "excluded",  "pseudo": "SBX Sanctionné (excl.)","handle": "sbx_exclu",   "role": "approved", "staff_kind": None, "sanction": "excluded"},
    {"slug": "banned",    "pseudo": "SBX Banni",             "handle": "sbx_banni",   "role": "banned",   "staff_kind": None},
]


class _SignedIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


def build_sandbox_router(db, *, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Sandbox"])

    async def _require_owner_and_mode(payload: _SignedIn) -> Dict[str, Any]:
        if not sandbox_enabled():
            raise HTTPException(status_code=403, detail="Mode test désactivé (CODEFORGE_TEST_MODE requis).")
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        await ensure_ownership(db)
        if not await is_owner_device(db, payload.key_id):
            raise HTTPException(status_code=403, detail="Réservé au propriétaire réel.")
        return dev

    @router.post("/sandbox/status")
    async def sandbox_status(payload: _SignedIn):
        if not sandbox_enabled():
            return {"enabled": False, "accounts": []}
        await _require_owner_and_mode(payload)
        accts = await db.device_keys.find(
            {"sandbox": True}, {"_id": 0, "public_key_jwk": 0},
        ).to_list(length=100)
        return {"enabled": True, "count": len(accts), "accounts": accts}

    @router.post("/sandbox/seed")
    async def sandbox_seed(payload: _SignedIn):
        await _require_owner_and_mode(payload)
        # Idempotent : purge d'abord.
        await _teardown(db)
        created: List[Dict[str, Any]] = []
        keys_by_slug: Dict[str, Dict[str, Any]] = {}
        for prof in SANDBOX_PROFILES:
            kp = _gen_keypair()
            uid = f"sbxu_{uuid.uuid4().hex[:10]}"
            doc: Dict[str, Any] = {
                "key_id": kp["key_id"],
                "public_key_jwk": kp["public_jwk"],
                "role": prof["role"],
                "staff_kind": prof.get("staff_kind"),
                "pseudo": prof["pseudo"],
                "public_handle": prof["handle"],
                "public_handle_lower": prof["handle"].lower(),
                "label": f"Sandbox · {prof['slug']}",
                "user_id": uid,
                "sandbox": True,
                "sandbox_slug": prof["slug"],
                "created_at": _now().isoformat(),
            }
            if prof.get("is_delegate"):
                doc["is_delegate_creator"] = True
            if prof.get("is_owner"):
                doc["sandbox_owner"] = True
            # Sanctions.
            if prof.get("sanction") == "muted":
                doc["muted"] = True
                doc["muted_at"] = _now().isoformat()
                doc["mute_reason"] = "Sandbox — mute de démonstration"
            if prof.get("sanction") == "excluded":
                doc["exclude_until"] = (_now() + timedelta(hours=1)).isoformat()
                doc["exclude_at"] = _now().isoformat()
                doc["exclude_reason"] = "Sandbox — exclusion temporaire (1h)"
            if prof["role"] == "banned":
                doc["banned"] = True
                doc["banned_at"] = _now().isoformat()
                doc["ban_reason"] = "Sandbox — bannissement de démonstration"
            await db.device_keys.insert_one(doc)
            await db.users.insert_one({
                "user_id": uid, "email": f"{prof['handle']}@sandbox.local",
                "pseudo": prof["pseudo"], "verified": True, "sandbox": True,
                "created_at": _now().isoformat(),
            })
            keys_by_slug[prof["slug"]] = kp
            created.append({"slug": prof["slug"], "key_id": kp["key_id"],
                            "pseudo": prof["pseudo"], "role": prof["role"],
                            "staff_kind": prof.get("staff_kind")})

        # Données réalistes isolées : conversations privées, mentions, notifs, demandes.
        await _seed_interactions(db, keys_by_slug)

        # Renvoie les paires de clés (privées incluses) pour incarnation.
        incarnations = [{
            "slug": s, "key_id": kp["key_id"],
            "public_jwk": kp["public_jwk"], "private_jwk": kp["private_jwk"],
        } for s, kp in keys_by_slug.items()]
        return {"ok": True, "created": created, "incarnations": incarnations}

    @router.post("/sandbox/keys")
    async def sandbox_keys(payload: _SignedIn):
        """Re-génère l'accès aux clés privées : impossible (les privées ne sont
        pas stockées). Le propriétaire doit re-seed pour obtenir de nouvelles clés."""
        await _require_owner_and_mode(payload)
        raise HTTPException(status_code=409, detail="Les clés privées ne sont renvoyées qu'au seed. Relance /sandbox/seed.")

    @router.post("/sandbox/teardown")
    async def sandbox_teardown(payload: _SignedIn):
        await _require_owner_and_mode(payload)
        report = await _teardown(db)
        return {"ok": True, "deleted": report}

    return router


async def _seed_interactions(db, keys: Dict[str, Dict[str, Any]]) -> None:
    now = _now().isoformat()

    def kid(slug: str) -> Optional[str]:
        return (keys.get(slug) or {}).get("key_id")

    # Discussion privée owner ↔ approved.
    conv_id = f"sbxdm_{uuid.uuid4().hex[:10]}"
    for txt, frm in [("Bonjour, ceci est un test privé sandbox.", "owner"),
                     ("Bien reçu côté utilisateur validé !", "approved")]:
        await db.private_messages.insert_one({
            "message_id": f"sbxmsg_{uuid.uuid4().hex[:10]}", "conversation_id": conv_id,
            "from_key_id": kid(frm), "to_key_id": kid("approved" if frm == "owner" else "owner"),
            "content": txt, "sandbox": True, "ts": now,
        })
    # Mention de l'utilisateur validé dans un groupe public.
    await db.mention_notifications.insert_one({
        "notif_id": f"sbxmn_{uuid.uuid4().hex[:10]}", "to_key_id": kid("approved"),
        "from_key_id": kid("admin"), "group_type": "public",
        "text": "@sbx_valide bienvenue dans le salon !", "read": False,
        "sandbox": True, "ts": now,
    })
    # Demandes entre comptes : validation appareil + rôle modo + rôle admin.
    for req_kind, requester in [("device_validation", "pending"),
                                ("role_modo", "approved"),
                                ("role_admin", "modo")]:
        await db.account_requests.insert_one({
            "request_id": f"sbxreq_{uuid.uuid4().hex[:10]}", "kind": req_kind,
            "from_key_id": kid(requester), "status": "pending",
            "sandbox": True, "ts": now,
        })
    # Un projet fictif + une demande d'export en attente.
    pid = f"sbxproj_{uuid.uuid4().hex[:10]}"
    await db.projects.insert_one({
        "project_id": pid, "user_id": (keys.get("approved") or {}).get("key_id"),
        "name": "Projet Sandbox Démo", "sandbox": True, "created_at": now,
    })
    await db.export_requests.insert_one({
        "request_id": f"sbxexp_{uuid.uuid4().hex[:10]}", "project_id": pid,
        "requester_key_id": kid("approved"), "kind": "source", "status": "pending",
        "sandbox": True, "ts": now,
    })


async def _teardown(db) -> Dict[str, int]:
    report: Dict[str, int] = {}
    for coll in ("device_keys", "users", "private_messages", "mention_notifications",
                 "account_requests", "projects", "export_requests"):
        res = await db[coll].delete_many({"sandbox": True})
        report[coll] = res.deleted_count
    return report
