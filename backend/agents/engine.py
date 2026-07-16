"""iter129 — Moteur du système multi-agents : Router → agent spécialisé.

Yields unifiés (prêts pour SSE) :
  {"agent": {id, name, objectif}}   : décision du Router
  {"event": {...}}                  : événement du journal d'activité
  {"delta": str}                    : token de la réponse finale
"""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .router_agent import route_message
from .chat_agent import run_chat_agent
from .dev_agent import run_dev_agent
from .planner_agent import run_planner_agent
from .registry import get_agent_card
from .common import resolve_model

logger = logging.getLogger(__name__)


async def run_pipeline(message: str, *, session_id: str, language: str = "fr",
                       project_id: Optional[str] = None,
                       history: Optional[List[Dict[str, Any]]] = None,
                       model_pref: Optional[str] = None,
                       agent_id: Optional[str] = None,
                       emit=None) -> AsyncIterator[Dict[str, Any]]:
    provider, model_id = resolve_model(model_pref)
    if agent_id not in ("chat", "dev", "planner"):
        try:
            agent_id = await route_message(message, history, session_id=session_id)
        except Exception as e:
            logger.warning(f"router failure, fallback chat: {e}")
            agent_id = "chat"
    card = get_agent_card(agent_id)
    yield {"agent": {"id": card["id"], "name": card["name"], "objectif": card["objectif"]}}

    if agent_id == "dev":
        gen = run_dev_agent(message, session_id=session_id, project_id=project_id,
                            language=language, history=history,
                            provider=provider, model_id=model_id, emit=emit)
    elif agent_id == "planner":
        gen = run_planner_agent(message, session_id=session_id, language=language,
                                history=history, provider=provider, model_id=model_id, emit=emit)
    else:
        gen = run_chat_agent(message, session_id=session_id, language=language,
                             history=history, provider=provider, model_id=model_id)
    async for item in gen:
        yield item
