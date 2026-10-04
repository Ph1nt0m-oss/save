"""iter158.20 — P2.3 : Anonymat `alt_pseudo` par appareil (incognito owner).

Nouveau endpoint `POST /api/devices/alt-pseudo` permettant au signataire de
l'appareil (et à lui seul) de définir ou effacer un pseudonyme alternatif
local à son appareil. Garanties CDC :

  - `alt_pseudo` est strictement **par appareil** (`device_keys.alt_pseudo`),
    jamais global à un propriétaire ni à une adresse email.
  - L'identité cryptographique sous-jacente reste intacte :
      * `key_id` inchangé
      * `public_key_jwk` inchangé
      * `role` / `staff_kind` inchangés
      * `pseudo` réel + `public_handle` inchangés en base
      * `owner_key_ids` inchangé — droits propriétaire préservés
  - L'anonymat est strictement local : seul l'affichage public (`/accounts/list`)
    substitue `alt_pseudo` à `pseudo`. Les flux `/ownership/*`,
    `/owner_notifications`, et les mécanismes de sanction ne sont pas affectés.
  - L'édition croisée est impossible : seul le détenteur de la clé privée
    peut toucher SON propre `alt_pseudo` (signature ECDSA requise).

Parcours couverts :
  1. Set alt_pseudo → persistance + affichage dans /accounts/list.
  2. Clear alt_pseudo → retour au pseudo réel.
  3. Isolation : deux appareils du MÊME propriétaire ont des alt_pseudos
     indépendants.
  4. L'alt_pseudo d'un propriétaire NE S'applique PAS à `is_owner` ni à
     `owner_key_ids` (invariants ownership).
  5. Un autre appareil ne peut PAS modifier l'alt_pseudo d'un tiers
     (signature ECDSA = seule le détenteur).
  6. Validation : 3-30 chars ; caractères spéciaux refusés.
  7. ON/OFF privilèges owner × alt_pseudo : indépendants (alt_pseudo stable
     à travers un toggle).
  8. Persistance : set → relecture via `/accounts/list` reflète la valeur.
  9. Pseudo réel reste visible à la Créa (`real_pseudo` + `has_alt_pseudo`
     pour anti-usurpation).
"""
from __future__ import annotations

import base64
import os
import uuid
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------------- Crypto helpers ----------------

def _b64url(b): return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")
def _b64url_int(n, length=32): return _b64url(n.to_bytes(length, "big"))
def _b64url_decode(s):
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def gen_keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    return priv, {"kty": "EC", "crv": "P-256",
                  "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}


def sign(priv, nonce_b64url):
    der = priv.sign(_b64url_decode(nonce_b64url), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register(label_prefix="IT158_20"):
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register",
                      json={"public_key_jwk": jwk,
                            "label": f"{label_prefix}_{uuid.uuid4().hex[:6]}"},
                      timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"]


def nonce(kid):
    r = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def signed_body(priv, kid, **extra):
    n = nonce(kid)
    return {"key_id": kid, "nonce": n, "signature": sign(priv, n), **extra}


def set_alt(priv, kid, alt):
    body = signed_body(priv, kid, alt_pseudo=alt)
    return requests.post(f"{API}/devices/alt-pseudo", json=body, timeout=15)


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture()
def owner_creator(mongo):
    """Créa signataire pour les lectures /accounts/list + 2 appareils owner."""
    priv_creator, kid_creator = register()
    priv_a, kid_a = register()
    priv_b, kid_b = register()
    priv_other, kid_other = register()

    mongo.ownership.update_one(
        {"_id": "root"},
        {"$addToSet": {"owner_key_ids": {"$each": [kid_a, kid_b]}}},
    )
    mongo.device_keys.update_one({"key_id": kid_creator}, {"$set": {
        "role": "creator", "pseudo": "CreaReaderP23",
        "public_handle": f"crea_r_{uuid.uuid4().hex[:6]}",
    }})
    mongo.device_keys.update_one({"key_id": kid_a}, {"$set": {
        "role": "creator", "pseudo": "RealAliceOwner",
        "public_handle": f"alice_owner_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    mongo.device_keys.update_one({"key_id": kid_b}, {"$set": {
        "role": "creator", "pseudo": "RealBobOwner",
        "public_handle": f"bob_owner_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    mongo.device_keys.update_one({"key_id": kid_other}, {"$set": {
        "role": "approved", "pseudo": "RandomOther",
        "public_handle": f"other_{uuid.uuid4().hex[:6]}",
    }})

    yield {
        "crea":  (priv_creator, kid_creator),
        "a":     (priv_a, kid_a),
        "b":     (priv_b, kid_b),
        "other": (priv_other, kid_other),
    }

    ids = [kid_creator, kid_a, kid_b, kid_other]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": ids}}})
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})


