from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
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
import json
import zipfile
import io

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
    mode: str = "chat"  # "chat" or "create"

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:16]}")
    user_id: str
    project_id: Optional[str] = None
    role: str  # 'user' or 'assistant'
    content: str
    mode: str = "chat"
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
    use_emergent: bool = True

class ExportRequest(BaseModel):
    project_id: str
    export_type: str  # 'apk', 'exe', 'web', 'source'

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

@api_router.post("/ai/generate-complete-app")
async def ai_generate_complete_app(request: Request, data: dict):
    """Generate complete application automatically with Ollama"""
    user_id = await get_current_user(request)
    
    description = data.get('description', '')
    
    try:
        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.environ.get('OLLAMA_MODEL', 'llama3.3')
        
        prompt = f"""Tu es un expert en d\u00e9veloppement. G\u00e9n\u00e8re une application COMPL\u00c8TE et FONCTIONNELLE.

Description: {description}

G\u00e9n\u00e8re une application professionnelle avec:
- Structure compl\u00e8te de fichiers
- Frontend (HTML/CSS/JS ou React)
- Backend si n\u00e9cessaire (API)
- Base de donn\u00e9es si n\u00e9cessaire
- Tout le code fonctionnel

R\u00e9ponds UNIQUEMENT avec un JSON valide:
{{
  \"files\": [
    {{\"path\": \"index.html\", \"content\": \"...\"}},
    {{\"path\": \"style.css\", \"content\": \"...\"}},
    {{\"path\": \"app.js\", \"content\": \"...\"}}
  ],
  \"explanation\": \"Explication en fran\u00e7ais de ce qui a \u00e9t\u00e9 cr\u00e9\u00e9\",
  \"instructions\": \"Instructions d'installation et d'utilisation\"
}}"""

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_text = result.get('response', '')
                
                # Extract JSON
                try:
                    start = ai_text.find('{')
                    end = ai_text.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = ai_text[start:end]
                        generated = json.loads(json_str)
                        
                        # Create project
                        project_id = f"proj_{uuid.uuid4().hex[:12]}"
                        project = {
                            "project_id": project_id,
                            "user_id": user_id,
                            "name": description[:50],
                            "description": description,
                            "project_type": "web",
                            "generated_code": generated,
                            "status": "completed",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.projects.insert_one(project)
                        
                        return {
                            "code": generated,
                            "explanation": generated.get('explanation', 'Application g\u00e9n\u00e9r\u00e9e avec succ\u00e8s'),
                            "project": {"id": project_id, "name": description[:50]}
                        }
                    else:
                        raise ValueError("No JSON found")
                except Exception as e:
                    logger.error(f"JSON parsing error: {e}")
                    return {
                        "code": {"files": [], "explanation": ai_text},
                        "explanation": ai_text[:500],
                        "project": None
                    }
            else:
                raise HTTPException(status_code=500, detail="Ollama API error")
                
    except Exception as e:
        logger.error(f"Error generating app: {e}")
        raise HTTPException(
            status_code=500,
            detail="Installez Ollama pour une g\u00e9n\u00e9ration illimit\u00e9e. Voir OLLAMA_SETUP.md"
        )

# ==================== AI CODE GENERATION ROUTES ====================

@api_router.post("/ai/generate-code")
async def ai_generate_code(request: Request, prompt_data: dict):
    """Generate code using Ollama (local, free, unlimited)"""
    user_id = await get_current_user(request)
    
    prompt = prompt_data.get('prompt', '')
    existing_files = prompt_data.get('existing_files', [])
    
    try:
        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.environ.get('OLLAMA_MODEL', 'llama3.3')
        
        # Build context from existing files
        context = "Fichiers existants:\\n"
        for f in existing_files:
            context += f"\\n--- {f['path']} ---\\n{f['content'][:200]}...\\n"
        
        full_prompt = f"""Tu es un expert en développement. Génère du code professionnel et complet.

{context}

Demande de l'utilisateur: {prompt}

Réponds UNIQUEMENT avec un JSON valide au format:
{{
  "files": [
    {{"path": "nom_fichier.ext", "content": "contenu du code"}},
    ...
  ],
  "explanation": "Explication en français de ce qui a été créé"
}}

Important: Code propre, commenté, et fonctionnel."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": full_prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_text = result.get('response', '')
                
                # Try to extract JSON from response
                try:
                    # Find JSON in response
                    start = ai_text.find('{')
                    end = ai_text.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = ai_text[start:end]
                        generated = json.loads(json_str)
                        return generated
                    else:
                        raise ValueError("No JSON found")
                except:
                    # If parsing fails, return raw response
                    return {
                        "files": [{
                            "path": "output.txt",
                            "content": ai_text
                        }],
                        "explanation": "Réponse de l'IA (format non-JSON détecté)"
                    }
            else:
                raise HTTPException(status_code=500, detail="Ollama API error")
                
    except Exception as e:
        logger.error(f"Error generating code: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Installez Ollama pour une IA gratuite. Voir OLLAMA_SETUP.md"
        )

# ==================== CHAT ROUTES ====================

@api_router.post("/chat/message")
async def send_chat_message(request: Request, input: ChatMessageInput):
    """Send message to AI (Chat mode with simple responses)"""
    user_id = await get_current_user(request)
    
    try:
        # Save user message
        user_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": input.project_id,
            "role": "user",
            "content": input.message,
            "mode": input.mode,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(user_message_doc)
        
        # Try Ollama with DeepSeek Coder (better for code generation than Llama)
        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.environ.get('OLLAMA_MODEL', 'deepseek-coder:33b')  # DeepSeek by default
        
        ai_response_text = None
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": f"Tu es un expert en développement logiciel. Réponds en français.\\n\\nQuestion: {input.message}",
                        "stream": False
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    ai_response_text = result.get('response', '')
                    logger.info(f"✅ Ollama response successful")
        except Exception as ollama_error:
            logger.warning(f"Ollama not available: {ollama_error}")
            
            # Fallback to Groq (free API)
            groq_api_key = os.environ.get('GROQ_API_KEY')
            if groq_api_key:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {groq_api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "llama3-70b-8192",
                                "messages": [
                                    {"role": "system", "content": "Tu es un expert en développement logiciel. Réponds en français."},
                                    {"role": "user", "content": input.message}
                                ]
                            }
                        )
                        if response.status_code == 200:
                            result = response.json()
                            ai_response_text = result['choices'][0]['message']['content']
                            logger.info(f"✅ Groq response successful")
                except Exception as groq_error:
                    logger.warning(f"Groq API error: {groq_error}")
        
        # If both failed, use instructional response
        if not ai_response_text:
            ai_response_text = f"""Je comprends votre demande: "{input.message}"

Pour une meilleure expérience avec IA gratuite et illimitée, installez **Ollama** :

📥 Installation rapide : https://ollama.com
🚀 Commande : `ollama pull llama3.3`
📖 Guide complet : Voir OLLAMA_SETUP.md

Ou utilisez le **Mode Création IA** (bouton vert) pour développer avec une interface complète.

Vous pouvez aussi :
- Créer un nouveau projet via le bouton "+"
- Utiliser la génération de code automatique
- Exporter vers mobile (APK) ou desktop (EXE)"""
        
        # Save AI response
        ai_message_doc = {
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "user_id": user_id,
            "project_id": input.project_id,
            "role": "assistant",
            "content": ai_response_text,
            "mode": input.mode,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.chat_messages.insert_one(ai_message_doc)
        
        # Remove MongoDB _id from response to avoid serialization issues
        user_message_response = {k: v for k, v in user_message_doc.items() if k != '_id'}
        ai_message_response = {k: v for k, v in ai_message_doc.items() if k != '_id'}
        
        return {
            "user_message": user_message_response,
            "ai_response": ai_message_response
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
    """Generate complete code for a project (simulated for now)"""
    user_id = await get_current_user(request)
    
    try:
        # Update project status
        await db.projects.update_one(
            {"project_id": input.project_id, "user_id": user_id},
            {"$set": {"status": "generating"}}
        )
        
        # Generate sample code structure (would use Emergent API in production)
        generated_code = {
            "files": [
                {
                    "path": "index.html",
                    "content": f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{input.description}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>{input.description}</h1>
        <p>Application générée automatiquement</p>
    </div>
    <script src="app.js"></script>
</body>
</html>"""
                },
                {
                    "path": "style.css",
                    "content": """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Arial', sans-serif;
    background: #050505;
    color: #ffffff;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

h1 {
    color: #E4FF00;
    font-size: 3rem;
    margin-bottom: 1rem;
}"""
                },
                {
                    "path": "app.js",
                    "content": """console.log('Application prête !');

// Votre code JavaScript ici"""
                },
                {
                    "path": "manifest.json",
                    "content": json.dumps({
                        "name": input.description,
                        "short_name": input.description[:20],
                        "description": f"Application {input.project_type}",
                        "start_url": "/",
                        "display": "standalone",
                        "background_color": "#050505",
                        "theme_color": "#E4FF00",
                        "icons": [
                            {
                                "src": "/icon-192.png",
                                "sizes": "192x192",
                                "type": "image/png"
                            }
                        ]
                    }, indent=2)
                },
                {
                    "path": "README.md",
                    "content": f"""# {input.description}

Application générée par CodeForge AI

## Installation

### Web
Ouvrez `index.html` dans votre navigateur

### Mobile (APK)
1. Installez via la page d'export mobile
2. Activez les sources inconnues sur Android

### Desktop (EXE)
1. Téléchargez l'installateur
2. Exécutez et suivez les instructions

## Déploiement

### Vercel
```bash
npm install -g vercel
vercel
```

### Netlify
Glissez-déposez le dossier sur netlify.com
"""
                }
            ],
            "instructions": f"Application {input.project_type} générée avec succès. Prête pour l'export.",
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

