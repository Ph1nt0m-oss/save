"""iter116 — Routes Community Bots extraites de server.py.

Approche : factory `build_community_bots_router(db, deps)` qui retourne un
APIRouter prêt à inclure (`prefix='/api'`). Les helpers (verify_signed,
require_creator_signature, log_change, logger) sont injectés en
dépendance pour rester découplé du module server.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from models.auth_signatures import SignedIn


# ----------------------------------------------------------------- Models

class CommunityBotIn(SignedIn):
    bot_id: Optional[str] = None
    name: str
    description: str
    kind: str = "assistance"
    prompt: str
    triggers: Optional[List[str]] = None
    is_published: bool = False


class BotRateIn(SignedIn):
    bot_id: str
    rating: int  # 1-5


class BotDeleteIn(SignedIn):
    bot_id: str


class BotTestIn(SignedIn):
    bot_id: str
    user_message: str


class BotKnowledgeIn(SignedIn):
    bot_id: str
    question: str
    answer: str
    entry_id: Optional[str] = None


class BotKnowledgeDeleteIn(SignedIn):
    bot_id: str
    entry_id: str


def build_community_bots_router(db, verify_signed, require_creator_signature, log_change, logger):
    """Factory qui retourne l'APIRouter community-bots branché sur les
    dépendances de server.py. Le router est ensuite inclus avec prefix='/api'."""
    router = APIRouter()

    @router.post("/community-bots/create")
    async def community_bots_create(payload: CommunityBotIn):
        """Admin/Créa créent un bot."""
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        if not payload.name.strip() or not payload.prompt.strip():
            raise HTTPException(status_code=400, detail="Nom et prompt requis.")
        bot_id = payload.bot_id or f"bot_{uuid.uuid4().hex[:12]}"
        doc = {
            "bot_id": bot_id,
            "name": payload.name.strip()[:60],
            "description": payload.description.strip()[:500],
            "kind": payload.kind,
            "prompt": payload.prompt.strip()[:4000],
            "triggers": [t.strip().lower() for t in (payload.triggers or []) if t.strip()][:20],
            "is_published": payload.is_published,
            "creator_key_id": payload.key_id,
            "ratings": [],
            "ts": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        if payload.bot_id:
            # iter126 Lot 2 #7 — bots protégés (agents de test) ne sont
            # éditables QUE par la créatrice (role==creator).
            existing = await db.community_bots.find_one(
                {"bot_id": payload.bot_id}, {"_id": 0, "protected": 1},
            )
            if existing and existing.get("protected") and dev.get("role") != "creator":
                raise HTTPException(status_code=403, detail="Bot protégé — édition réservée créatrice.")
            res = await db.community_bots.update_one(
                {"bot_id": payload.bot_id, "creator_key_id": payload.key_id},
                {"$set": {**doc, "updated_at": doc["ts"]}},
            )
            if res.matched_count == 0:
                raise HTTPException(status_code=404, detail="Bot introuvable ou non possédé.")
            return {"success": True, "bot_id": payload.bot_id, "updated": True}
        await db.community_bots.insert_one(doc)
        try:
            await log_change("model", f"Nouveau bot communautaire : {doc['name']}", {"bot_id": bot_id})
        except Exception:
            pass
        return {"success": True, "bot_id": bot_id}

    @router.get("/community-bots/list")
    async def community_bots_list(only_published: bool = True):
        # iter126 — bots protégés (agents de test) sont toujours listés.
        q = {"is_published": True} if only_published else {}
        rows = await db.community_bots.find(q, {"_id": 0, "prompt": 0}).sort("ts", -1).to_list(length=100)
        for b in rows:
            ratings = b.get("ratings") or []
            b["avg_rating"] = round(sum(r.get("rating", 0) for r in ratings) / len(ratings), 1) if ratings else None
            b["rating_count"] = len(ratings)
            b.pop("ratings", None)
            # Expose the protected flag so the front-end can disable edit/delete/code buttons.
            b["protected"] = bool(b.get("protected", False))
        return {"bots": rows}

    @router.post("/community-bots/delete")
    async def community_bots_delete(payload: BotDeleteIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        # iter126 Lot 2 #7 — Les "agents bots de test" (flag protected=True) ne
        # peuvent JAMAIS être supprimés, même par la créa hors mode visite.
        # En mode visite + role=creator OU role=creator stricte → autorisé.
        target = await db.community_bots.find_one({"bot_id": payload.bot_id}, {"_id": 0, "protected": 1})
        if target and target.get("protected"):
            # Vérifier que c'est bien la créatrice qui supprime
            dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
            if dev.get("role") != "creator":
                raise HTTPException(status_code=403, detail="Bot protégé — réservé créatrice.")
        await db.community_bots.delete_one({"bot_id": payload.bot_id})
        return {"success": True}

    @router.post("/community-bots/rate")
    async def community_bots_rate(payload: BotRateIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if payload.rating < 1 or payload.rating > 5:
            raise HTTPException(status_code=400, detail="Rating 1-5 requis.")
        await db.community_bots.update_one(
            {"bot_id": payload.bot_id, "ratings.key_id": {"$ne": payload.key_id}},
            {"$push": {"ratings": {
                "key_id": payload.key_id,
                "pseudo": dev.get("pseudo") or dev.get("label") or "Anonyme",
                "rating": payload.rating,
                "ts": datetime.now(timezone.utc).isoformat(),
            }}},
        )
        return {"success": True}

    @router.post("/community-bots/test")
    async def community_bots_test(payload: BotTestIn):
        """Lance un bot avec un message test. Réservé créa/admin."""
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        bot = await db.community_bots.find_one({"bot_id": payload.bot_id}, {"_id": 0})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot introuvable.")
        if not (payload.user_message or "").strip():
            raise HTTPException(status_code=400, detail="Message vide.")

        kb_entries = await db.bot_knowledge.find(
            {"bot_id": payload.bot_id}, {"_id": 0, "question": 1, "answer": 1}
        ).to_list(length=20)
        kb_text = ""
        if kb_entries:
            kb_text = "\n\n=== BASE DE CONNAISSANCES (FAQ) ===\n" + "\n".join(
                f"Q: {e.get('question', '')}\nR: {e.get('answer', '')}" for e in kb_entries
            )

        system_prompt = (bot.get("prompt") or "Tu es un assistant.") + kb_text
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            api_key = os.environ.get("EMERGENT_LLM_KEY") or ""
            if not api_key:
                raise HTTPException(status_code=503, detail="LLM key non configurée.")
            chat = LlmChat(api_key=api_key, session_id=f"bot_test_{payload.bot_id}", system_message=system_prompt)
            chat = chat.with_model("openai", "gpt-4o-mini")
            reply = await chat.send_message(UserMessage(text=payload.user_message[:3000]))
            return {
                "bot_id": payload.bot_id,
                "bot_name": bot.get("name"),
                "reply": str(reply or "")[:3000],
                "kb_used": len(kb_entries),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Bot test failed: {e}")
            raise HTTPException(status_code=500, detail=f"Erreur test bot: {str(e)[:200]}")

    @router.post("/community-bots/knowledge/upsert")
    async def community_bots_kb_upsert(payload: BotKnowledgeIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        if not payload.question.strip() or not payload.answer.strip():
            raise HTTPException(status_code=400, detail="Question et réponse requises.")
        bot = await db.community_bots.find_one({"bot_id": payload.bot_id}, {"_id": 0, "bot_id": 1})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot introuvable.")
        entry_id = payload.entry_id or f"kb_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "entry_id": entry_id,
            "bot_id": payload.bot_id,
            "question": payload.question.strip()[:300],
            "answer": payload.answer.strip()[:2000],
            "updated_at": now,
        }
        if payload.entry_id:
            res = await db.bot_knowledge.update_one(
                {"entry_id": payload.entry_id, "bot_id": payload.bot_id},
                {"$set": doc},
            )
            if res.matched_count == 0:
                raise HTTPException(status_code=404, detail="Entrée introuvable.")
            return {"success": True, "entry_id": entry_id, "updated": True}
        doc["created_at"] = now
        doc["author_key_id"] = payload.key_id
        await db.bot_knowledge.insert_one(doc)
        return {"success": True, "entry_id": entry_id}

    @router.get("/community-bots/knowledge/list")
    async def community_bots_kb_list(bot_id: str):
        rows = await db.bot_knowledge.find(
            {"bot_id": bot_id}, {"_id": 0, "author_key_id": 0}
        ).sort("updated_at", -1).to_list(length=200)
        return {"bot_id": bot_id, "entries": rows}

    @router.post("/community-bots/knowledge/delete")
    async def community_bots_kb_delete(payload: BotKnowledgeDeleteIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        role = dev.get("role"); sk = dev.get("staff_kind")
        if not (role == "creator" or sk == "admin"):
            raise HTTPException(status_code=403, detail="Réservé créa/admin.")
        await db.bot_knowledge.delete_one({"entry_id": payload.entry_id, "bot_id": payload.bot_id})
        return {"success": True}

    return router
