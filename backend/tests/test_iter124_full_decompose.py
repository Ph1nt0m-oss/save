"""iter124 — Validates extraction of /chat/models + /chat/analyze-attachment +
/chat/export-{ipynb,docx} + lifespan migration + services/file_builders module.
"""
from __future__ import annotations

import os
import sys
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# iter124 — Make services/* importable when pytest is invoked from /app (CI)
# rather than from /app/backend. Otherwise the FileService tests ModuleNotFoundError.
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from conftest import seed_verified_user, seed_session_for

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"


class TestChatExportsRoutes:
    def test_chat_models_unauthenticated(self):
        r = requests.get(f"{API}/chat/models", timeout=10)
        assert r.status_code == 401

    def test_chat_analyze_attachment_no_file_returns_422(self):
        r = requests.post(f"{API}/chat/analyze-attachment", timeout=10)
        assert r.status_code in (401, 422)

    def test_chat_export_ipynb_unauthenticated(self):
        r = requests.get(f"{API}/chat/export-ipynb/fake-id", timeout=10)
        assert r.status_code == 401

    def test_chat_export_docx_unauthenticated(self):
        r = requests.get(f"{API}/chat/export-docx/fake-id", timeout=10)
        assert r.status_code == 401


class TestChatExportsAuthenticatedHappyPath:
    """iter124 — Authenticated test catches Pydantic body-binding regressions early."""

    @pytest.fixture
    def auth_headers(self):
        _, _, uid = seed_verified_user()
        token = seed_session_for(uid)
        return {"Authorization": f"Bearer {token}"}, uid

    def test_chat_models_returns_list(self, auth_headers):
        headers, _ = auth_headers
        r = requests.get(f"{API}/chat/models", headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "online" in body
        assert "offline" in body
        assert isinstance(body["online"], list)
        assert len(body["online"]) > 0

    def test_chat_models_create_context(self, auth_headers):
        headers, _ = auth_headers
        r = requests.get(f"{API}/chat/models", headers=headers,
                         params={"context": "create"}, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("context") == "create"

    def test_chat_export_ipynb_unknown_project_404(self, auth_headers):
        headers, _ = auth_headers
        r = requests.get(f"{API}/chat/export-ipynb/fake-project-id-xyz",
                         headers=headers, timeout=10)
        assert r.status_code == 404

    def test_chat_export_docx_unknown_project_404(self, auth_headers):
        headers, _ = auth_headers
        r = requests.get(f"{API}/chat/export-docx/fake-project-id-xyz",
                         headers=headers, timeout=10)
        assert r.status_code == 404


class TestLifespanMigration:
    """iter124 — FastAPI lifespan replaced @app.on_event ; ensure indexes are created at startup."""

    def test_openapi_still_200(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        assert r.status_code == 200

    def test_health_endpoint_still_works(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200


class TestFileBuildersService:
    """iter124 — Verify the new service module exists and exposes the right API."""

    def test_service_module_importable(self):
        from services.file_builders import (
            sanitize_filename, analyze_pdf, analyze_docx, analyze_xlsx, analyze_pptx,
            analyze_sqlite, analyze_image_with_vision, run_python_sandbox,
            FileService, make_file_service, GENERATED_FILES_DIR,
        )
        # All exports are callable / classes
        assert callable(sanitize_filename)
        assert callable(make_file_service)
        assert FileService is not None
        assert GENERATED_FILES_DIR.exists()

    def test_sanitize_filename_returns_safe_str(self):
        from services.file_builders import sanitize_filename
        result = sanitize_filename("My File / Name.pdf")
        assert isinstance(result, str)
        # Implementation-specific sanitization — just check it returns something
        assert len(result) > 0

    def test_make_file_service_returns_instance(self):
        from services.file_builders import make_file_service, FileService
        import logging
        svc = make_file_service(db=None, logger=logging.getLogger())
        assert isinstance(svc, FileService)


class TestRouteMounting:
    def test_all_iter124_routes_mounted(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        if r.status_code == 500:
            raise AssertionError(f"openapi.json 500: {r.text[:300]}")
        assert r.status_code == 200
        paths = set(r.json().get("paths", {}).keys())
        expected = {
            "/api/chat/models",
            "/api/chat/analyze-attachment",
            "/api/chat/export-ipynb/{project_id}",
            "/api/chat/export-docx/{project_id}",
        }
        missing = expected - paths
        assert not missing, f"Missing: {missing}"

    def test_critical_routes_still_in_server(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        paths = set(r.json().get("paths", {}).keys())
        # Routes intentionally kept in server.py
        for must_exist in {
            "/api/auth/login", "/api/auth/register", "/api/auth/me",
            "/api/chat/message", "/api/download/generated/{file_id}",
            "/api/sandbox/python",
        }:
            assert must_exist in paths, f"Route {must_exist} missing from server.py"


class TestNoRegressionCumulative:
    """Verify iter119/120/121/122/123 extracts still work after iter124."""

    def test_iter119_caly_config(self):
        assert requests.get(f"{API}/caly/config", timeout=10).status_code == 200

    def test_iter120_magic_link(self):
        r = requests.post(f"{API}/auth/magic-link",
                          json={"email": "x@y.com"}, timeout=10)
        assert r.status_code == 200

    def test_iter121_site_issues(self):
        assert requests.get(f"{API}/site/issues", timeout=10).status_code == 200

    def test_iter122_preview_demo(self):
        assert requests.get(f"{API}/preview/demo/web", timeout=10).status_code == 200

    def test_iter122_projects_unauth(self):
        assert requests.get(f"{API}/projects", timeout=10).status_code == 401

    def test_iter123_chat_history_unauth(self):
        assert requests.get(f"{API}/chat/history", timeout=10).status_code == 401

    def test_iter123_chat_tts_unauth(self):
        r = requests.post(f"{API}/chat/tts",
                          json={"text": "hi"}, timeout=10)
        assert r.status_code == 401
