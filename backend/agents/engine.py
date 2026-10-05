"""iter129 — Moteur du système multi-agents : Router → agent spécialisé.

Chantier iter161 §P0.1/P1.1 :
  • Routage EXACT via resolve_model (plus de bascule silencieuse).
  • L'événement `agent` expose maintenant provider+model_id+model_label
    pour que le frontend affiche le vrai modèle au-dessus de chaque
    message IA (pas "Caly").

Yields unifiés (prêts pour SSE) :
  {"agent": {id, name, objectif, provider, model_id, model_label}}
  {"event": {...}}
  {"delta": str}
"""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .router_agent import route_message
from .chat_agent import run_chat_agent
from .dev_agent import run_dev_agent
from .planner_agent import run_planner_agent
from .registry import get_agent_card
from .common import resolve_model, friendly_model_label

logger = logging.getLogger(__name__)


async def run_pipeline(message: str, *, session_id: str, language: str = "fr",
                       project_id: Optional[str] = None,
                       history: Optional[List[Dict[str, Any]]] = None,
                       model_pref: Optional[str] = None,
                       agent_id: Optional[str] = None,
                       emit=None) -> AsyncIterator[Dict[str, Any]]:
    # iter161 — Résolution STRICTE : si le modèle n'a pas de handler réel,
    # resolve_model lève une HTTPException qui remonte directement à
    # l'endpoint SSE (/chat/stream) et devient une erreur explicite UI.
    provider, model_id = resolve_model(model_pref)

    if agent_id not in ("chat", "dev", "planner"):
        try:
            agent_id = await route_message(message, history, session_id=session_id)
        except Exception as e:
            logger.warning(f"router failure, fallback chat: {e}")
            agent_id = "chat"
    card = get_agent_card(agent_id)

    # Chantier iter161 §P1.1 — Le nom affiché pour l'agent "chat" doit être
    # le MODÈLE RÉEL (Claude 5 Fable, GPT 5.5…) et JAMAIS "Caly". Pour les
    # agents spécialisés (dev=Forge, planner=Archi), on garde leur identité.
    display_name = card["name"]
    if agent_id == "chat":
        display_name = friendly_model_label(provider, model_id)

    yield {"agent": {
        "id": card["id"],
        "name": display_name,
        "objectif": card["objectif"],
        "provider": provider,
        "model_id": model_id,
        "model_label": friendly_model_label(provider, model_id),
    }}

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
