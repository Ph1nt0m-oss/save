"""iter134 — Live tests: PUT /system/who-can-visit + GET /system/site-mode + regressions."""
import os
import requests

BASE_URL = "https://no-code-builder-25.preview.emergentagent.com"


class TestSiteModeGET:
    def test_site_mode_returns_visit_modes_and_view_forcing(self):
        r = requests.get(f"{BASE_URL}/api/system/site-mode", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # New fields
        assert "visit_modes" in data, f"visit_modes missing: {data}"
        assert "view_forcing" in data, f"view_forcing missing: {data}"
        # Types
        assert isinstance(data["visit_modes"], list)
        assert len(data["visit_modes"]) >= 1
        assert data["view_forcing"] in ("free", "forced"), f"invalid view_forcing: {data['view_forcing']}"

    def test_site_mode_regression_mode_and_modes(self):
        r = requests.get(f"{BASE_URL}/api/system/site-mode", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # Legacy fields still present
        assert "mode" in data
        assert "modes" in data
        assert isinstance(data["modes"], list)
        # No legacy garbage
        for m in data["modes"]:
            assert m not in ("none", "all"), f"legacy mode leaked: {m}"


class TestWhoCanVisitGating:
    def test_put_requires_creator_signature(self):
        # No signature -> should be 401/403/422 (Pydantic may 422 on missing body)
        r = requests.put(
            f"{BASE_URL}/api/system/who-can-visit",
            json={"visit_modes": ["public"], "view_forcing": "free"},
            timeout=15,
        )
        assert r.status_code in (401, 403, 422), f"unexpected: {r.status_code} {r.text[:200]}"

    def test_put_with_fake_signature_rejected(self):
        # Body includes key_id + nonce + signature (Pydantic requires them)
        # but signature is invalid → _require_creator_signature must reject.
        r = requests.put(
            f"{BASE_URL}/api/system/who-can-visit",
            json={
                "visit_modes": ["public"],
                "view_forcing": "free",
                "key_id": "fake_key",
                "nonce": "fake_nonce_abcdef",
                "signature": "fake_signature_deadbeef",
            },
            timeout=15,
        )
        assert r.status_code in (401, 403), f"fake sig accepted: {r.status_code} {r.text[:200]}"


class TestRegressionEndpoints:
    """iter131-133 endpoints still present."""

    def test_workspace_list_declared(self):
        # /workspace/list/{project_id} — with fake id, should 401/403/404 for that id but NOT 405
        r = requests.get(f"{BASE_URL}/api/workspace/list/nonexistent_project_id", timeout=15)
        assert r.status_code != 405, f"workspace/list/{{id}} method mismatch"
        # Must be a valid route response (not html 404 from ingress)
        assert r.headers.get("content-type", "").startswith("application/json") or r.status_code in (401, 403, 404), \
            f"workspace/list route not reachable: {r.status_code}"

    def test_private_integrations_status_declared(self):
        r = requests.get(f"{BASE_URL}/api/private/integrations/status", timeout=15)
        assert r.status_code != 404, f"private/integrations/status missing (404)"

    def test_staff_decisions_list_declared(self):
        r = requests.get(f"{BASE_URL}/api/staff-decisions/list", timeout=15)
        assert r.status_code != 404, f"staff-decisions/list missing (404)"

    def test_exports_pending_declared(self):
        r = requests.post(f"{BASE_URL}/api/exports/pending", json={}, timeout=15)
        assert r.status_code != 404, f"exports/pending missing (404)"


class TestFrontendLoads:
    def test_login_page_reachable(self):
        r = requests.get(f"{BASE_URL}/login", timeout=15)
        # Might return 200 (HTML) or redirect
        assert r.status_code in (200, 301, 302, 304), f"login page down: {r.status_code}"
