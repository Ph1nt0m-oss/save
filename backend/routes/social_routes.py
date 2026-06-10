"""iter85 — Routes sociales (friends + groups + send-to-staff) extraites de
server.py en première slice du refacto progressif demandé par l'utilisateur.

Importé et inclus depuis server.py via :
    from routes.social_routes import register_social_routes
    register_social_routes(api_router, db, helpers)

Ce module n'introduit pas de NOUVEAU endpoint — il déplace simplement les
implémentations existantes. Les routes /api/friends/*, /api/groups/*, et
/api/messages/send-to-staff restent identiques côté HTTP, donc le frontend ne
remarque rien. ✓

iter85 — première étape vers une architecture modulaire. Les futures slices
suivront le même pattern : extraire, garder même URL+signature, tester
régression, commiter."""
from __future__ import annotations

import uuid
import random as _rnd
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from pydantic import BaseModel


GROUP_TYPES = {
    "public", "private", "staff", "modo", "public_staff", "public_private",
}


def _groups_for_device(dev: Dict[str, Any]) -> List[str]:
    """Retourne la liste des groupes auxquels CE device a accès."""
    role = dev.get("role")
    sk = dev.get("staff_kind")
    if role == "creator":
        return list(GROUP_TYPES)
    if role == "blocked":
        return []
    is_staff = sk in ("admin", "modo")
    is_modo = sk == "modo"
    is_admin = sk == "admin"
    is_private = role == "approved" and not is_staff
    is_public = role in ("pending", "approved")
    out = []
    if is_public and not is_staff and not is_private:
        out.append("public")
        out.append("public_staff")
        out.append("public_private")
    if is_private:
        out.append("private")
        out.append("public_staff")
        out.append("public_private")
    if is_staff:
        out.append("staff")
        out.append("public_staff")
    if is_modo:
        out.append("modo")
    return list(set(out))
