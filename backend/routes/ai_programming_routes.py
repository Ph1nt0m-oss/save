"""iter143 — Programmation des IA : profils configurables par agent.

Chaque IA/bot possède :
  - Une fiche d'identité statique (registry.py — read-only sauf ajout).
  - Un PROFIL PROGRAMMABLE persistant en MongoDB : style d'écriture, comportement,
    domaines, limites, capacités, outils autorisés, spécialisations, prompt système
    personnalisé.
  - Un historique de VERSIONS (rollback possible).

Endpoints exposés :
  - POST /api/agents/profile/get       → renvoie profil courant (agent_id)
  - POST /api/agents/profile/save      → crée une nouvelle version (payload complet)
  - POST /api/agents/profile/versions  → liste les versions
  - POST /api/agents/profile/revert    → restaure une version antérieure

Restriction : accessible UNIQUEMENT à la Créa (signature ECDSA).
Aucune donnée sensible (clés/API secrets) ne doit transiter par ces endpoints —
les configs stockées ici sont uniquement des instructions comportementales.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.registry import AGENT_REGISTRY


class _SignedBase(BaseModel):
    key_id: str
    nonce: str
    signature: str


class GetProfileIn(_SignedBase):
    agent_id: str


class SaveProfileIn(_SignedBase):
    agent_id: str
    profile: Dict[str, Any]
    note: Optional[str] = None


class VersionsIn(_SignedBase):
    agent_id: str


class RevertIn(_SignedBase):
    agent_id: str
    version_id: str


# ---------------------------------------------------------------------------
# Champs autorisés — tout le reste est refusé (protection écriture arbitraire).
# ---------------------------------------------------------------------------
ALLOWED_FIELDS = {
    "writing_style",       # ex: "chaleureux, listes structurées"
    "behavior",            # ex: "toujours en français, tutoie"
    "domains",             # list[str] — domaines d'application
    "limits",              # list[str] — interdictions explicites
    "capabilities",        # list[str] — actions/outputs permis
    "allowed_tools",       # list[str] — outils autorisés
    "specializations",     # list[str] — spécialisations profondes
    "custom_system_prompt",  # str — prompt système override
    "response_format",     # ex: "markdown structuré, sections"
    "reasoning_mode",      # ex: "chain-of-thought interne, non exposé"
    "notes",               # str libre pour la Créa
}


def _sanitize(profile: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="Le profil doit être un objet JSON.")
    clean = {}
    for k, v in profile.items():
        if k in ALLOWED_FIELDS:
            clean[k] = v
    return clean


def build_ai_programming_router(db, verify_signed) -> APIRouter:
    router = APIRouter(tags=["AI Programming"])

    async def _require_creator(payload: _SignedBase) -> Dict[str, Any]:
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if dev.get("role") != "creator":
            raise HTTPException(status_code=403, detail="Réservé à la Créa.")
        return dev

    def _require_agent(agent_id: str) -> None:
        if agent_id not in AGENT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Agent inconnu : {agent_id}.")

    @router.post("/agents/profile/get")
    async def profile_get(payload: GetProfileIn):
        await _require_creator(payload)
        _require_agent(payload.agent_id)
        current = await db.ai_profiles.find_one(
            {"agent_id": payload.agent_id}, {"_id": 0},
        ) or {}
        return {
            "agent_id": payload.agent_id,
            "card": AGENT_REGISTRY[payload.agent_id],
            "profile": current.get("profile") or {},
            "version_id": current.get("version_id"),
            "updated_at": current.get("updated_at"),
        }

    @router.post("/agents/profile/save")
    async def profile_save(payload: SaveProfileIn):
        me = await _require_creator(payload)
        _require_agent(payload.agent_id)
        clean = _sanitize(payload.profile)
        version_id = f"v_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        # Archive current if exists.
        prev = await db.ai_profiles.find_one({"agent_id": payload.agent_id}, {"_id": 0})
        if prev:
            await db.ai_profile_versions.insert_one({
                "agent_id": payload.agent_id,
                "version_id": prev.get("version_id"),
                "profile": prev.get("profile") or {},
                "note": prev.get("note") or "",
                "created_at": prev.get("updated_at") or now,
                "archived_at": now,
                "actor_key_id": prev.get("actor_key_id"),
            })
        # Save new version as current.
        await db.ai_profiles.update_one(
            {"agent_id": payload.agent_id},
            {"$set": {
                "agent_id": payload.agent_id,
                "profile": clean,
                "version_id": version_id,
                "updated_at": now,
                "note": payload.note or "",
                "actor_key_id": payload.key_id,
            }},
            upsert=True,
        )
        return {"ok": True, "version_id": version_id, "updated_at": now}

    @router.post("/agents/profile/versions")
    async def profile_versions(payload: VersionsIn):
        await _require_creator(payload)
        _require_agent(payload.agent_id)
        rows = await db.ai_profile_versions.find(
            {"agent_id": payload.agent_id}, {"_id": 0},
        ).sort("archived_at", -1).limit(50).to_list(length=50)
        current = await db.ai_profiles.find_one({"agent_id": payload.agent_id}, {"_id": 0}) or {}
        return {
            "current": {
                "version_id": current.get("version_id"),
                "updated_at": current.get("updated_at"),
                "note": current.get("note") or "",
            },
            "history": rows,
        }

    @router.post("/agents/profile/revert")
    async def profile_revert(payload: RevertIn):
        await _require_creator(payload)
        _require_agent(payload.agent_id)
        row = await db.ai_profile_versions.find_one(
            {"agent_id": payload.agent_id, "version_id": payload.version_id},
            {"_id": 0},
        )
        if not row:
            raise HTTPException(status_code=404, detail="Version inconnue.")
        now = datetime.now(timezone.utc).isoformat()
        new_version = f"v_{uuid.uuid4().hex[:12]}"
        # Archive current before revert.
        prev = await db.ai_profiles.find_one({"agent_id": payload.agent_id}, {"_id": 0})
        if prev:
            await db.ai_profile_versions.insert_one({
                "agent_id": payload.agent_id,
                "version_id": prev.get("version_id"),
                "profile": prev.get("profile") or {},
                "note": prev.get("note") or "",
                "created_at": prev.get("updated_at") or now,
                "archived_at": now,
                "actor_key_id": prev.get("actor_key_id"),
            })
        # Apply the reverted profile as current.
        await db.ai_profiles.update_one(
            {"agent_id": payload.agent_id},
            {"$set": {
                "agent_id": payload.agent_id,
                "profile": row.get("profile") or {},
                "version_id": new_version,
                "updated_at": now,
                "note": f"[revert vers {payload.version_id}] " + (row.get("note") or ""),
                "actor_key_id": payload.key_id,
            }},
            upsert=True,
        )
        return {"ok": True, "version_id": new_version, "updated_at": now}

    @router.post("/agents/profile/list-all")
    async def profile_list_all(payload: _SignedBase):
        """Retourne toutes les fiches d'identité + les profils courants."""
        await _require_creator(payload)
        rows = await db.ai_profiles.find({}, {"_id": 0}).to_list(length=500)
        by_id = {r["agent_id"]: r for r in rows}
        items = []
        for aid, card in AGENT_REGISTRY.items():
            items.append({
                "agent_id": aid,
                "card": card,
                "profile": (by_id.get(aid) or {}).get("profile") or {},
                "version_id": (by_id.get(aid) or {}).get("version_id"),
                "updated_at": (by_id.get(aid) or {}).get("updated_at"),
            })
        return {"items": items}

    return router
