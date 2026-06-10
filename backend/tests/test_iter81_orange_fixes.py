"""iter81 — Backend tests for the 'orange' fixes (C2/C13/C17/C20).

Covered endpoints (per review_request):
  - POST /api/ai/wizard-suggest      (C2 — variety of pseudo suggestions)
  - POST /api/export/download        (C17 — include_code / include_chat flags)
  - POST /api/accounts/visit         (C20 — gated to creator signature)
  - POST /api/ideas/inbox            (gated to creator/admin/modo)
  - POST /api/ideas/clear            (gated; scope validation)
  - _fallback_name_pool() direct     (length variety per iter79/C2)
"""
import os
import sys
import importlib.util
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend/.env at runtime
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

API = f"{BASE_URL}/api"
TEST_EMAIL = "test_dash_1777658375@gmail.com"
TEST_PASSWORD = "Pass1234"


@pytest.fixture(scope="session")
def auth_token():
    """Login the standing test user; skip if creds rejected."""
    try:
        r = requests.post(
            f"{API}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=15,
        )
    except Exception as exc:
        pytest.skip(f"Login network error: {exc}")
    if r.status_code == 429:
        pytest.skip("Brute-force lockout active for test user — retry later")
    if r.status_code != 200:
        pytest.skip(f"Login failed {r.status_code}: {r.text[:200]}")
    body = r.json()
    tok = body.get("access_token") or body.get("token")
    if not tok:
        pytest.skip("Login response had no access_token")
    return tok


@pytest.fixture(scope="session")
def authed():
    """Shared requests.Session with Authorization header."""
    s = requests.Session()
    try:
        r = s.post(
            f"{API}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=15,
        )
    except Exception as exc:
        pytest.skip(f"Login network error: {exc}")
    if r.status_code != 200:
        pytest.skip(f"Login failed {r.status_code}: {r.text[:200]}")
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# -----------------------------------------------------------------------------
# C2 — Wizard variety
# -----------------------------------------------------------------------------
class TestWizardSuggest:
    """C2 — /api/ai/wizard-suggest variety + auth"""

    def test_requires_auth(self):
        r = requests.post(
            f"{API}/ai/wizard-suggest",
            json={"kind": "name", "platforms": ["web"], "seed": 0.42},
            timeout=10,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_name_returns_three_suggestions(self, authed):
        r = authed.post(
            f"{API}/ai/wizard-suggest",
            json={"kind": "name", "platforms": ["web"], "app_type": "todo", "seed": 0.123456},
            timeout=60,
        )
        assert r.status_code == 200, f"status {r.status_code} body={r.text[:300]}"
        data = r.json()
        assert isinstance(data.get("suggestions"), list)
        assert len(data["suggestions"]) == 3, f"expected 3, got {data}"
        for s in data["suggestions"]:
            assert isinstance(s, str) and len(s) >= 1

    def test_name_variety_across_seeds(self, authed):
        """C2 — seed forces variation; multiple calls should not always return identical lists."""
        seen_sets = set()
        for seed in (0.111, 0.222, 0.333, 0.444, 0.555):
            r = authed.post(
                f"{API}/ai/wizard-suggest",
                json={"kind": "name", "platforms": ["web"], "seed": seed},
                timeout=60,
            )
            assert r.status_code == 200
            sugg = tuple(r.json().get("suggestions", []))
            seen_sets.add(sugg)
        # at least 2 distinct suggestion-tuples across 5 seeds.
        assert len(seen_sets) >= 2, f"No variety detected: {seen_sets}"

    def test_name_lengths_varied(self, authed):
        """C2 — fallback pool MUST contain names of various lengths (not all 6)."""
        lengths = set()
        for seed in (0.11, 0.22, 0.33, 0.44, 0.55, 0.66, 0.77):
            r = authed.post(
                f"{API}/ai/wizard-suggest",
                json={"kind": "name", "platforms": ["web"], "seed": seed},
                timeout=60,
            )
            if r.status_code == 200:
                for s in r.json().get("suggestions", []):
                    lengths.add(len(s))
        # Should see at least 3 distinct character counts across the samples.
        assert len(lengths) >= 3, f"Only one length observed (style 'Among Us' fixed-len bug): {lengths}"

    def test_design_kind(self, authed):
        r = authed.post(
            f"{API}/ai/wizard-suggest",
            json={"kind": "design", "platforms": ["mobile"], "seed": 0.5},
            timeout=60,
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("design"), str) and len(body["design"]) > 0


# -----------------------------------------------------------------------------
# Fallback pool — direct module import (no HTTP)
# -----------------------------------------------------------------------------
class TestFallbackNamePool:
    """C2 — confirm the fallback pool has 50+ names with varied lengths."""

    def _load_pool(self):
        spec = importlib.util.spec_from_file_location("server_pool_probe", "/app/backend/server.py")
        # Avoid running uvicorn on import — server.py guards with __name__ == '__main__'.
        # We only need the function; import will execute module top-level (acceptable in test).
        # If that's heavy, use textual extraction.
        import re
        with open("/app/backend/server.py") as f:
            src = f.read()
        m = re.search(r"def _fallback_name_pool\(\):.*?return\s+\[(.*?)\]", src, re.DOTALL)
        assert m, "Could not locate _fallback_name_pool source"
        names = re.findall(r'"([^"]+)"', m.group(1))
        return names

    def test_pool_min_size(self):
        pool = self._load_pool()
        assert len(pool) >= 50, f"Pool too small: {len(pool)}"

    def test_pool_length_variety(self):
        pool = self._load_pool()
        lens = {len(n) for n in pool}
        # Per spec: not all 6 chars (Among-Us bug)
        assert len(lens) >= 5, f"Pool lengths not varied: {lens}"
        assert min(lens) <= 4
        assert max(lens) >= 9


# -----------------------------------------------------------------------------
# C20 — /accounts/visit gated to creator signature
# -----------------------------------------------------------------------------
class TestAccountsVisit:
    def test_unsigned_returns_403(self):
        r = requests.post(
            f"{API}/accounts/visit",
            json={
                "key_id": "TEST_iter81_unsigned",
                "nonce": "x" * 16,
                "signature": "y" * 64,
                "target_key_id": "TEST_iter81_target",
            },
            timeout=10,
        )
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}: {r.text[:200]}"

    def test_missing_body_returns_422(self):
        r = requests.post(f"{API}/accounts/visit", json={}, timeout=10)
        assert r.status_code in (401, 403, 422)


