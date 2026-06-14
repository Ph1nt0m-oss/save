"""iter120 — Validates extraction of heavy auth routes into 4 new route files.

Smoke tests that hit the extracted endpoints to ensure they're properly mounted
and respond as designed (validation, neutral messages, idempotency).
"""
from __future__ import annotations

import os
import uuid
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = os.environ.get("REACT_APP_BACKEND_URL_PUBLIC") or "http://localhost:8001"
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"


def _email():
    return f"iter120-{uuid.uuid4().hex[:8]}@codeforge.test"


class TestAuthSignupVerifyRoutes:
    """auth_signup_verify_routes.py — magic-link, resend, verify-email, verification-status."""

    def test_magic_link_unknown_email_neutral_200(self):
        r = requests.post(f"{API}/auth/magic-link", json={"email": _email()}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "Si un compte existe" in body.get("message", "")
        # Neutral: no token leaked
        assert "verification_token" not in body

    def test_magic_link_bad_email_400(self):
        r = requests.post(f"{API}/auth/magic-link", json={"email": "not-an-email"}, timeout=10)
        assert r.status_code == 400, r.text
        assert "invalide" in r.json().get("detail", "").lower()

    def test_resend_verification_unknown_email_neutral_200(self):
        r = requests.post(f"{API}/auth/resend-verification", json={"email": _email()}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("email_sent") is False

    def test_resend_verification_bad_email_400(self):
        r = requests.post(f"{API}/auth/resend-verification", json={"email": "bad"}, timeout=10)
        assert r.status_code == 400

    def test_verify_email_missing_token_400(self):
        r = requests.get(f"{API}/auth/verify-email", params={"token": ""}, timeout=10)
        assert r.status_code == 400

    def test_verify_email_unknown_token_400(self):
        r = requests.get(f"{API}/auth/verify-email", params={"token": "totally-fake-token"}, timeout=10)
        assert r.status_code == 400
        assert "invalide" in r.json().get("detail", "").lower()

    def test_verification_status_unknown_token_returns_expired(self):
        r = requests.get(f"{API}/auth/verification-status", params={"token": "fake"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "expired"


class TestAuthPwResetSessionRoutes:
    """auth_pwreset_session_routes.py — forgot/confirm/reset password + session-request."""

    def test_forgot_password_short_password_400(self):
        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": _email(), "password": "abc"},
            timeout=10,
        )
        assert r.status_code == 400
        assert "6 caractères" in r.json().get("detail", "")

    def test_forgot_password_bad_email_400(self):
        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": "bad", "password": "abc123"},
            timeout=10,
        )
        assert r.status_code == 400

    def test_forgot_password_unknown_email_neutral_200(self):
        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": _email(), "password": "abc123"},
            timeout=10,
        )
        assert r.status_code == 200
        assert "Si un compte existe" in r.json().get("message", "")

    def test_reset_password_missing_token_400(self):
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": "", "password": "newpass123"},
            timeout=10,
        )
        assert r.status_code == 400

    def test_reset_password_short_password_400(self):
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": "fake-token", "password": "abc"},
            timeout=10,
        )
        assert r.status_code == 400

    def test_reset_password_unknown_token_400(self):
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": "fake-token-xyz", "password": "abc123"},
            timeout=10,
        )
        assert r.status_code == 400

    def test_confirm_password_reset_no_token_html_error(self):
        r = requests.get(f"{API}/auth/confirm-password-reset", params={"token": ""}, timeout=10)
        # Endpoint returns HTML page, not JSON
        assert r.status_code == 200
        assert "Lien invalide" in r.text

    def test_confirm_password_reset_fake_token_html_error(self):
        r = requests.get(
            f"{API}/auth/confirm-password-reset", params={"token": "fake-xyz"}, timeout=10
        )
        assert r.status_code == 200
        assert "Lien invalide" in r.text or "invalide" in r.text.lower()

    def test_session_request_status_unknown_id_expired(self):
        r = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": "fake-request-id"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("status") == "expired"

    def test_session_pending_unauthenticated_401(self):
        r = requests.get(f"{API}/auth/session-pending", timeout=10)
        assert r.status_code == 401

    def test_session_decide_invalid_decision_400(self):
        # Send invalid decision — should fail validation BEFORE auth check
        # Actually the order in the route is: validate first, then auth.
        r = requests.post(
            f"{API}/auth/session-decide",
            json={"request_id": "x", "decision": "maybe"},
            timeout=10,
        )
        assert r.status_code == 400, r.text


