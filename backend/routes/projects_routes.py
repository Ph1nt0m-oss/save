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
        """Update a project.

        Chantier UX iter159 — Renommage manuel VERROUILLE le titre.
        Tout changement explicite de `name` passe `title_manual=True` ; le
        renommage automatique /auto-title n'écrasera plus ce titre.
        """
        user_id = await get_current_user(request)

        project = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id},
            {"_id": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        update_data = {k: v for k, v in input.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Chantier iter159 §3 — Verrou titre manuel : si le nom change via PUT
        # explicite, on marque le document pour empêcher tout renommage auto.
        if "name" in update_data and (update_data["name"] or "").strip():
            update_data["title_manual"] = True

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

    @router.post("/projects/{project_id}/auto-title")
    async def auto_title_project(request: Request, project_id: str):
        """Chantier iter159 §3 — Renommage automatique du projet.

        Génère un titre court (≤ 48 chars) via l'IA à partir du premier message
        utilisateur, UNIQUEMENT si :
          - le projet existe pour ce user,
          - il y a au moins un message user,
          - `title_manual` est falsy (jamais écraser un titre renommé par l'user).

        Fallback hors-ligne / sans LLM : truncation intelligente du 1er message.
        Retourne {title, source, applied}.
        """
        user_id = await get_current_user(request)
        project = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projet non trouvé")

        if project.get("title_manual"):
            return {
                "title": project.get("name"),
                "source": "locked",
                "applied": False,
                "reason": "title_manual",
            }

        # Récupère le 1er message USER (le titre doit refléter l'intention).
        first_user = await db.chat_messages.find_one(
            {"project_id": project_id, "user_id": user_id, "role": "user"},
            {"_id": 0, "content": 1},
            sort=[("timestamp", 1)],
        )
        if not first_user or not (first_user.get("content") or "").strip():
            return {
                "title": project.get("name"),
                "source": "empty",
                "applied": False,
                "reason": "no_user_message",
            }

        raw = (first_user["content"] or "").strip().replace("\n", " ")

        def _smart_trunc(txt: str, limit: int = 48) -> str:
            words = txt.split()
            out = ""
            for w in words:
                nxt = (out + " " + w).strip()
                if len(nxt) > limit:
                    break
                out = nxt
            if not out:
                out = txt[:limit]
            return out.rstrip(" ,.;:!?-—…").strip() or txt[:limit]

        fallback_title = _smart_trunc(raw, 48)
        llm_title = None

        try:
            key = os.environ.get("EMERGENT_LLM_KEY")
            if key:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                sys_msg = (
                    "Tu génères un TITRE court et pertinent pour une conversation "
                    "avec une IA, à partir du premier message de l'utilisateur. "
                    "RÈGLES STRICTES :\n"
                    "- 2 à 6 mots maximum, 48 caractères max.\n"
                    "- Résume le sujet réel, pas une reformulation du message.\n"
                    "- Pas de ponctuation finale, pas de guillemets, pas d'emoji.\n"
                    "- Pas de 'Discussion sur…' ni 'Chat à propos de…'.\n"
                    "- Langue identique à celle du message.\n"
                    "Réponds UNIQUEMENT par le titre, rien d'autre."
                )
                chat = LlmChat(
                    api_key=key,
                    session_id=f"title_{project_id[:8]}",
                    system_message=sys_msg,
                ).with_model("openai", "gpt-4o-mini")
                reply = await chat.send_message(UserMessage(text=raw[:800]))
                candidate = (str(reply) or "").strip().strip('"\'').strip()
                candidate = candidate.split("\n")[0].strip()
                if candidate and len(candidate) <= 60:
                    llm_title = _smart_trunc(candidate, 48)
        except Exception:
            llm_title = None

        chosen = llm_title or fallback_title
        source = "llm" if llm_title else "truncation"

        res = await db.projects.update_one(
            {"project_id": project_id, "user_id": user_id,
             "$or": [{"title_manual": {"$exists": False}}, {"title_manual": False}]},
            {"$set": {"name": chosen,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "title": chosen,
            "source": source,
            "applied": res.modified_count > 0,
        }

    @router.post("/projects/{project_id}/duplicate")
    async def duplicate_project(request: Request, project_id: str):
        """iter158 — Clonage direct RETIRÉ. Toute copie/export passe par le
        workflow sécurisé « Exporter ce projet » (demande → validation Créa)."""
        raise HTTPException(
            status_code=403,
            detail="Le clonage direct a été retiré. Utilise « Exporter ce projet » (validation Créa requise).",
        )

    @router.post("/projects/{project_id}/share")
    async def toggle_project_share(request: Request, project_id: str):
        """iter158 — Partage public direct RETIRÉ. On autorise UNIQUEMENT la
        désactivation d'un ancien partage (enable=false) ; toute activation est
        refusée côté serveur (non contournable par le frontend)."""
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
                {"$set": {"is_public": False, "share_slug": None,
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            return {"is_public": False, "slug": None, "url": None}
        raise HTTPException(
            status_code=403,
            detail="Le partage public direct a été retiré. Utilise « Exporter ce projet ».",
        )

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
