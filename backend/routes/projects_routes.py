"""iter122 — Routes /projects/* + /share/{slug} extraites de server.py.

8 endpoints :
  - POST   /projects               (create)
  - GET    /projects               (list)
  - GET    /projects/{id}          (read one)
  - PUT    /projects/{id}          (update)
  - DELETE /projects/{id}          (delete + cascade chat_messages)
  - POST   /projects/{id}/duplicate
  - POST   /projects/{id}/share    (toggle public share slug)
  - GET    /share/{slug}           (public read project)
  - GET    /share/{slug}/preview   (public rendered HTML)

Helpers injectés : db, get_current_user, Project, ProjectCreate, ProjectUpdate.
"""
import os
import unicodedata as _ud
import re as _re
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse


def _make_slug(name: str) -> str:
    """ASCII-safe URL slug."""
    base = _ud.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    base = _re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:50] or "projet"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def _backfill_project_fields(project: dict) -> dict:
    """Backfill ai_mode + datetime fields for legacy project documents."""
    if isinstance(project.get('created_at'), str):
        project['created_at'] = datetime.fromisoformat(project['created_at'])
    elif not project.get('created_at'):
        project['created_at'] = datetime.now(timezone.utc)
    if isinstance(project.get('updated_at'), str):
        project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    elif not project.get('updated_at'):
        project['updated_at'] = project['created_at']
    if not project.get('ai_mode'):
        src = (project.get('ai_source') or '').lower()
        project['ai_mode'] = 'offline' if src.startswith('ollama') else 'online'
    return project


def build_projects_router(db, *, get_current_user, Project, ProjectCreate, ProjectUpdate):
    router = APIRouter()

    @router.post("/projects", response_model=Project, status_code=201)
    async def create_project(request: Request, input: ProjectCreate):
        """Create a new project"""
        user_id = await get_current_user(request)

        project = Project(
            user_id=user_id,
            name=input.name,
            description=input.description,
            project_type=input.project_type,
        )

        project_dict = project.model_dump()
        project_dict['created_at'] = project_dict['created_at'].isoformat()
        project_dict['updated_at'] = project_dict['updated_at'].isoformat()

        await db.projects.insert_one(project_dict)

        return project

    @router.get("/projects", response_model=List[Project])
    async def get_projects(request: Request):
        """Get all projects for current user"""
        user_id = await get_current_user(request)

        projects = await db.projects.find(
            {"user_id": user_id},
            {"_id": 0},
        ).sort("created_at", -1).to_list(100)

        for project in projects:
            _backfill_project_fields(project)
        return projects

    @router.get("/projects/{project_id}", response_model=Project)
    async def get_project(request: Request, project_id: str):
        """Get specific project"""
        user_id = await get_current_user(request)

        project = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id},
            {"_id": 0},
        )

        if not project:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        return _backfill_project_fields(project)

    @router.put("/projects/{project_id}", response_model=Project)
    async def update_project(request: Request, project_id: str, input: ProjectUpdate):
        """Update a project"""
        user_id = await get_current_user(request)

        project = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id},
            {"_id": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        update_data = {k: v for k, v in input.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        await db.projects.update_one({"project_id": project_id}, {"$set": update_data})

        updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        if isinstance(updated_project['created_at'], str):
            updated_project['created_at'] = datetime.fromisoformat(updated_project['created_at'])
        if isinstance(updated_project['updated_at'], str):
            updated_project['updated_at'] = datetime.fromisoformat(updated_project['updated_at'])
        return updated_project

    @router.delete("/projects/{project_id}")
    async def delete_project(request: Request, project_id: str):
        """Delete a project (cascade chat_messages)."""
        user_id = await get_current_user(request)

        result = await db.projects.delete_one(
            {"project_id": project_id, "user_id": user_id}
        )
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        await db.chat_messages.delete_many({"project_id": project_id})
        return {"message": "Projet supprimé avec succès"}

    @router.post("/projects/{project_id}/duplicate")
    async def duplicate_project(request: Request, project_id: str):
        """Clone a project — new id + '(copie)' suffix. Chat history NOT copied."""
        user_id = await get_current_user(request)
        src = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0},
        )
        if not src:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        new_id = f"proj_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        clone = {
            **src,
            "project_id": new_id,
            "name": f"{src.get('name', 'Projet')} (copie)"[:80],
            "created_at": now_iso,
            "updated_at": now_iso,
            "share_slug": None,
            "is_public": False,
        }
        await db.projects.insert_one(clone)
        clone.pop("_id", None)
        return {"success": True, "project_id": new_id, "project": clone}

    @router.post("/projects/{project_id}/share")
    async def toggle_project_share(request: Request, project_id: str):
        """Generate (or refresh) a public share URL. Body (optional): {"enable": true|false}."""
        user_id = await get_current_user(request)
        try:
            body = await request.json()
        except Exception:
            body = {}
        enable = body.get("enable") if isinstance(body, dict) else None

        project = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        if enable is False:
            await db.projects.update_one(
                {"project_id": project_id},
                {"$set": {"is_public": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            return {"is_public": False, "slug": None, "url": None}

        slug = project.get("share_slug") or _make_slug(project.get("name") or project_id)
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {
                "is_public": True,
                "share_slug": slug,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        frontend_url = (
            os.environ.get("FRONTEND_URL")
            or os.environ.get("REACT_APP_BACKEND_URL")
            or ""
        )
        public_url = f"{frontend_url.rstrip('/')}/share/{slug}" if frontend_url else f"/share/{slug}"
        return {"is_public": True, "slug": slug, "url": public_url}

    @router.get("/share/{slug}")
    async def get_public_share(slug: str):
        """PUBLIC — return project metadata + generated files for a shared slug."""
        project = await db.projects.find_one(
            {"share_slug": slug, "is_public": True},
            {"_id": 0, "user_id": 0, "ai_source": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projet non partagé ou introuvable")
        return {
            "name": project.get("name"),
            "description": project.get("description"),
            "project_type": project.get("project_type"),
            "files": (project.get("generated_code") or {}).get("files", []),
            "created_at": project.get("created_at"),
        }

    @router.get("/share/{slug}/preview")
    async def get_public_share_preview(slug: str):
        """PUBLIC — rendered HTML preview for a shared web project."""
        project = await db.projects.find_one(
            {"share_slug": slug, "is_public": True}, {"_id": 0},
        )
        if not project:
            return HTMLResponse("<h1>Projet introuvable</h1>", status_code=404)

        files = (project.get("generated_code") or {}).get("files", []) or []
        html_parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{project.get('name', 'Projet')} · CodeForge AI</title>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif}</style>"
        ]
        for f in files:
            if f.get("path", "").endswith(".css"):
                html_parts.append(f"<style>{f.get('content', '')}</style>")
        html_parts.append("</head><body>")
        for f in files:
            if f.get("path", "").endswith(".html"):
                content = f.get("content", "")
                if "<body>" in content:
                    start = content.find("<body>") + 6
                    end = content.find("</body>")
                    content = content[start:end] if end > start else content
                html_parts.append(content)
        for f in files:
            if f.get("path", "").endswith(".js"):
                html_parts.append(f"<script>{f.get('content', '')}</script>")
        html_parts.append("</body></html>")
        return HTMLResponse("\n".join(html_parts))

    return router
