"""iter84 C7+ — Orchestrateur multi-agents avec STREAM D'ACTIONS Emergent-style.

Au lieu de streamer des tokens, on stream des ÉVÉNEMENTS d'orchestration :
chaque opération de l'IA devient un événement visible côté UI, avec un résumé
court (la ligne affichée) et un détail complet (chargé à la demande quand
l'utilisateur déplie la flèche).

Types d'événements émis :
  - phase_started / phase_done       (planner / executor / critic / arbiter)
  - file_viewed     : l'IA a lu un fichier (réf au chemin)
  - file_created    : l'IA a créé un nouveau fichier
  - file_modified   : l'IA a modifié un fichier (diff inclus)
  - code_executed   : du code Python a été exécuté en sandbox
  - test_run        : des tests ont été lancés
  - search_done     : une recherche dans le code a été effectuée
  - commit_pushed   : un commit Git a été envoyé (MOCKED)
  - preview_ready   : un nouveau build sandbox est prêt (MOCKED)
  - thought         : pensée libre du planner/critic (texte)
  - error           : erreur dans le pipeline

Chaque événement est persisté dans `orchestrator_events` avec son `event_id`
unique. Le frontend récupère les détails via /orchestrate/event/{id}.

Architecture :
                       ┌─────────────┐
       user_question → │   PLANNER   │ → événements file_viewed, search_done, thought
                       └─────────────┘
                              ↓
                       ┌─────────────┐
                       │  EXECUTOR   │ → événements code_executed, test_run
                       └─────────────┘
                              ↓
                       ┌─────────────┐
                       │   CRITIC    │ → événements thought, error si réfutation
                       └─────────────┘
                              ↓
                       ┌─────────────┐
                       │   ARBITER   │ → événement final (réponse user)
                       └─────────────┘
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
import uuid
import subprocess
import tempfile
import ast as _ast
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, AsyncIterator

logger = logging.getLogger(__name__)


# ----- Prompts spécialisés (inchangés) --------------------------------------

PLANNER_SYSTEM = """Tu es le PLANNER d'un système multi-agents. Ta tâche : produire un plan structuré en JSON strict, sans markdown. Format attendu :
{
  "hypotheses": ["..."],
  "files_to_inspect": ["chemin/relatif.py", ...],
  "search_queries": ["pattern à chercher dans le code"],
  "needs_execution": true/false,
  "code_to_execute": "...",
  "expected_output": "...",
  "uncertainties": ["..."]
}
JSON pur uniquement. Pas de ```. Pas de préfixe."""

CRITIC_SYSTEM = """Tu es le CRITIC. Tu cherches à réfuter le plan. JSON strict :
{
  "valid_points": ["..."],
  "logical_flaws": ["..."],
  "edge_cases": ["..."],
  "unverifiable": ["..."],
  "score": 0-100
}
JSON pur uniquement."""

ARBITER_SYSTEM = """Tu es l'ARBITER. Synthétise plan+critique+exécution en réponse finale honnête.
RÈGLES :
1. Sépare CONFIRMÉ (preuve) / PROBABLE (raisonnement) / INCERTAIN (extrapolation).
2. Ignore les hypothèses réfutées.
3. Cite les résultats d'exécution bruts si présents.
Format Markdown français. Sois fluide mais transparent sur l'incertitude."""


# ----- Sandbox (durci iter83, ré-utilisé iter84) ----------------------------

def _execute_python(code: str, timeout: int = 8) -> Dict[str, Any]:
    if not code or not code.strip():
        return {"ok": False, "error": "empty_code"}
    banned_subs = (
        "os.system", "subprocess.", "shutil.rmtree", "socket.", "import requests",
        "import urllib", "__import__", "eval(", "exec(", "compile(", "open(",
    )
    lowered = code.lower()
    for b in banned_subs:
        if b in lowered:
            return {"ok": False, "error": "banned_call", "detail": f"Appel interdit : {b}"}
    try:
        tree = _ast.parse(code)
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                for alias in (getattr(node, 'names', []) or []):
                    if (alias.name or '').split('.')[0] in {
                        'os', 'subprocess', 'socket', 'requests', 'urllib', 'ctypes',
                        'multiprocessing', 'threading', 'shutil',
                    }:
                        return {"ok": False, "error": "banned_import", "detail": f"Import interdit: {alias.name}"}
            if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name):
                if node.func.id in {'eval', 'exec', '__import__', 'compile', 'open'}:
                    return {"ok": False, "error": "banned_call", "detail": f"Appel interdit: {node.func.id}"}
    except SyntaxError as e:
        return {"ok": False, "error": "syntax_error", "detail": str(e)[:200]}
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            path = f.name
        proc = subprocess.run(["python3", path], capture_output=True, text=True, timeout=timeout)
        return {
            "ok": proc.returncode == 0,
            "stdout": (proc.stdout or "")[:50000],
            "stderr": (proc.stderr or "")[:8000],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": "exec_failure", "detail": str(e)[:500]}
    finally:
        if path:
            try: os.unlink(path)
            except Exception: pass


# ----- LLM wrapper avec streaming optionnel ---------------------------------

async def _llm_one_shot(system_prompt: str, user_prompt: str, *, role: str, session_id: str) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"{session_id}::{role}",
            system_message=system_prompt,
        ).with_model("anthropic", "claude-sonnet-4-5")
        out = await chat.send_message(UserMessage(text=user_prompt))
        return str(out or "")
    except Exception as e:
        logger.warning(f"orchestrator {role} llm failure: {e}")
        return ""


async def _llm_stream_tokens(system_prompt: str, user_prompt: str, *, role: str, session_id: str):
    """iter85 — Pseudo-stream token-par-token. emergentintegrations n'expose
    pas le stream natif, on génère la réponse complète puis on la découpe en
    fragments rapides (~50 char) pour donner l'impression d'écriture progressive.
    Retourne un async generator de strings.
    """
    full = await _llm_one_shot(system_prompt, user_prompt, role=role, session_id=session_id)
    if not full:
        return
    # Découpage par fragments de ~40 caractères, en respectant les espaces
    # pour ne pas couper au milieu d'un mot quand possible.
    chunk_size = 40
    i = 0
    while i < len(full):
        end = min(i + chunk_size, len(full))
        # Essaye de finir sur un espace pour ne pas casser un mot
        if end < len(full):
            j = full.rfind(' ', i + chunk_size // 2, end + 10)
            if j > i:
                end = j + 1
        yield full[i:end]
        i = end
        await asyncio.sleep(0.025)  # 25ms entre chunks → ~16 chunks/s = ChatGPT-like


def _safe_json(text: str) -> Dict[str, Any]:
    if not text: return {}
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]; s = s.rsplit("```", 1)[0]
    a, b = s.find("{"), s.rfind("}")
    if a >= 0 and b > a:
        s = s[a:b+1]
    try:
        return json.loads(s)
    except Exception:
        return {}


