"""iter124 — Service module : file generators + sandbox + sanitization.

Encapsule les helpers `_build_*` + `_run_python_sandbox` + `_sanitize_filename`
+ `_analyze_*` qui étaient dans server.py.

Usage côté server.py :
    from services.file_builders import (
        build_docx, build_pdf, build_image, build_pptx, build_xlsx, build_plain,
        run_python_sandbox, sanitize_filename,
        analyze_pdf, analyze_docx, analyze_xlsx, analyze_pptx, analyze_sqlite,
        analyze_image_with_vision, GENERATED_FILES_DIR,
    )

Le ServiceContext est passé en paramètre (db, logger) pour éviter les imports
circulaires avec server.py. Utilisation :
    from services.file_builders import make_file_service
    file_svc = make_file_service(db, logger)
    file_svc.build_docx(user_id, "Titre", sections)
"""
from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# All the heavy-lifting (libreoffice-style document builders + sandbox)
# lives in cfaction_engine — these are thin wrappers + DB persistence.
from cfaction_engine import (
    sanitize_filename as _cf_sanitize_filename,
    analyze_pdf as _cf_analyze_pdf,
    analyze_docx as _cf_analyze_docx,
    analyze_xlsx as _cf_analyze_xlsx,
    analyze_pptx as _cf_analyze_pptx,
    analyze_sqlite as _cf_analyze_sqlite,
    build_docx_bytes as _cf_build_docx_bytes,
    build_pdf_bytes as _cf_build_pdf_bytes,
    build_xlsx_bytes as _cf_build_xlsx_bytes,
    build_pptx_bytes as _cf_build_pptx_bytes,
    run_python_sandbox as _cf_run_python_sandbox,
)

# Directory for generated downloadable files (shared across the app).
GENERATED_FILES_DIR = Path("/app/backend/generated_files")
GENERATED_FILES_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str, ext: str = "") -> str:
    return _cf_sanitize_filename(name, ext)


async def analyze_pdf(data: bytes) -> str:
    return _cf_analyze_pdf(data)


async def analyze_docx(data: bytes) -> str:
    return _cf_analyze_docx(data)


async def analyze_xlsx(data: bytes) -> str:
    return _cf_analyze_xlsx(data)


async def analyze_pptx(data: bytes) -> str:
    return _cf_analyze_pptx(data)


async def analyze_sqlite(data: bytes) -> str:
    return _cf_analyze_sqlite(data)


async def analyze_image_with_vision(
    data: bytes, mime_type: str, question: Optional[str] = None, *, logger=None,
) -> str:
    """Use GPT-5.2 vision to describe an uploaded image."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        if not emergent_key:
            return "(clé Emergent non configurée)"
        b64 = base64.b64encode(data).decode("utf-8")
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"cf_vision_{uuid.uuid4().hex[:8]}",
            system_message="Tu analyses des images précisément et brièvement.",
        ).with_model("openai", "gpt-5.2")
        prompt = question or "Décris cette image de façon concise (contenu, contexte, éléments notables)."
        msg = UserMessage(text=prompt, file_contents=[ImageContent(b64)])
        return (await chat.send_message(msg) or "").strip()[:6000]
    except Exception as e:
        if logger:
            logger.warning(f"Vision analyze failed: {e}")
        return ""


async def run_python_sandbox(
    code: str, timeout_sec: int = 10,
    session_id: Optional[str] = None,
    files: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Délègue à cfaction_engine.run_python_sandbox."""
    return await _cf_run_python_sandbox(code, timeout_sec=timeout_sec, session_id=session_id, files=files)


@dataclass
class FileService:
    """Service object that captures `db` + `logger` so builders can persist."""
    db: Any
    logger: Any

    def _store_generated(self, blob: bytes, filename: str, mime: str, user_id: str) -> Dict[str, str]:
        file_id = f"gen_{uuid.uuid4().hex[:16]}"
        safe = sanitize_filename(filename)
        disk = GENERATED_FILES_DIR / f"{file_id}__{safe}"
        disk.write_bytes(blob)
        return {
            "file_id": file_id,
            "filename": safe,
            "url": f"/api/download/generated/{file_id}",
            "mime_type": mime,
            "size": len(blob),
            "disk_path": str(disk),
            "user_id": user_id,
        }

    async def _persist_generated(self, info: Dict[str, Any]) -> Dict[str, str]:
        await self.db.generated_files.insert_one({
            "file_id": info["file_id"],
            "user_id": info["user_id"],
            "filename": info["filename"],
            "mime_type": info["mime_type"],
            "size": info["size"],
            "path": info["disk_path"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "file_id": info["file_id"], "filename": info["filename"],
            "url": info["url"], "mime_type": info["mime_type"],
        }

    async def build_docx(self, user_id: str, title: str, sections: List[Dict[str, Any]]) -> Dict[str, str]:
        blob = _cf_build_docx_bytes(title or "Document", sections or [])
        info = self._store_generated(
            blob,
            f"{title or 'document'}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            user_id,
        )
        return await self._persist_generated(info)

    async def build_pdf(self, user_id: str, title: str, sections: List[Dict[str, Any]]) -> Dict[str, str]:
        blob = _cf_build_pdf_bytes(title or "Document", sections or [])
        info = self._store_generated(blob, f"{title or 'document'}.pdf", "application/pdf", user_id)
        return await self._persist_generated(info)

    async def build_xlsx(self, user_id: str, title: str, sheets: List[Dict[str, Any]]) -> Dict[str, str]:
        blob = _cf_build_xlsx_bytes(sheets or [])
        info = self._store_generated(
            blob,
            f"{title or 'classeur'}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            user_id,
        )
        return await self._persist_generated(info)

    async def build_pptx(self, user_id: str, title: str, slides: List[Dict[str, Any]]) -> Dict[str, str]:
        blob = _cf_build_pptx_bytes(title or "Présentation", slides or [])
        info = self._store_generated(
            blob,
            f"{title or 'presentation'}.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            user_id,
        )
        return await self._persist_generated(info)

    async def build_plain(self, user_id: str, title: str, content: str, ext: str, mime: str) -> Dict[str, str]:
        data = (content or "").encode("utf-8")
        name = title or "fichier"
        if not name.lower().endswith(ext):
            name = f"{name}{ext}"
        info = self._store_generated(data, name, mime, user_id)
        return await self._persist_generated(info)

    async def build_image(self, user_id: str, prompt: str) -> Dict[str, str]:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        if not emergent_key:
            raise ValueError("EMERGENT_LLM_KEY missing")
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"cf_imggen_{uuid.uuid4().hex[:8]}",
            system_message="You are a helpful AI assistant.",
        )
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
        _text, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
        if not images:
            raise ValueError("no image generated")
        img = images[0]
        data = base64.b64decode(img["data"])
        info = self._store_generated(
            data,
            f"{sanitize_filename((prompt[:40]) or 'image', ext='')}.png",
            img.get("mime_type", "image/png"),
            user_id,
        )
        return await self._persist_generated(info)


def make_file_service(db, logger) -> FileService:
    return FileService(db=db, logger=logger)
