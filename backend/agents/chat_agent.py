"""iter129 — IA Chat (Caly) : conversation générale avec mémoire conversationnelle.

Prompt système PROPRE (registry.CHAT_AGENT_SYSTEM). Aucun outil code.
Yields : {"delta": str} uniquement (réponse directe streamée).
"""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .common import format_history, lang_label, stream_llm
from .registry import CHAT_AGENT_SYSTEM

logger = logging.getLogger(__name__)


async def run_chat_agent(message: str, *, session_id: str, language: str = "fr",
                         history: Optional[List[Dict[str, Any]]] = None,
                         provider: str = "openai", model_id: str = "gpt-4o-mini",
                         ) -> AsyncIterator[Dict[str, Any]]:
    system = CHAT_AGENT_SYSTEM.format(lang_label=lang_label(language))
    # iter149 — Injection du profil configuré pour l'agent "chat" (Caly).
    try:
        from utils.ai_profile_injector import load_profile, build_profile_fragment
        from server import db as _srv_db
        _prof = await load_profile(_srv_db, "chat")
        _frag = build_profile_fragment(_prof or {})
        if _frag:
            system = system + _frag
    except Exception as _err:
        logger.warning(f"chat_agent: profile injection failed: {_err}")
    ctx = format_history(history)
    prompt = (f"Historique de la conversation :\n{ctx}\n\n" if ctx else "") + f"Message : {message}"
    async for delta in stream_llm(system, prompt, session_id=session_id,
                                  provider=provider, model_id=model_id):
        yield {"delta": delta}
