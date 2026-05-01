"""Iter 28 — Voice transcription endpoint smoke tests.

Scope: only status + body shape assertions. We do NOT test a real whisper
round-trip (no audio fixture in CI).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
TEST_EMAIL = "test_dash_1777658375@gmail.com"
TEST_PASS = "Pass1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


# --- voice/transcribe ---
def test_voice_transcribe_unauth_returns_401():
    files = {"file": ("t.webm", b"\x00\x01\x02\x03", "audio/webm")}
    r = requests.post(f"{BASE_URL}/api/voice/transcribe", files=files, timeout=30)
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


def test_voice_transcribe_auth_but_too_short_returns_400(token):
    files = {"file": ("t.webm", b"\x00\x01\x02\x03", "audio/webm")}
    r = requests.post(f"{BASE_URL}/api/voice/transcribe",
                      headers={"Authorization": f"Bearer {token}"},
                      files=files, timeout=30)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
    body = r.json()
    assert "detail" in body
    assert "court" in body["detail"].lower() or "short" in body["detail"].lower() or "vide" in body["detail"].lower()


def test_voice_transcribe_missing_file_returns_422(token):
    r = requests.post(f"{BASE_URL}/api/voice/transcribe",
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=30)
    assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"


# --- regression: auth/login still returns session_token ---
def test_auth_login_regression():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASS}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("email") == TEST_EMAIL
    assert data.get("verified") is True
    assert isinstance(data.get("session_token"), str) and len(data["session_token"]) > 10


def test_auth_me_with_token(token):
    r = requests.get(f"{BASE_URL}/api/auth/me",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("email") == TEST_EMAIL
