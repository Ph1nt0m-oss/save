"""iter129 — IA Dev Agent (Forge) : développement autonome avec moteur d'exécution visible.

Workflow : Planner → Task Executor (outils) → Validator → Response Generator.
Chaque étape émet un événement typé streamé en temps réel vers l'UI :
  status / status_done   : résumé opérationnel (jamais de pensées privées)
  search_done            : $ grep -rn "..." (résultats dépliables)
  file_viewed            : lecture d'un fichier du repo
  file_created/modified  : écriture workspace + diff avant/après dépliable
  code_executed          : sandbox Python (stdout/stderr dépliables)
  validation             : verdict du Validator (score, issues)

Yields : {"event": {...}} et {"delta": str} (réponse finale streamée).
"""
import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from orchestrator import _make_event, _read_file_safe, _grep_safe, _execute_python
from .common import format_history, lang_label, llm_json, stream_llm
from .registry import DEV_PLANNER_SYSTEM, DEV_VALIDATOR_SYSTEM, DEV_RESPONDER_SYSTEM
from .tools import workspace_write

logger = logging.getLogger(__name__)

MAX_STEPS = 8


async def run_dev_agent(message: str, *, session_id: str, project_id: Optional[str],
                        language: str = "fr",
                        history: Optional[List[Dict[str, Any]]] = None,
                        provider: str = "openai", model_id: str = "gpt-4o-mini",
                        emit=None) -> AsyncIterator[Dict[str, Any]]:
    async def ev(kind, summary, details=None, **extras):
        evt = _make_event(kind, summary, details, **extras)
        if emit:
            await emit(evt)
        return {"event": evt}

    # ---- 1) PLANNER ----
    yield await ev("status", "Analyse de la demande…", details={"agent": "dev", "message": message[:500]})
    ctx = format_history(history)
    plan = await llm_json(
        DEV_PLANNER_SYSTEM,
        (f"Historique de la conversation :\n{ctx}\n\n" if ctx else "")
        + f"Demande de développement :\n{message[:3000]}\n\nProduis le plan JSON.",
        session_id=f"{session_id}_devplan",
    )
    understanding = (plan.get("understanding") or "").strip()
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)][:MAX_STEPS]
    yield await ev("status_done", "✓ Compréhension du problème terminée",
                   details={"understanding": understanding, "plan": plan})
    if understanding:
        yield await ev("plan_ready", f"Plan : {understanding}",
                       details={"understanding": understanding,
                                "steps": [{"tool": s.get("tool"), "label": s.get("label"),
                                           "path": s.get("path"), "query": s.get("query")} for s in steps]})

    # ---- 2) TASK EXECUTOR ----
    executed: List[Dict[str, Any]] = []
    files_used: List[str] = []
    for step in steps:
        tool = (step.get("tool") or "").strip()
        label = (step.get("label") or "").strip()

        if tool == "search" and step.get("query"):
            q = str(step["query"])[:200]
            yield await ev("status", label or f"Recherche des fichiers concernés…")
            result = await asyncio.get_event_loop().run_in_executor(None, _grep_safe, q, 40)
            yield await ev("search_done", f'$ grep -rn "{q}"', details=result, query=q)
            executed.append({"tool": "search", "query": q,
                             "matches": (result.get("matches") or [])[:10]})

        elif tool == "read_repo" and step.get("path"):
            p = str(step["path"])[:300]
            result = _read_file_safe(p)
            summary = f"Analyse du code : {p}" if result.get("ok") else f"Fichier introuvable : {p}"
            yield await ev("file_viewed", summary, details=result, path=p)
            if result.get("ok"):
                files_used.append(p)
            executed.append({"tool": "read_repo", "path": p, "ok": result.get("ok"),
                             "excerpt": (result.get("content") or "")[:800]})

        elif tool == "write_file" and step.get("path"):
            p = str(step["path"])[:300]
            yield await ev("status", label or f"Écriture de {p}…")
            result = workspace_write(project_id or "global", p, str(step.get("content") or ""))
            if result.get("ok"):
                kind = "file_created" if result["action"] == "created" else "file_modified"
                summary = (f"{'Fichier créé' if kind == 'file_created' else 'Fichier modifié'} : {p} "
                           f"(+{result['lines_added']}/-{result['lines_removed']})")
                yield await ev(kind, summary, details=result, path=p,
                               lines_added=result["lines_added"], lines_removed=result["lines_removed"])
                files_used.append(p)
            else:
                yield await ev("error", f"Écriture impossible : {p} ({result.get('error')})", details=result)
            executed.append({"tool": "write_file", "path": p, "ok": result.get("ok"),
                             "action": result.get("action"),
                             "lines_added": result.get("lines_added"),
                             "lines_removed": result.get("lines_removed")})

        elif tool == "run_python" and step.get("code"):
            code = str(step["code"])[:8000]
            yield await ev("status", label or "Exécution du code (sandbox)…")
            result = await asyncio.get_event_loop().run_in_executor(None, _execute_python, code, 8)
            summary = "✓ Exécution réussie" if result.get("ok") else f"✗ Échec : {result.get('error', 'erreur')}"
            yield await ev("code_executed", summary, details={**result, "code": code})
            executed.append({"tool": "run_python", "ok": result.get("ok"),
                             "stdout": (result.get("stdout") or "")[:600],
                             "stderr": (result.get("stderr") or "")[:400]})

    # ---- 3) VALIDATOR ----
    yield await ev("status", "Validation automatique…")
    validation = await llm_json(
        DEV_VALIDATOR_SYSTEM,
        f"Demande : {message[:1500]}\n\nPlan : {json.dumps(plan, ensure_ascii=False)[:3000]}\n\n"
        f"Résultats d'exécution : {json.dumps(executed, ensure_ascii=False)[:4000]}\n\nValide en JSON strict.",
        session_id=f"{session_id}_devvalid",
    )
    score = validation.get("score")
    issues = validation.get("issues") or []
    v_summary = (f"✓ Validation réussie (score {score}/100)" if validation.get("ok")
                 else f"⚠ Validation : {len(issues)} problème(s) détecté(s)"
                 + (f" (score {score}/100)" if score is not None else ""))
    yield await ev("validation", v_summary, details=validation)

    # ---- 4) RESPONSE GENERATOR (streamé) ----
    yield await ev("status", "Rédaction de la réponse finale…")
    responder_input = (
        f"Demande utilisateur : {message[:2000]}\n\n"
        + (f"Historique : {ctx[:1200]}\n\n" if ctx else "")
        + f"Compréhension : {understanding}\n\n"
        f"Actions exécutées (résultats réels) : {json.dumps(executed, ensure_ascii=False)[:5000]}\n\n"
        f"Fichiers/Ressources : {json.dumps(files_used, ensure_ascii=False)}\n\n"
        f"Validation : {json.dumps(validation, ensure_ascii=False)[:1500]}\n\n"
        f"Rédige la réponse finale au FORMAT OBLIGATOIRE."
    )
    system = DEV_RESPONDER_SYSTEM.format(lang_label=lang_label(language))
    # iter149/156 — Identité registry + profil configuré pour l'agent "dev" (Forge).
    try:
        from utils.ai_profile_injector import compose_system_prompt
        from server import db as _srv_db
        system = await compose_system_prompt(_srv_db, "dev", system)
    except Exception as _err:
        logger.warning(f"dev_agent: identity+profile injection failed: {_err}")
    async for delta in stream_llm(system, responder_input, session_id=f"{session_id}_devresp",
                                  provider=provider, model_id=model_id):
        yield {"delta": delta}

    yield await ev("status_done", "✓ Tâche terminée",
                   details={"files": files_used, "steps_executed": len(executed)})
