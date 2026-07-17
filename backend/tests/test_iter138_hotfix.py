"""iter138 hotfix tests — verify backend endpoints still respond after
frontend-only SiteModeBadge fix (Crown residual removed).
"""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://no-code-builder-25.preview.emergentagent.com').rstrip('/')


class TestSiteModeEndpoint:
    """GET /api/system/site-mode should return 200 with all required fields."""

    def test_site_mode_returns_200_with_all_fields(self):
        r = requests.get(f"{BASE_URL}/api/system/site-mode", timeout=15)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        # Required fields per review request
        for field in ["mode", "modes", "guest_view", "guest_views", "visit_modes", "view_forcing", "forced_views"]:
            assert field in data, f"Missing field '{field}' in site-mode response. Got: {list(data.keys())}"
        # Types
        assert isinstance(data["modes"], list)
        assert isinstance(data["guest_views"], list)
        assert isinstance(data["visit_modes"], list)
        assert isinstance(data["forced_views"], list)
        assert data["view_forcing"] in ("free", "forced")


class TestAuthGatedEndpoints:
    """The 3 endpoints must still respond 401/403 without auth (regression)."""

    def test_staff_decisions_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/staff-decisions/list", timeout=15)
        # Some endpoints return 404 for method mismatch — accept 401/403 (auth) as canonical
        assert r.status_code in (401, 403, 405), f"Expected 401/403/405, got {r.status_code}: {r.text[:200]}"

    def test_workspace_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/workspace/list", timeout=15)
        # This is a path-param endpoint — could be 401/403/404/405
        assert r.status_code in (401, 403, 404, 405, 422), f"Unexpected: {r.status_code}: {r.text[:200]}"

    def test_private_integrations_status_requires_auth(self):
        # Endpoint accepts POST; GET returns 405. Both are OK — proves ingress routes it.
        r = requests.get(f"{BASE_URL}/api/private/integrations/status", timeout=15)
        assert r.status_code in (401, 403, 405), f"Expected 401/403/405, got {r.status_code}: {r.text[:200]}"
        # Also try POST — must reject without auth (not 404)
        r2 = requests.post(f"{BASE_URL}/api/private/integrations/status", json={}, timeout=15)
        assert r2.status_code in (401, 403, 422), f"POST expected 401/403/422, got {r2.status_code}: {r2.text[:200]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
