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

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.auth_signatures import SignedIn


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


class CalyConfigSetIn(SignedIn):
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

        # iter149 — Injection du profil configuré via /api/agents/profile/save
        # pour l'agent "caly_help" (l'assistante flottante). Isolé du reste.
        try:
            from utils.ai_profile_injector import load_profile, build_profile_fragment
            _prof = await load_profile(db, "caly_help")
            _frag = build_profile_fragment(_prof or {})
            if _frag:
                system_prompt = system_prompt + _frag
        except Exception:
            pass

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

    # ---------- iter130 — Caly en MODE AGENT (étapes visibles + streaming) ----------
    # Caly reste l'assistante d'aide au site (aucune fusion avec Forge) : ses
    # étapes opérationnelles sont les SIENNES — analyse de la question,
    # recherche réelle dans la FAQ/KB, puis réponse streamée token par token.

    @router.post("/caly/ask-stream")
    async def caly_ask_stream(input: CalyAskIn):
        if not (input.message or "").strip():
            raise HTTPException(status_code=400, detail="Message vide.")

        cfg = await db.bot_configs.find_one({"bot_id": "caly"}, {"_id": 0, "prompt": 1}) or {}
        system_prompt = cfg.get("prompt") or CALY_DEFAULT_SYSTEM_PROMPT

        kb_entries = await db.bot_knowledge.find(
            {"bot_id": "caly"}, {"_id": 0, "question": 1, "answer": 1}
        ).to_list(length=30)

        # Recherche RÉELLE dans la KB : fiches dont question/réponse matchent
        # les mots significatifs du message. Fallback : toutes les fiches.
        q_words = re.findall(r"\w{4,}", (input.message or "").lower())
        matched = [
            e for e in kb_entries
            if any(w in f"{e.get('question', '')} {e.get('answer', '')}".lower() for w in q_words)
        ] if q_words else []
        used_entries = matched or kb_entries
        if used_entries:
            kb_text = "\n\n=== BASE DE CONNAISSANCES (FAQ CodeForge) ===\n" + "\n".join(
                f"Q: {e.get('question', '')}\nR: {e.get('answer', '')}" for e in used_entries
            )
            system_prompt = system_prompt + kb_text

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
        session_id = input.session_id or f"caly_{uuid.uuid4().hex[:12]}"

        def sse(obj):
            return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

        async def gen():
            yield sse({"event": {"kind": "status", "summary": "Analyse de ta question…"}})
            if kb_entries:
                yield sse({"event": {
                    "kind": "search_done",
                    "summary": f"Recherche dans la FAQ CodeForge… ✓ {len(matched)} fiche(s) pertinente(s)"
                    if matched else f"Recherche dans la FAQ CodeForge… ({len(kb_entries)} fiches consultées)",
                }})
            yield sse({"event": {"kind": "status", "summary": "Rédaction de la réponse…"}})
            full = ""
            try:
                from agents.common import stream_llm
                async for delta in stream_llm(
                    system_prompt, composed[:4000],
                    session_id=session_id, provider="openai", model_id="gpt-4o-mini",
                ):
                    full += delta
                    yield sse({"delta": delta})
            except Exception as e:
                logger.warning(f"Caly ask-stream failed: {e}")
                if not full:
                    full = "Désolée, je n'arrive pas à répondre pour l'instant. Réessaie dans un moment."
                    yield sse({"delta": full})
            yield sse({"done": True, "reply": full[:2000], "session_id": session_id,
                       "kb_used": len(used_entries)})

        return StreamingResponse(gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })

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
