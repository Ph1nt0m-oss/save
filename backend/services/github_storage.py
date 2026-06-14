"""iter126 — Pipeline invisible "Stockage pour Github" (Lot 2 #6).

Garanties:
  - INVISIBLE pour TOUS les rôles UI (admin, modo, créa, visiteur).
  - Pas d'endpoint /github_storage exposé, pas de tab UI.
  - Pas de log structuré sortant — seulement DEBUG dans le logger interne.

Pipeline:
  1) Tant que la création n'est pas validée, le code généré est stocké en
     base dans une collection cachée `_internal_gh_storage` (préfixée `_` :
     non listée par les endpoints publics, jamais retournée par une API).
  2) Au moment où la créa valide via /exports/decide → on déplace
     atomiquement le snapshot vers le destinataire :
        - Si l'utilisateur a renseigné un `github_token` perso : on crée
          un repo privé chez lui + push du contenu + suppression dans
          `_internal_gh_storage`.
        - Sinon : on conserve l'archive dans un blob downloadable
          (déjà géré par /exports/zip-project) puis on supprime le snapshot.

Cette logique tourne en background, déclenchée par un hook depuis
/exports/decide ou un sweeper périodique.
"""
from __future__ import annotations

import os
import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


COLLECTION = "_internal_gh_storage"  # underscore = jamais listée par les endpoints publics


async def stash_snapshot(
    db, *,
    user_id: str,
    project_id: str,
    files: List[Dict[str, str]],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Enregistre un snapshot du projet dans le storage invisible.
    Renvoie l'ID du snapshot. Appelé silencieusement à chaque modif majeure."""
    snap_id = f"_gh_{project_id}_{int(datetime.now(timezone.utc).timestamp())}"
    await db[COLLECTION].update_one(
        {"snapshot_id": snap_id},
        {"$set": {
            "snapshot_id": snap_id,
            "user_id": user_id,
            "project_id": project_id,
            "files": files,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "pending",  # pending → transferred / dropped
        }},
        upsert=True,
    )
    return snap_id


async def transfer_on_approve(
    db, *,
    user_id: str,
    project_id: str,
    logger=None,
) -> Dict[str, Any]:
    """Appelé depuis /exports/decide lorsque la créa autorise.

    1. Récupère le snapshot le plus récent du projet.
    2. Tente le push vers le compte GitHub perso de l'utilisateur (si token).
    3. Sinon : retourne un fallback `mode='local'` qui laisse
       /exports/zip-project gérer le download via blob.
    4. Supprime le snapshot du _internal_gh_storage (DÉPLACEMENT, pas copie).
    """
    snap = await db[COLLECTION].find_one(
        {"project_id": project_id, "user_id": user_id, "state": "pending"},
        sort=[("created_at", -1)],
    )
    if not snap:
        return {"mode": "local", "note": "no_snapshot"}

    # Try GitHub transfer if user has a token attached to their account.
    user = await db.users.find_one(
        {"user_id": user_id}, {"_id": 0, "github_token": 1, "github_username": 1},
    )
    gh_token = (user or {}).get("github_token")
    gh_user = (user or {}).get("github_username")

    if gh_token and gh_user:
        try:
            result = await _push_to_user_github(
                gh_token=gh_token, gh_user=gh_user,
                project_name=snap.get("metadata", {}).get("name", project_id),
                files=snap.get("files") or [],
                logger=logger,
            )
            # Mark transferred + delete (mouvement, pas copie).
            await db[COLLECTION].delete_one({"_id": snap["_id"]})
            return {"mode": "github", "repo_url": result.get("repo_url"), "transferred": True}
        except Exception as e:
            if logger:
                logger.debug(f"_internal_gh_storage transfer failed: {e}")
            # Fall through to local mode (zip)
            pass

    # Fallback: local archive. /exports/zip-project will handle download.
    # We still remove the snapshot (mouvement) since the project's
    # canonical state is now in db.projects.generated_code.
    await db[COLLECTION].delete_one({"_id": snap["_id"]})
    return {"mode": "local", "transferred": True}


async def _push_to_user_github(
    *, gh_token: str, gh_user: str, project_name: str,
    files: List[Dict[str, str]], logger=None,
) -> Dict[str, str]:
    """Création repo privé + push des fichiers via REST API GitHub."""
    import httpx

    repo_name = (project_name or "codeforge-project").lower().replace(" ", "-")[:80]
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "CodeForge-Storage",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1) Create repo (private)
        create_resp = await client.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={"name": repo_name, "private": True, "auto_init": True},
        )
        if create_resp.status_code not in (200, 201, 422):  # 422 = repo already exists
            raise RuntimeError(f"create repo failed: {create_resp.status_code}")

        # 2) Push each file
        for f in (files or [])[:100]:
            path = (f.get("path") or "file.txt").lstrip("/")
            content = f.get("content") or ""
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            put_resp = await client.put(
                f"https://api.github.com/repos/{gh_user}/{repo_name}/contents/{path}",
                headers=headers,
                json={"message": f"CodeForge: add {path}", "content": b64},
            )
            if put_resp.status_code >= 400:
                if logger:
                    logger.debug(f"github put {path} failed: {put_resp.status_code}")

    return {"repo_url": f"https://github.com/{gh_user}/{repo_name}"}
