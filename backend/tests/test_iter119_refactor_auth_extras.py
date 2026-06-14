"""iter119 — Tests refactoring : extraction /auth/* extras (preferences + theft + update-pseudo)."""
import os
from pathlib import Path

import requests

API = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "https://no-code-builder-25.preview.emergentagent.com"
) + "/api"

ROOT = Path(__file__).resolve().parents[2]
SERVER = (ROOT / "backend" / "server.py").read_text()
AE = (ROOT / "backend" / "routes" / "auth_extras_routes.py").read_text()


def test_auth_extras_file_exists():
    assert (ROOT / "backend" / "routes" / "auth_extras_routes.py").exists()
    assert "def build_auth_extras_router(" in AE
    total = AE.count('@router.post("/auth/') + AE.count('@router.get("/auth/') + AE.count('@router.put("/auth/')
    assert total >= 6


def test_server_no_longer_defines_extracted_auth():
    """Les 6 routes auth extras ne sont plus dans server.py."""
    assert '@api_router.get("/auth/preferences")' not in SERVER
    assert '@api_router.put("/auth/preferences")' not in SERVER
    assert '@api_router.post("/auth/update-pseudo")' not in SERVER
    assert '@api_router.post("/auth/theft-email-request")' not in SERVER
    assert '@api_router.get("/auth/theft-email-confirm")' not in SERVER
    assert '@api_router.post("/auth/theft-iris-verify")' not in SERVER


def test_server_under_8000_lines_final():
    """Après iter116+117+118+119, server.py doit être < 8000 lignes."""
    line_count = SERVER.count("\n")
    assert line_count < 8000, f"server.py = {line_count} lignes (attendu < 8000)"


def test_server_includes_auth_extras_router():
    assert "build_auth_extras_router(" in SERVER


# Live HTTP tests
def test_auth_preferences_requires_auth():
    r = requests.get(f"{API}/auth/preferences", timeout=10)
    assert r.status_code == 401


def test_auth_update_pseudo_requires_auth():
    r = requests.post(f"{API}/auth/update-pseudo", json={"new_pseudo": "Test"}, timeout=10)
    assert r.status_code == 401


def test_auth_theft_email_request_idempotent():
    """Endpoint accepte n'importe quel email (anti-enumeration)."""
    r = requests.post(f"{API}/auth/theft-email-request", json={"email": "nobody@nowhere.test"}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_auth_theft_email_request_rejects_bad_email():
    r = requests.post(f"{API}/auth/theft-email-request", json={"email": "not-an-email"}, timeout=10)
    assert r.status_code == 400


def test_auth_theft_email_confirm_rejects_invalid_token():
    r = requests.get(f"{API}/auth/theft-email-confirm?token=invalid", timeout=10)
    assert r.status_code == 404


def test_auth_theft_iris_verify_requires_3_hashes():
    r = requests.post(f"{API}/auth/theft-iris-verify", json={"email": "x@y.z", "hashes": ["abc"]}, timeout=10)
    assert r.status_code == 400
    assert "3 captures" in r.text


# Cumul final
def test_total_extracted_endpoints():
    """Cumul iter116→119 : 8 nouveaux modules de routes."""
    modules = [
        "devices_routes.py", "community_bots_routes.py", "accounts_routes.py",
        "private_routes.py", "system_routes.py", "ideas_routes.py",
        "webauthn_routes.py", "auth_extras_routes.py",
    ]
    for m in modules:
        assert (ROOT / "backend" / "routes" / m).exists(), f"Module manquant : {m}"
