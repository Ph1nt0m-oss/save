"""iter147 LIVE — In-process E2E test.

Uses a single asyncio event loop for both motor client and FastAPI
TestClient calls to avoid cross-loop errors. Motor client is instantiated
inside the running loop via asyncio.run at the top of each test.

Seeds 2 test devices → invokes /groups/send handler directly (not through
TestClient which creates a separate loop) → asserts mention_notifications
+ mod_alerts invariants.
"""
from __future__ import annotations

import asyncio
import os
import sys
import pathlib
import uuid

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

os.environ["CODEFORGE_LLM_MOD_DISABLED"] = "1"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


async def _seed_device(db, *, key_id, public_handle, pseudo, role="creator",
                        anonymous=False):
    await db.device_keys.update_one(
        {"key_id": key_id},
        {"$set": {
            "key_id": key_id,
            "pseudo": pseudo,
            "public_handle": public_handle,
            "role": role,
            "email": f"{pseudo}@test.local",
            "device_id": f"dev_{key_id}",
        }},
        upsert=True,
    )
    await db.social_prefs.update_one(
        {"key_id": key_id},
        {"$set": {"key_id": key_id, "anonymous": bool(anonymous)}},
        upsert=True,
    )


async def _cleanup(db, *, key_ids, group_type):
    for kid in key_ids:
        await db.device_keys.delete_many({"key_id": kid})
        await db.social_prefs.delete_many({"key_id": kid})
        await db.mention_notifications.delete_many({"to_key_id": kid})
        await db.mention_notifications.delete_many({"from_key_id": kid})
        await db.mod_alerts.delete_many({"sender_key_id": kid})
        await db.mod_assignments.delete_many({"assignee_key_id": kid})
    await db.group_messages.delete_many({"group_type": group_type})


async def _invoke_groups_send(db, *, sender_key, group_type, content):
    """Directly call the /groups/send handler function without HTTP layer.

    Extracts the inner coroutine from build_groups_router so we stay in
    the same event loop as motor.
    """
    from routes.social_routes import build_groups_router
    from pydantic import BaseModel

    async def _verify_signed(key_id, nonce, signature):
        d = await db.device_keys.find_one({"key_id": key_id}, {"_id": 0})
        if not d:
            raise RuntimeError("unknown key_id")
        return d

    router = build_groups_router(db, _verify_signed, 4000)
    # Find the /groups/send POST handler
    handler = None
    for route in router.routes:
        if getattr(route, "path", "") == "/groups/send" and "POST" in getattr(route, "methods", set()):
            handler = route.endpoint
            break
    assert handler is not None, "Could not find /groups/send handler"

    # Build a Pydantic payload — import the class directly (annotation is
    # a string due to `from __future__ import annotations`).
    from routes.social_routes import GroupSendIn
    payload = GroupSendIn(
        key_id=sender_key,
        nonce="n",
        signature="s",
        group_type=group_type,
        content=content,
    )
    return await handler(payload)


