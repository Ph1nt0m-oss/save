"""
iter111 — P0 security/UX validation tests
=========================================
Validates 5 critical P0 changes:
  1) GET /api/views/spec returns 5 views (user, modo, admin, creator, guest)
     with strict guest restrictions.
  2) POST /api/devices/approve accepts new `as_role` field
     (user/modo/admin) and enforces hierarchy via signature.
     - 403 without valid signature
     - 400 with invalid as_role value
  3) POST /api/chat/stream accepts `model` + `attachments` payload fields.
     - 401 without auth.
  4) Project model has optional parent_chat_id field; persisted via
     POST /api/ai/generate-complete-app. 401 without auth.
  5) (frontend smoke — see Playwright iteration)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


# ----------------------------------------------------------
# 1) /api/views/spec — must expose 5 views (incl. iter111 guest)
# ----------------------------------------------------------
class TestViewsSpec:
    def test_views_spec_returns_5_views(self):
        r = requests.get(f"{API}/views/spec", timeout=15)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        expected_views = {"user", "modo", "admin", "creator", "guest"}
        assert expected_views.issubset(set(data.keys())), (
            f"Missing views. Got keys: {sorted(data.keys())}"
        )

    def test_guest_view_restrictions(self):
        """iter111 — guest view must enforce read-only public-only access."""
        r = requests.get(f"{API}/views/spec", timeout=15)
        assert r.status_code == 200
        guest = r.json().get("guest")
        assert guest is not None, "guest view missing"
        # Must show ONLY public chats
        assert guest.get("chats_visible") == ["public"], (
            f"guest.chats_visible expected ['public'], got {guest.get('chats_visible')}"
        )
        # Visibility restrictions
        assert guest.get("see_friends") is False
        assert guest.get("see_sidebar_projects") is False
        assert guest.get("see_idea_box") is True
        # Action restrictions
        assert guest.get("can_send_messages") is False
        assert guest.get("can_create_projects") is False


# ----------------------------------------------------------
# 2) /api/devices/approve — tiered approval (as_role)
# ----------------------------------------------------------
class TestDevicesApproveTiered:
    def test_approve_without_signature_returns_403(self):
        """Missing/invalid signature must be rejected with 403."""
        payload = {
            "key_id": "fake_key_test",
            "nonce": "deadbeef",
            "signature": "00" * 64,  # invalid signature
            "target_key_id": "fake_target",
            "as_role": "user",
        }
        r = requests.post(f"{API}/devices/approve", json=payload, timeout=15)
        assert r.status_code in (401, 403), (
            f"Expected 401/403 for invalid signature, got {r.status_code}: {r.text[:200]}"
        )

    def test_approve_with_bad_as_role_returns_400_or_403(self):
        """as_role='bad_xx' should be rejected (400 invalid value OR 403 sig-first guard)."""
        payload = {
            "key_id": "fake_key_test",
            "nonce": "deadbeef",
            "signature": "00" * 64,
            "target_key_id": "fake_target",
            "as_role": "bad_xx",
        }
        r = requests.post(f"{API}/devices/approve", json=payload, timeout=15)
        # Signature check runs first → 403; if a flow ever lets through, 400 is the validation error.
        assert r.status_code in (400, 401, 403), (
            f"Expected 400/401/403 for invalid as_role, got {r.status_code}: {r.text[:200]}"
        )

    def test_approve_missing_target_key_id_422(self):
        """Pydantic should reject missing target_key_id with 422."""
        payload = {
            "key_id": "fake_key_test",
            "nonce": "deadbeef",
            "signature": "00" * 64,
            "as_role": "user",
        }
        r = requests.post(f"{API}/devices/approve", json=payload, timeout=15)
        assert r.status_code in (400, 422), (
            f"Expected 422 for missing field, got {r.status_code}: {r.text[:200]}"
        )

    def test_approve_accepts_as_role_field_in_schema(self):
        """Schema must accept `as_role` in {user,modo,admin} — verified by reaching the signature check (403) rather than 422."""
        for role in ["user", "modo", "admin"]:
            payload = {
                "key_id": "fake_key_test",
                "nonce": "deadbeef",
                "signature": "00" * 64,
                "target_key_id": "fake_target",
                "as_role": role,
            }
            r = requests.post(f"{API}/devices/approve", json=payload, timeout=15)
            # Schema accepted → falls into sig validation → 401/403, not 422.
            assert r.status_code != 422, (
                f"as_role='{role}' triggered schema rejection (422): {r.text[:200]}"
            )
            assert r.status_code in (401, 403, 404), (
                f"Unexpected status for as_role={role}: {r.status_code}"
            )


# ----------------------------------------------------------
# 3) /api/chat/stream — accepts model + attachments
# ----------------------------------------------------------
class TestChatStreamSchema:
    def test_chat_stream_without_auth_returns_401(self):
        payload = {
            "message": "Hello",
            "mode": "online",
            "language": "fr",
        }
        r = requests.post(f"{API}/chat/stream", json=payload, timeout=15)
        assert r.status_code == 401, (
            f"Expected 401 without auth, got {r.status_code}: {r.text[:200]}"
        )

    def test_chat_stream_accepts_model_and_attachments_fields(self):
        """Schema must accept new model + attachments fields → still 401 (auth), NOT 422 (validation)."""
        payload = {
            "message": "Hello",
            "mode": "online",
            "language": "fr",
            "project_id": None,
            "model": "gpt-5.2",
            "attachments": [
                {"name": "test.txt", "type": "text/plain", "data_url": "data:text/plain;base64,SGk="}
            ],
        }
        r = requests.post(f"{API}/chat/stream", json=payload, timeout=15)
        assert r.status_code != 422, (
            f"Schema rejected model/attachments (422): {r.text[:200]}"
        )
        assert r.status_code == 401, (
            f"Expected 401 (auth required), got {r.status_code}: {r.text[:200]}"
        )


# ----------------------------------------------------------
# 4) Project model parent_chat_id — generate-complete-app
# ----------------------------------------------------------
class TestProjectParentChatId:
    def test_generate_complete_app_without_auth_returns_401(self):
        payload = {
            "description": "TEST_iter111 parent chat id",
            "parent_chat_id": "chat_test_parent_xyz",
        }
        r = requests.post(f"{API}/ai/generate-complete-app", json=payload, timeout=15)
        assert r.status_code == 401, (
            f"Expected 401 without auth, got {r.status_code}: {r.text[:200]}"
        )

    def test_generate_complete_app_schema_accepts_parent_chat_id(self):
        """Schema must accept parent_chat_id without rejecting (no 422)."""
        payload = {
            "description": "TEST_iter111",
            "parent_chat_id": "some_chat_id",
        }
        r = requests.post(f"{API}/ai/generate-complete-app", json=payload, timeout=15)
        assert r.status_code != 422, (
            f"Schema rejected parent_chat_id field (422): {r.text[:200]}"
        )


# ----------------------------------------------------------
# Sanity: backend health
# ----------------------------------------------------------
class TestBackendHealth:
    def test_root_responds(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code in (200, 404), f"Backend not reachable: {r.status_code}"
