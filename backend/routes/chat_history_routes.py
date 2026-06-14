"""iter123 — Routes /chat/history + /chat/attach extraites de server.py.

Endpoints simples liés à la persistance des conversations.

Helpers injectés : db, get_current_user.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class ChatAttachInput(BaseModel):
    message_id: Optional[str] = None
    project_id: str
    attach_all_orphans: Optional[bool] = False  # if true, attach all messages with project_id=null


def build_chat_history_router(db, *, get_current_user):
    router = APIRouter()

    @router.get("/chat/history")
    async def get_chat_history(request: Request, project_id: Optional[str] = None, limit: int = 50):
        """Get chat history for user or specific project."""
        user_id = await get_current_user(request)

        query = {"user_id": user_id}
        if project_id:
            query["project_id"] = project_id

        messages = await db.chat_messages.find(
            query,
            {"_id": 0},
        ).sort("timestamp", 1).limit(limit).to_list(limit)

        return messages

    @router.post("/chat/attach")
    async def attach_chat_to_project(request: Request, payload: ChatAttachInput):
        """Attach an orphan chat message (project_id=null) to a project — used
        when a user pins a free-running chat to the sidebar."""
        user_id = await get_current_user(request)
        # Validate the project belongs to the user.
        proj = await db.projects.find_one(
            {"project_id": payload.project_id, "user_id": user_id}, {"_id": 0},
        )
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        if payload.attach_all_orphans:
            result = await db.chat_messages.update_many(
                {"user_id": user_id, "project_id": None},
                {"$set": {"project_id": payload.project_id}},
            )
            return {"updated": result.modified_count}
        if not payload.message_id:
            raise HTTPException(status_code=400, detail="message_id or attach_all_orphans required")
        result = await db.chat_messages.update_one(
            {"message_id": payload.message_id, "user_id": user_id},
            {"$set": {"project_id": payload.project_id}},
        )
        return {"updated": result.modified_count}

    return router