def _run(coro):
    """Run an async test in a fresh event loop each time."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro())
    finally:
        loop.close()


# ------------------------------------------------------------------
# TEST 1: Anonymous sender → notification hides identity
# ------------------------------------------------------------------

def test_mention_notif_hides_identity_when_sender_anonymous():
    tag = uuid.uuid4().hex[:6]
    sender_key = f"TEST_sender_anon_{tag}"
    target_key = f"TEST_target_{tag}"
    target_handle = f"TgtHandle{tag}"
    group_type = "private"

    async def _t():
        os.environ["CODEFORGE_LLM_MOD_DISABLED"] = "1"
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
        await _seed_device(db, key_id=sender_key,
                           public_handle=f"SndrAnon{tag}",
                           pseudo=f"sndr_anon_{tag}",
                           role="creator", anonymous=True)
        await _seed_device(db, key_id=target_key,
                           public_handle=target_handle,
                           pseudo=f"tgt_{tag}",
                           role="creator", anonymous=False)
        content = (
            f"Salut @{target_handle}, casino gagnez argent facile "
            "cliquez vite gratuit maintenant"
        )
        try:
            await _invoke_groups_send(db,
                                      sender_key=sender_key,
                                      group_type=group_type,
                                      content=content)

            notif = await db.mention_notifications.find_one(
                {"to_key_id": target_key}, {"_id": 0},
                sort=[("ts", -1)],
            )
            assert notif is not None, "No mention_notification created"
            assert notif["author_hidden"] is True
            assert "from_pseudo" not in notif, f"leaked pseudo: {notif}"
            assert "from_public_handle" not in notif, f"leaked handle: {notif}"
            assert "from_role" not in notif, f"leaked role: {notif}"
            assert "from_key_id" not in notif, f"leaked key_id: {notif}"
            assert notif["type"] == "mention"
            assert notif["group_type"] == group_type
            assert notif["read"] is False

            alert = await db.mod_alerts.find_one(
                {"sender_key_id": sender_key}, {"_id": 0},
                sort=[("created_at", -1)],
            )
            assert alert is not None, "No mod_alert for spam message"
            assert "layer_local" in alert
            assert alert["layer_local"] is not None
            assert alert["layer_local"].get("layer") == "local"
            assert "layer_llm" in alert
            assert alert["layer_llm"] is None  # LLM disabled by env
        finally:
            await _cleanup(db, key_ids=[sender_key, target_key],
                           group_type=group_type)

    _run(_t)


# ------------------------------------------------------------------
# TEST 2: Non-anonymous sender → notification reveals identity
# ------------------------------------------------------------------

def test_mention_notif_reveals_identity_when_sender_not_anonymous():
    tag = uuid.uuid4().hex[:6]
    sender_key = f"TEST_sender_pub_{tag}"
    target_key = f"TEST_target_pub_{tag}"
    target_handle = f"TgtHandlePub{tag}"
    sender_pseudo = f"sndr_pub_{tag}"
    sender_handle = f"SndrPub{tag}"
    group_type = "private"

    async def _t():
        os.environ["CODEFORGE_LLM_MOD_DISABLED"] = "1"
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
        await _seed_device(db, key_id=sender_key,
                           public_handle=sender_handle,
                           pseudo=sender_pseudo,
                           role="creator", anonymous=False)
        await _seed_device(db, key_id=target_key,
                           public_handle=target_handle,
                           pseudo=f"tgt_pub_{tag}",
                           role="creator", anonymous=False)
        content = f"Coucou @{target_handle} regarde ce lien"
        try:
            await _invoke_groups_send(db,
                                      sender_key=sender_key,
                                      group_type=group_type,
                                      content=content)
            notif = await db.mention_notifications.find_one(
                {"to_key_id": target_key}, {"_id": 0},
                sort=[("ts", -1)],
            )
            assert notif is not None, "No mention_notification created"
            assert notif["author_hidden"] is False
            assert notif.get("from_pseudo") == sender_pseudo
            assert notif.get("from_public_handle") == sender_handle
            assert notif.get("from_role") == "creator"
            assert notif.get("from_key_id") == sender_key
        finally:
            await _cleanup(db, key_ids=[sender_key, target_key],
                           group_type=group_type)

    _run(_t)


# ------------------------------------------------------------------
# TEST 3: Deterministic layer alone creates alert with layer_local
# ------------------------------------------------------------------

def test_deterministic_layer_primary_creates_alert():
    tag = uuid.uuid4().hex[:6]
    sender_key = f"TEST_det_sender_{tag}"
    group_type = "private"

    async def _t():
        os.environ["CODEFORGE_LLM_MOD_DISABLED"] = "1"
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
        await _seed_device(db, key_id=sender_key,
                           public_handle=f"DetSndr{tag}",
                           pseudo=f"det_{tag}",
                           role="creator", anonymous=False)
        content = ("casino gagnez argent facile cliquez vite "
                   "gratuit maintenant free bitcoin click here porn sex")
        try:
            await _invoke_groups_send(db,
                                      sender_key=sender_key,
                                      group_type=group_type,
                                      content=content)
            alert = await db.mod_alerts.find_one(
                {"sender_key_id": sender_key}, {"_id": 0},
                sort=[("created_at", -1)],
            )
            assert alert is not None, (
                "Deterministic layer failed to create alert for obvious spam"
            )
            assert alert["layer_local"] is not None
            assert alert["layer_local"]["layer"] == "local"
            assert alert["layer_local"]["score"] >= 60
            assert alert["layer_local"]["suspicion"] is True
            assert alert["layer_llm"] is None
            reasons = alert.get("reasons") or []
            assert any(str(r).startswith("[règle]") for r in reasons), \
                f"No [règle] reason present: {reasons}"
        finally:
            await _cleanup(db, key_ids=[sender_key], group_type=group_type)

    _run(_t)
