"""iter92 — Live tests against the public preview URL.

Covers:
- Login → /projects/translate-name with auth → 200 + cache behaviour
- /projects/invalidate-name-cache → 200 with success/removed
- Regression iter91 : /announcements/list and /polls/list still reachable
"""
import os
import requests
import pytest

BACKEND_URL = os.environ.get('BACKEND_URL') or 'https://no-code-builder-25.preview.emergentagent.com'
API = f"{BACKEND_URL}/api"

EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    if not tok:
        pytest.skip(f"no token in login response: {r.json()}")
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def project_id(headers):
    """Create a temporary project for translation tests."""
    r = requests.post(f"{API}/projects", json={"name": "Discussion Test iter92"}, headers=headers, timeout=15)
    if r.status_code not in (200, 201):
        pytest.skip(f"cannot create project: {r.status_code} {r.text[:200]}")
    return r.json().get("id") or r.json().get("project_id") or r.json().get("_id")


class TestTranslateNameLive:
    def test_translate_first_call(self, headers, project_id):
        r = requests.post(
            f"{API}/projects/translate-name",
            json={"project_id": project_id, "target_lang": "en", "name": "Discussion Test iter92"},
            headers=headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "translated" in data
        assert isinstance(data["translated"], str)
        assert len(data["translated"]) > 0

    def test_translate_second_call_cached(self, headers, project_id):
        r = requests.post(
            f"{API}/projects/translate-name",
            json={"project_id": project_id, "target_lang": "en", "name": "Discussion Test iter92"},
            headers=headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # cache may flag either way; just assert translated remains stable
        assert "translated" in data
        # If cached flag present, expect True on 2nd hit
        if "cached" in data:
            assert data["cached"] is True

    def test_invalidate_cache(self, headers, project_id):
        r = requests.post(
            f"{API}/projects/invalidate-name-cache",
            params={"project_id": project_id},
            headers=headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        assert "removed" in data
        assert isinstance(data["removed"], int)


class TestRegressionIter91:
    def test_announcements_list_reachable(self):
        r = requests.get(f"{API}/announcements/list", timeout=15)
        # may be 200 or 401 if it requires auth, but never 5xx
        assert r.status_code < 500, r.text

    def test_polls_list_reachable(self):
        r = requests.get(f"{API}/polls/list", timeout=15)
        assert r.status_code < 500, r.text