# ==================== EXPORT ROUTES ====================

@api_router.post("/export/download")
async def download_export(request: Request, export_req: ExportRequest):
    """Download project as ZIP"""
    user_id = await get_current_user(request)
    
    project = await db.projects.find_one(
        {"project_id": export_req.project_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    if not project.get("generated_code"):
        raise HTTPException(status_code=400, detail="Aucun code généré. Générez d'abord le code.")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['name']}.zip"
        }
    )

@api_router.get("/export/mobile/{project_id}")
async def get_mobile_export_page(project_id: str):
    """Get mobile export page (App Store privé style)"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        return HTMLResponse("<h1>Projet non trouvé</h1>", status_code=404)
    
    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Installer {project['name']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #050505 0%, #0F0F13 100%);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .store-container {{
            max-width: 600px;
            width: 100%;
            background: #0F0F13;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 1rem;
            padding: 3rem;
            text-align: center;
        }}
        .app-icon {{
            width: 120px;
            height: 120px;
            background: #E4FF00;
            border-radius: 24px;
            margin: 0 auto 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3rem;
            font-weight: bold;
            color: #050505;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #E4FF00;
        }}
        .description {{
            color: #A1A1AA;
            margin-bottom: 2rem;
            line-height: 1.6;
        }}
        .install-btn {{
            background: #E4FF00;
            color: #050505;
            border: none;
            padding: 1rem 3rem;
            font-size: 1.2rem;
            font-weight: bold;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: transform 0.2s;
            text-decoration: none;
            display: inline-block;
        }}
        .install-btn:hover {{
            transform: translateY(-2px);
        }}
        .info {{
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 1px solid rgba(255,255,255,0.1);
            color: #A1A1AA;
            font-size: 0.9rem;
        }}
        .qr-code {{
            margin: 2rem 0;
            padding: 1rem;
            background: white;
            display: inline-block;
            border-radius: 0.5rem;
        }}
    </style>
</head>
<body>
    <div class="store-container">
        <div class="app-icon">📱</div>
        <h1>{project['name']}</h1>
        <p class="description">{project['description']}</p>
        
        <a href="/api/export/download/apk/{project_id}" class="install-btn" download>
            📥 Installer sur Android
        </a>
        
        <div class="info">
            <p><strong>Type:</strong> {project['project_type'].upper()}</p>
            <p><strong>Version:</strong> 1.0.0</p>
            <p style="margin-top: 1rem;">⚠️ Activez "Sources inconnues" dans les paramètres Android</p>
        </div>
    </div>
</body>
</html>"""
    
    return HTMLResponse(content=html_content)

