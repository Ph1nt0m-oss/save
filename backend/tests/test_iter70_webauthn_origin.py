"""iter70 — WebAuthn enroll-begin reads `origin` from request body so the
returned `rp.id` reflects the *public* host the browser uses, not the
internal Kubernetes hostname the ingress rewrites to.

A) POST /webauthn/enroll-begin with body {origin: <public_url>}  → 200 + options.rp.id == host(public_url).
B) POST /webauthn/enroll-begin with body {} → 200 (legacy header-based path).
C) POST /webauthn/enroll-begin with body {origin: 'https://example.com/'} → rp.id == 'example.com'.
D) Persisted challenge document has kind=='signup' and origin matches input.
"""
from __future__ import annotations
import os
from urllib.parse import urlparse

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


class TestIter70EnrollBeginOrigin:
    def test_origin_in_body_sets_rp_id_to_public_host(self, db):
        public_origin = BASE_URL  # e.g. https://no-code-builder-25.preview.emergentagent.com
        expected_host = urlparse(public_origin).hostname
        r = requests.post(
            f"{API}/webauthn/enroll-begin",
            json={"origin": public_origin, "email": "iter70_test@gmail.com"},
            timeout=15,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "options" in body and "options_token" in body, body
        rp = body["options"].get("rp", {})
        assert rp.get("id") == expected_host, f"rp.id={rp.get('id')} ≠ {expected_host}"
        # Persisted doc
        doc = db.webauthn_challenges.find_one(
            {"options_token": body["options_token"]}, {"_id": 0})
        assert doc, "challenge not persisted"
        assert doc.get("kind") == "signup"
        assert doc.get("rp_id") == expected_host
        assert doc.get("origin") == public_origin
        db.webauthn_challenges.delete_many({"options_token": body["options_token"]})

    def test_arbitrary_origin_strips_scheme_and_port(self, db):
        r = requests.post(
            f"{API}/webauthn/enroll-begin",
            json={"origin": "https://example.com:8443"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["options"]["rp"]["id"] == "example.com"
        db.webauthn_challenges.delete_many({"options_token": body["options_token"]})

    def test_empty_body_still_returns_200_legacy_path(self, db):
        r = requests.post(f"{API}/webauthn/enroll-begin", json={}, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "options_token" in body and len(body["options_token"]) >= 32
        # rp.id is whatever the ingress sent; just assert it's a non-empty string
        assert isinstance(body["options"]["rp"].get("id"), str)
        assert len(body["options"]["rp"]["id"]) > 0
        db.webauthn_challenges.delete_many({"options_token": body["options_token"]})


@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.webauthn_challenges.delete_many({"origin": "https://example.com:8443"})
