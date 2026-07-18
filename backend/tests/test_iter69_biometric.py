"""iter69 — biometric enrollment + /auth/disconnect-soft + 35s threshold.

Tests:
  A) POST /auth/register without biometric_kind → 400 "Identité biométrique requise".
  B) POST /auth/register with biometric_kind='iris' + 3 valid hashes → 200.
  C) POST /auth/register with biometric_kind='iris' + <3 hashes → 400.
  D) POST /auth/register with biometric_kind='webauthn' + invalid options_token → 400.
  E) POST /webauthn/enroll-begin anonymously → 200 + {options, options_token(>=32)}.
  F) Threshold = 35s: -20s session → 202 ; -40s → 200 ; -120s → 200.
  G) POST /auth/disconnect-soft?t=<session_token> → 200 + last_seen_at ≤ now-23h.
  H) POST /auth/disconnect-soft without token → 200 (no-op).
  I) Pseudo min 1 char → 200 ; empty pseudo → 400.
"""
from __future__ import annotations
import os
import time
import secrets
import base64
import hashlib
from datetime import datetime, timezone, timedelta

import bcrypt
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL and MONGO_URL and DB_NAME


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _iris_hash():
    """Return a 44-char b64 SHA-256 hash (within 20-128 char range)."""
    return base64.b64encode(hashlib.sha256(secrets.token_bytes(32)).digest()).decode()


def _base_register_payload(email, pseudo="t"):
    return {
        "email": email,
        "password": "Pass1234",
        "pseudo": pseudo,
        "public_handle": f"iter69_{secrets.token_hex(4)}",
        "frontend_url": BASE_URL,
        "device_capture_kind": "phone",
        "device_capture_product": "Galaxy S21 5G",
        "device_capture_model": "SM-G991U1",
    }


