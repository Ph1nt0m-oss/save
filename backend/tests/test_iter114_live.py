"""iter114 — Live backend tests: views/spec, devices/approve, chat/stream,
private/changelog, accounts/visit, regression of login (test_dash user)."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    "https://no-code-builder-25.preview.emergentagent.com"

TEST_EMAIL = "test_dash_1777658375@gmail.com"
TEST_PWD = "Pass1234"


# ---------------------------------------------------- /api/views/spec returns 5
def test_views_spec_has_five_views():
    r = requests.get(f"{BASE_URL}/api/views/spec", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # Response is a flat object keyed by view name
    for expected in ("user", "modo", "admin", "creator", "guest"):
        assert expected in data, f"missing {expected} in {list(data.keys())}"


# ---------------------------------------------------- /api/private/changelog 403 without sig
def test_private_changelog_requires_creator_signature():
    # Empty body → 422 (missing key_id/nonce/signature fields)
    r = requests.post(f"{BASE_URL}/api/private/changelog", json={}, timeout=15)
    assert r.status_code in (401, 403, 422), r.status_code
    # With fake signature → 403 (creator guard)
    r2 = requests.post(
        f"{BASE_URL}/api/private/changelog",
        json={"key_id": "x", "nonce": "y", "signature": "z"},
        timeout=15,
    )
    assert r2.status_code == 403, r2.status_code


# ---------------------------------------------------- /api/devices/approve gated
def test_devices_approve_requires_signature():
    r = requests.post(
        f"{BASE_URL}/api/devices/approve",
        json={"device_id": "fake", "tier": "creator"},
        timeout=15,
    )
    assert r.status_code in (401, 403, 422), r.status_code


# ---------------------------------------------------- /api/accounts/visit gated
def test_accounts_visit_requires_signature():
    r = requests.post(
        f"{BASE_URL}/api/accounts/visit",
        json={"user_id": "user_x"},
        timeout=15,
    )
    assert r.status_code in (401, 403, 422), r.status_code


# ---------------------------------------------------- /api/chat/stream gated
def test_chat_stream_endpoint_exists():
    # GET on /api/chat/stream (SSE) — without auth should NOT be 404
    r = requests.get(f"{BASE_URL}/api/chat/stream", timeout=10)
    assert r.status_code != 404, "chat/stream missing"


# ---------------------------------------------------- regression : login works
def test_login_test_dash_user_ok():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PWD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    body = r.json()
    # iter112 confirms key is 'session_token'
    assert body.get("session_token") or body.get("token"), body
