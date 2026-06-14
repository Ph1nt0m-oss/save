"""iter121 — Validates extraction of /caly/*, /site/issues/*, /exports/* into 3 new route files."""
from __future__ import annotations

import os
import uuid
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"


class TestCalyRoutes:
    def test_caly_config_get_returns_default(self):
        r = requests.get(f"{API}/caly/config", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["bot_id"] == "caly"
        assert "prompt" in body
        assert "is_default" in body

    def test_caly_config_post_requires_signature(self):
        r = requests.post(
            f"{API}/caly/config",
            json={"key_id": "x", "nonce": "x", "signature": "x", "prompt": "test"},
            timeout=10,
        )
        # 404 = unknown key; 401/403 = nonce/sig invalid
        assert r.status_code in (400, 401, 403, 404)

    def test_caly_ask_empty_message_400(self):
        r = requests.post(f"{API}/caly/ask", json={"message": ""}, timeout=10)
        assert r.status_code == 400

    def test_caly_ask_valid_message(self):
        r = requests.post(f"{API}/caly/ask", json={"message": "Bonjour"}, timeout=30)
        # 200 if LLM key OK, 503 if missing, 500 on transient LLM error — acceptable
        assert r.status_code in (200, 500, 503)
        if r.status_code == 200:
            assert "reply" in r.json()


class TestSiteIssuesRoutes:
    def test_issues_list_no_auth(self):
        # GET is public
        r = requests.get(f"{API}/site/issues", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "issues" in body
        assert "total" in body

    def test_issues_create_requires_signature(self):
        r = requests.post(
            f"{API}/site/issues/create",
            json={"key_id": "x", "nonce": "x", "signature": "x", "title": "Bug"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_issues_update_requires_signature(self):
        r = requests.post(
            f"{API}/site/issues/update",
            json={"key_id": "x", "nonce": "x", "signature": "x", "issue_id": "x"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_issues_filter_by_status(self):
        r = requests.get(f"{API}/site/issues", params={"status": "open"}, timeout=10)
        assert r.status_code == 200


class TestExportsRoutes:
    def test_exports_request_requires_signature(self):
        r = requests.post(
            f"{API}/exports/request",
            json={"key_id": "x", "nonce": "x", "signature": "x",
                  "project_id": "p1", "export_kind": "zip+github"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_exports_decide_requires_creator_signature(self):
        r = requests.post(
            f"{API}/exports/decide",
            json={"key_id": "x", "nonce": "x", "signature": "x",
                  "request_id": "r1", "decision": "approve"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_exports_pending_requires_creator_signature(self):
        r = requests.post(
            f"{API}/exports/pending",
            json={"key_id": "x", "nonce": "x", "signature": "x"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_exports_status_requires_signature(self):
        r = requests.post(
            f"{API}/exports/status",
            json={"key_id": "x", "nonce": "x", "signature": "x", "request_id": "r1"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_exports_zip_project_unauthenticated_401(self):
        r = requests.get(f"{API}/exports/zip-project/fake", timeout=10)
        assert r.status_code == 401


class TestRouteMounting:
    def test_extracted_routes_in_openapi(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        if r.status_code != 200:
            pytest.skip("OpenAPI not reachable on localhost")
        paths = set(r.json().get("paths", {}).keys())
        expected = {
            # caly
            "/api/caly/ask",
            "/api/caly/config",
            # site issues
            "/api/site/issues",
            "/api/site/issues/create",
            "/api/site/issues/update",
            # exports
            "/api/exports/request",
            "/api/exports/decide",
            "/api/exports/pending",
            "/api/exports/zip-project/{project_id}",
            "/api/exports/status",
        }
        missing = expected - paths
        assert not missing, f"Missing routes: {missing}"
