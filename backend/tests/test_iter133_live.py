"""iter133 — Live backend tests for staff_decisions endpoints & site-mode normalization."""
import os
import uuid

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# --- openapi presence ---
def test_openapi_includes_new_endpoints(s):
    # OpenAPI is only exposed on internal port 8001 (not via public preview routing).
    r = s.get("http://localhost:8001/openapi.json", timeout=15)
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    for ep in ("/api/staff-decisions/list", "/api/staff-decisions/validate", "/api/staff-decisions/revert"):
        assert ep in paths, f"Missing endpoint: {ep} in openapi. Found {[k for k in paths if 'staff' in k]}"


# --- creator gating: 401/403 without valid signature ---
def _fake_sig_payload(extra=None):
    p = {"key_id": "fake_key_" + uuid.uuid4().hex[:6], "nonce": uuid.uuid4().hex, "signature": "AA" * 32}
    if extra:
        p.update(extra)
    return p


@pytest.mark.parametrize("path,extra", [
    ("/api/staff-decisions/list", None),
    ("/api/staff-decisions/validate", {"decision_id": "nonexistent_id"}),
    ("/api/staff-decisions/revert", {"decision_id": "nonexistent_id"}),
])
def test_staff_decision_endpoints_reject_fake_signature(s, path, extra):
    r = s.post(f"{BASE}{path}", json=_fake_sig_payload(extra), timeout=15)
    assert r.status_code in (401, 403), f"{path} → {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("path,extra", [
    ("/api/staff-decisions/list", None),
    ("/api/staff-decisions/validate", {"decision_id": "x"}),
    ("/api/staff-decisions/revert", {"decision_id": "x"}),
])
def test_staff_decision_endpoints_reject_missing_signature(s, path, extra):
    body = {}
    if extra:
        body.update(extra)
    r = s.post(f"{BASE}{path}", json=body, timeout=15)
    # Missing required signature fields → 422 (pydantic) or 401/403
    assert r.status_code in (401, 403, 422), f"{path} → {r.status_code} {r.text[:200]}"


# --- site-mode public GET returns normalized modes ---
def test_site_mode_public_get_returns_normalized_modes(s):
    r = s.get(f"{BASE}/api/system/site-mode", timeout=15)
    assert r.status_code == 200
    data = r.json()
    # The endpoint returns either 'modes' (multi) or 'mode' (single)
    mode = data.get("mode")
    modes = data.get("modes") or ([mode] if mode else [])
    assert modes, f"No modes/mode in response: {data}"
    allowed = {"public", "private", "creator", "guest", "modo", "admin", "staff"}
    for m in modes:
        assert m in allowed, f"Unexpected mode value '{m}' — not in normalized set. Full response: {data}"
        assert m not in ("none", "all"), f"Legacy mode leaked: {m}"


def test_site_mode_put_rejects_none_all_without_creator(s):
    # PUT /site-mode requires creator; even with legacy 'none' payload should not succeed.
    body = _fake_sig_payload({"mode": "none"})
    r = s.put(f"{BASE}/api/system/site-mode", json=body, timeout=15)
    assert r.status_code in (400, 401, 403, 422)
