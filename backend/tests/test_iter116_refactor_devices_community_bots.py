"""iter116 — Tests refactoring : extraction routes/devices.py et routes/community_bots.py.

Valide que :
  - Les nouveaux modules existent et exposent leur factory build_*_router.
  - server.py a maigri (suppression des routes migrées).
  - Tous les endpoints /devices/* et /community-bots/* restent fonctionnels en HTTP.
"""
import os
from pathlib import Path

import requests


API = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "https://no-code-builder-25.preview.emergentagent.com"
) + "/api"

ROOT = Path(__file__).resolve().parents[2]
SERVER = (ROOT / "backend" / "server.py").read_text()
DEVICES = (ROOT / "backend" / "routes" / "devices_routes.py").read_text()
BOTS = (ROOT / "backend" / "routes" / "community_bots_routes.py").read_text()


# ---------------------------------------------------------------------- Files extracted


def test_devices_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "devices_routes.py").exists()
    assert "def build_devices_router(" in DEVICES
    # 17 endpoints attendus
    assert DEVICES.count("@router.post(\"/devices/") + DEVICES.count("@router.get(\"/devices/") >= 17


def test_community_bots_routes_file_exists():
    assert (ROOT / "backend" / "routes" / "community_bots_routes.py").exists()
    assert "def build_community_bots_router(" in BOTS
    # 7 endpoints attendus (create, list, delete, rate, test, knowledge upsert, knowledge list, knowledge delete = 8)
    total = BOTS.count("@router.post(\"/community-bots/") + BOTS.count("@router.get(\"/community-bots/")
    assert total >= 7


# ---------------------------------------------------------------------- server.py allégé


def test_server_no_longer_defines_devices_routes():
    """server.py ne doit plus contenir les définitions de routes /devices/* directement."""
    # Le seul match autorisé est éventuellement un commentaire dans le include_router.
    assert "@api_router.post(\"/devices/register\")" not in SERVER
    assert "@api_router.post(\"/devices/challenge\")" not in SERVER
    assert "@api_router.post(\"/devices/verify\")" not in SERVER
    assert "@api_router.post(\"/devices/approve\")" not in SERVER
    assert "@api_router.post(\"/devices/list\")" not in SERVER


def test_server_no_longer_defines_community_bots_routes():
    assert "@api_router.post(\"/community-bots/create\")" not in SERVER
    assert "@api_router.get(\"/community-bots/list\")" not in SERVER
    assert "@api_router.post(\"/community-bots/rate\")" not in SERVER
    assert "@api_router.post(\"/community-bots/knowledge/upsert\")" not in SERVER


def test_server_includes_both_routers():
    assert "build_devices_router(" in SERVER
    assert "build_community_bots_router(" in SERVER
    assert "from routes.devices_routes import build_devices_router" in SERVER
    assert "from routes.community_bots_routes import build_community_bots_router" in SERVER


def test_server_shrunk():
    """server.py doit être passé de ~9900 lignes à <9300 après extraction (~960 lignes retirées)."""
    line_count = SERVER.count("\n")
    assert line_count < 9300, f"server.py = {line_count} lignes (attendu < 9300)"


# ---------------------------------------------------------------------- HTTP live tests


def test_devices_register_endpoint_alive():
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": {"kty": "RSA"}}, timeout=10)
    assert r.status_code == 400  # JWK invalide → bad request
    assert "EC P-256" in r.text or "invalide" in r.text


def test_devices_challenge_endpoint_alive():
    r = requests.post(f"{API}/devices/challenge", json={"key_id": "unknown"}, timeout=10)
    assert r.status_code == 404
    assert "inconnu" in r.text


def test_devices_verify_endpoint_alive():
    r = requests.post(f"{API}/devices/verify", json={"key_id": "k", "nonce": "n", "signature": "s"}, timeout=10)
    assert r.status_code == 404


def test_devices_list_endpoint_requires_creator():
    r = requests.post(f"{API}/devices/list", json={"key_id": "k", "nonce": "n", "signature": "s"}, timeout=10)
    assert r.status_code == 403
    assert "créateur" in r.text or "Action réservée" in r.text


def test_devices_approve_endpoint_alive():
    r = requests.post(f"{API}/devices/approve", json={
        "key_id": "k", "nonce": "n", "signature": "s",
        "target_key_id": "t", "as_role": "admin",
    }, timeout=10)
    assert r.status_code == 403  # signature invalide attendue


def test_community_bots_list_endpoint_alive():
    r = requests.get(f"{API}/community-bots/list", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "bots" in data
    assert isinstance(data["bots"], list)


def test_community_bots_knowledge_list_endpoint_alive():
    r = requests.get(f"{API}/community-bots/knowledge/list?bot_id=test", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data


def test_community_bots_rate_endpoint_alive():
    r = requests.post(f"{API}/community-bots/rate", json={
        "key_id": "k", "nonce": "n", "signature": "s",
        "bot_id": "t", "rating": 5,
    }, timeout=10)
    # 404 (Clé inconnue) ou 403 (Action réservée) — selon ordre du check
    assert r.status_code in (403, 404)
    assert "inconnue" in r.text or "Action réservée" in r.text or "non" in r.text.lower()


def test_community_bots_delete_endpoint_alive():
    r = requests.post(f"{API}/community-bots/delete", json={
        "key_id": "k", "nonce": "n", "signature": "s", "bot_id": "t",
    }, timeout=10)
    assert r.status_code == 403
