"""
iter_30 — Forgot-password new "set then confirm" flow tests
Tests POST /api/auth/forgot-password + GET /api/auth/confirm-password-reset
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
EMAIL = "test_dash_1777658375@gmail.com"
OLD_PASSWORD = "Pass1234"
NEW_PASSWORD = "NewPass456!"

# Module-level state to share the reset token across test functions (pytest cache
# is disabled in some environments; this is simpler and more reliable).
STATE = {"token": None, "email_sent": None}


def _fetch_latest_token_from_mongo():
    """RESEND is live in this env, so forgot-password does NOT return `confirm_link`.
    Fall back to reading the token directly from the local mongo the backend uses.
    This is test-only and scoped to the deployed test user.
    """
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        c = MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
        col = c[db_name]["password_reset_tokens"]
        doc = col.find_one({"email": EMAIL, "consumed_at": None}, sort=[("created_at", -1)])
        return doc.get("token") if doc else None
    except Exception as e:
        print(f"[mongo fetch error] {e}")
        return None


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(api, password):
    return api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": password},
    )


# --- Regression: login still works with current password ---
def test_00_login_with_original_password(api):
    r = _login(api, OLD_PASSWORD)
    assert r.status_code == 200, f"Baseline login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    # Login returns user profile dict (email/created_at/…) — session is in httpOnly cookie.
    assert data.get("email") == EMAIL


# --- forgot-password: too-short password rejected ---
def test_01_forgot_password_short_rejected(api):
    r = api.post(
        f"{BASE_URL}/api/auth/forgot-password",
        json={"email": EMAIL, "password": "abc", "frontend_url": BASE_URL},
    )
    assert r.status_code == 400, f"Expected 400 for short password, got {r.status_code}: {r.text[:200]}"
    detail = r.json().get("detail", "")
    assert "6" in detail or "caractères" in detail.lower(), f"Unexpected detail: {detail}"


# --- forgot-password: happy path returns neutral message + confirm info ---
def test_02_forgot_password_happy(api):
    r = api.post(
        f"{BASE_URL}/api/auth/forgot-password",
        json={"email": EMAIL, "password": NEW_PASSWORD, "frontend_url": BASE_URL},
    )
    assert r.status_code == 200, f"forgot-password failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "message" in data
    # Either email_sent True, or in demo mode confirm_link is returned
    assert ("email_sent" in data) or ("confirm_link" in data)
    # Try to extract token from confirm_link OR make a request to the preview API to get the
    # token from the mongo collection indirectly. Most reliable: demo mode → confirm_link.
    token = None
    link = data.get("confirm_link")
    if link:
        m = re.search(r"token=([A-Za-z0-9_\-]+)", link)
        if m:
            token = m.group(1)
    if not token:
        # Live email mode: read token directly from mongo
        token = _fetch_latest_token_from_mongo()
    assert token, "No token could be obtained (neither confirm_link nor mongo)"
    STATE["token"] = token
    STATE["email_sent"] = bool(data.get("email_sent"))


# --- confirm-password-reset: invalid token returns friendly HTML ---
def test_03_confirm_invalid_token(api):
    r = api.get(f"{BASE_URL}/api/auth/confirm-password-reset?token=invalidtoken_xyz_123")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "Lien invalide" in r.text


# --- confirm-password-reset: valid token applies password and shows success ---
def test_04_confirm_valid_token_applies_password(api):
    token = STATE["token"]
    if not token:
        pytest.skip("No token from demo-mode response; cannot exercise the GET without real email.")
    r = api.get(f"{BASE_URL}/api/auth/confirm-password-reset?token={token}")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    # Success page content
    assert "Mot de passe mis à jour" in r.text
    # auto-redirect meta
    assert "meta http-equiv='refresh'" in r.text or 'meta http-equiv="refresh"' in r.text
    assert "/login" in r.text


# --- After confirm: new password works and old password rejected ---
def test_05_login_with_new_password(api):
    token = STATE["token"]
    if not token:
        pytest.skip("Skipped: no token available (real email mode).")
    r = _login(api, NEW_PASSWORD)
    assert r.status_code == 200, f"Login with new password failed: {r.status_code} {r.text[:300]}"


def test_06_old_password_rejected(api):
    token = STATE["token"]
    if not token:
        pytest.skip("Skipped: no token available (real email mode).")
    r = _login(api, OLD_PASSWORD)
    assert r.status_code in (401, 403), f"Old password should not log in anymore, got {r.status_code}"


# --- Reused token returns 'Lien déjà utilisé' ---
def test_07_reused_token(api):
    token = STATE["token"]
    if not token:
        pytest.skip("Skipped: no token available (real email mode).")
    r = api.get(f"{BASE_URL}/api/auth/confirm-password-reset?token={token}")
    assert r.status_code == 200
    assert "Lien déjà utilisé" in r.text


# --- Restore to original password for the next agent / future tests ---
def test_08_restore_original_password(api):
    token = STATE["token"]
    if not token:
        pytest.skip("Skipped: cannot restore (no demo mode).")
    # Step 1: POST forgot-password with original password
    r = api.post(
        f"{BASE_URL}/api/auth/forgot-password",
        json={"email": EMAIL, "password": OLD_PASSWORD, "frontend_url": BASE_URL},
    )
    assert r.status_code == 200, f"Restore forgot-password failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    link = data.get("confirm_link")
    t2 = None
    if link:
        m = re.search(r"token=([A-Za-z0-9_\-]+)", link)
        if m:
            t2 = m.group(1)
    if not t2:
        t2 = _fetch_latest_token_from_mongo()
    assert t2, "No restore token available"
    r2 = api.get(f"{BASE_URL}/api/auth/confirm-password-reset?token={t2}")
    assert r2.status_code == 200
    assert "Mot de passe mis à jour" in r2.text
    # Verify original password works again
    r3 = _login(api, OLD_PASSWORD)
    assert r3.status_code == 200, f"Post-restore login failed: {r3.status_code}"
