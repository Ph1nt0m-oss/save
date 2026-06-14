"""iter126 Lot 2 — Validates protected test agents + invisible GitHub storage + backdrop targeting."""
from __future__ import annotations

import os
import uuid
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"


def _mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


class TestProtectedTestAgents:
    """Lot 2 #7 — 5 protected agents are seeded at startup; visible but locked."""

    def test_list_includes_5_protected_agents(self):
        r = requests.get(f"{API}/community-bots/list", params={"only_published": True}, timeout=10)
        assert r.status_code == 200
        bots = r.json().get("bots", [])
        protected = [b for b in bots if b.get("protected")]
        assert len(protected) >= 5, f"Expected ≥5 protected agents, got {len(protected)}"
        # Verify known IDs
        ids = {b["bot_id"] for b in protected}
        for must in {"_agent_security_v1", "_agent_quality_v1", "_agent_compliance_v1",
                     "_agent_originality_v1", "_agent_export_validator_v1"}:
            assert must in ids, f"Missing protected agent: {must}"

    def test_protected_bots_have_no_prompt_exposed(self):
        r = requests.get(f"{API}/community-bots/list", timeout=10)
        bots = r.json().get("bots", [])
        for b in bots:
            assert "prompt" not in b, "Bot prompt should not be exposed in list endpoint"

    def test_delete_protected_requires_creator(self):
        # Non-creator key cannot delete a protected agent
        r = requests.post(
            f"{API}/community-bots/delete",
            json={"key_id": "fake", "nonce": "x", "signature": "y",
                  "bot_id": "_agent_security_v1"},
            timeout=10,
        )
        # 401/403/404 — never 200.
        assert r.status_code != 200, f"Protected agent deleted by non-creator: {r.status_code}"


class TestInvisibleGitHubStorage:
    """Lot 2 #6 — Storage collection is hidden, no public endpoint exposes it."""

    def test_no_storage_endpoint_exists(self):
        r = requests.get("http://localhost:8001/openapi.json", timeout=10)
        assert r.status_code == 200
        paths = set(r.json().get("paths", {}).keys())
        # No public route exposes the internal storage.
        suspect = [p for p in paths if "github_storage" in p or "gh_storage" in p
                   or "_internal" in p]
        assert not suspect, f"Internal storage leaked in OpenAPI: {suspect}"

    def test_storage_module_importable(self):
        from services.github_storage import stash_snapshot, transfer_on_approve, COLLECTION
        assert COLLECTION.startswith("_"), "Collection name must be underscore-prefixed (hidden)"
        assert callable(stash_snapshot)
        assert callable(transfer_on_approve)

    def test_storage_collection_not_in_public_apis(self):
        """The collection name starts with `_` — by convention, no MongoDB
        list-collections-style endpoint should return it. Verify by spot-checking
        common admin/community list endpoints."""
        # /community-bots/list shouldn't return docs from the internal collection.
        r = requests.get(f"{API}/community-bots/list", timeout=10)
        assert r.status_code == 200
        bots = r.json().get("bots", [])
        for b in bots:
            assert not b.get("snapshot_id"), "Bots endpoint leaked GitHub storage docs"


class TestExportsDecideHookSafe:
    """Lot 2 — /exports/decide silently triggers the GitHub transfer hook
    but never breaks if it fails (best-effort, hidden errors)."""

    def test_decide_endpoint_still_responds(self):
        # No valid signature → 401/403/422/404. Should NOT 500 (the hook is wrapped).
        r = requests.post(
            f"{API}/exports/decide",
            json={"key_id": "fake", "nonce": "x", "signature": "y",
                  "request_id": "fake", "decision": "approve"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404, 422), f"Got {r.status_code}: {r.text[:200]}"


class TestRegressionCumulative:
    def test_openapi_ok(self):
        assert requests.get("http://localhost:8001/openapi.json", timeout=10).status_code == 200

    def test_caly_config(self):
        assert requests.get(f"{API}/caly/config", timeout=10).status_code == 200

    def test_exports_pending_signature_required(self):
        r = requests.post(
            f"{API}/exports/pending",
            json={"key_id": "x", "nonce": "x", "signature": "x"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403, 404, 422)