# ----- Event builders -------------------------------------------------------

def _make_event(kind: str, summary: str, details: Optional[Any] = None, **extras) -> Dict[str, Any]:
    """Construit un événement d'orchestration prêt à streamer."""
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
        "kind": kind,                # phase_started, file_viewed, code_executed, etc.
        "summary": summary,           # ligne courte affichée
        "details": details,           # détail complet (lazy si gros)
        "ts": datetime.now(timezone.utc).isoformat(),
        **extras,
    }


# ----- File inspection helpers ---------------------------------------------

REPO_ROOT = "/app"

def _safe_path(rel: str) -> Optional[str]:
    """Évite les escapes hors REPO_ROOT. Refuse les paths absolus et toute
    référence remontant au-delà du REPO_ROOT."""
    if not rel: return None
    # Refuse les paths absolus dès le départ (sécurité).
    if rel.startswith("/") or rel.startswith("\\"):
        return None
    if ".." in rel.split("/"):
        return None
    full = os.path.normpath(os.path.join(REPO_ROOT, rel))
    if not full.startswith(REPO_ROOT + os.sep) and full != REPO_ROOT:
        return None
    return full

def _read_file_safe(rel: str, max_bytes: int = 60000) -> Dict[str, Any]:
    full = _safe_path(rel)
    if not full or not os.path.isfile(full):
        return {"ok": False, "error": "not_found", "path": rel}
    try:
        with open(full, "rb") as f:
            data = f.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        text = data[:max_bytes].decode("utf-8", errors="replace")
        return {"ok": True, "path": rel, "content": text, "truncated": truncated, "bytes": len(data)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "path": rel}