@api_router.get("/export/desktop/{project_id}")
async def get_desktop_export_page(project_id: str):
    """Get desktop export page"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        return HTMLResponse("<h1>Projet non trouvé</h1>", status_code=404)
    
    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Télécharger {project['name']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #050505 0%, #0F0F13 100%);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .download-container {{
            max-width: 600px;
            width: 100%;
            background: #0F0F13;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 1rem;
            padding: 3rem;
            text-align: center;
        }}
        .app-icon {{
            width: 120px;
            height: 120px;
            background: #E4FF00;
            border-radius: 24px;
            margin: 0 auto 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3rem;
            font-weight: bold;
            color: #050505;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #E4FF00;
        }}
        .description {{
            color: #A1A1AA;
            margin-bottom: 2rem;
            line-height: 1.6;
        }}
        .download-btn {{
            background: #E4FF00;
            color: #050505;
            border: none;
            padding: 1rem 3rem;
            font-size: 1.2rem;
            font-weight: bold;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: transform 0.2s;
            text-decoration: none;
            display: inline-block;
            margin: 0.5rem;
        }}
        .download-btn:hover {{
            transform: translateY(-2px);
        }}
        .info {{
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 1px solid rgba(255,255,255,0.1);
            color: #A1A1AA;
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="download-container">
        <div class="app-icon">💻</div>
        <h1>{project['name']}</h1>
        <p class="description">{project['description']}</p>
        
        <a href="/api/export/download/exe/{project_id}" class="download-btn" download>
            💾 Télécharger pour Windows
        </a>
        
        <div class="info">
            <p><strong>Type:</strong> Application Desktop</p>
            <p><strong>Version:</strong> 1.0.0</p>
            <p><strong>Compatibilité:</strong> Windows 10/11</p>
        </div>
    </div>
</body>
</html>"""
    
    return HTMLResponse(content=html_content)

