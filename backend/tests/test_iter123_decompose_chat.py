"""iter123 — Validates extraction of /chat/* + /orchestrate/* into 3 new route files.

12 endpoints extracted this round :
  - chat_advanced_routes.py     : /chat/translate-messages, /chat/suggest-enhancements,
                                  /chat/tts, /chat/orchestrate, /chat/orchestrate-stream,
                                  /orchestrate/test-loop, /chat/stream
  - chat_history_routes.py      : /chat/history, /chat/attach
  - chat_generate_routes.py     : /chat/generate-docx, /chat/generate-pdf, /chat/generate-image
"""
from __future__ import annotations

import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"


class TestChatAdvancedRoutes:
    def test_translate_messages_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/translate-messages",
            json={"messages": [], "target_lang": "en"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_suggest_enhancements_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/suggest-enhancements",
            json={"last_ai_message": "Hello", "language": "fr"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_tts_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/tts",
            json={"text": "test", "voice": "alloy"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_orchestrate_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/orchestrate",
            json={"message": "x", "language": "fr"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_orchestrate_stream_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/orchestrate-stream",
            json={"message": "x"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_test_loop_unauthenticated(self):
        r = requests.post(
            f"{API}/orchestrate/test-loop",
            json={"target": "backend"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_chat_stream_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/stream",
            json={"message": "hello"},
            timeout=10,
        )
        assert r.status_code == 401


class TestChatHistoryRoutes:
    def test_history_unauthenticated(self):
        r = requests.get(f"{API}/chat/history", timeout=10)
        assert r.status_code == 401

    def test_attach_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/attach",
            json={"project_id": "X"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_attach_missing_fields_validation(self):
        # 422 if project_id missing
        r = requests.post(
            f"{API}/chat/attach",
            json={},
            timeout=10,
        )
        assert r.status_code in (401, 422)


class TestChatGenerateRoutes:
    def test_generate_docx_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/generate-docx",
            json={"title": "T", "sections": []},
            timeout=10,
        )
        assert r.status_code == 401

    def test_generate_pdf_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/generate-pdf",
            json={"title": "T", "sections": []},
            timeout=10,
        )
        assert r.status_code == 401

    def test_generate_image_unauthenticated(self):
        r = requests.post(
            f"{API}/chat/generate-image",
            json={"prompt": "a cat"},
            timeout=10,
        )
        assert r.status_code == 401


class TestRouteMounting:
    def test_extracted_routes_mounted_via_openapi(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        if r.status_code == 500:
            raise AssertionError(f"openapi.json returns 500: {r.text[:300]}")
        if r.status_code != 200:
            pytest.skip(f"OpenAPI not reachable (got {r.status_code})")
        paths = set(r.json().get("paths", {}).keys())
        expected = {
            # chat advanced
            "/api/chat/translate-messages",
            "/api/chat/suggest-enhancements",
            "/api/chat/tts",
            "/api/chat/orchestrate",
            "/api/chat/orchestrate-stream",
            "/api/orchestrate/test-loop",
            "/api/chat/stream",
            # chat history
            "/api/chat/history",
            "/api/chat/attach",
            # chat generate
            "/api/chat/generate-docx",
            "/api/chat/generate-pdf",
            "/api/chat/generate-image",
        }
        missing = expected - paths
        assert not missing, f"Missing routes: {missing}"

    def test_routes_still_in_server_intact(self):
        """/auth/login + /chat/message + /chat/models stay in server.py."""
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        assert r.status_code == 200
        paths = set(r.json().get("paths", {}).keys())
        # Routes intentionally kept in server.py
        for must_exist in {"/api/auth/login", "/api/chat/message", "/api/chat/models", "/api/auth/register"}:
            assert must_exist in paths, f"Route {must_exist} missing from server.py"


class TestNoRegressionPrevExtractions:
    """Make sure previous extracts (iter119-iter122) still respond correctly."""

    def test_caly_config_still_works(self):
        r = requests.get(f"{API}/caly/config", timeout=10)
        assert r.status_code == 200

    def test_site_issues_still_works(self):
        r = requests.get(f"{API}/site/issues", timeout=10)
        assert r.status_code == 200

    def test_preview_demo_still_works(self):
        r = requests.get(f"{API}/preview/demo/web", timeout=10)
        assert r.status_code == 200

    def test_projects_list_still_401(self):
        r = requests.get(f"{API}/projects", timeout=10)
        assert r.status_code == 401

    def test_auth_magic_link_still_works(self):
        r = requests.post(
            f"{API}/auth/magic-link",
            json={"email": "test@example.com"},
            timeout=10,
        )
        assert r.status_code == 200