def _ensure_user(db, email, password):
    existing = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if existing:
        db.users.update_one({"email": email}, {"$set": {
            "password_hash": _hash(password), "verified": True, "active": True}})
        return existing["user_id"]
    uid = f"TEST_iter69_{int(time.time()*1000)}_{email.split('@')[0]}"
    db.users.insert_one({
        "user_id": uid, "email": email, "password_hash": _hash(password),
        "pseudo": email.split("@")[0][:30], "verified": True, "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return uid


def _seed_devkey(db, key_id, role="inactive", email=None):
    db.device_keys.delete_many({"key_id": key_id})
    doc = {"key_id": key_id,
           "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
           "role": role, "created_at": datetime.now(timezone.utc).isoformat()}
    if email:
        doc["email"] = email
    db.device_keys.insert_one(doc)


def _seed_session(db, uid, key_id, last_seen_offset_sec=0, token_prefix="TEST_iter69_sess_"):
    token = token_prefix + secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    seen = now + timedelta(seconds=last_seen_offset_sec)
    db.user_sessions.insert_one({
        "session_token": token, "user_id": uid,
        "device_key_id": key_id, "device_label": "iter69-test",
        "auth_type": "email",
        "created_at": now.isoformat(),
        "last_seen_at": seen.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })
    return token


# ---------------------------------------------------------------------------
# A) /auth/register without biometric_kind → 400
# ---------------------------------------------------------------------------
class TestRegisterBiometricValidation:
    def test_register_without_biometric_returns_400(self, db):
        ts = int(time.time()*1000)
        email = f"test_iter69_nobio_{ts}@gmail.com"
        db.users.delete_many({"email": email})
        payload = _base_register_payload(email)
        r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "biom" in detail, f"detail should mention biometric: {detail}"

    def test_register_with_iris_3_hashes_returns_200(self, db):
        ts = int(time.time()*1000) + 1
        email = f"test_iter69_iris_{ts}@gmail.com"
        db.users.delete_many({"email": email})
        payload = _base_register_payload(email)
        payload["biometric_kind"] = "iris"
        payload["biometric_iris_hashes"] = [_iris_hash() for _ in range(3)]
        r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        # verification_token presence (or verification_link or user_id) — accept any sign of success
        assert any(k in body for k in ("verification_token", "verification_link", "user_id", "ok", "message")), body
        # And verify user was created with biometric field
        user = db.users.find_one({"email": email}, {"_id": 0, "biometric": 1})
        assert user and user.get("biometric"), "biometric not stored on user"
        assert user["biometric"].get("kind") == "iris"
        assert len(user["biometric"].get("hashes") or []) == 3
        # cleanup
        db.users.delete_many({"email": email})

    def test_register_with_iris_2_hashes_returns_400(self, db):
        ts = int(time.time()*1000) + 2
        email = f"test_iter69_iris2_{ts}@gmail.com"
        db.users.delete_many({"email": email})
        payload = _base_register_payload(email)
        payload["biometric_kind"] = "iris"
        payload["biometric_iris_hashes"] = [_iris_hash() for _ in range(2)]
        r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "3" in detail or "iris" in detail, f"detail: {detail}"

    def test_register_with_webauthn_invalid_options_token_returns_400(self, db):
        ts = int(time.time()*1000) + 3
        email = f"test_iter69_wabad_{ts}@gmail.com"
        db.users.delete_many({"email": email})
        payload = _base_register_payload(email)
        payload["biometric_kind"] = "webauthn"
        payload["biometric_options_token"] = "DOES_NOT_EXIST_" + secrets.token_urlsafe(8)
        payload["biometric_credential"] = {"id": "fake", "rawId": "fake", "response": {}, "type": "public-key"}
        r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "défi" in detail or "introuvable" in detail or "challenge" in detail or "expir" in detail, detail


# ---------------------------------------------------------------------------
# B) /webauthn/enroll-begin (anonymous, signup-flow)
# ---------------------------------------------------------------------------
class TestWebAuthnEnrollBegin:
    def test_enroll_begin_anonymous_returns_options_and_token(self, db):
        r = requests.post(f"{API}/webauthn/enroll-begin",
                          json={"email": "anon_test@gmail.com", "origin": BASE_URL},
                          timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "options" in body and isinstance(body["options"], dict), body
        assert "options_token" in body and isinstance(body["options_token"], str), body
        assert len(body["options_token"]) >= 32, f"options_token too short: {len(body['options_token'])}"
        # And challenge is persisted with kind='signup'
        doc = db.webauthn_challenges.find_one(
            {"options_token": body["options_token"]}, {"_id": 0})
        assert doc, "challenge not persisted"
        assert doc.get("kind") == "signup", f"kind={doc.get('kind')}"
        # cleanup
        db.webauthn_challenges.delete_many({"options_token": body["options_token"]})

    def test_enroll_begin_without_body_still_returns_200(self, db):
        r = requests.post(f"{API}/webauthn/enroll-begin", json={}, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "options_token" in body
        db.webauthn_challenges.delete_many({"options_token": body["options_token"]})


# ---------------------------------------------------------------------------
# C) /auth/disconnect-soft
# ---------------------------------------------------------------------------
class TestDisconnectSoft:
    def test_disconnect_soft_with_token_sets_last_seen_to_past(self, db):
        ts = int(time.time()*1000)
        email = f"test_iter69_dsoft_{ts}@gmail.com"
        uid = _ensure_user(db, email, "Pass1234")
        db.user_sessions.delete_many({"user_id": uid})
        kA = f"iter69_dsoft_{ts}"
        _seed_devkey(db, kA, email=email)
        token = _seed_session(db, uid, kA, last_seen_offset_sec=-5)

        r = requests.post(f"{API}/auth/disconnect-soft", params={"t": token}, timeout=10)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"

        doc = db.user_sessions.find_one({"session_token": token}, {"_id": 0, "last_seen_at": 1})
        assert doc, "session disappeared"
        ls = datetime.fromisoformat(doc["last_seen_at"])
        age_hours = (datetime.now(timezone.utc) - ls).total_seconds() / 3600
        assert age_hours >= 23, f"last_seen_at not pushed far enough ({age_hours}h)"

    def test_disconnect_soft_without_token_returns_200_noop(self):
        r = requests.post(f"{API}/auth/disconnect-soft", timeout=10)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        assert r.json().get("ok") is True


# ---------------------------------------------------------------------------
# D) Threshold = 35s
# ---------------------------------------------------------------------------
class TestThreshold35s:
    def test_session_20s_old_triggers_202(self, db):
        ts = int(time.time()) + 700
        email = f"test_iter69_th20_{ts}@gmail.com"
        uid = _ensure_user(db, email, "Pass1234")
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})
        ka, kb = f"iter69_th20A_{ts}", f"iter69_th20B_{ts}"
        _seed_devkey(db, ka, email=email)
        _seed_devkey(db, kb)
        _seed_session(db, uid, ka, last_seen_offset_sec=-20)
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": "Pass1234",
            "device_key_id": kb, "device_label": "th20-B"}, timeout=15)
        assert r.status_code == 202, f"-20s should be fresh → 202, got {r.status_code}: {r.text[:200]}"

    def test_session_40s_old_returns_200(self, db):
        ts = int(time.time()) + 800
        email = f"test_iter69_th40_{ts}@gmail.com"
        uid = _ensure_user(db, email, "Pass1234")
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})
        ka, kb = f"iter69_th40A_{ts}", f"iter69_th40B_{ts}"
        _seed_devkey(db, ka, email=email)
        _seed_devkey(db, kb)
        _seed_session(db, uid, ka, last_seen_offset_sec=-40)
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": "Pass1234",
            "device_key_id": kb, "device_label": "th40-B"}, timeout=15)
        assert r.status_code == 200, f"-40s should be stale → 200, got {r.status_code}: {r.text[:200]}"

    def test_session_120s_old_returns_200(self, db):
        ts = int(time.time()) + 900
        email = f"test_iter69_th120_{ts}@gmail.com"
        uid = _ensure_user(db, email, "Pass1234")
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})
        ka, kb = f"iter69_th120A_{ts}", f"iter69_th120B_{ts}"
        _seed_devkey(db, ka, email=email)
        _seed_devkey(db, kb)
        _seed_session(db, uid, ka, last_seen_offset_sec=-120)
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": "Pass1234",
            "device_key_id": kb, "device_label": "th120-B"}, timeout=15)
        assert r.status_code == 200, f"-120s should be stale → 200, got {r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# E) Pseudo min 1 char
