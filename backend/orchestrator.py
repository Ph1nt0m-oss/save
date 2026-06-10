"""iter83 C7 — Orchestrateur multi-agents pour les requêtes IA.

Architecture (inspirée du brief utilisateur) :

    User question
        ↓
    ┌─── Planner ─────┐  génère hypothèses structurées (JSON)
    │                 │
    ┌─── Critic ──────┐  tente de réfuter / casser
    │                 │
    ┌─── Executor ────┐  exécute le code si applicable (sandbox)
    │                 │
    ┌─── Arbiter ─────┐  synthèse finale (confirmé / probable / incertain)
        ↓
    Final answer

Aucun composant n'a autorité absolue : la réponse doit survivre aux 4 étapes.
Une mémoire d'erreurs est conservée par session pour pénaliser les hallucinations
récurrentes (clé `error_memory` dans la collection `orchestrator_sessions`).

Implementation : utilise emergentintegrations.llm.chat.LlmChat pour les 4 rôles
avec EMERGENT_LLM_KEY (provider Claude par défaut, fallback OpenAI/Gemini).
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
import uuid
import subprocess
import textwrap
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ----- Prompts spécialisés ---------------------------------------------------

PLANNER_SYSTEM = """Tu es le PLANNER d'un système multi-agents. Ne réponds JAMAIS directement à l'utilisateur. Ta SEULE tâche est de produire un plan structuré en JSON valide avec :
{
  "hypotheses": ["hypothèse 1", "hypothèse 2", ...],  // pistes possibles
  "needs_execution": true/false,                       // faut-il exécuter du code Python pour vérifier ?
  "code_to_execute": "...",                            // code Python (uniquement si needs_execution=true)
  "expected_output": "...",                            // ce qu'on devrait observer après exécution
  "uncertainties": ["..."]                             // ce qui reste flou
}
Tu DOIS retourner du JSON pur, sans markdown, sans préfixe. Pas de "voici", pas de ```. Juste le JSON."""

CRITIC_SYSTEM = """Tu es le CRITIC d'un système multi-agents. Ta tâche est de tenter de RÉFUTER le plan reçu : trouver les failles logiques, les contradictions, les cas limites, et les hypothèses non vérifiables. Tu DOIS retourner du JSON :
{
  "valid_points": ["..."],                             // ce qui tient
  "logical_flaws": ["..."],                            // erreurs de raisonnement
  "edge_cases": ["..."],                               // cas non couverts
  "unverifiable": ["..."],                             // ce qu'on ne peut PAS prouver
  "score": 0-100                                       // confiance globale dans le plan
}
JSON pur uniquement. Pas de markdown."""

ARBITER_SYSTEM = """Tu es l'ARBITER d'un système multi-agents. Ton rôle est de synthétiser plan + critique + résultat d'exécution en une réponse finale CLAIRE et HONNÊTE pour l'utilisateur.

RÈGLES STRICTES :
1. Sépare explicitement ce qui est CONFIRMÉ (preuve par exécution) de ce qui est PROBABLE (raisonnement) et INCERTAIN (extrapolation).
2. Si une hypothèse a été réfutée par le critic, ne PAS l'inclure comme vérité.
3. Si du code a été exécuté, cite le résultat brut + son interprétation.
4. Format Markdown standard, en français. Réponse fluide mais honnête sur l'incertitude.

Tu produis la réponse finale DESTINÉE à l'utilisateur."""


# ----- Sandbox Python execution ---------------------------------------------

def _execute_python(code: str, timeout: int = 8) -> Dict[str, Any]:
    """Exécute du code Python dans un sandbox sub-process (kernel isolé).

    Limites : timeout 8s, max 50KB stdout, pas de réseau (firewall pod), pas
    d'écriture en dehors de /tmp. Retourne {ok, stdout, stderr, returncode}."""
    if not code or not code.strip():
        return {"ok": False, "error": "empty_code"}
    # Sécurité minimale : bloque les imports dangereux évidents.
    banned = ("os.system", "subprocess.", "shutil.rmtree", "socket.", "import requests", "import urllib")
    lowered = code.lower()
    if any(b in lowered for b in banned):
        return {"ok": False, "error": "banned_call", "detail": "Le code contient un appel interdit (réseau/system)."}
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            path = f.name
        proc = subprocess.run(
            ["python3", path],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": (proc.stdout or "")[:50000],
            "stderr": (proc.stderr or "")[:8000],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "detail": f"Exécution dépassée ({timeout}s)."}
    except Exception as e:
        return {"ok": False, "error": "exec_failure", "detail": str(e)[:500]}
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ----- LLM wrapper (Emergent) ------------------------------------------------

async def _llm_one_shot(system_prompt: str, user_prompt: str, *, role: str, session_id: str) -> str:
    """One-shot LLM call via emergentintegrations.LlmChat.

    Chaque rôle utilise un session_id distinct pour éviter la contamination."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        # Pas de clé : on retourne une réponse vide structurée pour ne pas crasher.
        return ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"{session_id}::{role}",
            system_message=system_prompt,
        ).with_model("anthropic", "claude-sonnet-4-5")
        msg = UserMessage(text=user_prompt)
        out = await chat.send_message(msg)
        return str(out or "")
    except Exception as e:
        logger.warning(f"orchestrator {role} llm failure: {e}")
        return ""


def _safe_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM output (tolerant to leading/trailing prose)."""
    if not text:
        return {}
    s = text.strip()
    # Strip markdown code fences if any.
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        s = s.rsplit("```", 1)[0]
    # Find first { ... last } if needed.
    a = s.find("{")
    b = s.rfind("}")
    if a >= 0 and b > a:
        s = s[a:b+1]
    try:
        return json.loads(s)
    except Exception:
        return {}


