"""iter149 — Runtime tests: verifies AI profile fragment is actually
INJECTED into the LLM system_message at call time (not just imported).

Approach: monkey-patch `emergentintegrations.llm.chat.LlmChat` to capture
the `system_message` passed to it, then call the actual route functions
(caly_ask, community_bots_test) with a stub DB. Also tests fault-tolerance
(empty ai_profiles, DB throwing) and isolation across agent_ids.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ------------------------------------------------------------------
# Helper: build a fake db with ai_profiles seeded per agent_id.
# ------------------------------------------------------------------
class _AsyncCursorList:
    def __init__(self, data): self._data = data
    async def to_list(self, length=None): return list(self._data)


class _FakeCollection:
    def __init__(self, docs=None, raise_on_find=False):
        self._docs = docs or []
        self._raise = raise_on_find
    async def find_one(self, query, projection=None):
        if self._raise:
            raise RuntimeError("db down")
        for d in self._docs:
            if all(d.get(k) == v for k, v in (query or {}).items()):
                return {k: v for k, v in d.items() if k != "_id"}
        return None
    def find(self, query=None, projection=None):
        return _AsyncCursorList([d for d in self._docs
                                 if all(d.get(k) == v for k, v in (query or {}).items())])


class _FakeDB:
    def __init__(self, ai_profiles=None, bot_configs=None, bot_knowledge=None,
                 community_bots=None, ai_profiles_raise=False):
        self.ai_profiles = _FakeCollection(ai_profiles, raise_on_find=ai_profiles_raise)
        self.bot_configs = _FakeCollection(bot_configs)
        self.bot_knowledge = _FakeCollection(bot_knowledge)
        self.community_bots = _FakeCollection(community_bots)


# ------------------------------------------------------------------
# Helper: patch LlmChat so we can capture system_message.
# ------------------------------------------------------------------
class _CaptureLlmChat:
    """Drop-in replacement for emergentintegrations.llm.chat.LlmChat.
    Captures ctor kwargs (system_message) and returns a canned reply."""
    last_instance = None

    def __init__(self, api_key=None, session_id=None, system_message=None, **_kw):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        _CaptureLlmChat.last_instance = self

    def with_model(self, provider, model_id):
        self.provider = provider; self.model_id = model_id
        return self

    async def send_message(self, message):
        # Return a plain string; caly_ask casts str(reply)[:3000]
        return "OK captured"


class _CaptureUserMessage:
    def __init__(self, text=None, **_):
        self.text = text


def _patch_llmchat(monkeypatch):
    """Insert a fake emergentintegrations module so `from emergentintegrations.llm.chat
    import LlmChat, UserMessage` inside the routes yields our capture class."""
    import types
    mod_root = types.ModuleType("emergentintegrations")
    mod_llm = types.ModuleType("emergentintegrations.llm")
    mod_chat = types.ModuleType("emergentintegrations.llm.chat")
    mod_chat.LlmChat = _CaptureLlmChat
    mod_chat.UserMessage = _CaptureUserMessage
    monkeypatch.setitem(sys.modules, "emergentintegrations", mod_root)
    monkeypatch.setitem(sys.modules, "emergentintegrations.llm", mod_llm)
    monkeypatch.setitem(sys.modules, "emergentintegrations.llm.chat", mod_chat)
    # Make sure caly module re-imports (it imports lazily inside the function).
    return _CaptureLlmChat


# ------------------------------------------------------------------
# Task 1 — Caly injection
# ------------------------------------------------------------------
def test_caly_ask_injects_profile_fragment(monkeypatch):
    _patch_llmchat(monkeypatch)
    monkeypatch.setenv("EMERGENT_LLM_KEY", "test-key")

    profile = {
        "writing_style": "STYLE_CALY_UNIQUE_TOKEN",
        "behavior": "toujours en franglais",
    }
    db = _FakeDB(ai_profiles=[{"agent_id": "caly_help", "profile": profile}])

    from routes.caly_routes import build_caly_router
    router = build_caly_router(
        db,
        verify_signed=AsyncMock(),
        log_change=AsyncMock(),
        logger=MagicMock(),
    )
    # Find the /caly/ask endpoint function
    ask_fn = None
    for route in router.routes:
        if getattr(route, "path", "") == "/caly/ask":
            ask_fn = route.endpoint; break
    assert ask_fn is not None

    from routes.caly_routes import CalyAskIn
    resp = asyncio.run(ask_fn(CalyAskIn(message="Bonjour")))
    assert resp is not None
    captured = _CaptureLlmChat.last_instance
    assert captured is not None
    sysmsg = captured.system_message or ""
    assert "STYLE_CALY_UNIQUE_TOKEN" in sysmsg, \
        f"profile fragment missing from Caly system_message: {sysmsg[-500:]}"
    assert "PROGRAMMATION SPÉCIFIQUE" in sysmsg
    assert "STYLE D'ÉCRITURE : STYLE_CALY_UNIQUE_TOKEN" in sysmsg


def test_caly_ask_isolation_dev_profile_does_not_bleed(monkeypatch):
    """Profile for agent_id='dev' MUST NOT bleed into caly (agent_id='caly_help')."""
    _patch_llmchat(monkeypatch)
    monkeypatch.setenv("EMERGENT_LLM_KEY", "test-key")

    db = _FakeDB(ai_profiles=[
        {"agent_id": "dev", "profile": {"writing_style": "DEV_ONLY_TOKEN"}},
    ])

    from routes.caly_routes import build_caly_router, CalyAskIn
    router = build_caly_router(db, verify_signed=AsyncMock(),
                               log_change=AsyncMock(), logger=MagicMock())
    ask_fn = next(r.endpoint for r in router.routes if getattr(r, "path", "") == "/caly/ask")
    asyncio.run(ask_fn(CalyAskIn(message="ping")))
    sysmsg = _CaptureLlmChat.last_instance.system_message or ""
    assert "DEV_ONLY_TOKEN" not in sysmsg, "dev profile leaked into caly!"


def test_caly_ask_fault_tolerant_when_db_throws(monkeypatch):
    """If db.ai_profiles.find_one raises, caly still works with base prompt."""
    _patch_llmchat(monkeypatch)
    monkeypatch.setenv("EMERGENT_LLM_KEY", "test-key")

    db = _FakeDB(ai_profiles_raise=True)
    from routes.caly_routes import build_caly_router, CalyAskIn
    router = build_caly_router(db, verify_signed=AsyncMock(),
                               log_change=AsyncMock(), logger=MagicMock())
    ask_fn = next(r.endpoint for r in router.routes if getattr(r, "path", "") == "/caly/ask")
    resp = asyncio.run(ask_fn(CalyAskIn(message="ping")))
    assert resp is not None
    sysmsg = _CaptureLlmChat.last_instance.system_message or ""
    # Base prompt still present, no fragment.
    assert "Caly" in sysmsg or "caly" in sysmsg.lower()
    assert "PROGRAMMATION SPÉCIFIQUE" not in sysmsg


def test_caly_ask_no_profile_uses_base_only(monkeypatch):
    _patch_llmchat(monkeypatch)
    monkeypatch.setenv("EMERGENT_LLM_KEY", "test-key")
    db = _FakeDB(ai_profiles=[])
    from routes.caly_routes import build_caly_router, CalyAskIn
    router = build_caly_router(db, verify_signed=AsyncMock(),
                               log_change=AsyncMock(), logger=MagicMock())
    ask_fn = next(r.endpoint for r in router.routes if getattr(r, "path", "") == "/caly/ask")
    asyncio.run(ask_fn(CalyAskIn(message="ping")))
    sysmsg = _CaptureLlmChat.last_instance.system_message or ""
    assert "PROGRAMMATION SPÉCIFIQUE" not in sysmsg


# ------------------------------------------------------------------
# Task 2 — Community bots injection (agent_id = bot_id)
# ------------------------------------------------------------------
def test_community_bots_test_injects_bot_specific_profile(monkeypatch):
    _patch_llmchat(monkeypatch)
    monkeypatch.setenv("EMERGENT_LLM_KEY", "test-key")

    db = _FakeDB(
        community_bots=[{"bot_id": "bot_alpha", "name": "Alpha", "prompt": "Tu es Alpha."}],
        ai_profiles=[
            {"agent_id": "bot_alpha", "profile": {"writing_style": "ALPHA_STYLE_TOKEN"}},
            {"agent_id": "bot_beta",  "profile": {"writing_style": "BETA_STYLE_TOKEN"}},
        ],
    )
    from routes.community_bots_routes import build_community_bots_router, BotTestIn

    async def _fake_verify(*args, **kwargs):
        return {"role": "creator", "staff_kind": None, "key_id": "kid"}

    router = build_community_bots_router(
        db, verify_signed=_fake_verify,
        require_creator_signature=_fake_verify,
        log_change=AsyncMock(), logger=MagicMock(),
    )
    # Locate the /community-bots/test endpoint
    test_fn = None
    for route in router.routes:
        if getattr(route, "path", "") == "/community-bots/test":
            test_fn = route.endpoint; break
    assert test_fn is not None

    payload = BotTestIn(bot_id="bot_alpha", user_message="hello",
                        key_id="kid", nonce="n", signature="sig")
    resp = asyncio.run(test_fn(payload))
    assert resp["bot_id"] == "bot_alpha"
    sysmsg = _CaptureLlmChat.last_instance.system_message or ""
    assert "ALPHA_STYLE_TOKEN" in sysmsg, \
        f"bot-specific profile not injected: {sysmsg[-500:]}"
    # Cross-bot isolation
    assert "BETA_STYLE_TOKEN" not in sysmsg, "Beta profile leaked into Alpha!"
