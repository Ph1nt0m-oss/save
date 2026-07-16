"""iter123 — Routes /chat/* avancées + /orchestrate/test-loop extraites de server.py.

7 endpoints (lourds, ~770 lignes au total) :
  - POST /chat/translate-messages        : batch translate via gpt-5.2 + cache MongoDB
  - POST /chat/suggest-enhancements      : claude-sonnet propose 3-5 améliorations
  - POST /chat/tts                       : OpenAI TTS → MP3 base64
  - POST /chat/orchestrate                : pipeline planner→executor→critic (sync)
  - POST /chat/orchestrate-stream         : pipeline en SSE (avec on_commit / on_preview hooks)
  - POST /orchestrate/test-loop           : pytest en boucle, événements SSE
  - POST /chat/stream                     : VRAI streaming token-par-token via emergentintegrations

Helpers injectés explicitement pour éviter les imports circulaires :
  - db, logger, get_current_user
  - send_chat_message_fn   : fallback complexe pour /chat/stream
  - ChatMessageInput_cls   : modèle Pydantic du fallback
  - GITHUB_ENABLED, push_to_github
"""
import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Orchestrator is a stand-alone module already used elsewhere; safe to import here.
from orchestrator import orchestrate as _run_orchestrate  # noqa: F401
from orchestrator import orchestrate_actions as _stream_actions


class TranslateMessagesBatchIn(BaseModel):
    messages: List[Dict[str, Any]]  # [{message_id, content}]
    target_lang: str


class EnhancementAnalyzeIn(BaseModel):
    last_ai_message: str
    project_type: Optional[str] = None
    language: Optional[str] = "fr"


class TTSIn(BaseModel):
    text: str
    voice: Optional[str] = "alloy"


class OrchestrateIn(BaseModel):
    message: str
    project_id: Optional[str] = None
    language: Optional[str] = "fr"
    enable_commit: Optional[bool] = False
    enable_preview_rebuild: Optional[bool] = False


class TestLoopIn(BaseModel):
    target: Optional[str] = "backend"
    path: Optional[str] = "tests/"
    project_id: Optional[str] = None


class ChatStreamIn(BaseModel):
    message: str
    mode: str = "online"
    project_id: Optional[str] = None
    language: Optional[str] = "fr"
    model: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    # iter128.6 — Persona créa-only. Si `aiReplies` est explicitement False
    # ET que l'appelant est la créatrice physique, on bypass la génération
    # IA (la créa veut parler à la place / interrompre). Champ ignoré pour
    # tout autre rôle. Cf. CreatorChatPersonaBar.jsx.
    persona_override: Optional[Dict[str, Any]] = None


