"""iter91 — Refacto slice 4b : routes /polls/* extraites de server.py.

Factory pattern : `build_polls_router(db, verify_signed,
require_creator_signature, audience_matches)` retourne un APIRouter inclus
ensuite dans server.py via `app.include_router(..., prefix='/api')`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


VALID_AUDIENCE_GROUPS = {"all", "approved", "creator", "admin", "modo", "pending", "non_validated"}


class PollCreateIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    question: str
    options: List[str] = Field(default_factory=list)
    audience: Any = "all"
    max_selections: int = 0
    allow_user_suggestions: bool = False


class PollEditIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    poll_id: str
    question: Optional[str] = None
    options: Optional[List[str]] = None
    audience: Any = None
    max_selections: Optional[int] = None
    allow_user_suggestions: Optional[bool] = None


class PollSuggestIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    poll_id: str
    text: str


class PollSuggestDecideIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    suggestion_id: str
    decision: str  # 'approve' | 'remove'


class PollVoteIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    poll_id: str
    option_index: Optional[int] = None
    option_indices: Optional[List[int]] = None


class _PollDeleteIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str
    poll_id: str


def build_polls_router(db, verify_signed, require_creator_signature, audience_matches):
    router = APIRouter()

    @router.post("/polls/create")
    async def polls_create(payload: PollCreateIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        q = (payload.question or "").strip()
        opts = [o.strip() for o in (payload.options or []) if o.strip()]
        if not q or len(opts) < 2:
            raise HTTPException(status_code=400, detail="Question + 2 options requis.")
        try:
            max_sel = int(payload.max_selections or 0)
        except Exception:
            max_sel = 0
        if max_sel < 0:
            max_sel = 0
        elif max_sel > 0:
            max_sel = min(max_sel, len(opts[:50]))
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        raw_aud = body.get("audience")
        aud = raw_aud if isinstance(raw_aud, list) else [raw_aud or "all"]
        aud = [g for g in aud if g in VALID_AUDIENCE_GROUPS] or ["all"]
        doc = {
            "poll_id": f"poll_{uuid.uuid4().hex[:12]}",
            "question": q[:300],
            "options": opts[:50],
            "audience": aud,
            "max_selections": max_sel,
            "allow_user_suggestions": bool(payload.allow_user_suggestions),
            "ts": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        await db.polls.insert_one(doc)
        return {"success": True, "poll_id": doc["poll_id"]}

    @router.post("/polls/edit")
    async def polls_edit(payload: PollEditIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        upd = {}
        if body.get("question") is not None:
            q = (body.get("question") or "").strip()
            if not q:
                raise HTTPException(status_code=400, detail="Question requise.")
            upd["question"] = q[:300]
        if body.get("options") is not None:
            opts = [o.strip() for o in (body.get("options") or []) if isinstance(o, str) and o.strip()]
            if len(opts) < 2:
                raise HTTPException(status_code=400, detail="2 options minimum.")
            upd["options"] = opts[:50]
        if body.get("audience") is not None:
            raw_aud = body.get("audience")
            aud = raw_aud if isinstance(raw_aud, list) else [raw_aud]
            aud = [g for g in aud if g in VALID_AUDIENCE_GROUPS] or ["all"]
            upd["audience"] = aud
        if body.get("max_selections") is not None:
            try:
                upd["max_selections"] = max(0, int(body.get("max_selections")))
            except Exception:
                pass
        if body.get("allow_user_suggestions") is not None:
            upd["allow_user_suggestions"] = bool(body.get("allow_user_suggestions"))
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = await db.polls.update_one({"poll_id": payload.poll_id}, {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Sondage introuvable.")
        if "options" in upd:
            await db.poll_votes.delete_many({"poll_id": payload.poll_id})
        return {"success": True, "updated_at": upd["updated_at"]}

    @router.post("/polls/suggest-option")
    async def polls_suggest_option(payload: PollSuggestIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        poll = await db.polls.find_one({"poll_id": payload.poll_id}, {"_id": 0, "allow_user_suggestions": 1})
        if not poll:
            raise HTTPException(status_code=404, detail="Sondage introuvable.")
        if not poll.get("allow_user_suggestions"):
            raise HTTPException(status_code=403, detail="Propositions désactivées sur ce sondage.")
        text = (payload.text or "").strip()
        if not text or len(text) > 200:
            raise HTTPException(status_code=400, detail="Texte requis (≤200 chars).")
        sid = f"sug_{uuid.uuid4().hex[:12]}"
        await db.poll_suggestions.insert_one({
            "suggestion_id": sid,
            "poll_id": payload.poll_id,
            "key_id": payload.key_id,
            "pseudo": dev.get("label") or dev.get("pseudo") or "Anonyme",
            "text": text,
            "status": "pending",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True, "suggestion_id": sid}

    @router.post("/polls/decide-suggestion")
    async def polls_decide_suggestion(payload: PollSuggestDecideIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        if payload.decision not in ("approve", "remove"):
            raise HTTPException(status_code=400, detail="decision invalide.")
        sug = await db.poll_suggestions.find_one({"suggestion_id": payload.suggestion_id}, {"_id": 0})
        if not sug:
            raise HTTPException(status_code=404, detail="Proposition introuvable.")
        new_status = "approved" if payload.decision == "approve" else "removed"
        await db.poll_suggestions.update_one(
            {"suggestion_id": payload.suggestion_id},
            {"$set": {"status": new_status, "decided_at": datetime.now(timezone.utc).isoformat()}},
        )
        if payload.decision == "approve":
            await db.polls.update_one({"poll_id": sug["poll_id"]}, {"$push": {"options": sug["text"]}})
        return {"success": True, "status": new_status}

    @router.get("/polls/list")
    async def polls_list(key_id: Optional[str] = None):
        rows = await db.polls.find({}, {"_id": 0}).sort("ts", -1).to_list(length=50)
        dev = None
        role = "public"
        if key_id:
            dev = await db.device_keys.find_one({"key_id": key_id}, {"_id": 0, "role": 1, "staff_kind": 1})
            role = (dev or {}).get("role") or "public"
        out = []
        for p in rows:
            if not audience_matches(p.get("audience"), dev):
                continue
            if "max_selections" not in p:
                p["max_selections"] = 1
            votes = await db.poll_votes.aggregate([
                {"$match": {"poll_id": p["poll_id"]}},
                {"$unwind": "$option_indices"},
                {"$group": {"_id": "$option_indices", "count": {"$sum": 1}}},
            ]).to_list(length=200)
            tally = {v["_id"]: v["count"] for v in votes}
            p["tally"] = [tally.get(i, 0) for i in range(len(p.get("options", [])))]
            voters = await db.poll_votes.count_documents({"poll_id": p["poll_id"]})
            p["voters"] = voters
            my = None
            if key_id:
                mv = await db.poll_votes.find_one(
                    {"poll_id": p["poll_id"], "voter_key_id": key_id},
                    {"_id": 0, "option_indices": 1, "option_index": 1},
                )
                if mv:
                    if isinstance(mv.get("option_indices"), list):
                        my = mv["option_indices"]
                    elif mv.get("option_index") is not None:
                        my = [mv["option_index"]]
            p["my_vote"] = my
            aud = p.get("audience")
            is_community = ("all" in aud) if isinstance(aud, list) else (aud in (None, "all"))
            if role == "creator" and not is_community:
                voters_rows = await db.poll_votes.find(
                    {"poll_id": p["poll_id"]},
                    {"_id": 0, "voter_key_id": 1, "option_indices": 1, "option_index": 1, "ts": 1},
                ).to_list(length=500)
                kids = list({v.get("voter_key_id") for v in voters_rows if v.get("voter_key_id")})
                pseudos = {}
                if kids:
                    async for d in db.device_keys.find(
                        {"key_id": {"$in": kids}}, {"_id": 0, "key_id": 1, "label": 1, "pseudo": 1, "email": 1},
                    ):
                        pseudos[d["key_id"]] = d.get("pseudo") or d.get("label") or d.get("email") or d["key_id"][:10]
                for v in voters_rows:
                    v["pseudo"] = pseudos.get(v.get("voter_key_id"), "Anonyme")
                    if isinstance(v.get("option_indices"), list):
                        pass
                    elif v.get("option_index") is not None:
                        v["option_indices"] = [v["option_index"]]
                p["voters_detail"] = voters_rows
            else:
                p["voters_detail"] = None
            if p.get("allow_user_suggestions"):
                suggestions = await db.poll_suggestions.find(
                    {"poll_id": p["poll_id"]}, {"_id": 0},
                ).sort("ts", 1).to_list(length=100)
                if role != "creator":
                    suggestions = [s for s in suggestions if s.get("status") in ("approved", "pending")]
                p["suggestions"] = suggestions
            else:
                p["suggestions"] = []
            out.append(p)
        return {"polls": out}

    @router.post("/polls/vote")
    async def polls_vote(payload: PollVoteIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        poll = await db.polls.find_one({"poll_id": payload.poll_id}, {"_id": 0})
        if not poll:
            raise HTTPException(status_code=404, detail="Sondage introuvable.")
        if not audience_matches(poll.get("audience"), dev):
            raise HTTPException(status_code=403, detail="Audience non autorisée.")
        n = len(poll.get("options", []))
        max_sel = int(poll.get("max_selections") or 0)
        if payload.option_indices is not None:
            chosen = sorted({int(i) for i in payload.option_indices if isinstance(i, int)})
        elif payload.option_index is not None:
            chosen = [int(payload.option_index)]
        else:
            raise HTTPException(status_code=400, detail="option_index(s) requis.")
        if not chosen:
            raise HTTPException(status_code=400, detail="Sélection vide.")
        if max_sel > 0 and len(chosen) > max_sel:
            raise HTTPException(status_code=400, detail=f"Max {max_sel} sélection(s) autorisée(s).")
        for idx in chosen:
            if not (0 <= idx < n):
                raise HTTPException(status_code=400, detail="Option invalide.")
        await db.poll_votes.update_one(
            {"poll_id": payload.poll_id, "voter_key_id": payload.key_id},
            {"$set": {
                "poll_id": payload.poll_id,
                "voter_key_id": payload.key_id,
                "option_indices": chosen,
                "ts": datetime.now(timezone.utc).isoformat(),
            }, "$unset": {"option_index": ""}},
            upsert=True,
        )
        return {"success": True}

    @router.post("/polls/delete")
    async def polls_delete(payload: _PollDeleteIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        if not payload.poll_id:
            raise HTTPException(status_code=400, detail="poll_id requis.")
        await db.polls.delete_one({"poll_id": payload.poll_id})
        await db.poll_votes.delete_many({"poll_id": payload.poll_id})
        return {"success": True}

    return router
