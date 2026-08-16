"""iter158.14 — P1.3 : effectiveView correctement recalculé quand Owner OFF.

Corrige le calcul de `effectiveView` du hook `useViewSpec` afin que, lorsque
le propriétaire désactive `owner_privileges_active`, l'UI reflète le rôle
temporairement actif et ne montre PLUS aucune icône/fonction propriétaire
« fantôme ».

Le backend reste l'autorité de sécurité — ce fix est un clamp UX côté hook,
pas un mécanisme de sécurité.

Scénarios :
  1. `useViewSpec` définit un flag `ownerOff` dérivé de `useDeviceIdentity`.
  2. Quand `ownerOff=true`, `effectiveView = viewMode || 'user'` (jamais
     'creator').
  3. `isPhysicallyCreator` retombe à `false` quand `ownerOff=true`, masquant
     les icônes créa physiques (lightbulb, robots, exports, secret keys,
     programmation, bots édition, visite depuis liste, rename+mute local).
  4. `useDeviceIdentity` expose `isOwnerDevice` + `ownerPrivilegesActive`
     depuis `/ownership/status`.
  5. `OwnerPrivilegesToggle` émet l'event `codeforge:owner-privileges-changed`
     après bascule → propagation immédiate sans reload.
  6. Bascule ON → OFF → ON en live : la valeur backend suit et la fixture
     état final = ON (comportement inchangé quand ON).

Le rôle backend (`device_keys.role`) n'est JAMAIS modifié par la simple
bascule de privilèges — seuls les sanctions actives peuvent le changer.
`owner_key_ids` reste intact quel que soit l'état.
"""
from __future__ import annotations

import base64
import os
import re
import uuid
from pathlib import Path
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

