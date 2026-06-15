"""Schémas Pydantic pour les payloads signés ECDSA créa/staff.

Ces modèles étaient dupliqués à l'identique dans une douzaine de
fichiers de routes (`accounts_routes`, `announcements_routes`,
`community_bots_routes`, `devices_routes`, `exports_routes`,
`messages_routes`, `ideas_routes`, `system_routes`, ...). Centralisés
ici pour réduire la dette technique.

- `SignedIn`        : key_id + nonce + signature (strict, ne tolère pas
                      d'autres champs). À étendre pour ajouter des
                      champs typés.
- `CreatorSigIn`    : variante avec `extra="allow"` pour les endpoints
                      acceptant des champs ad-hoc (password, scope, …).
- `TargetCreatorSigIn` : `CreatorSigIn` + `target_key_id`.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SignedIn(BaseModel):
    """Payload signé strict (3 champs obligatoires, rien de plus)."""
    key_id: str
    nonce: str
    signature: str


class CreatorSigIn(BaseModel):
    """Payload signé tolérant aux champs additionnels (preuve créa/staff)."""
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


class TargetCreatorSigIn(CreatorSigIn):
    """Variante avec une cible explicite (action modération sur autre compte)."""
    target_key_id: str
