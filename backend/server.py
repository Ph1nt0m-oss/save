from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
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

# Import and include PWA routes
from routes.pwa_routes import export_router as pwa_router
from routes.desktop_routes import desktop_router

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

class SMSAuthRequest(BaseModel):
    phone_number: str
    code: Optional[str] = None

# ==================== AUTH ROUTES ====================

async def send_sms_via_twilio(phone_number: str, message: str) -> bool:
    """Send SMS via Twilio if configured, otherwise return False"""
    twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not all([twilio_sid, twilio_token, twilio_phone]):
        logger.warning("Twilio not configured - SMS will be simulated")
        return False
    
    try:
        # Twilio API call
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                auth=(twilio_sid, twilio_token),
                data={
                    "From": twilio_phone,
                    "To": phone_number,
                    "Body": message
                }
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"SMS sent successfully to {phone_number}")
                return True
            else:
                logger.error(f"Twilio error: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Twilio exception: {e}")
        return False

@api_router.post("/auth/sms/send")
async def send_sms_code(request: SMSAuthRequest):
    """Send SMS verification code (for offline auth)"""
    try:
        # Generate 6-digit code
        code = str(uuid.uuid4().int)[:6]
        
        # Store code in database (expires in 5 minutes)
        await db.sms_codes.insert_one({
            "phone_number": request.phone_number,
            "code": code,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Try to send via Twilio
        message = f"Votre code CodeForge AI: {code}. Valide 5 minutes."
        sms_sent = await send_sms_via_twilio(request.phone_number, message)
        
        logger.info(f"SMS Code for {request.phone_number}: {code} (Twilio: {sms_sent})")
        
        response_data = {
            "message": "Code SMS envoyé" if sms_sent else "Code généré (mode démo)",
            "sms_sent": sms_sent
        }
        
        # Return code in response only if Twilio is not configured (for testing)
        if not sms_sent:
            response_data["code"] = code  # DEMO MODE - remove when Twilio is configured
        
        return response_data
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auth/sms/verify")
async def verify_sms_code(request: SMSAuthRequest, response: Response):
    """Verify SMS code and create session"""
    try:
        # Find valid code
        code_doc = await db.sms_codes.find_one({
            "phone_number": request.phone_number,
            "code": request.code
        }, {"_id": 0})
        
        if not code_doc:
            return JSONResponse(status_code=401, content={"detail": "Code invalide"})
        
        # Check expiry
        expires_at = datetime.fromisoformat(code_doc["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            return JSONResponse(status_code=401, content={"detail": "Code expiré"})
        
        # Create or get user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        existing_user = await db.users.find_one({"phone_number": request.phone_number}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
        else:
            new_user = {
                "user_id": user_id,
                "phone_number": request.phone_number,
                "name": f"User {request.phone_number[-4:]}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
        
        # Create session
        session_token = f"sms_session_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        session_doc = {
            "session_token": session_token,
            "user_id": user_id,
            "auth_type": "sms",
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        # Set cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60,
            path="/"
        )
        
        # Delete used code
        await db.sms_codes.delete_one({"phone_number": request.phone_number, "code": request.code})
        
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        return user
    
    except Exception as e:
        logger.error(f"Error verifying SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
            
            logger.info(f"Emergent Auth response: {auth_response.status_code}")
            
            if auth_response.status_code == 404:
                logger.error("Session ID not found or expired")
                raise HTTPException(status_code=401, detail="Session expirée ou invalide. Veuillez vous reconnecter.")
            
            if auth_response.status_code != 200:
                logger.error(f"Emergent Auth error: {auth_response.text}")
                raise HTTPException(status_code=401, detail="Session ID invalide")
            
            user_data = auth_response.json()
            logger.info(f"User authenticated: {user_data.get('email')}")
        
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
    """Generate complete application like Emergent - React + Backend"""
    user_id = await get_current_user(request)
    
    description = data.get('description', '')
    mode = data.get('mode', 'online')
    wizard_config = data.get('wizard_config', {})
    app_type = wizard_config.get('appType', 'web')
    
    # Prompt ULTRA DÉTAILLÉ comme Emergent
    prompt = f"""Tu es un développeur expert comme Emergent AI. Tu génères des applications COMPLÈTES, PROFESSIONNELLES et PRÊTES À L'EMPLOI.

=== PROJET À CRÉER ===
{description}

=== EXIGENCES STRICTES ===
1. Application React moderne avec composants fonctionnels et hooks
2. Design professionnel avec TailwindCSS
3. Code 100% fonctionnel - AUCUN placeholder, AUCUN commentaire "à implémenter"
4. Responsive et mobile-first
5. Animations fluides avec transitions CSS
6. Gestion d'état avec useState/useEffect
7. LocalStorage pour la persistance des données

=== STRUCTURE REACT COMPLÈTE ===
Génère ces fichiers:

1. **index.html** - Point d'entrée avec CDN React, ReactDOM, Babel, TailwindCSS
2. **App.jsx** - Composant principal avec toute la logique
3. **styles.css** - Styles additionnels et animations
4. **manifest.json** - Pour PWA (installable sur mobile)
5. **sw.js** - Service Worker pour mode offline
6. **README.md** - Documentation complète

=== TEMPLATE INDEX.HTML OBLIGATOIRE ===
```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#050505">
    <link rel="manifest" href="manifest.json">
    <title>APP_NAME</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="styles.css">
</head>
<body class="bg-[#050505] text-white min-h-screen">
    <div id="root"></div>
    <script type="text/babel" src="App.jsx"></script>
    <script>if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js');</script>
</body>
</html>
```

=== DESIGN SYSTEM (COMME EMERGENT) ===
- Background: #050505 (noir), #0F0F13 (cartes)
- Primary: #E4FF00 (jaune cyber)
- Secondary: #00FF66 (vert)
- Accent: #00D4FF (cyan)
- Text: #FFFFFF, #A1A1AA (secondaire)
- Borders: rgba(255,255,255,0.1)
- Radius: rounded-lg, rounded-xl
- Shadows: shadow-lg, shadow-[0_0_30px_rgba(228,255,0,0.3)]

=== FORMAT JSON STRICT ===
{{
  "files": [
    {{"path": "index.html", "content": "CONTENU COMPLET"}},
    {{"path": "App.jsx", "content": "COMPOSANT REACT COMPLET"}},
    {{"path": "styles.css", "content": "STYLES CSS"}},
    {{"path": "manifest.json", "content": "MANIFEST PWA"}},
    {{"path": "sw.js", "content": "SERVICE WORKER"}},
    {{"path": "README.md", "content": "DOCUMENTATION"}}
  ],
  "explanation": "Description détaillée",
  "instructions": "Guide d'utilisation",
  "features": ["feature1", "feature2"],
  "pwa_ready": true
}}

IMPORTANT: 
- Le code doit fonctionner IMMÉDIATEMENT en ouvrant index.html
- L'app doit être installable comme PWA sur mobile
- Design IDENTIQUE à Emergent (sombre, moderne, animations)"""

    ai_text = None
    ai_source = None
    
    # Try Ollama first (for offline mode or if requested)
    if mode == 'offline':
        try:
            ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
            ollama_model = os.environ.get('OLLAMA_MODEL', 'deepseek-coder:6.7b')
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9,
                            "num_predict": 4096
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' not in result:
                        ai_text = result.get('response', '')
                        ai_source = 'ollama'
                        logger.info("Generation via Ollama successful")
                    else:
                        logger.warning(f"Ollama error: {result.get('error')}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
    
    # Fallback to Emergent AI (GPT) for online mode or if Ollama failed
    if ai_text is None:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            emergent_key = os.environ.get('EMERGENT_LLM_KEY')
            if not emergent_key:
                raise ValueError("EMERGENT_LLM_KEY not configured")
            
            # Initialize chat with GPT-4o
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"codeforge_{uuid.uuid4().hex[:8]}",
                system_message="Tu es un expert développeur senior. Tu génères du code complet, fonctionnel et professionnel. Réponds TOUJOURS en JSON valide."
            ).with_model("openai", "gpt-4o")
            
            # Send generation request
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            ai_text = response
            ai_source = 'emergent_gpt4o'
            logger.info("Generation via Emergent GPT-4o successful")
        except Exception as e:
            logger.error(f"Emergent AI error: {e}")
            
            # Last resort: generate a basic template
            ai_text = generate_basic_template(description)
            ai_source = 'template'
            logger.info("Using basic template as fallback")
    
    # Process AI response
    try:
        # Extract JSON from response
        start = ai_text.find('{')
        end = ai_text.rfind('}') + 1
        
        if start >= 0 and end > start:
            json_str = ai_text[start:end]
            generated = json.loads(json_str)
        else:
            # If no JSON found, use template
            generated = json.loads(generate_basic_template(description))
        
        # Create project
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        project = {
            "project_id": project_id,
            "user_id": user_id,
            "name": description[:50],
            "description": description,
            "project_type": "web",
            "generated_code": generated,
            "ai_source": ai_source,
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.projects.insert_one(project)

        # Create preview
        preview_id = f"preview_{uuid.uuid4().hex[:12]}"
        preview_doc = {
            "preview_id": preview_id,
            "project_id": project_id,
            "user_id": user_id,
            "files": generated.get("files", []),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.previews.insert_one(preview_doc)
        
        # Get backend URL
        backend_url = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001')
        preview_url = f"{backend_url}/api/preview/{preview_id}"

        return {
            "code": generated,
            "explanation": generated.get('explanation', 'Application générée avec succès'),
            "project": {"id": project_id, "name": description[:50]},
            "preview_url": preview_url,
            "ai_source": ai_source
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        raise HTTPException(status_code=500, detail="Erreur de parsing de la réponse IA")
    except Exception as e:
        logger.error(f"Error generating app: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_basic_template(description: str) -> str:
    """Generate a basic HTML/CSS/JS template as fallback"""
    app_name = description[:30] if description else "Mon Application"
    
    return json.dumps({
        "files": [
            {
                "path": "index.html",
                "content": f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_name}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="app-container">
        <header>
            <h1>{app_name}</h1>
            <p class="subtitle">Généré par CodeForge AI</p>
        </header>
        <main>
            <section class="hero">
                <h2>Bienvenue</h2>
                <p>{description}</p>
                <button id="startBtn" class="btn-primary">Commencer</button>
            </section>
            <section class="features">
                <div class="feature-card">
                    <span class="icon">⚡</span>
                    <h3>Rapide</h3>
                    <p>Performance optimisée</p>
                </div>
                <div class="feature-card">
                    <span class="icon">🎨</span>
                    <h3>Moderne</h3>
                    <p>Design élégant</p>
                </div>
                <div class="feature-card">
                    <span class="icon">📱</span>
                    <h3>Responsive</h3>
                    <p>Tous les appareils</p>
                </div>
            </section>
        </main>
        <footer>
            <p>Créé avec CodeForge AI</p>
        </footer>
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

:root {
    --bg-primary: #050505;
    --bg-secondary: #0F0F13;
    --accent-primary: #E4FF00;
    --accent-secondary: #00FF66;
    --text-primary: #FFFFFF;
    --text-secondary: #A1A1AA;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
}

.app-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

header {
    text-align: center;
    padding: 4rem 0;
}

header h1 {
    font-size: 3rem;
    color: var(--accent-primary);
    margin-bottom: 0.5rem;
}

.subtitle {
    color: var(--text-secondary);
}

.hero {
    text-align: center;
    padding: 4rem 2rem;
    background: var(--bg-secondary);
    border-radius: 1rem;
    margin-bottom: 3rem;
}

.hero h2 {
    font-size: 2rem;
    margin-bottom: 1rem;
}

.hero p {
    color: var(--text-secondary);
    margin-bottom: 2rem;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
}

.btn-primary {
    background: var(--accent-primary);
    color: var(--bg-primary);
    border: none;
    padding: 1rem 2rem;
    font-size: 1.1rem;
    font-weight: bold;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(228, 255, 0, 0.3);
}

.features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
}

.feature-card {
    background: var(--bg-secondary);
    padding: 2rem;
    border-radius: 0.5rem;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.1);
    transition: border-color 0.2s;
}

.feature-card:hover {
    border-color: var(--accent-primary);
}

.feature-card .icon {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 1rem;
}

.feature-card h3 {
    color: var(--accent-secondary);
    margin-bottom: 0.5rem;
}

footer {
    text-align: center;
    padding: 3rem 0;
    color: var(--text-secondary);
    border-top: 1px solid rgba(255,255,255,0.1);
    margin-top: 4rem;
}

@media (max-width: 768px) {
    header h1 {
        font-size: 2rem;
    }
    .hero h2 {
        font-size: 1.5rem;
    }
}"""
            },
            {
                "path": "app.js",
                "content": """// Application JavaScript
document.addEventListener('DOMContentLoaded', () => {
    console.log('Application chargée avec succès!');
    
    // Bouton démarrer
    const startBtn = document.getElementById('startBtn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            alert('Bienvenue dans votre application!');
        });
    }
    
    // Animation des cartes au scroll
    const cards = document.querySelectorAll('.feature-card');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    });
    
    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s, transform 0.5s';
        observer.observe(card);
    });
});"""
            },
            {
                "path": "manifest.json",
                "content": """{
    "name": \"""" + app_name + """\",
    "short_name": "App",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#050505",
    "theme_color": "#E4FF00",
    "icons": []
}"""
            },
            {
                "path": "README.md",
                "content": f"""# {app_name}

Application générée par CodeForge AI.

## Description
{description}

## Installation
1. Téléchargez les fichiers
2. Ouvrez `index.html` dans votre navigateur

## Technologies
- HTML5
- CSS3 (Variables CSS, Flexbox, Grid)
- JavaScript ES6+

## Fonctionnalités
- Design responsive
- Animations fluides
- Mode sombre

---
Créé avec ❤️ par CodeForge AI"""
            }
        ],
        "explanation": f"Application '{app_name}' générée avec un template moderne et responsive.",
        "instructions": "Ouvrez index.html dans votre navigateur pour voir l'application.",
        "features": ["Design responsive", "Mode sombre", "Animations", "PWA ready"]
    })

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

@api_router.post("/projects", response_model=Project, status_code=201)
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
async def redirect_to_pwa_install(project_id: str):
    """Redirect to PWA installation page"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/api/pwa/install/{project_id}")
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    generated_code = project.get("generated_code", {})
    files = generated_code.get("files", [])
    
    # Create APK-ready package with all necessary files
    import io
    import zipfile
    
    zip_buffer = io.BytesIO()
    app_name = project.get('name', 'App')[:30]
    safe_name = ''.join(c if c.isalnum() else '' for c in app_name.lower())
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add all generated files to www folder
        for file in files:
            zip_file.writestr(f"www/{file['path']}", file['content'])
        
        # Add Capacitor config for APK build
        capacitor_config = f'''{{
  "appId": "com.codeforge.{safe_name}",
  "appName": "{app_name}",
  "webDir": "www",
  "server": {{
    "androidScheme": "https"
  }},
  "plugins": {{
    "SplashScreen": {{
      "launchShowDuration": 2000,
      "backgroundColor": "#050505"
    }}
  }}
}}'''
        zip_file.writestr("capacitor.config.json", capacitor_config)
        
        # Add package.json for Capacitor
        package_json = f'''{{
  "name": "{safe_name}",
  "version": "1.0.0",
  "description": "Application générée par CodeForge AI",
  "main": "www/index.html",
  "scripts": {{
    "build:android": "npx cap add android && npx cap sync && cd android && ./gradlew assembleDebug"
  }},
  "dependencies": {{
    "@capacitor/android": "^5.0.0",
    "@capacitor/core": "^5.0.0",
    "@capacitor/cli": "^5.0.0"
  }}
}}'''
        zip_file.writestr("package.json", package_json)
        
        # Add build script for easy APK generation
        build_script = '''#!/bin/bash
echo "🚀 Building APK for Android..."
npm install
npx cap add android
npx cap sync
cd android && ./gradlew assembleDebug
echo "✅ APK généré dans: android/app/build/outputs/apk/debug/app-debug.apk"
'''
        zip_file.writestr("build-apk.sh", build_script)
        
        # Windows batch file
        build_bat = '''@echo off
echo Building APK for Android...
call npm install
call npx cap add android
call npx cap sync
cd android && gradlew assembleDebug
echo APK genere dans: android\\app\\build\\outputs\\apk\\debug\\app-debug.apk
pause
'''
        zip_file.writestr("build-apk.bat", build_bat)
        
        # Add comprehensive README
        readme = f'''# {app_name} - Package Android

## 🚀 Méthode 1: PWABuilder (Le plus simple)
1. Hébergez les fichiers du dossier `www/` sur un serveur web
2. Allez sur https://www.pwabuilder.com/
3. Entrez l'URL de votre site
4. Cliquez "Package for stores" → "Android"
5. Téléchargez votre APK !

## 📱 Méthode 2: Installation PWA directe
1. Hébergez les fichiers `www/` sur un serveur HTTPS
2. Ouvrez le site dans Chrome sur Android
3. Menu ⋮ → "Ajouter à l'écran d'accueil"
4. L'app s'installe comme une vraie application !

## 🔧 Méthode 3: Capacitor (Développeurs)
Prérequis: Node.js, Android Studio, JDK 17+

```bash
# Linux/Mac
chmod +x build-apk.sh
./build-apk.sh

# Windows
build-apk.bat
```

L'APK sera dans: `android/app/build/outputs/apk/debug/app-debug.apk`

## 📁 Contenu du package
- `www/` - Code source de l'application
- `capacitor.config.json` - Configuration Capacitor
- `package.json` - Dépendances Node.js
- `build-apk.sh` - Script de build Linux/Mac
- `build-apk.bat` - Script de build Windows

## 💡 Conseils
- Pour publier sur le Play Store, utilisez `./gradlew assembleRelease`
- Signez l'APK avec votre clé de développeur

Généré par CodeForge AI 🎨
'''
        zip_file.writestr("README.md", readme)
    
    zip_buffer.seek(0)
    
    filename = f"{app_name.replace(' ', '_')}_android.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@api_router.get("/export/desktop/{project_id}")
async def redirect_to_desktop_install(project_id: str):
    """Redirect to Desktop installation page"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/api/desktop/install/{project_id}")

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

@api_router.get("/preview/{preview_id}")
async def get_preview(preview_id: str):
    """Get preview HTML for generated content"""
    preview = await db.previews.find_one({"preview_id": preview_id}, {"_id": 0})
    
    if not preview:
        return HTMLResponse("<h1>Prévisualisation non trouvée</h1>", status_code=404)
    
    # Return HTML preview
    html_content = preview.get("html_content", "")
    
    if not html_content:
        # Generate preview from files
        files = preview.get("files", [])
        html_parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Prévisualisation</title>"]
        
        # Add CSS
        for file in files:
            if file["path"].endswith(".css"):
                html_parts.append(f"<style>{file['content']}</style>")
        
        html_parts.append("</head><body>")
        
        # Add HTML
        for file in files:
            if file["path"].endswith(".html"):
                html_parts.append(file["content"])
        
        # Add JS
        for file in files:
            if file["path"].endswith(".js"):
                html_parts.append(f"<script>{file['content']}</script>")
        
        html_parts.append("</body></html>")
        html_content = "\n".join(html_parts)
    
    return HTMLResponse(content=html_content)

@api_router.get("/preview/project/{project_id}")
async def get_project_preview(project_id: str):
    """Get preview for a specific project"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        return HTMLResponse("<h1>Projet non trouvé</h1>", status_code=404)
    
    generated_code = project.get("generated_code", {})
    files = generated_code.get("files", [])
    
    # Generate combined HTML preview
    html_parts = ["""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation - """ + project.get("name", "Projet") + """</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #050505; color: #fff; }
    </style>"""]
    
    # Add CSS files
    for file in files:
        if file["path"].endswith(".css"):
            html_parts.append(f"<style>{file['content']}</style>")
    
    html_parts.append("</head><body>")
    
    # Add HTML content
    for file in files:
        if file["path"].endswith(".html"):
            # Extract body content if full HTML
            content = file["content"]
            if "<body>" in content:
                start = content.find("<body>") + 6
                end = content.find("</body>")
                content = content[start:end] if end > start else content
            html_parts.append(content)
    
    # Add JS files
    for file in files:
        if file["path"].endswith(".js"):
            html_parts.append(f"<script>{file['content']}</script>")
    
    html_parts.append("</body></html>")
    
    return HTMLResponse(content="\n".join(html_parts))

@api_router.get("/preview/demo/{preview_type}")
async def get_demo_preview(preview_type: str):
    """Get demo preview pages for different formats (Web, PDF, DOCX, App)"""
    
    previews = {
        "web": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation Web - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: system-ui, -apple-system, sans-serif; 
            background: linear-gradient(135deg, #050505 0%, #0F0F13 100%); 
            color: #ffffff; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container { max-width: 800px; padding: 3rem; text-align: center; }
        .icon { font-size: 5rem; margin-bottom: 2rem; }
        h1 { color: #E4FF00; font-size: 3rem; margin-bottom: 1rem; }
        p { color: #A1A1AA; font-size: 1.2rem; line-height: 1.8; margin-bottom: 2rem; }
        .badge { 
            display: inline-block; 
            background: #00FF66; 
            color: #050505; 
            padding: 0.5rem 1.5rem; 
            border-radius: 2rem; 
            font-weight: bold;
            margin: 0.5rem;
        }
        .features { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 1.5rem; 
            margin-top: 3rem;
            text-align: left;
        }
        .feature { 
            background: rgba(255,255,255,0.05); 
            padding: 1.5rem; 
            border-radius: 0.5rem; 
            border: 1px solid rgba(255,255,255,0.1);
        }
        .feature h3 { color: #E4FF00; margin-bottom: 0.5rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🌐</div>
        <h1>Prévisualisation Web</h1>
        <p>Ceci est une démonstration de prévisualisation pour les applications web générées par CodeForge AI.</p>
        <span class="badge">HTML5</span>
        <span class="badge">CSS3</span>
        <span class="badge">JavaScript</span>
        <div class="features">
            <div class="feature">
                <h3>Responsive</h3>
                <p>S'adapte à tous les écrans</p>
            </div>
            <div class="feature">
                <h3>Moderne</h3>
                <p>Technologies récentes</p>
            </div>
            <div class="feature">
                <h3>Rapide</h3>
                <p>Performance optimisée</p>
            </div>
        </div>
    </div>
</body>
</html>""",

        "app": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation Application - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: system-ui, sans-serif; 
            background: #050505; 
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .phone-frame {
            width: 375px;
            height: 667px;
            background: #0F0F13;
            border-radius: 40px;
            padding: 20px;
            border: 3px solid #333;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
        }
        .phone-screen {
            background: linear-gradient(180deg, #1a1a2e 0%, #0F0F13 100%);
            height: 100%;
            border-radius: 25px;
            overflow: hidden;
        }
        .status-bar {
            height: 44px;
            background: rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            font-size: 12px;
        }
        .app-content {
            padding: 20px;
            text-align: center;
        }
        .app-icon {
            width: 80px;
            height: 80px;
            background: #E4FF00;
            border-radius: 20px;
            margin: 30px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
        }
        h2 { color: #E4FF00; margin-bottom: 10px; }
        p { color: #A1A1AA; font-size: 14px; }
        .btn {
            background: #E4FF00;
            color: #050505;
            border: none;
            padding: 15px 40px;
            border-radius: 25px;
            font-weight: bold;
            margin-top: 30px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="phone-frame">
        <div class="phone-screen">
            <div class="status-bar">
                <span>9:41</span>
                <span>📶 🔋</span>
            </div>
            <div class="app-content">
                <div class="app-icon">📱</div>
                <h2>Mon Application</h2>
                <p>Application mobile générée par CodeForge AI</p>
                <button class="btn">Démarrer</button>
            </div>
        </div>
    </div>
</body>
</html>""",

        "pdf": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation PDF - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Times New Roman', serif; 
            background: #404040; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .pdf-page {
            width: 595px;
            min-height: 842px;
            background: white;
            color: #000;
            padding: 60px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
        .header {
            border-bottom: 2px solid #E4FF00;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo { 
            font-size: 24px; 
            font-weight: bold; 
            color: #050505;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logo span { background: #E4FF00; padding: 5px 15px; }
        h1 { font-size: 28px; margin: 30px 0 20px; color: #1a1a1a; }
        p { line-height: 1.8; margin-bottom: 15px; color: #333; }
        .section { margin: 30px 0; }
        .highlight { background: #FFFFD0; padding: 15px; border-left: 4px solid #E4FF00; }
        .footer { 
            margin-top: 50px; 
            padding-top: 20px; 
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="pdf-page">
        <div class="header">
            <div class="logo">
                <span>CodeForge</span> AI
            </div>
        </div>
        <h1>Document de Prévisualisation</h1>
        <p>Ce document représente un aperçu de la génération PDF par CodeForge AI. Les documents générés peuvent inclure du texte formaté, des images et des tableaux.</p>
        
        <div class="section">
            <h2>Caractéristiques</h2>
            <ul style="margin-left: 20px; line-height: 2;">
                <li>Génération automatique de contenu</li>
                <li>Mise en page professionnelle</li>
                <li>Export haute qualité</li>
                <li>Compatible tous appareils</li>
            </ul>
        </div>
        
        <div class="highlight">
            <strong>Note:</strong> Les PDFs générés sont entièrement personnalisables et peuvent être modifiés selon vos besoins.
        </div>
        
        <div class="footer">
            Généré par CodeForge AI - Création Sans Limites
        </div>
    </div>
</body>
</html>""",

        "docx": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation DOCX - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Calibri', 'Arial', sans-serif; 
            background: #2b579a; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .word-container {
            background: #f3f3f3;
            padding: 20px;
            border-radius: 5px;
        }
        .toolbar {
            background: #2b579a;
            color: white;
            padding: 10px 20px;
            border-radius: 5px 5px 0 0;
            font-size: 14px;
            display: flex;
            gap: 20px;
        }
        .doc-page {
            width: 612px;
            min-height: 792px;
            background: white;
            color: #000;
            padding: 72px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        h1 { font-size: 26px; color: #2b579a; margin-bottom: 20px; }
        h2 { font-size: 18px; color: #2b579a; margin: 25px 0 15px; }
        p { line-height: 1.6; margin-bottom: 12px; }
        .table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .table th, .table td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        .table th { background: #2b579a; color: white; }
        .footer { 
            margin-top: 40px; 
            font-size: 11px; 
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 10px;
        }
    </style>
</head>
<body>
    <div class="word-container">
        <div class="toolbar">
            <span>📄 Document1.docx</span>
            <span>Fichier</span>
            <span>Édition</span>
            <span>Affichage</span>
        </div>
        <div class="doc-page">
            <h1>Document Word - Prévisualisation</h1>
            <p>Ce document représente un aperçu de la génération de fichiers DOCX par CodeForge AI. Les documents peuvent être édités dans Microsoft Word ou LibreOffice.</p>
            
            <h2>Fonctionnalités supportées</h2>
            <p>Les documents générés supportent de nombreuses fonctionnalités :</p>
            
            <table class="table">
                <tr>
                    <th>Fonctionnalité</th>
                    <th>Support</th>
                </tr>
                <tr>
                    <td>Texte formaté</td>
                    <td>✅ Complet</td>
                </tr>
                <tr>
                    <td>Tableaux</td>
                    <td>✅ Complet</td>
                </tr>
                <tr>
                    <td>Images</td>
                    <td>✅ Complet</td>
                </tr>
                <tr>
                    <td>En-têtes/Pieds de page</td>
                    <td>✅ Complet</td>
                </tr>
            </table>
            
            <div class="footer">
                Page 1 sur 1 | Généré par CodeForge AI
            </div>
        </div>
    </div>
</body>
</html>""",

        "image": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prévisualisation Image - CodeForge AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: system-ui, sans-serif; 
            background: #1a1a1a; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .image-preview {
            background: #0F0F13;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .image-frame {
            width: 600px;
            height: 400px;
            background: linear-gradient(135deg, #E4FF00 0%, #00FF66 50%, #00D4FF 100%);
            border-radius: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #050505;
            font-size: 24px;
            font-weight: bold;
        }
        .info {
            margin-top: 15px;
            color: #A1A1AA;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="image-preview">
        <div class="image-frame">
            🖼️ Image Générée par IA
        </div>
        <div class="info">
            Format: PNG | Résolution: 1920x1080 | Taille: ~2.4 MB
        </div>
    </div>
</body>
</html>"""
    }
    
    content = previews.get(preview_type, previews["web"])
    return HTMLResponse(content=content)

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

# Include PWA routes under /api/pwa
app.include_router(pwa_router, prefix="/api/pwa", tags=["PWA"])

# Include Desktop routes under /api/desktop
app.include_router(desktop_router, prefix="/api/desktop", tags=["Desktop"])

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