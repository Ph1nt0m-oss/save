"""iter121 — Routes /caly/* extraites de server.py (3 endpoints).

  - POST /caly/ask     : LLM dédié au widget Caly (gpt-4o-mini via Emergent LLM Key)
  - GET  /caly/config  : récupère le prompt système + KB Caly
  - POST /caly/config  : créa/admin only — modifie le prompt système persistant

Helpers injectés (anti-circular imports) :
  - db
  - verify_signed       : pour l'auth créa/admin du POST /config
  - log_change          : journalisation des modifs (best-effort)
  - logger
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


CALY_DEFAULT_SYSTEM_PROMPT = """Tu es Caly, l'assistante d'aide à l'utilisation de CodeForge AI.
Tu réponds aux questions des utilisateurs sur le site : créer une appli, modifier
une création, comprendre l'inscription cryptographique (clé ECDSA par appareil,
inscription GitHub obligatoire), les exports (ZIP, APK, EXE), le mode privé/public,
les vues (utilisateur/modo/admin/créatrice), le profil, les amis, les bots
communautaires, les sondages et annonces, les paramètres de langue.

Règles :
- Réponses CONCISES (max 3 phrases), en français.
- Tutoie l'utilisateur.
- Ne donne JAMAIS de code source, ni de tokens, ni d'informations secrètes.
- Si tu ne sais pas, dis-le franchement et propose de contacter un modo.
- Si l'utilisateur demande une fonctionnalité technique, redirige vers l'onglet
  approprié (Dashboard pour créer, Profil pour la clé, etc.)."""


class CalyAskIn(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None  # [{role, content}]
    session_id: Optional[str] = None
    language: Optional[str] = "fr"


class CalyConfigSetIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    prompt: str


def build_caly_router(db, *, verify_signed, log_change, logger):
    router = APIRouter()

    @router.post("/caly/ask")
    async def caly_ask(input: CalyAskIn):
        """LLM dédié pour Caly (gpt-4o-mini via Emergent LLM key).
        Enrichi avec la KB éventuelle pour Caly (bot_knowledge où bot_id='caly').
        Public — pas de signature requise (c'est un help widget)."""
        if not (input.message or "").strip():
            raise HTTPException(status_code=400, detail="Message vide.")

        cfg = await db.bot_configs.find_one({"bot_id": "caly"}, {"_id": 0, "prompt": 1}) or {}
        system_prompt = cfg.get("prompt") or CALY_DEFAULT_SYSTEM_PROMPT

        # Enrichi avec la knowledge base Caly
        kb_entries = await db.bot_knowledge.find(
            {"bot_id": "caly"}, {"_id": 0, "question": 1, "answer": 1}
        ).to_list(length=30)
        if kb_entries:
            kb_text = "\n\n=== BASE DE CONNAISSANCES (FAQ CodeForge) ===\n" + "\n".join(
                f"Q: {e.get('question', '')}\nR: {e.get('answer', '')}" for e in kb_entries
            )
            system_prompt = system_prompt + kb_text

        # Récupère l'historique récent (max 8 derniers messages)
        history_text = ""
        if input.history:
            recent = input.history[-8:]
            history_text = "\n".join(
                f"{('Utilisateur' if h.get('role') == 'user' else 'Caly')} : {h.get('content', '')}"
                for h in recent if h.get('content')
            )

        composed = (
            f"### Historique récent :\n{history_text}\n\n### Nouveau message :\n{input.message}"
            if history_text else input.message
        )

        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            api_key = os.environ.get("EMERGENT_LLM_KEY") or ""
            if not api_key:
                raise HTTPException(status_code=503, detail="LLM key non configurée.")
            session_id = input.session_id or f"caly_{uuid.uuid4().hex[:12]}"
            chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_prompt)
            chat = chat.with_model("openai", "gpt-4o-mini")
            reply = await chat.send_message(UserMessage(text=composed[:4000]))
            return {
                "reply": str(reply or "")[:2000],
                "session_id": session_id,
                "kb_used": len(kb_entries),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Caly ask failed: {e}")
            raise HTTPException(status_code=500, detail=f"Erreur Caly: {str(e)[:200]}")

    @router.get("/caly/config")
    async def caly_config_get():
        cfg = await db.bot_configs.find_one({"bot_id": "caly"}, {"_id": 0}) or {}
        return {
            "bot_id": "caly",
            "prompt": cfg.get("prompt") or CALY_DEFAULT_SYSTEM_PROMPT,
            "is_default": not bool(cfg.get("prompt")),
        }

    @router.post("/caly/config")
    async def caly_config_set(payload: CalyConfigSetIn):
        """Créa/admin only : modifie le system prompt Caly persistant."""
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role")
        sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        if not payload.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt vide.")
        if len(payload.prompt) > 8000:
            raise HTTPException(status_code=413, detail="Prompt trop long (> 8000 chars).")
        await db.bot_configs.update_one(
            {"bot_id": "caly"},
            {"$set": {
                "bot_id": "caly",
                "prompt": payload.prompt.strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by_key": payload.key_id,
            }},
            upsert=True,
        )
        try:
            await log_change("model", "Prompt système Caly mis à jour", {"bytes": len(payload.prompt)})
        except Exception:
            pass
        return {"success": True}

    return router