# ---------------------------------------------------------------------------
class TestPseudoMin1Char:
    def test_pseudo_1_char_accepted(self, db):
        ts = int(time.time()*1000) + 9
        email = f"test_iter69_p1_{ts}@gmail.com"
        db.users.delete_many({"email": email})
        payload = _base_register_payload(email, pseudo="a")
        payload["biometric_kind"] = "iris"
        payload["biometric_iris_hashes"] = [_iris_hash() for _ in range(3)]
        r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r.status_code == 200, f"1-char pseudo should be accepted, got {r.status_code}: {r.text[:200]}"
        db.users.delete_many({"email": email})

    def test_pseudo_empty_returns_400(self, db):
        ts = int(time.time()*1000) + 10
        email = f"test_iter69_pempty_{ts}@gmail.com"
        db.users.delete_many({"email": email})
        payload = _base_register_payload(email, pseudo="")
        payload["biometric_kind"] = "iris"
        payload["biometric_iris_hashes"] = [_iris_hash() for _ in range(3)]
        r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r.status_code == 400, f"empty pseudo must be rejected, got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "pseudo" in detail, detail


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.users.delete_many({"email": {"$regex": "^test_iter69_"}})
    db.users.delete_many({"user_id": {"$regex": "^TEST_iter69_"}})
    db.user_sessions.delete_many({"session_token": {"$regex": "^TEST_iter69_"}})
    db.session_requests.delete_many({"user_id": {"$regex": "^TEST_iter69_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^iter69_"}})