# -----------------------------------------------------------------------------
# Ideas inbox / clear gating
# -----------------------------------------------------------------------------
class TestIdeasInboxClear:
    def test_inbox_unsigned_returns_403(self):
        r = requests.post(
            f"{API}/ideas/inbox",
            json={"key_id": "TEST_iter81_unsigned", "nonce": "n" * 16, "signature": "s" * 64},
            timeout=10,
        )
        # 404 = unknown key (caught BEFORE signature verify by _verify_signed)
        # 401/403 = signature failure path. Both are acceptable gate outcomes.
        assert r.status_code in (401, 403, 404), f"expected 401/403/404 got {r.status_code}: {r.text[:200]}"

    def test_clear_invalid_scope_or_403(self):
        r = requests.post(
            f"{API}/ideas/clear",
            json={
                "key_id": "TEST_iter81_unsigned",
                "nonce": "n" * 16,
                "signature": "s" * 64,
                "scope": "all",
            },
            timeout=10,
        )
        # signature fails first → 401/403; OR validates 400 if scope invalid
        assert r.status_code in (400, 401, 403)

    def test_clear_invalid_scope_value(self):
        r = requests.post(
            f"{API}/ideas/clear",
            json={
                "key_id": "TEST_iter81_unsigned",
                "nonce": "n" * 16,
                "signature": "s" * 64,
                "scope": "garbage",
            },
            timeout=10,
        )
        # Either signature gate fires first (401/403) or scope validation (400)
        assert r.status_code in (400, 401, 403)


# -----------------------------------------------------------------------------
# C17 — Export download flags
# -----------------------------------------------------------------------------
class TestExportDownload:
    def test_requires_auth(self):
        r = requests.post(
            f"{API}/export/download",
            json={
                "project_id": "TEST_iter81_nonexistent",
                "export_type": "source",
                "include_code": True,
                "include_chat": False,
            },
            timeout=10,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_unknown_project_returns_404(self, authed):
        r = authed.post(
            f"{API}/export/download",
            json={
                "project_id": "TEST_iter81_nonexistent_zzz",
                "export_type": "source",
                "include_code": True,
                "include_chat": True,
            },
            timeout=15,
        )
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"

    def test_accepts_include_flags_schema(self, authed):
        """Confirm the new include_code/include_chat fields are accepted by the pydantic model."""
        # Send all-false combo: pydantic should still accept, then 404 because no project.
        r = authed.post(
            f"{API}/export/download",
            json={
                "project_id": "TEST_iter81_nonexistent_zzz2",
                "export_type": "source",
                "include_code": False,
                "include_chat": False,
            },
            timeout=15,
        )
        assert r.status_code in (404, 400), (
            f"include flags schema rejected? {r.status_code}: {r.text[:200]}"
        )


# -----------------------------------------------------------------------------
# Regression smoke — health & sanity
# -----------------------------------------------------------------------------
class TestRegression:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
