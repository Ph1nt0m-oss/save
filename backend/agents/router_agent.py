"""iter129 — IA Router / Manager : dirige chaque message vers l'agent spécialisé."""
import re
from typing import Any, Dict, List, Optional

from .common import llm_json, format_history
from .registry import ROUTER_SYSTEM

_DEV_PATTERNS = re.compile(
    r"\b(code|coder|bug|fichier|module|api|endpoint|fonction|script|composant|"
    r"corrige|implémente|implemente|développe|developpe|crée[- ]moi (une|un) (app|application|site|module|script)|"
    r"debug|refactor|classe|backend|frontend|base de données|database|test unitaire|patch)\b",
    re.IGNORECASE,
)
_PLANNER_PATTERNS = re.compile(
    r"\b(planifie|planning|roadmap|organise|organisation du projet|découpe|decoupe|"
    r"priorise|priorités|priorites|jalons|étapes du projet|etapes du projet|feuille de route|backlog)\b",
    re.IGNORECASE,
)
_GREETINGS = re.compile(
    r"^(salut|bonjour|bonsoir|coucou|hello|hey|hi|ça va|ca va|merci|ok|oui|non|d'accord|cool|super|👍|😊).{0,40}$",
    re.IGNORECASE,
)


async def route_message(message: str, history: Optional[List[Dict[str, Any]]] = None,
                        *, session_id: str = "router") -> str:
    """Retourne 'chat' | 'dev' | 'planner'. Heuristiques rapides puis LLM léger."""
    text = (message or "").strip()
    if not text or _GREETINGS.match(text):
        return "chat"
    if _PLANNER_PATTERNS.search(text):
        return "planner"
    if _DEV_PATTERNS.search(text):
        return "dev"
    if len(text) < 60:
        return "chat"
    ctx = format_history(history, max_chars=800)
    decision = await llm_json(
        ROUTER_SYSTEM,
        (f"Historique récent :\n{ctx}\n\n" if ctx else "") + f"Message utilisateur :\n{text[:1200]}",
        session_id=f"{session_id}_route", provider="openai", model_id="gpt-4o-mini",
    )
    agent = (decision.get("agent") or "chat").strip().lower()
    return agent if agent in ("chat", "dev", "planner") else "chat"
