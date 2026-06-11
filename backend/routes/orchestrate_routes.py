"""iter95 — Refacto slice 4d : routes /orchestrate/* (lecture seule) extraites
de server.py via factory pattern. NOTE : /chat/orchestrate et
/chat/orchestrate-stream restent dans server.py car ils dépendent fortement
de closures locales (on_commit_real, on_preview_real, _stream_actions).

Ce module extrait UNIQUEMENT :
  - GET /orchestrate/event/{event_id}/details
  - POST /orchestrate/history

/orchestrate/test-loop reste aussi dans server.py (subprocess pytest local
avec accès au cwd /app/backend).
"""
from __future__ import annotations

from typing import Optional, Callable, Awaitable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class OrchestrateHistoryIn(BaseModel):
    project_id: Optional[str] = None
    limit: int = 50


def build_orchestrate_router(
    db,
    *,
    get_current_user: Callable[[Request], Awaitable[str]],
):
    router = APIRouter()

    @router.get("/orchestrate/event/{event_id}/details")
    async def orchestrate_event_details(event_id: str, request: Request):
        """Récupère le détail complet d'un événement d'orchestration.
        L'UI appelle cet endpoint quand l'utilisateur déplie la flèche."""
        user_id = await get_current_user(request)
        doc = await db.orchestrator_events.find_one(
            {"event_id": event_id, "user_id": user_id}, {"_id": 0},
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Événement introuvable.")
        return doc

    @router.post("/orchestrate/history")
    async def orchestrate_history(request: Request, payload: OrchestrateHistoryIn):
        """Récupère l'historique des événements d'orchestration d'une session."""
        user_id = await get_current_user(request)
        q = {"user_id": user_id}
        if payload.project_id:
            q["project_id"] = payload.project_id
        limit = max(1, min(payload.limit, 200))
        rows = await db.orchestrator_events.find(
            q, {"_id": 0, "details": 0},
        ).sort("ts", -1).limit(limit).to_list(length=200)
        return {"events": list(reversed(rows))}

    return router
