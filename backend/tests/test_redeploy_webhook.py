"""
Auto-deploy webhook regression tests.
Validates the /api/admin/redeploy endpoint behavior:
- Auth gating (401 without secret, 401 with wrong secret)
- 200 with correct secret + .env preservation
- /api/health remains healthy after redeploy
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://no-code-builder-25.preview.emergentagent.com",
).rstrip("/")
DEPLOY_URL = f"{BASE_URL}/api/admin/redeploy"
HEALTH_URL = f"{BASE_URL}/api/health"


def _read_deploy_secret():
    """Read DEPLOY_SECRET from backend/.env (skip test if absent)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            if line.startswith("DEPLOY_SECRET="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    return None


class TestRedeployAuth:
    def test_no_secret_header_returns_401(self):
        r = requests.post(DEPLOY_URL, timeout=10)
        assert r.status_code == 401, r.text

    def test_wrong_secret_returns_401(self):
        r = requests.post(
            DEPLOY_URL,
            headers={"X-Deploy-Secret": "definitely-not-the-secret"},
            timeout=10,
        )
        assert r.status_code == 401, r.text


class TestRedeployHappyPath:
    def test_redeploy_succeeds_and_preserves_env(self):
        secret = _read_deploy_secret()
        if not secret:
            pytest.skip("DEPLOY_SECRET not configured in backend/.env")

        r = requests.post(
            DEPLOY_URL,
            headers={"X-Deploy-Secret": secret},
            timeout=45,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "deploying"
        # New robust webhook returns these fields:
        assert "commit" in body
        assert "env_preserved" in body
        # backend/.env must be in the preserved list
        assert any("backend/.env" in p for p in body["env_preserved"])

    def test_health_still_healthy_after_redeploy(self):
        # give hot-reload a moment to settle
        time.sleep(6)
        r = requests.get(HEALTH_URL, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "commit" in data
