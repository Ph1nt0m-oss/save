"""iter158 — Garde d'export sécurisée.

Le téléchargement d'un projet n'est autorisé QUE si une demande d'export a été
APPROUVÉE par la Créa (ou déléguée avec la permission `approve_exports`), OU si
le demandeur est un appareil propriétaire réel. Aucune route de téléchargement
direct ne doit servir un fichier sans cette validation serveur.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


async def assert_export_approved(db, project_id: str, user_id: Optional[str]) -> None:
    """Lève 403 si aucune demande d'export approuvée n'existe pour ce projet.

    Un appareil propriétaire réel lié à `user_id` passe outre (il peut toujours
    récupérer ses propres projets)."""
    # Appareil propriétaire ?
    if user_id:
        try:
            from utils.ownership_guard import owner_key_ids  # noqa: WPS433
            owners = await owner_key_ids(db)
            dev = await db.device_keys.find_one(
                {"user_id": user_id, "key_id": {"$in": list(owners)}}, {"_id": 0, "key_id": 1},
            )
            if dev:
                return
        except Exception:
            pass
    approved = await db.export_requests.find_one(
        {"project_id": project_id, "status": "approved"}, {"_id": 0, "request_id": 1},
    )
    if approved:
        return
    raise HTTPException(
        status_code=403,
        detail="Export non autorisé : envoie d'abord une demande « Exporter ce projet » et attends la validation de la Créa.",
    )