def _accounts_list(crea_priv, crea_kid):
    r = requests.post(f"{API}/accounts/list",
                      json=signed_body(crea_priv, crea_kid), timeout=15)
    r.raise_for_status()
    return {a["key_id"]: a for a in r.json()["accounts"]}


# ============================================================================
# Parcours 1 — Set alt_pseudo + persistence + affichage
# ============================================================================

def test_p23_set_alt_pseudo_persists_and_overrides_public_display(
    owner_creator, mongo,
):
    priv_a, kid_a = owner_creator["a"]
    priv_crea, kid_crea = owner_creator["crea"]

    # État initial : pas d'alt_pseudo. L'affichage public = pseudo réel.
    acc = _accounts_list(priv_crea, kid_crea)[kid_a]
    assert acc["pseudo"] == "RealAliceOwner"
    assert acc.get("has_alt_pseudo") is False

    # Set alt_pseudo.
    r = set_alt(priv_a, kid_a, "IncognitoWitch")
    assert r.status_code == 200, r.text
    assert r.json()["alt_pseudo"] == "IncognitoWitch"

    # Persistance DB.
    dev = mongo.device_keys.find_one({"key_id": kid_a})
    assert dev.get("alt_pseudo") == "IncognitoWitch"
    # Pseudo réel inchangé.
    assert dev.get("pseudo") == "RealAliceOwner"
    # public_handle inchangé.
    assert dev.get("public_handle").startswith("alice_owner_")

    # Affichage public via /accounts/list :
    acc2 = _accounts_list(priv_crea, kid_crea)[kid_a]
    assert acc2["pseudo"] == "IncognitoWitch", (
        "L'alt_pseudo DOIT prendre le pas sur pseudo dans la vue publique"
    )
    assert acc2["real_pseudo"] == "RealAliceOwner", (
        "Le pseudo réel doit rester visible côté créa (anti-usurpation)"
    )
    assert acc2["has_alt_pseudo"] is True


# ============================================================================
# Parcours 2 — Clear alt_pseudo retire l'override
# ============================================================================

