"""iter71 — POST /api/auth/theft-iris-verify stub endpoint.

Coverage:
  (a) empty token         → 400
  (b) token + <3 hashes   → 400
  (c) valid token + 3 OK  → 200 {success:true} AND a doc is persisted in theft_iris_attempts
  (d) hash too short      → 400
  (e) (covered by c)      → doc inserted in theft_iris_attempts collection
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone

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


@pytest.fixture()
def seeded_token(db):
    """Insert a theft_email_tokens row mimicking a freshly-clicked email link."""
    token = f"TEST_iter71_{uuid.uuid4().hex}"
    email = f"TEST_iter71_{uuid.uuid4().hex[:8]}@example.com"
    db.theft_email_tokens.insert_one({
        "token": token,
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "used": False,
    })
    yield {"token": token, "email": email}
    db.theft_email_tokens.delete_many({"token": token})
    db.theft_iris_attempts.delete_many({"token": token})


class TestIter71TheftIrisVerify:
    # (a) sans token → 400
    def test_empty_token_returns_400(self):
        r = requests.post(
            f"{API}/auth/theft-iris-verify",
            json={"token": "", "hashes": ["a" * 30, "b" * 30, "c" * 30]},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    # (b) token + <3 hashes → 400
    def test_too_few_hashes_returns_400(self, seeded_token):
        r = requests.post(
            f"{API}/auth/theft-iris-verify",
            json={"token": seeded_token["token"], "hashes": ["a" * 30, "b" * 30]},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    # (d) hash too short → 400
    def test_hash_too_short_returns_400(self, seeded_token):
        r = requests.post(
            f"{API}/auth/theft-iris-verify",
            json={"token": seeded_token["token"], "hashes": ["short", "b" * 30, "c" * 30]},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    # (d-bis) hash too long → 400
    def test_hash_too_long_returns_400(self, seeded_token):
        r = requests.post(
            f"{API}/auth/theft-iris-verify",
            json={"token": seeded_token["token"], "hashes": ["x" * 200, "b" * 30, "c" * 30]},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    # (c) valid token + 3 OK hashes → 200 success:true
    # (e) theft_iris_attempts doc inserted
    def test_valid_payload_returns_200_and_persists(self, seeded_token, db):
        hashes = ["a" * 30, "b" * 40, "c" * 50]
        r = requests.post(
            f"{API}/auth/theft-iris-verify",
            json={"token": seeded_token["token"], "hashes": hashes},
            timeout=15,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body.get("success") is True, body

        # (e) verify the doc was persisted
        doc = db.theft_iris_attempts.find_one(
            {"token": seeded_token["token"]}, {"_id": 0}
        )
        assert doc is not None, "theft_iris_attempts doc was not inserted"
        assert doc.get("email") == seeded_token["email"]
        assert doc.get("hashes") == hashes
        assert doc.get("verified") is False
        assert "created_at" in doc

    # Unknown token (well-formed payload but token not in DB) → 404
    def test_unknown_token_returns_404(self):
        r = requests.post(
            f"{API}/auth/theft-iris-verify",
            json={"token": f"TEST_unknown_{uuid.uuid4().hex}", "hashes": ["a" * 30, "b" * 30, "c" * 30]},
            timeout=15,
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"
