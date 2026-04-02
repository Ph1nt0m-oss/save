# ==================== CORE CONFIG ====================

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, uuid, logging, asyncio, time
from datetime import datetime, timezone
import httpx

# ==================== INIT ====================

app = FastAPI()
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI-SYSTEM")

# ==================== DATABASE ====================

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

# ==================== GLOBAL CONFIG ====================

SYSTEM_PROMPT = """
You are a powerful AI system that can:

* chat naturally
* build full applications
* generate production-ready code
* think like a senior engineer

Always respond clearly and efficiently.
"""

# ==================== AI MODELS ====================

class BaseModelClient:
async def generate(self, messages):
raise NotImplementedError

# -------- OLLAMA --------

class OllamaClient(BaseModelClient):
def **init**(self):
self.url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
self.model = os.getenv("OLLAMA_MODEL", "llama3")

```
async def generate(self, messages):
    prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{self.url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False}
        )
    return r.json()["response"]
```

# -------- GROQ --------

class GroqClient(BaseModelClient):
def **init**(self):
self.key = os.getenv("GROQ_API_KEY")

```
async def generate(self, messages):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": "llama3-70b-8192", "messages": messages}
        )
    return r.json()["choices"][0]["message"]["content"]
```

# -------- GPT --------

class GPTClient(BaseModelClient):
def **init**(self):
self.key = os.getenv("EMERGENT_LLM_KEY")

```
async def generate(self, messages):
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=self.key,
        session_id=str(uuid.uuid4())
    ).with_model("openai", "gpt-4o")

    return await chat.send_message(UserMessage(text=messages[-1]["content"]))
```

# ==================== AI ROUTER PRO ====================

class AIRouter:

```
def __init__(self):
    self.models = [
        OllamaClient(),
        GroqClient(),
        GPTClient()
    ]

async def generate(self, messages):
    """
    PARALLEL EXECUTION (race)
    """

    tasks = [self._safe_call(m, messages) for m in self.models]

    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()

    for task in done:
        result = task.result()
        if result:
            return result

    return "Erreur IA temporaire."

async def _safe_call(self, model, messages):
    try:
        return await model.generate(messages)
    except Exception as e:
        logger.warning(f"Model failed: {e}")
        return None
```

ai_router = AIRouter()

# ==================== MEMORY ====================

class MemoryManager:

```
async def get_context(self, user_id, limit=12):
    msgs = await db.chat_messages.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    return list(reversed(msgs))

async def summarize_if_needed(self, user_id):
    count = await db.chat_messages.count_documents({"user_id": user_id})

    if count > 50:
        logger.info("Summarizing conversation...")
```

memory = MemoryManager()

# ==================== AUTH ====================

async def get_user_id(request: Request):
token = request.cookies.get("session_token")
if not token:
raise HTTPException(401)

```
session = await db.user_sessions.find_one({"session_token": token})
if not session:
    raise HTTPException(401)

return session["user_id"]
```

# ==================== CHAT ====================

@api.post("/chat/message")
async def chat(request: Request, data: dict):

```
user_id = await get_user_id(request)
text = data.get("message")

# SAVE USER
await db.chat_messages.insert_one({
    "id": str(uuid.uuid4()),
    "user_id": user_id,
    "role": "user",
    "content": text,
    "timestamp": datetime.now(timezone.utc).isoformat()
})

# CONTEXT
history = await memory.get_context(user_id)

messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

# AI
response = await ai_router.generate(messages)

# SAVE AI
await db.chat_messages.insert_one({
    "id": str(uuid.uuid4()),
    "user_id": user_id,
    "role": "assistant",
    "content": response,
    "timestamp": datetime.now(timezone.utc).isoformat()
})

return {"response": response}
```

# ==================== BUILDER AGENTS ====================

class ArchitectAgent:
async def run(self, description):
return await ai_router.generate([
{"role": "system", "content": "You design software architecture"},
{"role": "user", "content": description}
])

class StructureAgent:
async def run(self, plan):
return await ai_router.generate([
{"role": "system", "content": "Return JSON file tree"},
{"role": "user", "content": plan}
])

class CodeAgent:
async def run(self, structure):
return await ai_router.generate([
{"role": "system", "content": "Generate full code JSON"},
{"role": "user", "content": structure}
])

architect = ArchitectAgent()
structure_agent = StructureAgent()
coder = CodeAgent()

# ==================== BUILDER PIPELINE ====================

@api.post("/ai/generate-complete-app")
async def generate_app(request: Request, data: dict):

```
user_id = await get_user_id(request)
description = data.get("description")

# PIPELINE
plan = await architect.run(description)
structure = await structure_agent.run(plan)
code = await coder.run(structure)

project = {
    "id": str(uuid.uuid4()),
    "user_id": user_id,
    "description": description,
    "plan": plan,
    "structure": structure,
    "code": code,
    "created_at": datetime.now(timezone.utc).isoformat()
}

await db.projects.insert_one(project)

return project
```

# ==================== OFFLINE MODE ====================

@api.post("/offline/chat")
async def offline_chat(data: dict):
"""
Force Ollama only
"""
model = OllamaClient()
return {"response": await model.generate(data["messages"])}

# ==================== HISTORY ====================

@api.get("/chat/history")
async def history(request: Request):
user_id = await get_user_id(request)

```
msgs = await db.chat_messages.find(
    {"user_id": user_id},
    {"_id": 0}
).sort("timestamp", 1).to_list(100)

return msgs
```

# ==================== HEALTH ====================

@api.get("/health")
async def health():
return {
"status": "ok",
"time": time.time()
}

# ==================== APP ====================

app.include_router(api)

app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)
