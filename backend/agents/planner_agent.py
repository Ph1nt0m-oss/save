"""iter129 — IA Planner (Archi) : organisation de projet, plan, tâches, priorités.

Prompt système PROPRE (registry.PLANNER_AGENT_SYSTEM). Aucun outil code.
Workflow visible : Analyse des objectifs → Structuration → Réponse plan streamée.
Yields : {"event": {...}} pour le journal + {"delta": str} pour la réponse.
"""
from typing import Any, AsyncIterator, Dict, List, Optional

from orchestrator import _make_event
from .common import format_history, lang_label, stream_llm
from .registry import PLANNER_AGENT_SYSTEM


async def run_planner_agent(message: str, *, session_id: str, language: str = "fr",
                            history: Optional[List[Dict[str, Any]]] = None,
                            provider: str = "openai", model_id: str = "gpt-4o-mini",
                            emit=None) -> AsyncIterator[Dict[str, Any]]:
    async def ev(kind, summary, details=None, **extras):
        evt = _make_event(kind, summary, details, **extras)
        if emit:
            await emit(evt)
        return {"event": evt}

    yield await ev("status", "Analyse des objectifs du projet…",
                   details={"agent": "planner", "message": message[:500]})
    yield await ev("status_done", "✓ Objectifs identifiés")
    yield await ev("status", "Structuration du plan et priorisation…")

    system = PLANNER_AGENT_SYSTEM.format(lang_label=lang_label(language))
    # iter149 — Injection du profil configuré pour l'agent "planner" (Archi).
    try:
        from utils.ai_profile_injector import load_profile, build_profile_fragment
        from server import db as _srv_db
        _prof = await load_profile(_srv_db, "planner")
        _frag = build_profile_fragment(_prof or {})
        if _frag:
            system = system + _frag
    except Exception:
        pass
    ctx = format_history(history)
    prompt = (f"Historique de la conversation :\n{ctx}\n\n" if ctx else "") + f"Demande : {message}"
    async for delta in stream_llm(system, prompt, session_id=session_id,
                                  provider=provider, model_id=model_id):
        yield {"delta": delta}

    yield await ev("status_done", "✓ Plan livré")