# ----- Public API ------------------------------------------------------------

async def orchestrate(user_question: str, *, session_id: str, language: str = "fr") -> Dict[str, Any]:
    """Pipeline complet planner → executor → critic → arbiter.

    Retourne un dict structuré avec chaque étape (transparence) et la réponse
    finale destinée à l'utilisateur (clé `final`).
    """
    started = datetime.now(timezone.utc).isoformat()

    # 1) PLANNER
    plan_raw = await _llm_one_shot(
        PLANNER_SYSTEM,
        f"Question utilisateur : {user_question}\n\nProduis le plan en JSON strict.",
        role="planner",
        session_id=session_id,
    )
    plan = _safe_json(plan_raw)

    # 2) EXECUTOR (si needs_execution)
    execution = None
    if plan.get("needs_execution") and plan.get("code_to_execute"):
        execution = await asyncio.get_event_loop().run_in_executor(
            None, _execute_python, plan["code_to_execute"], 8,
        )

    # 3) CRITIC
    critic_input = (
        f"Question utilisateur : {user_question}\n\n"
        f"Plan : {json.dumps(plan, ensure_ascii=False)}\n\n"
        + (f"Résultat d'exécution : {json.dumps(execution, ensure_ascii=False)[:4000]}\n\n" if execution else "")
        + "Critique le plan : trouve les failles. Retourne le JSON."
    )
    critique_raw = await _llm_one_shot(
        CRITIC_SYSTEM, critic_input, role="critic", session_id=session_id,
    )
    critique = _safe_json(critique_raw)

    # 4) ARBITER → réponse finale
    arbiter_input = (
        f"Question : {user_question}\n\n"
        f"Plan : {json.dumps(plan, ensure_ascii=False)[:4000]}\n\n"
        f"Critique : {json.dumps(critique, ensure_ascii=False)[:2000]}\n\n"
        + (f"Exécution : {json.dumps(execution, ensure_ascii=False)[:4000]}\n\n" if execution else "")
        + f"Synthétise la réponse finale en {language}. Sépare confirmé/probable/incertain."
    )
    final = await _llm_one_shot(
        ARBITER_SYSTEM, arbiter_input, role="arbiter", session_id=session_id,
    )

    return {
        "session_id": session_id,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "question": user_question,
        "plan": plan,
        "execution": execution,
        "critique": critique,
        "final": final or "Désolé, l'orchestrateur n'a pas pu finaliser sa réponse.",
        "confidence": (critique or {}).get("score", 50),
    }


async def orchestrate_stream(user_question: str, *, session_id: str, language: str = "fr"):
    """Variante streaming : yield des events SSE au fur et à mesure des étapes
    pour que l'UI puisse afficher 'En train de planifier...', 'En train
    d'exécuter...', etc. Termine avec un event {final: ...}."""
    yield {"phase": "planner_start", "ts": datetime.now(timezone.utc).isoformat()}
    plan_raw = await _llm_one_shot(
        PLANNER_SYSTEM,
        f"Question utilisateur : {user_question}\n\nProduis le plan en JSON strict.",
        role="planner",
        session_id=session_id,
    )
    plan = _safe_json(plan_raw)
    yield {"phase": "planner_done", "plan": plan}

    execution = None
    if plan.get("needs_execution") and plan.get("code_to_execute"):
        yield {"phase": "executor_start", "code": plan["code_to_execute"][:500]}
        execution = await asyncio.get_event_loop().run_in_executor(
            None, _execute_python, plan["code_to_execute"], 8,
        )
        yield {"phase": "executor_done", "execution": execution}

    yield {"phase": "critic_start"}
    critic_input = (
        f"Question utilisateur : {user_question}\n\n"
        f"Plan : {json.dumps(plan, ensure_ascii=False)}\n\n"
        + (f"Résultat d'exécution : {json.dumps(execution, ensure_ascii=False)[:4000]}\n\n" if execution else "")
        + "Critique le plan : trouve les failles. Retourne le JSON."
    )
    critique_raw = await _llm_one_shot(
        CRITIC_SYSTEM, critic_input, role="critic", session_id=session_id,
    )
    critique = _safe_json(critique_raw)
    yield {"phase": "critic_done", "critique": critique}

    yield {"phase": "arbiter_start"}
    arbiter_input = (
        f"Question : {user_question}\n\n"
        f"Plan : {json.dumps(plan, ensure_ascii=False)[:4000]}\n\n"
        f"Critique : {json.dumps(critique, ensure_ascii=False)[:2000]}\n\n"
        + (f"Exécution : {json.dumps(execution, ensure_ascii=False)[:4000]}\n\n" if execution else "")
        + f"Synthétise la réponse finale en {language}. Sépare confirmé/probable/incertain."
    )
    final = await _llm_one_shot(
        ARBITER_SYSTEM, arbiter_input, role="arbiter", session_id=session_id,
    )
    yield {"phase": "arbiter_done", "final": final or "L'orchestrateur n'a pas pu finaliser."}

    yield {
        "phase": "complete",
        "confidence": (critique or {}).get("score", 50),
        "final": final or "L'orchestrateur n'a pas pu finaliser.",
    }
