"""Schémas Pydantic pour les payloads signés ECDSA créa/staff.

Ces deux modèles étaient dupliqués à l'identique dans 5+ fichiers de
routes (`accounts_routes`, `announcements_routes`, `exports_routes`,
`ideas_routes`, `system_routes`, ...). Centralisés ici pour réduire la
dette technique.

`extra="allow"` permet aux endpoints d'accepter des champs additionnels
(ex. `password`, `duration_minutes`, `project_id`) tout en validant les
trois champs cryptographiques obligatoires.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CreatorSigIn(BaseModel):
    """Payload minimal d'un appel signé : preuve de possession de la clé créa."""
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


class TargetCreatorSigIn(CreatorSigIn):
    """Variante avec une cible explicite (action modération sur autre compte)."""
    target_key_id: str
