"""iter117 — Tests refactoring : extraction /accounts/*, /private/*, /system/*."""
import os
from pathlib import Path

import requests


API = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "https://no-code-builder-25.preview.emergentagent.com"
) + "/api"

ROOT = Path(__file__).resolve().parents[2]
SERVER = (ROOT / "backend" / "server.py").read_text()
ACCOUNTS = (ROOT / "backend" / "routes" / "accounts_routes.py").read_text()
PRIVATE = (ROOT / "backend" / "routes" / "private_routes.py").read_text()
SYSTEM = (ROOT / "backend" / "routes" / "system_routes.py").read_text()


# ---------------------------------------------------------------------- Files extracted


def test_accounts_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "accounts_routes.py").exists()
    assert "def build_accounts_router(" in ACCOUNTS
    # 16 endpoints attendus
    total = ACCOUNTS.count('@router.post("/accounts/') + ACCOUNTS.count('@router.get("/accounts/')
    assert total >= 16


def test_private_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "private_routes.py").exists()
    assert "def build_private_router(" in PRIVATE
    total = PRIVATE.count('@router.post("/private/') + PRIVATE.count('@router.get("/private/')
    assert total >= 5


def test_system_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "system_routes.py").exists()
    assert "def build_system_router(" in SYSTEM
    total = SYSTEM.count('@router.post("/system/') + SYSTEM.count('@router.get("/system/')
    assert total >= 4


# ---------------------------------------------------------------------- server.py allégé


def test_server_no_longer_defines_accounts_routes():
    assert '@api_router.post("/accounts/list")' not in SERVER
    assert '@api_router.post("/accounts/ban")' not in SERVER
    assert '@api_router.post("/accounts/visit")' not in SERVER


def test_server_no_longer_defines_private_routes():
    assert '@api_router.post("/private/changelog")' not in SERVER
    assert '@api_router.post("/private/code/write-file")' not in SERVER
    assert '@api_router.post("/private/code/read-file")' not in SERVER


def test_server_no_longer_defines_system_kick_routes():
    assert '@api_router.post("/system/schedule-kick")' not in SERVER
    assert '@api_router.get("/system/ollama-status")' not in SERVER
    # /system/site-mode reste dans server.py (helpers trop imbriqués)
    assert '@api_router.get("/system/site-mode")' in SERVER


def test_server_includes_all_three_new_routers():
    assert "build_accounts_router(" in SERVER
    assert "build_private_router(" in SERVER
    assert "build_system_router(" in SERVER


def test_server_under_8500_lines():
    """Après iter116+117, server.py doit être passé de 9909 lignes à <8500."""
    line_count = SERVER.count("\n")
    assert line_count < 8500, f"server.py = {line_count} lignes (attendu < 8500)"


# ---------------------------------------------------------------------- HTTP live tests


def test_accounts_list_alive():
    r = requests.post(f"{API}/accounts/list", json={"key_id": "k", "nonce": "n", "signature": "s"}, timeout=10)
    assert r.status_code == 403
    assert "créateur" in r.text


def test_accounts_visit_alive():
    r = requests.post(f"{API}/accounts/visit", json={"key_id": "k", "nonce": "n", "signature": "s", "target_key_id": "t"}, timeout=10)
    assert r.status_code == 403


def test_accounts_mute_alive():
    r = requests.post(f"{API}/accounts/mute", json={"key_id": "k", "nonce": "n", "signature": "s", "target_key_id": "t"}, timeout=10)
    assert r.status_code == 403


def test_private_changelog_alive():
    r = requests.post(f"{API}/private/changelog", json={"key_id": "k", "nonce": "n", "signature": "s"}, timeout=10)
    assert r.status_code == 403


def test_private_read_file_alive():
    r = requests.post(f"{API}/private/code/read-file", json={"key_id": "k", "nonce": "n", "signature": "s", "path": "backend/server.py"}, timeout=10)
    assert r.status_code == 403


def test_system_ollama_status_alive():
    r = requests.get(f"{API}/system/ollama-status", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
    assert "models" in data


def test_system_scheduled_kicks_alive():
    r = requests.get(f"{API}/system/scheduled-kicks", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "scheduled_kicks" in data
    assert isinstance(data["scheduled_kicks"], list)


def test_system_schedule_kick_requires_creator():
    r = requests.post(f"{API}/system/schedule-kick", json={"key_id": "k", "nonce": "n", "signature": "s", "minutes": 1}, timeout=10)
    assert r.status_code == 403
