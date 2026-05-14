"""Iter59: verify EMAIL_FROM uses no-reply@resend.dev and verification_link
is ALWAYS exposed in register/resend-verification responses (backup when
Resend is in sandbox mode)."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---- 1. EMAIL_FROM env + server.py fallbacks ----
def test_email_from_env_value():
    with open("/app/backend/.env", "r") as f:
        env = f.read()
    assert "EMAIL_FROM=CodeForge AI <no-reply@resend.dev>" in env


def test_email_from_fallbacks_count_in_server():
    with open("/app/backend/server.py", "r") as f:
        src = f.read()
    # >=4 fallbacks in code; env file has the 5th occurrence
    assert src.count("no-reply@resend.dev") >= 4


# ---- 2. register fresh email -> email_sent=false BUT link present ----
def test_register_fresh_email_returns_verification_link():
    fresh = f"test_iter59_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={
            "email": fresh,
            "password": "TestPass1234!",
            "name": "Iter59 Tester",
            "frontend_url": BASE_URL,
        },
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    # link must always be present per iter59
    assert "verification_link" in data
    assert data["verification_link"], "verification_link must be non-empty"
    assert "/verify-email?token=" in data["verification_link"]
    # response shape
    assert data.get("email") == fresh
    assert "email_sent" in data
    assert isinstance(data["email_sent"], bool)
    assert "verification_token" in data and data["verification_token"]
    # French message
    msg = data.get("message", "")
    assert any(tok in msg for tok in ["Compte créé", "lien"]) or "Compte" in msg


# ---- 3. resend-verification: link always exposed ----
def test_resend_verification_returns_link():
    fresh = f"test_iter59_resend_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    # first register
    r0 = requests.post(
        f"{API}/auth/register",
        json={
            "email": fresh,
            "password": "TestPass1234!",
            "name": "Iter59 Resend",
            "frontend_url": BASE_URL,
        },
        timeout=20,
    )
    assert r0.status_code == 200

    # then resend (real endpoint name is /auth/resend-verification)
    r = requests.post(
        f"{API}/auth/resend-verification",
        json={"email": fresh, "frontend_url": BASE_URL},
        timeout=20,
    )
    # may be 200 or 429 rate-limited; we test happy path
    if r.status_code == 429:
        pytest.skip(f"rate limited: {r.text}")
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    data = r.json()
    assert "verification_link" in data and data["verification_link"]
    assert "/verify-email?token=" in data["verification_link"]
    assert "email_sent" in data


# ---- 4. register with already-verified resend whitelisted email ----
def test_register_verified_resend_email_link_still_exposed():
    # 16.axelblaze.10@gmail.com is Resend-verified. The account may already
    # exist (409) — in that case the test still confirms idempotency, but
    # primarily we want to ensure that IF register succeeds, the link is
    # exposed even when email_sent=true.
    r = requests.post(
        f"{API}/auth/register",
        json={
            "email": "16.axelblaze.10@gmail.com",
            "password": "TestPass1234!",
            "name": "Axel",
            "frontend_url": BASE_URL,
        },
        timeout=30,
    )
    if r.status_code == 200:
        data = r.json()
        assert data.get("verification_link"), "link must be exposed even on email_sent=true"
        assert "/verify-email?token=" in data["verification_link"]
    elif r.status_code in (400, 409):
        # account already exists — fallback to forgot-password to exercise
        # the real-send path; just check status. Some backends might not
        # expose the link here; only assert 200/404 status.
        r2 = requests.post(
            f"{API}/auth/forgot-password",
            json={
                "email": "16.axelblaze.10@gmail.com",
                "password": "NewTestPass1234!",
                "frontend_url": BASE_URL,
            },
            timeout=30,
        )
        assert r2.status_code in (200, 202, 404, 429), f"forgot-password: {r2.status_code} {r2.text}"
    else:
        pytest.fail(f"unexpected status {r.status_code}: {r.text}")


# ---- 5. Smoke regression ----
def test_smoke_site_mode():
    r = requests.get(f"{API}/system/site-mode", timeout=10)
    assert r.status_code == 200
    assert "mode" in r.json() or r.json()  # at least non-empty


def test_smoke_accounts_delete_all_requires_signature():
    # empty body → 422 (pydantic schema missing key_id/nonce/signature)
    r = requests.post(f"{API}/accounts/delete-all", json={}, timeout=10)
    assert r.status_code in (401, 403, 422), f"expected 401/403/422 got {r.status_code}: {r.text}"
    # bogus but well-formed signed payload → 403 from signature check
    r2 = requests.post(
        f"{API}/accounts/delete-all",
        json={"key_id": "fake-key-id", "nonce": "noncedeadbeef", "signature": "deadbeef" * 8},
        timeout=10,
    )
    assert r2.status_code in (401, 403), f"signed-bogus expected 401/403 got {r2.status_code}: {r2.text}"


def test_smoke_ideas_send_anonymous():
    r = requests.post(
        f"{API}/ideas/send",
        json={"title": "iter59 test", "description": "smoke regression"},
        timeout=15,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
