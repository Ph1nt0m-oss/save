"""iter127 — Modèles Pydantic centralisés.

Regroupe les schémas partagés entre routes (signatures créa, etc.) pour
éviter la duplication qui était présente dans /app/backend/routes/*.
"""
from .auth_signatures import CreatorSigIn, TargetCreatorSigIn

__all__ = ["CreatorSigIn", "TargetCreatorSigIn"]
