"""iter129 — Écosystème multi-agents spécialisés CodeForge AI.

Architecture :
                 Utilisateur
                      |
                      v
              IA Router / Manager   (router_agent.py)
                      |
       --------------------------------
       |              |               |
       v              v               v
 IA Chat       IA Dev Agent      IA Planner
 (chat_agent)  (dev_agent)       (planner_agent)
       |              |               |
 Prompt propre  Prompt spécialisé  Prompt spécialisé
 Mémoire conv.  Outils code/tests  Format plan/tâches

Chaque agent est INDÉPENDANT : son propre prompt système, son propre rôle,
ses propres outils, son propre format de sortie, ses propres étapes
d'exécution. Interdiction de fusion des personnalités (cf. registry.py).
"""
from .engine import run_pipeline  # noqa: F401
from .registry import AGENT_REGISTRY, get_agent_card  # noqa: F401
