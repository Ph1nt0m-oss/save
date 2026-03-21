from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_token: str
    user_id: str
    expires_at: datetime
    created_at: datetime

class SessionDataRequest(BaseModel):
    session_id: str

class ChatMessageInput(BaseModel):
    message: str
    project_id: Optional[str] = None

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:16]}")
    user_id: str
    project_id: Optional[str] = None
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")
    project_id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    description: str
    project_type: str  # 'web', 'mobile', 'desktop'
    generated_code: Optional[Dict[str, Any]] = None
    status: str = "draft"  # 'draft', 'generating', 'completed', 'error'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProjectCreate(BaseModel):
    name: str
    description: str
    project_type: str

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    generated_code: Optional[Dict[str, Any]] = None

class GenerateCodeRequest(BaseModel):
    project_id: str
    description: str
    project_type: str

# ==================== HELPER FUNCTIONS ====================

async def get_current_user(request: Request) -> str:
    """Extract user_id from session_token (cookie or Authorization header)"""
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.replace("Bearer ", "")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    # Verify session in database
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Session invalide")
    
    # Check expiry
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expirée")
    
    return session_doc["user_id"]

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/session")
async def create_session(request: SessionDataRequest, response: Response):
    """Exchange session_id for user data and create persistent session"""
    try:
        # Call Emergent Auth API
        async with httpx.AsyncClient() as http_client:
            auth_response = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": request.session_id}
            )
            
            if auth_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Session ID invalide")
            
            user_data = auth_response.json()
        
        # Create or update user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        existing_user = await db.users.find_one({"email": user_data["email"]}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            # Update user info
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": user_data["name"],
                    "picture": user_data.get("picture")
                }}
            )
        else:
            # Create new user
            new_user = {
                "user_id": user_id,
                "email": user_data["email"],
                "name": user_data["name"],
                "picture": user_data.get("picture"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
        
        # Create session
        session_token = user_data["session_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        session_doc = {
            "session_token": session_token,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        # Set httpOnly cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60,
            path="/"
        )
        
        # Return user data
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        return user
    
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/auth/me")
async def get_me(request: Request):
    """Get current user from session"""
    user_id = await get_current_user(request)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    return user

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user and clear session"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie("session_token", path="/")
    return {"message": "Déconnexion réussie"}

# ==================== CHAT ROUTES ====================

@api_router.post("/chat/message")
async def send_chat_message(request: Request, input: ChatMessageInput):
    """Send message to AI and get response"""
    user_id = await get_current_user(request)
    
    try:
        # Save user message
        user_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": input.project_id,
            "role": "user",
            "content": input.message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(user_message_doc)
        
        # Initialize AI chat
        emergent_key = os.environ.get('EMERGENT_LLM_KEY')
        if not emergent_key:
            raise HTTPException(status_code=500, detail="Clé d'IA non configurée")
        
        session_id = input.project_id or user_id
        chat = LlmChat(
            api_key=emergent_key,
            session_id=session_id,
            system_message="Tu es un assistant IA expert en développement logiciel. Tu aides les utilisateurs à créer des applications complètes (web, mobile, desktop) en générant du code de haute qualité. Réponds toujours en français."
        ).with_model("openai", "gpt-5.2")
        
        # Get AI response
        ai_message = UserMessage(text=input.message)
        ai_response = await chat.send_message(ai_message)
        
        # Save AI response
        ai_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": input.project_id,
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(ai_message_doc)
        
        return {
            "user_message": user_message_doc,
            "ai_response": ai_message_doc
        }
    
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur de chat: {str(e)}")

@api_router.get("/chat/history")
async def get_chat_history(request: Request, project_id: Optional[str] = None, limit: int = 50):
    """Get chat history for user or specific project"""
    user_id = await get_current_user(request)
    
    query = {"user_id": user_id}
    if project_id:
        query["project_id"] = project_id
    
    messages = await db.chat_messages.find(
        query,
        {"_id": 0}
    ).sort("timestamp", 1).limit(limit).to_list(limit)
    
    return messages

# ==================== PROJECT ROUTES ====================

@api_router.post("/projects", response_model=Project)
async def create_project(request: Request, input: ProjectCreate):
    """Create a new project"""
    user_id = await get_current_user(request)
    
    project = Project(
        user_id=user_id,
        name=input.name,
        description=input.description,
        project_type=input.project_type
    )
    
    project_dict = project.model_dump()
    project_dict['created_at'] = project_dict['created_at'].isoformat()
    project_dict['updated_at'] = project_dict['updated_at'].isoformat()
    
    await db.projects.insert_one(project_dict)
    
    return project

@api_router.get("/projects", response_model=List[Project])
async def get_projects(request: Request):
    """Get all projects for current user"""
    user_id = await get_current_user(request)
    
    projects = await db.projects.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Convert ISO strings to datetime
    for project in projects:
        if isinstance(project['created_at'], str):
            project['created_at'] = datetime.fromisoformat(project['created_at'])
        if isinstance(project['updated_at'], str):
            project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    
    return projects

@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(request: Request, project_id: str):
    """Get specific project"""
    user_id = await get_current_user(request)
    
    project = await db.projects.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Convert ISO strings to datetime
    if isinstance(project['created_at'], str):
        project['created_at'] = datetime.fromisoformat(project['created_at'])
    if isinstance(project['updated_at'], str):
        project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    
    return project

@api_router.put("/projects/{project_id}", response_model=Project)
async def update_project(request: Request, project_id: str, input: ProjectUpdate):
    """Update a project"""
    user_id = await get_current_user(request)
    
    # Check project exists and belongs to user
    project = await db.projects.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Build update dict
    update_data = {k: v for k, v in input.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update_data}
    )
    
    # Return updated project
    updated_project = await db.projects.find_one(
        {"project_id": project_id},
        {"_id": 0}
    )
    
    # Convert ISO strings to datetime
    if isinstance(updated_project['created_at'], str):
        updated_project['created_at'] = datetime.fromisoformat(updated_project['created_at'])
    if isinstance(updated_project['updated_at'], str):
        updated_project['updated_at'] = datetime.fromisoformat(updated_project['updated_at'])
    
    return updated_project

@api_router.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str):
    """Delete a project"""
    user_id = await get_current_user(request)
    
    result = await db.projects.delete_one(
        {"project_id": project_id, "user_id": user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    # Also delete related chat messages
    await db.chat_messages.delete_many({"project_id": project_id})
    
    return {"message": "Projet supprimé avec succès"}

# ==================== CODE GENERATION ROUTES ====================

@api_router.post("/generate/code")
async def generate_code(request: Request, input: GenerateCodeRequest):
    """Generate complete code for a project using AI"""
    user_id = await get_current_user(request)
    
    try:
        # Update project status
        await db.projects.update_one(
            {"project_id": input.project_id, "user_id": user_id},
            {"$set": {"status": "generating"}}
        )
        
        # Initialize AI
        emergent_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=emergent_key,
            session_id=input.project_id,
            system_message=f"""Tu es un expert en génération de code. Génère du code complet et fonctionnel pour {input.project_type}.
Réponds UNIQUEMENT avec du code structuré en JSON avec les clés: 'files' (tableau d'objets {{path, content}}), 'instructions' (string), 'dependencies' (array).
Sois précis et professionnel. Code en français pour les commentaires."""
        ).with_model("openai", "gpt-5.2")
        
        prompt = f"""Génère une application {input.project_type} complète pour: {input.description}

Inclus:
- Structure de fichiers complète
- Code frontend et backend si applicable
- Configuration nécessaire
- Instructions de déploiement

Format de réponse JSON:
{{
  "files": [{{
    "path": "chemin/fichier",
    "content": "contenu du code"
  }}],
  "instructions": "Instructions détaillées",
  "dependencies": ["liste", "des", "dépendances"]
}}"""
        
        ai_message = UserMessage(text=prompt)
        ai_response = await chat.send_message(ai_message)
        
        # Parse response (attempt JSON extraction)
        import json
        try:
            # Try to extract JSON from response
            generated_code = json.loads(ai_response)
        except:
            # If not pure JSON, wrap response
            generated_code = {
                "files": [],
                "instructions": ai_response,
                "dependencies": []
            }
        
        # Update project with generated code
        await db.projects.update_one(
            {"project_id": input.project_id},
            {"$set": {
                "generated_code": generated_code,
                "status": "completed",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "project_id": input.project_id,
            "generated_code": generated_code,
            "status": "completed"
        }
    
    except Exception as e:
        logger.error(f"Error generating code: {e}")
        
        # Update project status to error
        await db.projects.update_one(
            {"project_id": input.project_id},
            {"$set": {"status": "error"}}
        )
        
        raise HTTPException(status_code=500, detail=f"Erreur de génération: {str(e)}")

# ==================== EXPORT ROUTES (BASIC) ====================

@api_router.post("/export/prepare")
async def prepare_export(request: Request, project_id: str, export_type: str):
    """Prepare project for export (.apk, .exe, web)"""
    user_id = await get_current_user(request)
    
    project = await db.projects.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    if not project.get("generated_code"):
        raise HTTPException(status_code=400, detail="Aucun code généré pour ce projet")
    
    # For now, return structure - actual build process would be implemented later
    return {
        "project_id": project_id,
        "export_type": export_type,
        "status": "ready",
        "message": f"Export {export_type} préparé. Fonctionnalité complète en développement.",
        "generated_code": project["generated_code"]
    }

# ==================== ROOT ROUTE ====================

@api_router.get("/")
async def root():
    return {
        "message": "API Plateforme de Génération IA",
        "version": "1.0.0",
        "status": "online"
    }

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "ai_model": "gpt-5.2"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()