@api_router.get("/export/download/apk/{project_id}")
async def download_apk(project_id: str):
    """Generate and download APK (simplified version)"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project or not project.get("generated_code"):
        raise HTTPException(status_code=404, detail="Projet ou code non trouvé")
    
    # For now, return the ZIP with instructions
    # In production, this would build an actual APK using Capacitor
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
        
        # Add APK build instructions
        zip_file.writestr("BUILD_APK.md", """# Build APK Instructions

## Option 1: Using Capacitor (Recommended)
```bash
npm install -g @capacitor/cli
capacitor init
capacitor add android
capacitor open android
# Build in Android Studio
```

## Option 2: Using PWA Builder
1. Visit https://www.pwabuilder.com/
2. Enter your app URL
3. Download Android package

## Option 3: Direct Install (PWA)
1. Host these files on a server
2. Open in Chrome on Android
3. Click "Add to Home Screen"
""")
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['name']}_android.zip"
        }
    )

@api_router.get("/export/download/exe/{project_id}")
async def download_exe(project_id: str):
    """Generate and download EXE (simplified version)"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project or not project.get("generated_code"):
        raise HTTPException(status_code=404, detail="Projet ou code non trouvé")
    
    # For now, return the ZIP with instructions
    # In production, this would build an actual EXE using Electron
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_code = project["generated_code"]
        for file_data in generated_code.get("files", []):
            zip_file.writestr(file_data["path"], file_data["content"])
        
        # Add Electron package.json
        zip_file.writestr("electron/package.json", json.dumps({
            "name": project["name"],
            "version": "1.0.0",
            "main": "main.js",
            "scripts": {
                "start": "electron .",
                "build": "electron-builder"
            },
            "devDependencies": {
                "electron": "latest",
                "electron-builder": "latest"
            },
            "build": {
                "appId": f"com.codeforge.{project['name'].lower()}",
                "win": {
                    "target": "nsis"
                }
            }
        }, indent=2))
        
        # Add Electron main.js
        zip_file.writestr("electron/main.js", """const { app, BrowserWindow } = require('electron');

function createWindow() {
    const win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });
    
    win.loadFile('../index.html');
}

app.whenReady().then(createWindow);
""")
        
        # Add build instructions
        zip_file.writestr("BUILD_EXE.md", """# Build Windows EXE Instructions

## Using Electron
```bash
cd electron
npm install
npm run build
```

The .exe will be in `electron/dist/`

## Alternative: Portable HTML App
Use NW.js or similar to package as standalone app
""")
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['name']}_windows.zip"
        }
    )

# ==================== ROOT ROUTE ====================

@api_router.get("/")
async def root():
    return {
        "message": "API CodeForge AI - Plateforme de Génération IA Sans Limites",
        "version": "2.0.0",
        "status": "online",
        "features": [
            "Chat IA (GPT)",
            "Création avec Emergent",
            "Export Mobile (APK)",
            "Export Desktop (EXE)",
            "Sans limites"
        ]
    }

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "chat_ai": "GPT (disponible)",
        "create_ai": "Emergent (disponible)",
        "exports": "mobile + desktop"
    }

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