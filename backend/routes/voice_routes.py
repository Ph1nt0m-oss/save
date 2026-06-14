"""iter122 — Route /voice/transcribe extraite de server.py.

OpenAI Whisper transcription via emergentintegrations.

Helpers injectés : get_current_user, logger.
"""
from __future__ import annotations

import io
import os

from fastapi import APIRouter, File, HTTPException, Request, UploadFile


def build_voice_router(db, *, get_current_user, logger):
    router = APIRouter()

    @router.post("/voice/transcribe")
    async def voice_transcribe(
        request: Request,
        file: UploadFile = File(...),
        language: str = "auto",
    ):
        """Transcribe a short voice recording (<25MB) to text via OpenAI Whisper.

        Used by the chat & create pages for two UX flows:
        - "Voice message" — record → instant send (the AI receives the transcript).
        - "Dictation" — record → fill the input field for review before send.

        Returns: { "text": "...", "language": "fr", "size_bytes": N }
        """
        user_id = await get_current_user(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentification requise")

        # Validate file type & size early (Whisper accepts mp3/mp4/mpeg/mpga/m4a/wav/webm).
        allowed = {"audio/webm", "audio/mp3", "audio/mpeg", "audio/mp4",
                   "audio/m4a", "audio/wav", "audio/x-wav", "audio/ogg",
                   "video/webm"}
        if file.content_type and file.content_type.split(";")[0].strip() not in allowed:
            logger.info(f"voice/transcribe: unusual content-type {file.content_type}")

        raw = await file.read()
        if len(raw) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Fichier audio trop volumineux (>25MB)")
        if len(raw) < 200:
            raise HTTPException(status_code=400, detail="Enregistrement trop court ou vide")

        try:
            from emergentintegrations.llm.openai import OpenAISpeechToText
            emergent_key = os.environ.get("EMERGENT_LLM_KEY")
            if not emergent_key:
                raise ValueError("EMERGENT_LLM_KEY not configured")

            stt = OpenAISpeechToText(api_key=emergent_key)
            audio_buf = io.BytesIO(raw)
            audio_buf.name = file.filename or "recording.webm"

            kwargs = {"file": audio_buf, "model": "whisper-1", "response_format": "json"}
            if language and language != "auto":
                kwargs["language"] = language[:2]  # ISO-639-1

            response = await stt.transcribe(**kwargs)
            text = (getattr(response, "text", "") or "").strip()
            if not text:
                raise HTTPException(
                    status_code=422,
                    detail="Aucun texte reconnu — réessaie en parlant plus clairement.",
                )

            return {"text": text, "language": language, "size_bytes": len(raw)}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"voice/transcribe error: {e}")
            raise HTTPException(status_code=500, detail=f"Erreur de transcription : {e}")

    return router
