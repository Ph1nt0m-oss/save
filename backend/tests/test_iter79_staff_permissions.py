"""iter79 — Staff permissions gating + UX backend tests.

Coverage:
  - GET /api/announcements/list -> 200, list
  - GET /api/polls/list -> 200, list
  - GET /api/system/scheduled-kicks -> 200
  - POST /api/ai/wizard-suggest kind=name -> fallback returns 3 varied names
    (at least one > 6 chars)
  - Signature-gated endpoints reject unsigned payloads with 403/404 :
      * /accounts/mute, /accounts/unmute, /accounts/ban, /accounts/unban,
        /accounts/exclude, /accounts/set-staff-kind
      * /devices/block, /devices/unblock, /devices/approve
  - /chat/export-docx/{project_id} without auth -> 401/403
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = BASE_URL + "/api"

UNSIGNED = {
    "key_id": "TEST_iter79_fake_key",
    "nonce": "TEST_iter79_fake_nonce",
    "signature": "TEST_iter79_fake_signature",
    "target_key_id": "TEST_iter79_fake_target",
}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Public GET endpoints
# ---------------------------------------------------------------------------
class TestPublicGet:
    def test_announcements_list_200(self, client):
        r = client.get(f"{API}/announcements/list", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Some endpoints wrap, some return raw list — accept both.
        if isinstance(data, dict):
            arr = data.get("items") or data.get("announcements") or data.get("list") or []
        else:
            arr = data
        assert isinstance(arr, list)

    def test_polls_list_200(self, client):
        r = client.get(f"{API}/polls/list", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        if isinstance(data, dict):
            arr = data.get("items") or data.get("polls") or data.get("list") or []
        else:
            arr = data
        assert isinstance(arr, list)

    def test_system_scheduled_kicks_200(self, client):
        r = client.get(f"{API}/system/scheduled-kicks", timeout=15)
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Wizard pseudo variety (iter79)
# ---------------------------------------------------------------------------
class TestWizardSuggest:
    def test_wizard_name_requires_auth(self, client):
        """Unauthenticated call must be rejected (401/403)."""
        payload = {"kind": "name", "platforms": ["web"], "app_type": "todo", "seed": 0.42}
        r = client.post(f"{API}/ai/wizard-suggest", json=payload, timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_wizard_fallback_pool_variety(self):
        """iter79 — fallback pool contains many varied (length & style) pseudos.
        We assert the SOURCE pool (since the endpoint is auth-gated and the LLM
        path is non-deterministic). Rules from the iter79 spec:
          - pool >= 50 entries
          - lengths between 3 and 12 characters
          - at least one name strictly > 6 chars
          - a random sample of 3 yields >=1 name > 6 chars in >=95% of seeds.
        """
        import sys
        sys.path.insert(0, "/app/backend")
        from server import _fallback_name_pool
        import random as _rnd

        pool = _fallback_name_pool()
        assert isinstance(pool, list)
        assert len(pool) >= 50, f"pool too small: {len(pool)}"
        for n in pool:
            assert isinstance(n, str), n
            assert 3 <= len(n) <= 12, f"bad length: {n} ({len(n)})"
        long_count = sum(1 for n in pool if len(n) > 6)
        assert long_count >= 10, f"need 10+ long names, got {long_count}"

        # Random-sample 200 seeds; >=95% should include at least one >6-char name.
        hits = 0
        for seed in range(200):
            _rnd.seed(seed)
            sample = _rnd.sample(pool, 3)
            if any(len(n) > 6 for n in sample):
                hits += 1
        assert hits >= 190, f"variety rule failed: {hits}/200 samples had a >6-char name"


# ---------------------------------------------------------------------------
# Signature-gated endpoints — unsigned payloads must be rejected (403 or 404)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path,payload",
    [
        ("/accounts/mute", UNSIGNED),
        ("/accounts/unmute", UNSIGNED),
        ("/accounts/ban", UNSIGNED),
        ("/accounts/unban", UNSIGNED),
        ("/accounts/exclude", {**UNSIGNED, "duration_minutes": 10, "reason": "test"}),
        ("/accounts/set-staff-kind", {**UNSIGNED, "staff_kind": "modo"}),
        ("/devices/block", UNSIGNED),
        ("/devices/unblock", UNSIGNED),
        ("/devices/approve", UNSIGNED),
    ],
)
def test_staff_gated_rejects_unsigned(client, path, payload):
    r = client.post(f"{API}{path}", json=payload, timeout=15)
    assert r.status_code in (403, 404), f"{path} -> {r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# /chat/export-docx without auth → 401 or 403
# ---------------------------------------------------------------------------
class TestExportDocx:
    def test_export_docx_without_auth(self):
        # Use a fresh session to avoid any prior cookie pollution.
        s = requests.Session()
        try:
            r = s.get(f"{API}/chat/export-docx/TEST_iter79_nope", timeout=15)
            assert r.status_code in (401, 403), f"got {r.status_code} {r.text[:200]}"
        finally:
            s.close()


# ---------------------------------------------------------------------------
# Backend healthy
# ---------------------------------------------------------------------------
def test_backend_root_healthy(client):
    # /api/ exists in the FastAPI router prefix — at minimum, announcements/list
    # already proved the backend is up. Ping any known light endpoint.
    r = client.get(f"{API}/system/scheduled-kicks", timeout=10)
    assert r.status_code == 200