def build_chat_advanced_router(
    db,
    *,
    get_current_user,
    logger,
    send_chat_message_fn,
    ChatMessageInput_cls,
    GITHUB_ENABLED,
    push_to_github,
):
    router = APIRouter()

    async def _persist_event(event, *, user_id, session_id, project_id):
        try:
            await db.orchestrator_events.insert_one({
                "event_id": event.get("event_id"),
                "user_id": user_id,
                "session_id": session_id,
                "project_id": project_id,
                "kind": event.get("kind"),
                "summary": event.get("summary"),
                "details": event.get("details"),
                "ts": event.get("ts"),
            })
        except Exception:
            pass

    # ============================== /chat/translate-messages ============================

    @router.post("/chat/translate-messages")
    async def translate_chat_messages(request: Request, payload: TranslateMessagesBatchIn):
        user_id = await get_current_user(request)
        target = (payload.target_lang or "en").strip().lower()
        items = payload.messages or []
        if not items or not target:
            return {"translations": {}}
        items = items[:200]
        msg_ids = [m.get("message_id") for m in items if m.get("message_id")]
        if not msg_ids:
            return {"translations": {}}
        cached_rows = await db.chat_message_translations.find(
            {"message_id": {"$in": msg_ids}, "lang": target},
            {"_id": 0, "message_id": 1, "translated": 1},
        ).to_list(length=len(msg_ids))
        cache_map = {r["message_id"]: r["translated"] for r in cached_rows}
        todo = [m for m in items if m.get("message_id") not in cache_map and (m.get("content") or "").strip()]
        if not todo:
            return {"translations": cache_map, "cached_hits": len(cache_map)}
        new_translations: Dict[str, str] = {}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            key = os.environ.get("EMERGENT_LLM_KEY")
            if not key:
                return {"translations": cache_map, "error": "llm_unavailable"}
            BATCH = 8
            for offset in range(0, len(todo), BATCH):
                chunk = todo[offset:offset + BATCH]
                joined = "\n".join(f"[{i}] {(m.get('content') or '')[:1500]}" for i, m in enumerate(chunk))
                chat = LlmChat(
                    api_key=key,
                    session_id=f"trans_msg_{uuid.uuid4().hex[:6]}",
                    system_message=(
                        f"Translate each numbered message into {target}. "
                        f"Output ONLY the translations in the exact same numbered format ([0] xxx). "
                        f"Keep meaning, tone, and formatting. No quotes, no prose."
                    ),
                ).with_model("openai", "gpt-5.2")
                response = (await chat.send_message(UserMessage(text=joined)) or "").strip()
                lines = [l for l in response.split("\n") if l.strip()]
                for line in lines:
                    line = line.strip()
                    if not line.startswith("["):
                        continue
                    try:
                        bracket_end = line.index("]")
                        idx_str = line[1:bracket_end]
                        idx = int(idx_str)
                        text = line[bracket_end + 1:].strip()
                        if 0 <= idx < len(chunk) and text:
                            mid = chunk[idx].get("message_id")
                            if mid:
                                new_translations[mid] = text[:2000]
                    except (ValueError, IndexError):
                        continue
            if new_translations:
                await db.chat_message_translations.insert_many([
                    {"message_id": mid, "lang": target, "translated": txt,
                     "ts": datetime.now(timezone.utc).isoformat(), "user_id": user_id}
                    for mid, txt in new_translations.items()
                ])
        except Exception as e:
            logger.warning(f"chat messages translate failed: {e}")
        cache_map.update(new_translations)
        return {"translations": cache_map, "cached_hits": len(cached_rows),
                "new_translations": len(new_translations)}

    # ============================== /chat/suggest-enhancements ==========================

    @router.post("/chat/suggest-enhancements")
    async def suggest_enhancements(request: Request, payload: EnhancementAnalyzeIn):
        await get_current_user(request)
        text = (payload.last_ai_message or "").strip()
        if not text:
            return {"suggestions": []}
        lang = (payload.language or "fr").strip().lower()
        project_type = payload.project_type or "chat"

        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            key = os.environ.get("EMERGENT_LLM_KEY")
            if not key:
                return {"suggestions": [], "error": "llm_unavailable"}
            prompt = (
                f"Analyse la réponse précédente de l'assistant IA (en {lang}) et propose 3 à 5 "
                f"améliorations CONCRÈTES et ACTIONNABLES que l'utilisateur pourrait demander ensuite. "
                f"Contexte projet : {project_type}.\n\n"
                f"Réponse IA :\n\"\"\"{text[:3000]}\"\"\"\n\n"
                f"Réponds STRICTEMENT en JSON valide avec ce format :\n"
                f'[{{"kind": "feature|fix|design|integration|performance", "title": "court titre (≤60 chars)", "description": "explication concrète (≤180 chars)"}}, ...]\n\n'
                f"Règles :\n"
                f"- Choisis le 'kind' qui correspond le mieux à chaque suggestion\n"
                f"- Titres courts et orientés action (verbe à l'infinitif)\n"
                f"- Descriptions concrètes (pas de blabla)\n"
                f"- Adapte au contexte projet ({project_type})\n"
                f"- Réponds UNIQUEMENT le JSON, rien d'autre."
            )
            chat = LlmChat(
                api_key=key,
                session_id=f"enh_sug_{uuid.uuid4().hex[:6]}",
                system_message=(
                    "You are an expert software architect and product manager. "
                    "You analyze AI responses and propose contextual, actionable "
                    "enhancement suggestions. Always respond in valid JSON only."
                ),
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            response = (await chat.send_message(UserMessage(text=prompt)) or "").strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1]) if len(lines) >= 3 else response
            import json as _json
            parsed = _json.loads(response)
            if not isinstance(parsed, list):
                return {"suggestions": []}
            suggestions = []
            valid_kinds = {"feature", "fix", "design", "integration", "performance"}
            for i, item in enumerate(parsed[:5]):
                if not isinstance(item, dict):
                    continue
                kind = item.get("kind") or "feature"
                if kind not in valid_kinds:
                    kind = "feature"
                title = str(item.get("title") or "").strip()[:80]
                desc = str(item.get("description") or "").strip()[:200]
                if not title:
                    continue
                suggestions.append({
                    "id": f"enh-llm-{uuid.uuid4().hex[:8]}",
                    "kind": kind, "title": title, "description": desc,
                })
            return {"suggestions": suggestions}
        except Exception as e:
            logger.warning(f"enhancement suggestion failed: {e}")
            return {"suggestions": [], "error": str(e)[:200]}

    # ============================== /chat/tts ==========================================

    @router.post("/chat/tts")
    async def chat_tts(request: Request, payload: TTSIn):
        await get_current_user(request)
        text = (payload.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Texte vide.")
        if len(text) > 4000:
            text = text[:4000]
        voice = payload.voice or "alloy"
        if voice not in ("alloy", "echo", "fable", "onyx", "nova", "shimmer"):
            voice = "alloy"
        try:
            from openai import AsyncOpenAI
            key = os.environ.get("EMERGENT_LLM_KEY")
            if not key:
                raise HTTPException(status_code=503, detail="TTS indisponible (clé manquante).")
            client = AsyncOpenAI(
                api_key=key,
                base_url="https://integrations.emergentagent.com/llm",
                timeout=30.0,
            )
            response = await client.audio.speech.create(
                model="tts-1", voice=voice, input=text, response_format="mp3",
            )
            audio_bytes = response.read() if hasattr(response, 'read') else response.content
            import base64
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            return {"audio_base64": audio_b64, "mime_type": "audio/mpeg",
                    "voice": voice, "char_count": len(text)}
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"TTS failed: {e}")
            raise HTTPException(status_code=503, detail=f"TTS indisponible: {str(e)[:150]}")

    # ============================== /chat/orchestrate (sync) ===========================

    @router.post("/chat/orchestrate")
    async def chat_orchestrate(request: Request, payload: OrchestrateIn):
        user_id = await get_current_user(request)
        session_id = f"orch_{user_id}_{payload.project_id or 'global'}"
        result = await _run_orchestrate(
            payload.message, session_id=session_id, language=payload.language or "fr",
        )
        try:
            for evt in (result.get("events") or []):
                await _persist_event(evt, user_id=user_id, session_id=session_id,
                                     project_id=payload.project_id)
        except Exception:
            pass
        return result

    # ============================== /chat/orchestrate-stream (SSE) =====================

    @router.post("/chat/orchestrate-stream")
    async def chat_orchestrate_stream(request: Request, payload: OrchestrateIn):
        user_id = await get_current_user(request)
        session_id = f"orch_{user_id}_{payload.project_id or 'global'}"
        lang = payload.language or "fr"

        async def persist(evt):
            await _persist_event(evt, user_id=user_id, session_id=session_id,
                                 project_id=payload.project_id)

        async def on_commit_real(branch: str, summary: str, content: str):
            if not GITHUB_ENABLED:
                return {"ok": False, "error": "GITHUB_DISABLED"}
            if not getattr(payload, "enable_commit", False):
                return {"ok": False, "note": "enable_commit=false (opt-in)"}
            safe_branch = branch.replace("/", "-").replace(" ", "-")[:48]
            file_path = f"orchestrate-runs/{safe_branch}.py"
            body = f"# Orchestrator run for: {summary}\n# Branch: {branch}\n\n{content}\n"
            ok = await push_to_github(file_path, body, branch="main", retries=2)
            return {"ok": bool(ok), "ref": file_path, "branch_label": branch}

        async def on_preview_real():
            if not getattr(payload, "enable_preview_rebuild", False):
                return {
                    "ok": False, "note": "enable_preview_rebuild=false (opt-in)",
                    "url": os.environ.get("PREVIEW_BASE_URL") or "https://no-code-builder-25.preview.emergentagent.com",
                }
            import subprocess as _sub
            import asyncio as _aio
            try:
                loop = _aio.get_event_loop()
                proc = await loop.run_in_executor(
                    None,
                    lambda: _sub.run(
                        ["yarn", "build"],
                        capture_output=True, text=True, timeout=90, cwd="/app/frontend",
                    ),
                )
                base_url = os.environ.get("PREVIEW_BASE_URL") or "https://no-code-builder-25.preview.emergentagent.com"
                return {
                    "ok": proc.returncode == 0,
                    "url": base_url,
                    "returncode": proc.returncode,
                    "build_summary": ((proc.stdout or "")[-2000:] + (("\n" + (proc.stderr or "")[-1000:]) if proc.stderr else "")),
                }
            except Exception as e:
                return {"ok": False, "error": str(e)[:300]}

        async def event_gen():
            try:
                async for evt in _stream_actions(
                    payload.message, session_id=session_id, language=lang,
                    persist_event=persist,
                    on_commit=on_commit_real,
                    on_preview=on_preview_real,
                ):
                    payload_evt = {k: v for k, v in evt.items() if k != "details"}
                    yield f"data: {json.dumps(payload_evt, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'kind': 'error', 'summary': str(e)[:300]}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })

    # ============================== /orchestrate/test-loop (SSE pytest) =================

    @router.post("/orchestrate/test-loop")
    async def orchestrate_test_loop(request: Request, payload: TestLoopIn):
        user_id = await get_current_user(request)
        session_id = f"testloop_{user_id}_{payload.project_id or 'global'}"

        async def event_gen():
            import subprocess as _sub
            evt0 = {
                "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                "kind": "test_run",
                "summary": f"Lancement des tests : {payload.target}/{payload.path}",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            await _persist_event(evt0, user_id=user_id, session_id=session_id,
                                 project_id=payload.project_id)
            yield f"data: {json.dumps(evt0, ensure_ascii=False)}\n\n"

            try:
                if payload.target == "backend":
                    safe_path = (payload.path or "tests/").lstrip("/")
                    if ".." in safe_path:
                        raise HTTPException(status_code=400, detail="Path invalide.")
                    full_path = os.path.normpath(os.path.join("/app/backend", safe_path))
                    if not full_path.startswith("/app/backend"):
                        raise HTTPException(status_code=400, detail="Path hors backend.")

                    proc = _sub.run(
                        ["python", "-m", "pytest", full_path, "-q", "--tb=short", "--no-header"],
                        capture_output=True, text=True, timeout=90, cwd="/app/backend",
                    )
                    summary_line = ""
                    for line in (proc.stdout or "").splitlines()[::-1]:
                        if "passed" in line or "failed" in line or "error" in line:
                            summary_line = line.strip(); break
                    kind = "test_run" if proc.returncode in (0, 5) else "error"
                    summary = summary_line or (f"pytest exit {proc.returncode}")
                    evt1 = {
                        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                        "kind": kind, "summary": summary,
                        "details": {
                            "returncode": proc.returncode,
                            "stdout": (proc.stdout or "")[-8000:],
                            "stderr": (proc.stderr or "")[-2000:],
                        },
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                    await _persist_event(evt1, user_id=user_id, session_id=session_id,
                                         project_id=payload.project_id)
                    p1 = {k: v for k, v in evt1.items() if k != "details"}
                    yield f"data: {json.dumps(p1, ensure_ascii=False)}\n\n"
                else:
                    evt1 = {
                        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                        "kind": "error",
                        "summary": f"target inconnu : {payload.target}",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                    await _persist_event(evt1, user_id=user_id, session_id=session_id,
                                         project_id=payload.project_id)
                    yield f"data: {json.dumps(evt1, ensure_ascii=False)}\n\n"
            except Exception as e:
                evt_err = {
                    "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                    "kind": "error",
                    "summary": f"test-loop crash : {str(e)[:200]}",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                yield f"data: {json.dumps(evt_err, ensure_ascii=False)}\n\n"

            evt_done = {
                "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                "kind": "complete",
                "summary": "Test-loop terminé",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            await _persist_event(evt_done, user_id=user_id, session_id=session_id,
                                 project_id=payload.project_id)
            yield f"data: {json.dumps(evt_done, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })

    # ============================== /chat/stream (native token streaming) ==============

    @router.post("/chat/stream")
    async def chat_stream(request: Request, input: ChatStreamIn):
        """iter114 — VRAI streaming token-par-token via emergentintegrations.
        Fallback sur le pseudo-streaming pour les cas complexes (attachments / mode offline)."""
        user_id = await get_current_user(request)
        has_attachments = bool(input.attachments)
        is_offline = (input.mode or "online").lower() == "offline"

        # iter131 — Persona créa : on résout d'abord si l'appelant est bien la
        # créatrice ; sinon on ignore les overrides. Métadonnées persistées
        # sur le message utilisateur pour rendu (pseudo/avatar customs + ghost).
        po = input.persona_override or {}
        user_doc = await db.users.find_one({"id": user_id}) or {}
        is_creator = user_doc.get("role") == "creator"
        persona_active = bool(po) and is_creator
        persona_id = (po.get("id") if persona_active else None) or None
        persona_pseudo = ((po.get("customPseudo") or "").strip() if persona_active else "") or None
        persona_avatar = ((po.get("customAvatar") or "").strip() if persona_active else "") or None
        persona_visible = bool(po.get("visible", True)) if persona_active else True
        persona_ai_replies = bool(po.get("aiReplies", True)) if persona_active else True

        if persona_active and persona_ai_replies is False:
            # La créa intervient manuellement : on PERSISTE quand même son
            # message (avec métadonnées persona) puis on renvoie un stream
            # vide (done skipped=True) — pas de génération IA.
            manual_msg_id = f"msg_{uuid.uuid4().hex[:16]}"
            pid_manual = input.project_id
            if not pid_manual:
                short = (input.message or "Nouveau chat").strip().replace("\n", " ")
                short = short[:40] + ("…" if len(short) > 40 else "")
                new_proj = {
                    "project_id": f"proj_{uuid.uuid4().hex[:12]}", "user_id": user_id,
                    "name": short or "Nouveau chat", "description": "",
                    "project_type": "chat", "ai_mode": "online",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.projects.insert_one(new_proj)
                pid_manual = new_proj["project_id"]
            try:
                await db.chat_messages.insert_one({
                    "message_id": manual_msg_id,
                    "user_id": user_id, "project_id": pid_manual,
                    "role": "user", "content": input.message, "mode": input.mode,
                    "persona_id": persona_id, "persona_pseudo": persona_pseudo,
                    "persona_avatar": persona_avatar, "visible_to_target": persona_visible,
                    "ai_replies": False, "creator_manual": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.warning(f"chat/stream manual persist failed: {e}")

            async def silent_gen():
                import json as _j
                yield "data: " + _j.dumps({
                    "done": True, "skipped": True,
                    "reason": "creator_persona_silence",
                    "user_message_id": manual_msg_id,
                    "project_id": pid_manual,
                    "persona": {"id": persona_id, "pseudo": persona_pseudo,
                                "avatar": persona_avatar, "visible": persona_visible},
                }) + "\n\n"
            return StreamingResponse(silent_gen(), media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

        # Fallback : modes complexes → réutilise send_chat_message + pseudo-stream.
        if has_attachments or is_offline:
            full_input = ChatMessageInput_cls(
                message=input.message, mode=input.mode,
                project_id=input.project_id, language=input.language,
                model=input.model, attachments=input.attachments or [],
            )
            resp = await send_chat_message_fn(request, full_input)
            ai_text = ((resp or {}).get("ai_response") or {}).get("content") or ""
            msg_id = ((resp or {}).get("ai_response") or {}).get("message_id") or ""
            download = ((resp or {}).get("ai_response") or {}).get("download")
            auto_pid = (resp or {}).get("project_id")

            async def fallback_gen():
                import asyncio as _aio
                text = ai_text
                i = 0; idx = 0
                while i < len(text):
                    yield f"data: {json.dumps({'delta': text[i:i+3], 'index': idx})}\n\n"
                    i += 3; idx += 1
                    await _aio.sleep(0.006)
                yield "data: " + json.dumps({
                    "done": True, "message_id": msg_id, "download": download,
                    "content": ai_text, "project_id": auto_pid,
                }) + "\n\n"

            return StreamingResponse(fallback_gen(), media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

        # ---------- iter129 : PIPELINE MULTI-AGENTS (online, no attachments) ----------
        # Router → agent spécialisé (Caly chat / Forge dev / Archi planner).
        # Chaque agent stream ses événements d'exécution + sa réponse finale.
        project_id_eff = input.project_id
        auto_created = False
        if not project_id_eff:
            short = (input.message or "Nouveau chat").strip().replace("\n", " ")
            short = short[:40] + ("…" if len(short) > 40 else "")
            new_proj = {
                "project_id": f"proj_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "name": short or "Nouveau chat",
                "description": "",
                "project_type": "chat",
                "ai_mode": "online",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.projects.insert_one(new_proj)
            project_id_eff = new_proj["project_id"]
            auto_created = True

        # Mémoire conversationnelle : historique récent AVANT insertion du
        # message courant (les agents reçoivent le contexte).
        recent_history = []
        try:
            recent_history = await db.chat_messages.find(
                {"user_id": user_id, "project_id": project_id_eff},
                {"_id": 0, "role": 1, "content": 1},
            ).sort("timestamp", -1).limit(14).to_list(length=14)
            recent_history = list(reversed(recent_history))
        except Exception:
            recent_history = []

        user_msg_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id, "project_id": project_id_eff,
            "role": "user", "content": input.message, "mode": input.mode,
            # iter131 — Persona créa (id, pseudo custom, avatar, visible).
            "persona_id": persona_id, "persona_pseudo": persona_pseudo,
            "persona_avatar": persona_avatar, "visible_to_target": persona_visible,
            "ai_replies": persona_ai_replies,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await db.chat_messages.insert_one(user_msg_doc)

        msg_id_final = f"msg_{uuid.uuid4().hex[:16]}"
        session_id = f"chat_stream_{project_id_eff}"

        def _compact_evt(evt):
            keep = ("event_id", "kind", "summary", "ts", "path", "query",
                    "lines_added", "lines_removed")
            return {k: evt[k] for k in keep if evt.get(k) is not None}

        async def agent_stream_gen():
            from agents import run_pipeline
            full_text = ""
            idx = 0
            agent_info = None
            agent_events = []

            async def persist(evt):
                await _persist_event(evt, user_id=user_id, session_id=session_id,
                                     project_id=project_id_eff)

            try:
                async for item in run_pipeline(
                    input.message, session_id=session_id,
                    language=(input.language or "fr").lower(),
                    project_id=project_id_eff, history=recent_history,
                    model_pref=input.model, emit=persist,
                ):
                    if "delta" in item:
                        full_text += item["delta"]
                        yield f"data: {json.dumps({'delta': item['delta'], 'index': idx}, ensure_ascii=False)}\n\n"
                        idx += 1
                    elif "event" in item:
                        compact = _compact_evt(item["event"])
                        agent_events.append(compact)
                        yield f"data: {json.dumps({'event': compact}, ensure_ascii=False)}\n\n"
                    elif "agent" in item:
                        agent_info = item["agent"]
                        yield f"data: {json.dumps({'agent': agent_info}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.warning(f"chat/stream agent pipeline failed: {e}; fallback message")
                fallback_text = "Désolée, le service de chat est momentanément indisponible. Réessaie dans un instant."
                if not full_text:
                    full_text = fallback_text
                    yield f"data: {json.dumps({'delta': fallback_text, 'index': idx})}\n\n"

            try:
                await db.chat_messages.insert_one({
                    "message_id": msg_id_final,
                    "user_id": user_id, "project_id": project_id_eff,
                    "role": "assistant", "content": full_text,
                    "mode": input.mode,
                    "agent_id": (agent_info or {}).get("id"),
                    "agent_name": (agent_info or {}).get("name"),
                    "agent_events": agent_events,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.warning(f"chat/stream DB persist failed: {e}")

            yield "data: " + json.dumps({
                "done": True,
                "message_id": msg_id_final,
                "content": full_text,
                "agent": agent_info,
                "agent_events": agent_events,
                "project_id": project_id_eff if auto_created else None,
            }, ensure_ascii=False) + "\n\n"

        return StreamingResponse(agent_stream_gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })

    # ============================== /agents/registry ====================================

    @router.get("/agents/registry")
    async def agents_registry(request: Request):
        """iter129 — Fiches d'identité de toutes les IA du site (transparence)."""
        await get_current_user(request)
        from agents import AGENT_REGISTRY
        return {"agents": list(AGENT_REGISTRY.values())}

    return router