def test_p23_clear_alt_pseudo_reverts_to_real_pseudo(owner_creator, mongo):
    priv_a, kid_a = owner_creator["a"]
    priv_crea, kid_crea = owner_creator["crea"]

    # Set puis clear (null).
    set_alt(priv_a, kid_a, "TempAlias").raise_for_status()
    assert mongo.device_keys.find_one({"key_id": kid_a}).get("alt_pseudo") == "TempAlias"

    r = requests.post(
        f"{API}/devices/alt-pseudo",
        json=signed_body(priv_a, kid_a, alt_pseudo=None), timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json()["alt_pseudo"] is None

    # DB : champ $unset ou vide → pseudo réel ressort.
    dev = mongo.device_keys.find_one({"key_id": kid_a})
    assert not dev.get("alt_pseudo")

    acc = _accounts_list(priv_crea, kid_crea)[kid_a]
    assert acc["pseudo"] == "RealAliceOwner"
    assert acc["has_alt_pseudo"] is False


def test_p23_clear_with_empty_string_also_works(owner_creator, mongo):
    """Un alt_pseudo = '' ou blanc est aussi traité comme clear."""
    priv_a, kid_a = owner_creator["a"]

    set_alt(priv_a, kid_a, "ToBeCleared")
    r = requests.post(
        f"{API}/devices/alt-pseudo",
        json=signed_body(priv_a, kid_a, alt_pseudo="   "), timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json()["alt_pseudo"] is None
    assert not mongo.device_keys.find_one({"key_id": kid_a}).get("alt_pseudo")


# ============================================================================
# Parcours 3 — Isolation entre appareils du MÊME propriétaire
# ============================================================================

def test_p23_isolation_between_two_owner_devices(owner_creator, mongo):
    """Deux appareils owner (A, B) peuvent avoir des alt_pseudos distincts.
    Le changement sur A ne touche PAS B."""
    priv_a, kid_a = owner_creator["a"]
    priv_b, kid_b = owner_creator["b"]
    priv_crea, kid_crea = owner_creator["crea"]

    set_alt(priv_a, kid_a, "AliceGhost")
    set_alt(priv_b, kid_b, "BobPhantom")

    accs = _accounts_list(priv_crea, kid_crea)
    assert accs[kid_a]["pseudo"] == "AliceGhost"
    assert accs[kid_b]["pseudo"] == "BobPhantom"
    assert accs[kid_a]["real_pseudo"] == "RealAliceOwner"
    assert accs[kid_b]["real_pseudo"] == "RealBobOwner"

    # Changer A ne touche pas B.
    set_alt(priv_a, kid_a, "AliceNewGhost")
    accs2 = _accounts_list(priv_crea, kid_crea)
    assert accs2[kid_a]["pseudo"] == "AliceNewGhost"
    assert accs2[kid_b]["pseudo"] == "BobPhantom", (
        "L'alt_pseudo de B NE DOIT PAS être altéré par un changement sur A"
    )


# ============================================================================
# Parcours 4 — Invariants ownership totalement préservés
# ============================================================================

def test_p23_owner_rights_unchanged_by_alt_pseudo(owner_creator, mongo):
    """owner_key_ids + role + is_owner intacts après set/clear alt_pseudo."""
    priv_a, kid_a = owner_creator["a"]

    doc_before = mongo.ownership.find_one({"_id": "root"})
    dev_before = mongo.device_keys.find_one({"key_id": kid_a})

    set_alt(priv_a, kid_a, "GhostCreator").raise_for_status()

    # ownership intact.
    doc_after = mongo.ownership.find_one({"_id": "root"})
    assert set(doc_after["owner_key_ids"]) == set(doc_before["owner_key_ids"])
    # device role / handle / pseudo réel intacts.
    dev_after = mongo.device_keys.find_one({"key_id": kid_a})
    assert dev_after.get("role") == dev_before.get("role")
    assert dev_after.get("public_handle") == dev_before.get("public_handle")
    assert dev_after.get("pseudo") == dev_before.get("pseudo")
    assert dev_after.get("public_key_jwk") == dev_before.get("public_key_jwk")

    # /ownership/status retourne toujours is_owner=True.
    r = requests.post(f"{API}/ownership/status",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200
    s = r.json()
    assert s["is_owner"] is True
    # L'alt_pseudo N'APPARAÎT PAS dans /ownership/status (hors scope anonymat
    # owner — l'owner garde son identité pour l'audit interne).

    # Clear → mêmes invariants.
    requests.post(f"{API}/devices/alt-pseudo",
                  json=signed_body(priv_a, kid_a, alt_pseudo=None),
                  timeout=15).raise_for_status()
    doc_final = mongo.ownership.find_one({"_id": "root"})
    assert set(doc_final["owner_key_ids"]) == set(doc_before["owner_key_ids"])


# ============================================================================
# Parcours 5 — Édition croisée interdite (signature-only self-edit)
# ============================================================================

def test_p23_other_device_cannot_edit_alt_pseudo(owner_creator, mongo):
    """Un appareil tiers signant ne peut pas modifier l'alt_pseudo d'un
    autre appareil — le payload n'a PAS de target_key_id.

    En effet, l'endpoint applique l'alt_pseudo UNIQUEMENT au key_id du
    signataire. Vérifions qu'une tentative avec une signature de l'owner
    "other" ne modifie pas kid_a."""
    priv_a, kid_a = owner_creator["a"]
    priv_other, kid_other = owner_creator["other"]

    set_alt(priv_a, kid_a, "AliceAlt")

    # L'appareil "other" signe une requête alt_pseudo.
    r = set_alt(priv_other, kid_other, "TryHijack")
    assert r.status_code == 200, r.text
    # Seul SON alt_pseudo (kid_other) est modifié.
    assert mongo.device_keys.find_one({"key_id": kid_other}).get("alt_pseudo") == "TryHijack"
    # kid_a reste à "AliceAlt" (non altéré).
    assert mongo.device_keys.find_one({"key_id": kid_a}).get("alt_pseudo") == "AliceAlt"


def test_p23_invalid_signature_rejected(owner_creator):
    """Une signature invalide → 401. Pas d'édition sans ECDSA valide."""
    priv_a, kid_a = owner_creator["a"]
    priv_fake, _ = gen_keypair()
    n = nonce(kid_a)
    body = {"key_id": kid_a, "nonce": n,
            "signature": sign(priv_fake, n),  # mauvaise clé privée
            "alt_pseudo": "ShouldNotPass"}
    r = requests.post(f"{API}/devices/alt-pseudo", json=body, timeout=15)
    assert r.status_code == 401, (
        f"Signature invalide doit renvoyer 401 — {r.status_code}: {r.text}"
    )


# ============================================================================
# Parcours 6 — Validation stricte des valeurs
# ============================================================================

def test_p23_alt_pseudo_too_short_rejected(owner_creator):
    priv_a, kid_a = owner_creator["a"]
    r = set_alt(priv_a, kid_a, "AB")
    assert r.status_code == 400
    assert "invalide" in r.json()["detail"].lower()


def test_p23_alt_pseudo_too_long_rejected(owner_creator):
    priv_a, kid_a = owner_creator["a"]
    r = set_alt(priv_a, kid_a, "x" * 31)
    assert r.status_code == 400


def test_p23_alt_pseudo_special_chars_rejected(owner_creator):
    priv_a, kid_a = owner_creator["a"]
    r = set_alt(priv_a, kid_a, "bad\npseudo")
    assert r.status_code == 400


# ============================================================================
# Parcours 7 — Interaction avec Owner Privileges ON/OFF
# ============================================================================

def test_p23_alt_pseudo_stable_through_owner_toggle(owner_creator, mongo):
    """L'alt_pseudo persiste à travers une bascule ON → OFF → ON.
    Il n'est PAS altéré par le toggle de privilèges."""
    priv_a, kid_a = owner_creator["a"]

    set_alt(priv_a, kid_a, "StableGhost")

    # ON → OFF
    requests.post(f"{API}/ownership/toggle-privileges",
                  json=signed_body(priv_a, kid_a), timeout=15)
    assert mongo.device_keys.find_one({"key_id": kid_a}).get("alt_pseudo") == "StableGhost"

    # OFF → ON
    requests.post(f"{API}/ownership/toggle-privileges",
                  json=signed_body(priv_a, kid_a), timeout=15)
    assert mongo.device_keys.find_one({"key_id": kid_a}).get("alt_pseudo") == "StableGhost"


# ============================================================================
# Parcours 8 — Non-régression /accounts/list : pseudo d'origine quand absent
# ============================================================================

def test_p23_accounts_list_backward_compat_no_alt_pseudo(owner_creator, mongo):
    """Pour un compte SANS alt_pseudo, /accounts/list renvoie :
      - pseudo = pseudo réel (comportement iter127 préservé)
      - real_pseudo = pseudo réel (identique)
      - has_alt_pseudo = False"""
    priv_crea, kid_crea = owner_creator["crea"]
    _, kid_other = owner_creator["other"]

    accs = _accounts_list(priv_crea, kid_crea)
    other = accs[kid_other]
    assert other["pseudo"] == "RandomOther"
    assert other["real_pseudo"] == "RandomOther"
    assert other["has_alt_pseudo"] is False


# ============================================================================
# Parcours 9 — alt_pseudo N'affecte PAS owner_notifications (anonymat local)
# ============================================================================

def test_p23_alt_pseudo_does_not_leak_into_owner_notifications(
    owner_creator, mongo,
):
    """L'alt_pseudo est pour l'affichage public, PAS pour les notifications
    propriétaire (audit interne). Si un admin agit sur un owner OFF, la
    notification doit garder l'identité réelle (ou public_handle), pas
    l'alt_pseudo."""
    priv_a, kid_a = owner_creator["a"]

    # Set alt_pseudo sur l'owner A.
    set_alt(priv_a, kid_a, "InvisibleOwner")

    # Setup admin + OFF + sanction via /staff/action.
    priv_adm, kid_adm = register()
    mongo.device_keys.update_one({"key_id": kid_adm}, {"$set": {
        "role": "approved", "staff_kind": "admin", "pseudo": "AdminP23",
        "public_handle": f"adm_p23_{uuid.uuid4().hex[:6]}",
    }})
    try:
        # A → OFF
        requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv_a, kid_a), timeout=15)

        mongo.owner_notifications.delete_many({"owner_key_id": kid_a})
        r = requests.post(f"{API}/staff/action",
                          json=signed_body(priv_adm, kid_adm,
                                           target_key_id=kid_a, action="mute"),
                          timeout=15)
        assert r.status_code == 200, r.text

        notif = mongo.owner_notifications.find_one(
            {"owner_key_id": kid_a, "action": "mute"}
        )
        assert notif is not None
        # Target details dans la notif : public_handle de l'owner (identité
        # cryptographique), pas l'alt_pseudo.
        # L'alt_pseudo ne doit PAS être le champ principal utilisé.
        for v in notif.values():
            if isinstance(v, str):
                assert "InvisibleOwner" not in v, (
                    f"alt_pseudo ne doit PAS apparaître dans la notif owner : {v}"
                )
            if isinstance(v, dict):
                for v2 in v.values():
                    if isinstance(v2, str):
                        assert "InvisibleOwner" not in v2
    finally:
        # Clean up admin + sanctions + return owner to ON.
        requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv_a, kid_a), timeout=15)
        mongo.device_keys.delete_many({"key_id": kid_adm})
        mongo.device_nonces.delete_many({"key_id": kid_adm})
        mongo.owner_notifications.delete_many({"actor_key_id": kid_adm})
        mongo.staff_actions_log.delete_many({"actor_key_id": kid_adm})


# ============================================================================
# Parcours 10 — Endpoint monté correctement (contrat de disponibilité)
# ============================================================================

def test_p23_endpoint_mounted_and_accessible():
    """Smoke : /api/devices/alt-pseudo retourne 422 (body manquant) ou 401
    sans body signé — pas 404 (endpoint monté)."""
    r = requests.post(f"{API}/devices/alt-pseudo", json={}, timeout=10)
    assert r.status_code in (400, 401, 422), (
        f"Endpoint doit être monté — reçu {r.status_code}"
    )