class TestAuthAccountRoutes:
    """auth_account_routes.py — change-password/email, delete-me, export."""

    def test_change_password_unauthenticated_401(self):
        r = requests.post(
            f"{API}/auth/change-password",
            json={"current_password": "x", "new_password": "newpass123"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_change_email_unauthenticated_401(self):
        r = requests.post(
            f"{API}/auth/change-email",
            json={"new_email": "new@x.com", "current_password": "x"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_delete_me_unauthenticated_401(self):
        r = requests.delete(
            f"{API}/auth/me",
            json={"current_password": "x"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_export_unauthenticated_401(self):
        r = requests.get(f"{API}/auth/export", timeout=10)
        assert r.status_code == 401


class TestSmsAuthRoutes:
    """sms_auth_routes.py — sms/send + sms/verify."""

    def test_sms_send_demo_mode_returns_code(self):
        # Without Twilio configured, /sms/send returns the code in DEMO mode
        r = requests.post(
            f"{API}/auth/sms/send",
            json={"phone_number": "+33600000000"},
            timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("sms_sent") is False
        assert "code" in body  # DEMO mode echoes code back
        assert len(body["code"]) == 6

    def test_sms_verify_invalid_code_401(self):
        r = requests.post(
            f"{API}/auth/sms/verify",
            json={"phone_number": "+33600000001", "code": "999999"},
            timeout=10,
        )
        assert r.status_code == 401
        assert "invalide" in r.json().get("detail", "").lower()

    def test_sms_verify_send_then_verify_creates_session(self):
        phone = f"+3360000{uuid.uuid4().int % 10000:04d}"
        # Step 1: request a code (returned in demo mode)
        r1 = requests.post(f"{API}/auth/sms/send", json={"phone_number": phone}, timeout=10)
        assert r1.status_code == 200
        code = r1.json().get("code")
        assert code

        # Step 2: verify with that code → user + session created
        r2 = requests.post(
            f"{API}/auth/sms/verify",
            json={"phone_number": phone, "code": code},
            timeout=10,
        )
        assert r2.status_code == 200, r2.text
        u = r2.json()
        assert u.get("phone_number") == phone
        assert u.get("user_id", "").startswith("user_")


class TestRouteCount:
    """Ensures all 16 extracted routes are mounted via OpenAPI inspection."""

    def test_all_extracted_routes_are_mounted(self):
        # OpenAPI lives at root (not under /api prefix)
        root = API.rsplit("/api", 1)[0]
        r = requests.get(f"{root}/openapi.json", timeout=10)
        assert r.status_code == 200, r.text
        paths = set(r.json().get("paths", {}).keys())
        expected = {
            # signup_verify
            "/api/auth/magic-link",
            "/api/auth/resend-verification",
            "/api/auth/verify-email",
            "/api/auth/verification-status",
            # pwreset_session
            "/api/auth/forgot-password",
            "/api/auth/confirm-password-reset",
            "/api/auth/reset-password",
            "/api/auth/session-request-status",
            "/api/auth/session-pending",
            "/api/auth/session-decide",
            # account
            "/api/auth/change-password",
            "/api/auth/change-email",
            "/api/auth/me",  # GET + DELETE both exist
            "/api/auth/export",
            # sms
            "/api/auth/sms/send",
            "/api/auth/sms/verify",
        }
        missing = expected - paths
        assert not missing, f"Missing routes: {missing}"
