"""iter123 — Routes /chat/generate-* extraites de server.py (3 endpoints).

Helpers injectés : get_current_user, build_docx, build_pdf, build_image, logger.
"""
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class GenerateDocxInput(BaseModel):
    title: Optional[str] = "Document"
    sections: List[Dict[str, Any]] = []  # [{heading: str, body: str}]


class GeneratePdfInput(BaseModel):
    title: Optional[str] = "Document"
    sections: List[Dict[str, Any]] = []


class GenerateImageInput(BaseModel):
    prompt: str


def build_chat_generate_router(
    db,
    *,
    get_current_user,
    build_docx,
    build_pdf,
    build_image,
    logger,
):
    router = APIRouter()

    @router.post("/chat/generate-docx")
    async def chat_generate_docx(request: Request, payload: GenerateDocxInput):
        user_id = await get_current_user(request)
        return await build_docx(user_id, payload.title or "Document", payload.sections or [])

    @router.post("/chat/generate-pdf")
    async def chat_generate_pdf(request: Request, payload: GeneratePdfInput):
        user_id = await get_current_user(request)
        return await build_pdf(user_id, payload.title or "Document", payload.sections or [])

    @router.post("/chat/generate-image")
    async def chat_generate_image(request: Request, payload: GenerateImageInput):
        user_id = await get_current_user(request)
        try:
            return await build_image(user_id, payload.prompt)
        except Exception as e:
            logger.warning(f"image gen failed: {e}")
            raise HTTPException(status_code=500, detail=f"Génération d'image impossible : {e}")

    return router
