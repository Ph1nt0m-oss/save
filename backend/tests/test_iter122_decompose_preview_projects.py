"""iter122 — Validates extraction of /preview/*, /voice/*, /projects/*, /share/* into 3 new route files."""
from __future__ import annotations

import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

from conftest import seed_verified_user, seed_session_for

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"


class TestPreviewRoutes:
    def test_preview_unknown_id_returns_404_html(self):
        r = requests.get(f"{API}/preview/fake-id", timeout=10)
        assert r.status_code == 404
        assert "non trouv" in r.text.lower()

    def test_preview_project_unknown_returns_404_html(self):
        r = requests.get(f"{API}/preview/project/fake-id", timeout=10)
        assert r.status_code == 404

    def test_preview_demo_web_returns_200(self):
        r = requests.get(f"{API}/preview/demo/web", timeout=10)
        assert r.status_code == 200
        # The demo HTML contains the expected branding
        assert "CodeForge AI" in r.text

    def test_preview_demo_app_returns_200(self):
        r = requests.get(f"{API}/preview/demo/app", timeout=10)
        assert r.status_code == 200
        # The "app" demo HTML has a phone frame
        assert "phone-frame" in r.text or "phone" in r.text.lower()

    def test_preview_demo_unknown_falls_back_to_web(self):
        r = requests.get(f"{API}/preview/demo/unknown-type", timeout=10)
        assert r.status_code == 200
        # Falls back to "web" demo
        assert "CodeForge AI" in r.text


class TestVoiceRoutes:
    def test_voice_transcribe_unauthenticated(self):
        # No file uploaded, no auth — returns 401 (auth check before body validation)
        # OR 422 if FastAPI validates the missing file first
        r = requests.post(f"{API}/voice/transcribe", timeout=10)
        assert r.status_code in (401, 422)


class TestProjectsRoutes:
    def test_projects_list_unauthenticated_401(self):
        r = requests.get(f"{API}/projects", timeout=10)
        assert r.status_code == 401

    def test_projects_get_one_unauthenticated_401(self):
        r = requests.get(f"{API}/projects/fake", timeout=10)
        assert r.status_code == 401

    def test_projects_create_unauthenticated_401(self):
        r = requests.post(
            f"{API}/projects",
            json={"name": "Test", "description": "x", "project_type": "web"},
            timeout=10,
        )
        # 401 = no auth ; 422 if FastAPI validation rejects missing/invalid project_type first
        assert r.status_code in (401, 422)

    def test_projects_update_unauthenticated_401(self):
        r = requests.put(
            f"{API}/projects/fake",
            json={"name": "Updated"},
            timeout=10,
        )
        assert r.status_code in (401, 422)

    def test_projects_delete_unauthenticated_401(self):
        r = requests.delete(f"{API}/projects/fake", timeout=10)
        assert r.status_code == 401

    def test_projects_duplicate_unauthenticated_401(self):
        r = requests.post(f"{API}/projects/fake/duplicate", timeout=10)
        assert r.status_code == 401

    def test_projects_share_unauthenticated_401(self):
        r = requests.post(f"{API}/projects/fake/share", json={"enable": True}, timeout=10)
        assert r.status_code == 401


class TestShareRoutes:
    def test_share_unknown_slug_404(self):
        r = requests.get(f"{API}/share/unknown-slug-xyz", timeout=10)
        assert r.status_code == 404

    def test_share_preview_unknown_slug_404(self):
        r = requests.get(f"{API}/share/unknown-slug-xyz/preview", timeout=10)
        assert r.status_code == 404
        # HTMLResponse, not JSON
        assert "Projet introuvable" in r.text


class TestProjectsAuthenticatedCRUD:
    """iter122 — Catches the body-binding regression (testing_agent iteration_102)."""

    @pytest.fixture
    def auth_headers(self):
        _, _, uid = seed_verified_user()
        token = seed_session_for(uid)
        return {"Authorization": f"Bearer {token}"}, uid

    def test_create_then_get_then_update_then_delete(self, auth_headers):
        headers, uid = auth_headers
        # Create
        r = requests.post(
            f"{API}/projects",
            json={"name": "iter122 test", "description": "extracted route", "project_type": "web"},
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 201, r.text
        proj = r.json()
        pid = proj["project_id"]
        assert proj["name"] == "iter122 test"
        # Get one
        r = requests.get(f"{API}/projects/{pid}", headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        # Update
        r = requests.put(
            f"{API}/projects/{pid}",
            json={"name": "iter122 updated"},
            headers=headers,
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "iter122 updated"
        # List (must include our project)
        r = requests.get(f"{API}/projects", headers=headers, timeout=10)
        assert r.status_code == 200
        ids = [p["project_id"] for p in r.json()]
        assert pid in ids
        # Delete
        r = requests.delete(f"{API}/projects/{pid}", headers=headers, timeout=10)
        assert r.status_code == 200
        # 404 after delete
        r = requests.get(f"{API}/projects/{pid}", headers=headers, timeout=10)
        assert r.status_code == 404

    def test_duplicate_creates_copy(self, auth_headers):
        headers, _ = auth_headers
        # Create then duplicate
        r = requests.post(
            f"{API}/projects",
            json={"name": "Original", "description": "src", "project_type": "web"},
            headers=headers,
            timeout=10,
        )
        assert r.status_code == 201
        pid = r.json()["project_id"]
        r2 = requests.post(f"{API}/projects/{pid}/duplicate", headers=headers, timeout=10)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["project_id"] != pid
        assert "(copie)" in body["project"]["name"]
        # Cleanup
        requests.delete(f"{API}/projects/{pid}", headers=headers, timeout=10)
        requests.delete(f"{API}/projects/{body['project_id']}", headers=headers, timeout=10)


class TestRouteMounting:
    def test_extracted_routes_in_openapi(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        # FAIL loud on 500 (PydanticUserError) — silently skipping hid the iter122 regression
        if r.status_code == 500:
            raise AssertionError(f"openapi.json returns 500 (regression): {r.text[:300]}")
        if r.status_code != 200:
            pytest.skip(f"OpenAPI not reachable on localhost (got {r.status_code})")
        paths = set(r.json().get("paths", {}).keys())
        expected = {
            # preview
            "/api/preview/{preview_id}",
            "/api/preview/project/{project_id}",
            "/api/preview/demo/{preview_type}",
            # voice
            "/api/voice/transcribe",
            # projects
            "/api/projects",
            "/api/projects/{project_id}",
            "/api/projects/{project_id}/duplicate",
            "/api/projects/{project_id}/share",
            # share
            "/api/share/{slug}",
            "/api/share/{slug}/preview",
        }
        missing = expected - paths
        assert not missing, f"Missing routes: {missing}"
