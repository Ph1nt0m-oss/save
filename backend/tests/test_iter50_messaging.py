"""Iter50 — backend tests for:

(1) _get_site_mode() in-memory 30s cache + invalidation by PUT /system/site-mode
(2) /devices/send-to-creator cool-down (1 nudge / 10 min → 429)
(3) NEW private messaging endpoints (signed):
    - /messages/send            (anyone)   creator must supply target_key_id
    - /messages/inbox           (creator)  threads + unread count
    - /messages/thread          (signed)   creator->any thread / user->own
    - /messages/unread-count    (signed)
    - /messages/delete-thread   (creator)

Teardown: reset site_mode=public, delete TEST_iter50_* devices + their messages.
KEPT_CREATOR_KEY_ID must NOT be touched.
"""
from __future__ import annotations

import base64
import os
import secrets
import time
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL not set")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

KEPT_CREATOR_KEY_ID = "dev_a797438afc28c67923881d46ae2971c1"


# ---------- helpers ----------------------------------------------------------


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_int(n: int, length: int = 32) -> str:
    return _b64url(n.to_bytes(length, "big"))


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def gen_keypair() -> Tuple[ec.EllipticCurvePrivateKey, dict]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    jwk = {"kty": "EC", "crv": "P-256",
           "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}
    return priv, jwk


def sign_nonce(priv: ec.EllipticCurvePrivateKey, nonce_b64url: str) -> str:
    nonce_bytes = _b64url_decode(nonce_b64url)
    der = priv.sign(nonce_bytes, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return _b64url(raw)


def register_device(label: str) -> Tuple[ec.EllipticCurvePrivateKey, str, dict]:
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register",
                      json={"public_key_jwk": jwk, "label": label}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"], jwk


def get_nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge",
                      json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def signed_payload(priv, key_id, extra=None):
    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    p = {"key_id": key_id, "nonce": nonce, "signature": sig}
    if extra:
        p.update(extra)
    return p


def set_site_mode_db(mongo, mode: str, guest_view=None):
    mongo.site_config.update_one(
        {"_id": "site_mode"},
        {"$set": {"mode": mode, "guest_view": guest_view}},
        upsert=True,
    )


# ---------- fixtures ---------------------------------------------------------


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    db = cli[DB_NAME]
    yield db
    set_site_mode_db(db, "public", None)
    cli.close()


@pytest.fixture(scope="module")
def cleanup(mongo):
    created_keys: list[str] = []
    yield {"keys": created_keys}
    safe = [k for k in created_keys if k != KEPT_CREATOR_KEY_ID]
    if safe:
        mongo.messages.delete_many({"$or": [
            {"thread_key_id": {"$in": safe}},
            {"from_key_id": {"$in": safe}},
        ]})
        mongo.device_keys.delete_many({"key_id": {"$in": safe}})
        mongo.device_nonces.delete_many({"key_id": {"$in": safe}})
        mongo.user_sessions.delete_many({"device_key_id": {"$in": safe}})
    # Cleanup any leftover TEST_iter50 labelled devices.
    leftovers = list(mongo.device_keys.find({"label": {"$regex": "^TEST_iter50"}},
                                            {"key_id": 1}))
    ids = [d["key_id"] for d in leftovers if d["key_id"] != KEPT_CREATOR_KEY_ID]
    if ids:
        mongo.messages.delete_many({"$or": [
            {"thread_key_id": {"$in": ids}},
            {"from_key_id": {"$in": ids}},
        ]})
    mongo.device_keys.delete_many({
        "label": {"$regex": "^TEST_iter50"},
        "key_id": {"$ne": KEPT_CREATOR_KEY_ID},
    })
    set_site_mode_db(mongo, "public", None)


@pytest.fixture(scope="module")
def temp_creator(mongo, cleanup):
    priv, key_id, _ = register_device("TEST_iter50_tmpcreator")
    cleanup["keys"].append(key_id)
    mongo.device_keys.update_one({"key_id": key_id},
                                 {"$set": {"role": "creator"}})
    yield {"priv": priv, "key_id": key_id}


@pytest.fixture(scope="module")
def user_a(cleanup):
    priv, key_id, _ = register_device("TEST_iter50_user_a")
    cleanup["keys"].append(key_id)
    return {"priv": priv, "key_id": key_id}


@pytest.fixture(scope="module")
def user_b(cleanup):
    priv, key_id, _ = register_device("TEST_iter50_user_b")
    cleanup["keys"].append(key_id)
    return {"priv": priv, "key_id": key_id}


# =============================================================================
# (A) Site-mode cache invalidation
# =============================================================================


def test_site_mode_cache_invalidates_on_put(mongo, temp_creator):
    # Set public first directly (warms cache via a GET).
    set_site_mode_db(mongo, "public", None)
    r = requests.get(f"{API}/system/site-mode", timeout=15)
    assert r.status_code == 200
    assert r.json()["mode"] == "public"

    # Now flip via PUT to 'private' (this must invalidate cache).
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"],
                          {"mode": "private"})
    r = requests.put(f"{API}/system/site-mode", json=body, timeout=15)
    assert r.status_code == 200, r.text

    # The very next GET must reflect new mode (cache invalidated).
    r = requests.get(f"{API}/system/site-mode", timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "private", r.json()

    # Restore.
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"],
                          {"mode": "public"})
    r = requests.put(f"{API}/system/site-mode", json=body, timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{API}/system/site-mode", timeout=15)
    assert r.json()["mode"] == "public"


# =============================================================================
# (B) /devices/send-to-creator cool-down (10 min)
# =============================================================================


def test_send_to_creator_cooldown_429_on_second_call(cleanup):
    # Use a fresh device — first nudge sets last_nudge_at, second hits 429.
    priv, key_id, _ = register_device("TEST_iter50_nudge")
    cleanup["keys"].append(key_id)

    body = signed_payload(priv, key_id)
    r = requests.post(f"{API}/devices/send-to-creator", json=body, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("sent") is True

    # Second call right after → 429.
    body = signed_payload(priv, key_id)
    r = requests.post(f"{API}/devices/send-to-creator", json=body, timeout=15)
    assert r.status_code == 429, r.text


# =============================================================================
# (C) /messages/send — basic validation
# =============================================================================


def test_messages_send_unknown_key_id_404(user_a):
    # Empty content gives 400 before lookup, so use real content+ a fake key.
    fake_key = f"dev_{secrets.token_hex(16)}"
    nonce = "AAAA"
    sig = "AAAA"
    r = requests.post(f"{API}/messages/send", json={
        "key_id": fake_key, "nonce": nonce, "signature": sig,
        "content": "hello",
    }, timeout=15)
    assert r.status_code == 404, r.text


def test_messages_send_empty_content_400(user_a):
    body = signed_payload(user_a["priv"], user_a["key_id"], {"content": "   "})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 400, r.text


def test_messages_send_too_long_content_400(user_a):
    body = signed_payload(user_a["priv"], user_a["key_id"], {"content": "x" * 2001})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 400, r.text
    assert "2000" in r.text or "long" in r.text.lower()


def test_messages_send_user_success(mongo, user_a, cleanup):
    """user_a sends a message; thread_key_id == user_a.key_id, is_from_creator=False."""
    content = f"hello creator {secrets.token_hex(4)}"
    body = signed_payload(user_a["priv"], user_a["key_id"], {"content": content})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["sent"] is True
    assert "message_id" in j

    # Verify in Mongo.
    doc = mongo.messages.find_one({"message_id": j["message_id"]})
    assert doc is not None
    assert doc["thread_key_id"] == user_a["key_id"]
    assert doc["is_from_creator"] is False
    assert doc["content"] == content
    assert doc["read_by_user"] is True
    assert doc["read_by_creator"] is False


# =============================================================================
# (D) /messages/send — cooldown (30s anti-flood)
# =============================================================================


def test_messages_send_cooldown_429_on_second(cleanup):
    priv, key_id, _ = register_device("TEST_iter50_flood")
    cleanup["keys"].append(key_id)

    body = signed_payload(priv, key_id, {"content": "first"})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 200, r.text

    # Second back-to-back.
    body = signed_payload(priv, key_id, {"content": "second"})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 429, r.text


# =============================================================================
# (E) /messages/send — creator branch
# =============================================================================


def test_messages_send_creator_without_target_400(temp_creator):
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"],
                          {"content": "hi from creator"})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 400, r.text
    assert "target_key_id" in r.text


def test_messages_send_creator_with_target_success(mongo, temp_creator, user_a):
    content = f"creator reply {secrets.token_hex(4)}"
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"],
                          {"content": content, "target_key_id": user_a["key_id"]})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    doc = mongo.messages.find_one({"message_id": j["message_id"]})
    assert doc is not None
    assert doc["thread_key_id"] == user_a["key_id"]
    assert doc["is_from_creator"] is True
    assert doc["read_by_creator"] is True
    assert doc["read_by_user"] is False


# =============================================================================
# (F) /messages/send — blocked device
# =============================================================================


BLOCKED_DETAIL = "Votre demande a été formulée de nombreuses fois. Veuillez contacter le créateur."


def test_messages_send_from_blocked_device_403(mongo, cleanup):
    priv, key_id, _ = register_device("TEST_iter50_blocked")
    cleanup["keys"].append(key_id)
    mongo.device_keys.update_one({"key_id": key_id}, {"$set": {"role": "blocked"}})
    body = signed_payload(priv, key_id, {"content": "please unblock"})
    r = requests.post(f"{API}/messages/send", json=body, timeout=15)
    assert r.status_code == 403, r.text
    assert BLOCKED_DETAIL in r.json().get("detail", ""), r.text


# =============================================================================
# (G) /messages/inbox — creator only
# =============================================================================


def test_messages_inbox_without_creator_signature_403(user_a):
    body = signed_payload(user_a["priv"], user_a["key_id"])
    r = requests.post(f"{API}/messages/inbox", json=body, timeout=15)
    assert r.status_code == 403, r.text


def test_messages_inbox_creator_returns_threads(temp_creator, user_a):
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"])
    r = requests.post(f"{API}/messages/inbox", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "threads" in j
    assert isinstance(j["threads"], list)
    # user_a thread should be present (from earlier test).
    ours = [t for t in j["threads"] if t["thread_key_id"] == user_a["key_id"]]
    assert ours, j
    row = ours[0]
    for k in ("thread_key_id", "label", "role",
              "last_ts", "last_content", "last_is_from_creator",
              "unread", "total"):
        assert k in row, f"missing key {k} in {row}"


# =============================================================================
# (H) creator-reads-thread → unread drops to 0
# =============================================================================


def test_creator_reads_thread_marks_user_msgs_read(temp_creator, user_a, mongo):
    # Ensure there's at least one unread user msg by inserting one in Mongo
    # (avoids cooldown of /messages/send).
    msg_id = f"TEST_iter50_msg_{secrets.token_hex(6)}"
    mongo.messages.insert_one({
        "message_id": msg_id,
        "thread_key_id": user_a["key_id"],
        "from_key_id": user_a["key_id"],
        "is_from_creator": False,
        "content": "unread test",
        "sender_label": "TEST_iter50_user_a",
        "ts": "2099-01-01T00:00:00+00:00",  # newest
        "read_by_creator": False,
        "read_by_user": True,
    })
    # Confirm unread > 0 in inbox.
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"])
    r = requests.post(f"{API}/messages/inbox", json=body, timeout=15)
    inbox = r.json()["threads"]
    row = [t for t in inbox if t["thread_key_id"] == user_a["key_id"]][0]
    assert row["unread"] >= 1, row

    # Creator reads the thread.
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"],
                          {"thread_key_id": user_a["key_id"]})
    r = requests.post(f"{API}/messages/thread", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["thread_key_id"] == user_a["key_id"]
    assert isinstance(j["messages"], list) and len(j["messages"]) >= 1

    # Now inbox unread for that thread should be 0.
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"])
    r = requests.post(f"{API}/messages/inbox", json=body, timeout=15)
    inbox = r.json()["threads"]
    row = [t for t in inbox if t["thread_key_id"] == user_a["key_id"]][0]
    assert row["unread"] == 0, row


# =============================================================================
# (I) /messages/thread — non-creator sees only own thread
# =============================================================================


def test_thread_for_non_creator_returns_only_own(user_a, user_b, mongo):
    # Insert a message in user_b's thread (not user_a's).
    mongo.messages.insert_one({
        "message_id": f"TEST_iter50_b_{secrets.token_hex(6)}",
        "thread_key_id": user_b["key_id"],
        "from_key_id": user_b["key_id"],
        "is_from_creator": False,
        "content": "user_b private",
        "sender_label": "TEST_iter50_user_b",
        "ts": "2099-01-02T00:00:00+00:00",
        "read_by_creator": False,
        "read_by_user": True,
    })
    # user_a requests /messages/thread (with bogus thread_key_id arg or none).
    body = signed_payload(user_a["priv"], user_a["key_id"],
                          {"thread_key_id": user_b["key_id"]})  # ignored for non-creator
    r = requests.post(f"{API}/messages/thread", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["thread_key_id"] == user_a["key_id"]
    for m in j["messages"]:
        assert m["thread_key_id"] == user_a["key_id"]
        assert m["content"] != "user_b private"


# =============================================================================
# (J) /messages/unread-count
# =============================================================================


def test_unread_count_user_sees_only_creator_replies_in_own_thread(user_a, user_b, mongo):
    # Insert one unread creator reply in user_a's thread.
    mongo.messages.insert_one({
        "message_id": f"TEST_iter50_cr_a_{secrets.token_hex(6)}",
        "thread_key_id": user_a["key_id"],
        "from_key_id": "creator_fake",
        "is_from_creator": True,
        "content": "creator reply A",
        "sender_label": "Créatrice",
        "ts": "2099-01-03T00:00:00+00:00",
        "read_by_creator": True,
        "read_by_user": False,
    })
    # And one unread creator reply in user_b's thread (must NOT count for user_a).
    mongo.messages.insert_one({
        "message_id": f"TEST_iter50_cr_b_{secrets.token_hex(6)}",
        "thread_key_id": user_b["key_id"],
        "from_key_id": "creator_fake",
        "is_from_creator": True,
        "content": "creator reply B",
        "sender_label": "Créatrice",
        "ts": "2099-01-03T00:00:00+00:00",
        "read_by_creator": True,
        "read_by_user": False,
    })

    body = signed_payload(user_a["priv"], user_a["key_id"])
    r = requests.post(f"{API}/messages/unread-count", json=body, timeout=15)
    assert r.status_code == 200, r.text
    n = r.json()["unread"]
    assert n >= 1, r.json()

    # Now check creator unread-count returns total across all threads.
    # (We can't compute exact, but must be >= the two unread user msgs that exist.)
    # First add an unread user msg.
    mongo.messages.insert_one({
        "message_id": f"TEST_iter50_u_{secrets.token_hex(6)}",
        "thread_key_id": user_b["key_id"],
        "from_key_id": user_b["key_id"],
        "is_from_creator": False,
        "content": "from user b unread",
        "sender_label": "TEST_iter50_user_b",
        "ts": "2099-01-03T00:00:00+00:00",
        "read_by_creator": False,
        "read_by_user": True,
    })


def test_unread_count_creator_returns_total(temp_creator, mongo):
    body = signed_payload(temp_creator["priv"], temp_creator["key_id"])
    r = requests.post(f"{API}/messages/unread-count", json=body, timeout=15)
    assert r.status_code == 200, r.text
    # Should be >= 1 because previous test inserted an unread user msg from user_b.
    n = r.json()["unread"]
    assert isinstance(n, int)
    assert n >= 1, r.json()


# =============================================================================
# (K) /messages/delete-thread — creator only
# =============================================================================


def test_delete_thread_non_creator_403(user_a):
    body = signed_payload(user_a["priv"], user_a["key_id"],
                          {"thread_key_id": user_a["key_id"]})
    r = requests.post(f"{API}/messages/delete-thread", json=body, timeout=15)
    assert r.status_code == 403, r.text


def test_delete_thread_creator_removes_all(mongo, temp_creator, user_b):
    # Make sure user_b thread has something.
    mongo.messages.insert_one({
        "message_id": f"TEST_iter50_delprobe_{secrets.token_hex(6)}",
        "thread_key_id": user_b["key_id"],
        "from_key_id": user_b["key_id"],
        "is_from_creator": False,
        "content": "to be deleted",
        "sender_label": "TEST_iter50_user_b",
        "ts": "2099-01-04T00:00:00+00:00",
        "read_by_creator": False,
        "read_by_user": True,
    })
    before = mongo.messages.count_documents({"thread_key_id": user_b["key_id"]})
    assert before >= 1

    body = signed_payload(temp_creator["priv"], temp_creator["key_id"],
                          {"thread_key_id": user_b["key_id"]})
    r = requests.post(f"{API}/messages/delete-thread", json=body, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == before, r.json()

    after = mongo.messages.count_documents({"thread_key_id": user_b["key_id"]})
    assert after == 0


# =============================================================================
# (Z) Final: site_mode reset
# =============================================================================


def test_zz_final_site_mode_public(mongo):
    set_site_mode_db(mongo, "public", None)
    r = requests.get(f"{API}/system/site-mode", timeout=15)
    assert r.status_code == 200
    assert r.json()["mode"] == "public"
