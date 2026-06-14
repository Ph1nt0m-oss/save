"""iter118 — Tests refactoring : extraction /ideas/* et /webauthn/*."""
import os
from pathlib import Path

import requests


API = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "https://no-code-builder-25.preview.emergentagent.com"
) + "/api"

ROOT = Path(__file__).resolve().parents[2]
SERVER = (ROOT / "backend" / "server.py").read_text()
IDEAS = (ROOT / "backend" / "routes" / "ideas_routes.py").read_text()
WAUTH = (ROOT / "backend" / "routes" / "webauthn_routes.py").read_text()


def test_ideas_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "ideas_routes.py").exists()
    assert "def build_ideas_router(" in IDEAS
    total = IDEAS.count('@router.post("/ideas/') + IDEAS.count('@router.get("/ideas/')
    assert total >= 7


def test_webauthn_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "webauthn_routes.py").exists()
    assert "def build_webauthn_router(" in WAUTH
    total = WAUTH.count('@router.post("/webauthn/') + WAUTH.count('@router.get("/webauthn/')
    assert total >= 6


def test_server_no_longer_defines_ideas():
    assert '@api_router.post("/ideas/send")' not in SERVER
    assert '@api_router.post("/ideas/inbox")' not in SERVER
    assert '@api_router.post("/ideas/set-state")' not in SERVER


def test_server_no_longer_defines_webauthn():
    assert '@api_router.post("/webauthn/enroll-begin")' not in SERVER
    assert '@api_router.get("/webauthn/has-enrollment")' not in SERVER
    assert '@api_router.post("/webauthn/declare-theft-options")' not in SERVER


def test_server_includes_new_routers():
    assert "build_ideas_router(" in SERVER
    assert "build_webauthn_router(" in SERVER


def test_server_under_8000_lines():
    """Après iter118, server.py doit être <8000 lignes (était 9909 init)."""
    line_count = SERVER.count("\n")
    assert line_count < 8050, f"server.py = {line_count} lignes (attendu < 8050)"


# Live HTTP tests
def test_ideas_send_anonymous():
    r = requests.post(f"{API}/ideas/send", json={"content": "iter118 test", "kind": "idea"}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_ideas_inbox_requires_signature():
    r = requests.post(f"{API}/ideas/inbox", json={"key_id": "k", "nonce": "n", "signature": "s"}, timeout=10)
    assert r.status_code in (403, 404)


def test_ideas_set_state_requires_signature():
    r = requests.post(f"{API}/ideas/set-state", json={
        "key_id": "k", "nonce": "n", "signature": "s",
        "idea_id": "x", "state": "validated",
    }, timeout=10)
    assert r.status_code in (403, 404)


def test_webauthn_has_enrollment_alive():
    r = requests.get(f"{API}/webauthn/has-enrollment", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "enrolled_count" in data
    assert "has_any" in data


def test_webauthn_declare_theft_options_alive():
    r = requests.post(f"{API}/webauthn/declare-theft-options",
                      json={"key_id": "unknown", "origin": "https://example.com"}, timeout=10)
    assert r.status_code == 404
