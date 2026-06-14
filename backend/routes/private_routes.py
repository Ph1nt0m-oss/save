"""iter117 — Routes /private/* (créa-only) extraites de server.py.

5 endpoints créa-only :
  - /private/changelog (lecture du journal des modifs)
  - /private/changelog/log (ajout manuel d'une entrée)
  - /private/code/read-file (lecture intégrale d'un fichier source)
  - /private/code/grep (recherche dans la base de code)
  - /private/code/write-file (édition + backup .bak + log)
"""
from __future__ import annotations

import pathlib
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class CodeforgeChangelogIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    limit: Optional[int] = 50


class CodeforgeManualLogIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    category: str
    summary: str
    details: Optional[Dict[str, Any]] = None


class PrivateReadFileIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    path: str


class PrivateGrepIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    pattern: str


class PrivateWriteFileIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    path: str
    content: str


_WRITE_ALLOWED_PREFIXES = (
    "backend/", "frontend/src/", "frontend/public/", "orchestrator.py",
)
_WRITE_FORBIDDEN_SUFFIXES = (".env", ".git", ".pem", ".key", ".secret")


def build_private_router(db, *, require_creator_signature, log_change, logger):
    router = APIRouter()

    @router.post("/private/changelog")
    async def private_changelog(payload: CodeforgeChangelogIn):
        """iter92 — Retourne le journal des modifications faites au site/IA."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        limit = max(1, min(int(payload.limit or 50), 500))
        rows = await db.codeforge_changelog.find(
            {}, {"_id": 0},
        ).sort("ts", -1).limit(limit).to_list(length=limit)
        return {"changes": rows}

    @router.post("/private/changelog/log")
    async def private_changelog_log(payload: CodeforgeManualLogIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        cat = (payload.category or "manual").strip().lower()
        if cat not in ("manual", "code", "config", "model", "site_mode", "deploy"):
            cat = "manual"
        summary = (payload.summary or "").strip()
        if not summary:
            raise HTTPException(status_code=400, detail="summary requis.")
        await log_change(cat, summary, payload.details)
        return {"success": True}

    @router.post("/private/code/read-file")
    async def private_read_file(payload: PrivateReadFileIn):
        """iter89 — Creator-only. Le frontend gate selon viewMode."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        from orchestrator import _read_file_safe
        return _read_file_safe(payload.path, full_read=True)

    @router.post("/private/code/grep")
    async def private_grep(payload: PrivateGrepIn):
        """iter89 — Creator-only."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        from orchestrator import _grep_safe
        return _grep_safe(payload.pattern)

    @router.post("/private/code/write-file")
    async def private_write_file(payload: PrivateWriteFileIn):
        """iter104 — Édition en place + backup .bak + log changelog."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        rel = (payload.path or "").lstrip("/").strip()
        if not rel:
            raise HTTPException(status_code=400, detail="Chemin requis.")
        if ".." in rel or rel.startswith("/"):
            raise HTTPException(status_code=400, detail="Chemin invalide.")
        if not any(rel.startswith(p) for p in _WRITE_ALLOWED_PREFIXES):
            raise HTTPException(status_code=403, detail=f"Préfixe non autorisé : {rel}")
        if any(rel.endswith(s) for s in _WRITE_FORBIDDEN_SUFFIXES):
            raise HTTPException(status_code=403, detail=f"Extension protégée : {rel}")
        if len(payload.content) > 2_000_000:
            raise HTTPException(status_code=413, detail="Fichier trop gros (> 2MB).")

        abs_path = pathlib.Path("/app") / rel
        if not abs_path.parent.exists():
            raise HTTPException(status_code=404, detail="Dossier parent inexistant.")
        backup_path = None
        if abs_path.exists():
            backup_path = abs_path.with_suffix(abs_path.suffix + ".bak")
            try:
                backup_path.write_bytes(abs_path.read_bytes())
            except Exception as e:
                logger.warning(f"Backup failed for {rel}: {e}")
        try:
            abs_path.write_text(payload.content, encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Écriture impossible : {str(e)[:200]}")

        try:
            await log_change(
                "code",
                f"Édition manuelle de {rel} via /private-programming",
                {"path": rel, "bytes": len(payload.content),
                 "backup": str(backup_path.relative_to("/app")) if backup_path else None},
            )
        except Exception:
            pass
        return {
            "success": True,
            "path": rel,
            "bytes": len(payload.content),
            "backup": str(backup_path.relative_to("/app")) if backup_path else None,
        }

    return router