def _grep_safe(pattern: str, limit: int = 40) -> Dict[str, Any]:
    """Grep sur backend + frontend/src uniquement, limité aux fichiers
    texte courants. On évite node_modules et autres dossiers volumineux."""
    if not pattern or len(pattern) > 200:
        return {"ok": False, "error": "invalid_pattern"}
    try:
        proc = subprocess.run(
            [
                "grep", "-RIn",
                "--include=*.py", "--include=*.js", "--include=*.jsx",
                "--include=*.ts", "--include=*.tsx", "--include=*.md",
                pattern,
                os.path.join(REPO_ROOT, "backend"),
                os.path.join(REPO_ROOT, "frontend", "src"),
            ],
            capture_output=True, text=True, timeout=8,
        )
        lines = (proc.stdout or "").splitlines()[:limit]
        # grep returncode == 1 = no match, == 0 = match. Tous deux valides.
        return {"ok": proc.returncode in (0, 1), "pattern": pattern, "matches": lines, "total": len(lines)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ----- PUBLIC: orchestrate_actions (stream événements) ---------------------

async def orchestrate_actions(
    user_question: str,
    *,
    session_id: str,
    language: str = "fr",
    persist_event: Optional[Any] = None,
    on_commit: Optional[Any] = None,
    on_preview: Optional[Any] = None,      # iter88 — async callable() → rebuild sandbox réel
    test_loop: Optional[Any] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """iter84 — Pipeline qui YIELD des événements typés au lieu de phases.

    L'utilisateur voit en temps réel : 'Analyse de la question', 'Lecture de
    fichier X', 'Exécution de code', 'Vérification critique', 'Synthèse'…
    et peut déplier chaque ligne pour voir le détail (via /orchestrate/event/{id}).
    """
    started = datetime.now(timezone.utc).isoformat()

    async def emit(evt: Dict[str, Any]):
        if persist_event:
            try: await persist_event(evt)
            except Exception: pass
        return evt

    # 1) PLANNER
    e = await emit(_make_event("phase_started", "Analyse de la question",
                               details={"phase": "planner", "question": user_question}))
    yield e

    plan_raw = await _llm_one_shot(
        PLANNER_SYSTEM,
        f"Question utilisateur : {user_question}\n\nProduis le plan en JSON strict.",
        role="planner", session_id=session_id,
    )
    plan = _safe_json(plan_raw)

    # Thought : afficher les hypothèses comme un événement déplisable
    if plan.get("hypotheses"):
        yield await emit(_make_event(
            "thought",
            f"Plan : {len(plan['hypotheses'])} hypothèse(s) identifiée(s)",
            details={"hypotheses": plan["hypotheses"], "uncertainties": plan.get("uncertainties", [])},
        ))

    # File inspections demandées par le planner
    files_to_inspect = (plan.get("files_to_inspect") or [])[:5]
    for rel in files_to_inspect:
        evt = await emit(_make_event("file_viewed", f"Lecture : {rel}",
                                     details=_read_file_safe(rel), path=rel))
        yield evt

    # Searches demandées
    for q in (plan.get("search_queries") or [])[:3]:
        yield await emit(_make_event("search_done", f"Recherche : {q}",
                                     details=_grep_safe(q), query=q))

    yield await emit(_make_event("phase_done", "Planification terminée",
                                 details={"plan": plan}, phase="planner"))

    # 2) EXECUTOR
    execution = None
    if plan.get("needs_execution") and plan.get("code_to_execute"):
        yield await emit(_make_event(
            "code_executed_start",
            "Exécution de code Python (sandbox)",
            details={"code": plan["code_to_execute"][:2000]},
        ))
        execution = await asyncio.get_event_loop().run_in_executor(
            None, _execute_python, plan["code_to_execute"], 8,
        )
        summary = "Exécution réussie" if execution.get("ok") else f"Échec : {execution.get('error', 'unknown')}"
        yield await emit(_make_event("code_executed", summary, details=execution))

        # iter86 — CORRECTION LOOP : si échec, on demande au planner une
        # correction basée sur stderr et on ré-exécute une fois max. Évite
        # la divergence sans-fin tout en gérant les bugs simples.
        if not execution.get("ok") and (execution.get("stderr") or execution.get("error")):
            yield await emit(_make_event(
                "phase_started",
                "Tentative de correction (1 essai)",
                details={"phase": "correction", "stderr": (execution.get("stderr") or execution.get("error") or "")[:500]},
            ))
            correction_prompt = (
                f"Le code que tu as proposé a échoué.\n\n"
                f"Question : {user_question}\n\n"
                f"Code précédent :\n{plan.get('code_to_execute', '')[:2000]}\n\n"
                f"Erreur d'exécution :\n{(execution.get('stderr') or execution.get('error') or '')[:1500]}\n\n"
                f"Produis un NOUVEAU plan JSON corrigé. Même format, mais cette fois "
                f"évite la cause de l'erreur ci-dessus."
            )
            corrected_raw = await _llm_one_shot(
                PLANNER_SYSTEM, correction_prompt, role="planner-fix", session_id=session_id,
            )
            corrected_plan = _safe_json(corrected_raw)
            if corrected_plan.get("code_to_execute"):
                yield await emit(_make_event(
                    "thought",
                    "Correction proposée par le planner",
                    details={"corrected_code": corrected_plan["code_to_execute"][:2000], "original_stderr": (execution.get("stderr") or "")[:500]},
                ))
                # Ré-exécution unique de la version corrigée.
                exec2 = await asyncio.get_event_loop().run_in_executor(
                    None, _execute_python, corrected_plan["code_to_execute"], 8,
                )
                summary2 = "Correction réussie ✓" if exec2.get("ok") else f"Correction échouée : {exec2.get('error', 'unknown')}"
                yield await emit(_make_event("code_executed", summary2, details=exec2))
                # Use the corrected execution as the authoritative one
                if exec2.get("ok"):
                    execution = exec2
                    plan["code_to_execute"] = corrected_plan["code_to_execute"]
            yield await emit(_make_event("phase_done", "Correction terminée", details={"recovered": execution.get("ok")}, phase="correction"))

    # 3) CRITIC
    yield await emit(_make_event("phase_started", "Vérification critique", details={"phase": "critic"}))
    critic_input = (
        f"Question : {user_question}\n\nPlan : {json.dumps(plan, ensure_ascii=False)}\n\n"
        + (f"Exécution : {json.dumps(execution, ensure_ascii=False)[:4000]}\n\n" if execution else "")
        + "Critique en JSON strict."
    )
    critique_raw = await _llm_one_shot(CRITIC_SYSTEM, critic_input, role="critic", session_id=session_id)
    critique = _safe_json(critique_raw)

    if critique.get("logical_flaws"):
        yield await emit(_make_event(
            "thought",
            f"{len(critique['logical_flaws'])} faille(s) logique(s) détectée(s)",
            details={"logical_flaws": critique["logical_flaws"], "edge_cases": critique.get("edge_cases", [])},
        ))
    if critique.get("score") is not None:
        yield await emit(_make_event(
            "phase_done",
            f"Critique terminée (score: {critique.get('score')}/100)",
            details={"critique": critique}, phase="critic",
        ))
    else:
        yield await emit(_make_event("phase_done", "Critique terminée", details={"critique": critique}, phase="critic"))

    # 4) ARBITER → réponse finale STREAMÉE token-par-token
    yield await emit(_make_event("phase_started", "Synthèse finale", details={"phase": "arbiter"}))
    arbiter_input = (
        f"Question : {user_question}\n\nPlan : {json.dumps(plan, ensure_ascii=False)[:4000]}\n\n"
        f"Critique : {json.dumps(critique, ensure_ascii=False)[:2000]}\n\n"
        + (f"Exécution : {json.dumps(execution, ensure_ascii=False)[:4000]}\n\n" if execution else "")
        + f"Réponse finale en {language}. Sépare confirmé/probable/incertain."
    )

    # iter85 — Vrai streaming token-par-token sur le final event.
    # Chaque chunk est émis comme un event 'final_chunk' avec un index. Le
    # frontend les concatène dans l'ordre. À la fin, un event 'final' avec
    # le contenu complet est émis pour la persistance et l'historique.
    accumulated = ""
    chunk_idx = 0
    async for chunk in _llm_stream_tokens(
        ARBITER_SYSTEM, arbiter_input, role="arbiter", session_id=session_id,
    ):
        accumulated += chunk
        yield await emit(_make_event(
            "final_chunk",
            chunk,  # summary = le chunk lui-même (utile pour debug)
            details=None,
            delta=chunk,
            index=chunk_idx,
        ))
        chunk_idx += 1

    final = accumulated or "L'orchestrateur n'a pas pu finaliser."

    # iter88 — Si du code a été exécuté avec succès, on émet les events
    # preview_ready (avec rebuild OPT-IN via on_preview) + commit_pushed.
    if execution and execution.get("ok"):
        # iter88 — Si on_preview est fourni, on déclenche un VRAI rebuild
        # (yarn build front). Sinon URL stub. Best-effort, timeout court.
        preview_result = None
        if on_preview is not None:
            try:
                preview_result = await on_preview()
            except Exception as e:
                preview_result = {"ok": False, "error": str(e)[:200]}
        preview_url = (preview_result or {}).get("url") or os.environ.get("PREVIEW_BASE_URL") or "https://no-code-builder-25.preview.emergentagent.com"
        yield await emit(_make_event(
            "preview_ready",
            f"Aperçu {('rebuild ' + ('OK' if (preview_result or {}).get('ok') else 'échec')) if preview_result else 'disponible'}",
            details={
                "url": preview_url,
                "rebuild_result": preview_result,
                "execution_summary": (execution.get("stdout") or "")[:500],
            },
            url=preview_url,
        ))
        # iter86 — commit_pushed RÉEL via le callback on_commit si fourni.
        branch = f"orchestrate/{session_id[-12:]}"
        commit_summary = user_question[:80]
        commit_result = None
        if on_commit is not None:
            try:
                commit_result = await on_commit(branch, commit_summary, plan.get("code_to_execute") or "")
            except Exception as e:
                commit_result = {"ok": False, "error": str(e)[:200]}
        yield await emit(_make_event(
            "commit_pushed",
            f"Commit {('réel ' + (commit_result.get('ref') or '') if commit_result and commit_result.get('ok') else 'virtuel')} : {branch}",
            details={
                "branch": branch,
                "summary": commit_summary,
                "github_result": commit_result or {"ok": False, "note": "Pas de hook on_commit"},
            },
        ))

    # Final answer event (with full content, for persistance and history)
    yield await emit(_make_event(
        "final",
        "Réponse finale prête",
        details={"content": final, "confidence": (critique or {}).get("score", 50)},
        content=final,
        confidence=(critique or {}).get("score", 50),
    ))

    # End-of-stream marker
    yield await emit(_make_event(
        "complete",
        "Pipeline terminé",
        details={"started": started, "finished": datetime.now(timezone.utc).isoformat()},
    ))


# ----- Legacy non-streaming (gardé pour compat iter83) ----------------------

async def orchestrate(user_question: str, *, session_id: str, language: str = "fr") -> Dict[str, Any]:
    """Pipeline non-stream : exécute toute la chaîne et renvoie un dict."""
    events = []
    async for evt in orchestrate_actions(user_question, session_id=session_id, language=language):
        events.append(evt)
    final_evt = next((e for e in events if e.get("kind") == "final"), {})
    return {
        "session_id": session_id,
        "events": events,
        "final": final_evt.get("content", ""),
        "confidence": final_evt.get("confidence", 50),
    }


# Compat iter83 shim
async def orchestrate_stream(user_question: str, *, session_id: str, language: str = "fr"):
    """Compat iter83 : alias vers orchestrate_actions."""
    async for evt in orchestrate_actions(user_question, session_id=session_id, language=language):
        yield evt