FRONT = Path("/app/frontend/src")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_int(n: int, length: int = 32) -> str:
    return _b64url(n.to_bytes(length, "big"))


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def gen_keypair() -> Tuple[ec.EllipticCurvePrivateKey, dict]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    return priv, {"kty": "EC", "crv": "P-256",
                  "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}


def sign(priv, nonce_b64url: str) -> str:
    der = priv.sign(_b64url_decode(nonce_b64url), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    priv, jwk = gen_keypair()
    r = requests.post(
        f"{API}/devices/register",
        json={"public_key_jwk": jwk, "label": f"IT158_14_{uuid.uuid4().hex[:6]}"},
        timeout=15,
    )
    r.raise_for_status()
    return priv, r.json()["key_id"]


def nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge", json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def signed_body(priv, key_id: str, **extra):
    n = nonce(key_id)
    return {"key_id": key_id, "nonce": n, "signature": sign(priv, n), **extra}


def status(priv, kid):
    r = requests.post(f"{API}/ownership/status", json=signed_body(priv, kid), timeout=15)
    r.raise_for_status()
    return r.json()


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------- Source-level : garanties de wiring frontend -------------

def test_use_device_identity_fetches_ownership_status():
    """Le hook useDeviceIdentity DOIT fetcher /ownership/status quand role
    est 'creator' pour exposer isOwnerDevice + ownerPrivilegesActive."""
    src = _read(FRONT / "hooks/useDeviceIdentity.js")
    # Fetch dans refresh()
    assert "/ownership/status" in src, (
        "useDeviceIdentity doit appeler /ownership/status"
    )
    assert "isOwnerDevice" in src
    assert "ownerPrivilegesActive" in src
    # État initial défini (pas de valeur `undefined` fuyant vers useViewSpec).
    initial_state = src[src.find("useState({"):src.find("useState({") + 500]
    assert "isOwnerDevice: false" in initial_state
    assert "ownerPrivilegesActive: true" in initial_state


def test_use_device_identity_listens_to_privileges_event():
    """Un event global 'codeforge:owner-privileges-changed' doit re-déclencher
    refresh() pour propager immédiatement sans reload."""
    src = _read(FRONT / "hooks/useDeviceIdentity.js")
    assert "codeforge:owner-privileges-changed" in src
    assert "addEventListener('codeforge:owner-privileges-changed'" in src


def test_owner_privileges_toggle_dispatches_event():
    """Le composant OwnerPrivilegesToggle DOIT dispatcher l'event après
    bascule pour propager la nouvelle valeur au hook."""
    src = _read(FRONT / "components/OwnerPrivilegesToggle.jsx")
    assert "codeforge:owner-privileges-changed" in src
    assert "dispatchEvent" in src


def test_use_view_spec_clamps_effective_view_when_owner_off():
    """Quand ownerOff=true, effectiveView doit tomber à viewMode || 'user',
    JAMAIS à 'creator', pour masquer les icônes/fonctions propriétaire."""
    src = _read(FRONT / "hooks/useViewSpec.js")
    assert "ownerOff" in src, (
        "useViewSpec doit dériver un flag ownerOff depuis useDeviceIdentity"
    )
    assert "isOwnerDevice" in src
    assert "ownerPrivilegesActive" in src

    # Le calcul doit brancher sur ownerOff pour clamper.
    assert re.search(r"if\s*\(\s*ownerOff\s*\)", src), (
        "effectiveView doit avoir une branche 'if (ownerOff)'"
    )
    # Fallback à 'user' quand ownerOff sans viewMode.
    assert "|| 'user'" in src


def test_use_view_spec_clamps_physically_creator_when_owner_off():
    """isPhysicallyCreator doit être false quand ownerOff — masque les
    icônes physiques (lightbulb, robots, exports…)."""
    src = _read(FRONT / "hooks/useViewSpec.js")
    # Recherche : `isPhysicallyCreator = device?.role === 'creator' && !ownerOff`
    pat = re.compile(
        r"isPhysicallyCreator\s*=\s*device\?\.role\s*===\s*['\"]creator['\"]\s*&&\s*!\s*ownerOff"
    )
    assert pat.search(src), (
        "isPhysicallyCreator doit combiner role=='creator' ET !ownerOff"
    )


def test_use_view_spec_on_behavior_unchanged():
    """Quand ownerPrivilegesActive=true (ON), le calcul retombe sur le
    chemin d'origine : viewMode || role || 'user'. Comportement strictement
    inchangé pour ON (protection non-régression)."""
    src = _read(FRONT / "hooks/useViewSpec.js")
    # La branche else doit conserver la formule d'origine.
    else_idx = src.find("} else {", src.find("if (ownerOff)"))
    assert else_idx > 0
    else_block = src[else_idx:else_idx + 300]
    assert "device?.viewMode || device?.role || 'user'" in else_block, (
        "La branche ON doit conserver la formule d'origine (non-régression)"
    )


def test_flags_gated_on_is_physically_creator_are_masked_when_off():
    """Vérifie que TOUS les flags dépendants de isPhysicallyCreator sont
    naturellement masqués quand ownerOff (car isPhysicallyCreator=false)."""
    src = _read(FRONT / "hooks/useViewSpec.js")
    for flag in (
        "canSeeProgramming: isPhysicallyCreator",
        "canAccessSecretKeys: isPhysicallyCreator",
        "canSeeIdeasLightbulb: isPhysicallyCreator",
        "canSeeRobotBots: isPhysicallyCreator",
        "canEditTestBots: isPhysicallyCreator",
        "canViewTestBotsCode: isPhysicallyCreator",
        "canVisitAccountFromList: isPhysicallyCreator",
        "canLocalRenameMuteInProfile: isPhysicallyCreator",
    ):
        assert flag in src, f"Flag manquant ou renommé : {flag}"


def test_exports_flag_uses_effective_view_and_hides_when_off():
    """`canSeeExports: effectiveView === 'creator'` — quand ownerOff clampe
    effectiveView à 'user', ce flag devient automatiquement false."""
    src = _read(FRONT / "hooks/useViewSpec.js")
    assert "canSeeExports: effectiveView === 'creator'" in src


# ---------------- Live : bascule ON → OFF → ON via backend ----------------

@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def owner_pair(mongo):
    """Un appareil propriétaire test injecté pour les tests live."""
    priv, kid = register()
    mongo.ownership.update_one(
        {"_id": "root"}, {"$addToSet": {"owner_key_ids": kid}}
    )
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {
        "role": "creator", "pseudo": "OwnerP13",
        "public_handle": f"owner_p13_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    yield priv, kid
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": kid}})
    mongo.device_keys.delete_many({"key_id": kid})
    mongo.device_nonces.delete_many({"key_id": kid})


def test_live_on_off_on_cycle_preserves_ownership_and_role(owner_pair, mongo):
    """Cycle ON → OFF → ON : owner_key_ids intact, role='creator' constant
    (aucune sanction ne l'altère), owner_privileges_active suit la bascule."""
    priv, kid = owner_pair

    # État initial : ON
    s0 = status(priv, kid)
    assert s0["is_owner"] is True
    assert s0.get("owner_privileges_active") is True

    # Snapshot owner_key_ids et role.
    doc_before = mongo.ownership.find_one({"_id": "root"})
    assert kid in doc_before["owner_key_ids"]
    dev_before = mongo.device_keys.find_one({"key_id": kid})
    assert dev_before.get("role") == "creator"

    # ON → OFF
    r = requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv, kid), timeout=15)
    assert r.status_code == 200
    assert r.json()["owner_privileges_active"] is False

    # Invariants critiques : owner_key_ids intact, is_owner intact,
    # role='creator' inchangé (aucune sanction appliquée).
    s1 = status(priv, kid)
    assert s1["is_owner"] is True, "Statut owner ne DOIT JAMAIS changer via toggle"
    assert s1["owner_privileges_active"] is False

    doc_off = mongo.ownership.find_one({"_id": "root"})
    assert kid in doc_off["owner_key_ids"], (
        "owner_key_ids DOIT rester intact quel que soit l'état de privilèges"
    )
    dev_off = mongo.device_keys.find_one({"key_id": kid})
    assert dev_off.get("role") == "creator", (
        "role='creator' inchangé par un simple toggle OFF (sans sanction)"
    )

    # OFF → ON
    r = requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv, kid), timeout=15)
    assert r.status_code == 200
    assert r.json()["owner_privileges_active"] is True

    # Retour ON : état strictement équivalent à l'initial.
    s2 = status(priv, kid)
    assert s2["is_owner"] is True
    assert s2["owner_privileges_active"] is True

    doc_on = mongo.ownership.find_one({"_id": "root"})
    assert kid in doc_on["owner_key_ids"]
    dev_on = mongo.device_keys.find_one({"key_id": kid})
    assert dev_on.get("role") == "creator"


def test_live_off_state_exposed_to_frontend_via_status(owner_pair):
    """Le champ `owner_privileges_active` DOIT être présent dans la réponse
    de /ownership/status pour que useDeviceIdentity puisse le consommer."""
    priv, kid = owner_pair

    # Force OFF
    requests.post(f"{API}/ownership/toggle-privileges",
                  json=signed_body(priv, kid), timeout=15)
    s = status(priv, kid)
    assert "owner_privileges_active" in s, (
        "Le hook frontend requiert ce champ pour clamper effectiveView"
    )
    assert s["owner_privileges_active"] is False
    assert s["is_owner"] is True  # invariant

    # Revenir à ON pour cleanup.
    requests.post(f"{API}/ownership/toggle-privileges",
                  json=signed_body(priv, kid), timeout=15)
    s2 = status(priv, kid)
    assert s2["owner_privileges_active"] is True
