"""
Iter57 backend smoke — /api/accounts/delete-one and /api/accounts/delete-all.

Scope:
- /api/accounts/delete-one:
    * requires creator signature → non-creator caller → 403
    * (cannot exercise self/target-not-found from black-box without a creator
      device, but the signature gate is verified)
- /api/accounts/delete-all:
    * requires creator signature → non-creator caller → 403
    * missing signature → 4xx
- Regression: /api/accounts/remove-creator (iter56) still creator-gated
- Regression: /api/ideas/send anonymous (iter55) still 200
"""
import base64
import os
import uuid
import requests
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")


def _b64u(b):
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64u_decode(s):
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _int_to_b64u(n, length=32):
    return _b64u(n.to_bytes(length, "big"))


class Device:
    def __init__(self):
        self.priv = ec.generate_private_key(ec.SECP256R1())
        pn = self.priv.public_key().public_numbers()
        self.jwk = {"kty": "EC", "crv": "P-256",
                    "x": _int_to_b64u(pn.x), "y": _int_to_b64u(pn.y)}
        self.key_id = None
        self.role = None

    def sign(self, nonce_b64u):
        sig_der = self.priv.sign(_b64u_decode(nonce_b64u),
                                 ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(sig_der)
        return _b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))

    def register(self, label="iter57-test"):
        r = requests.post(f"{BASE_URL}/api/devices/register",
                          json={"public_key_jwk": self.jwk, "label": label},
                          timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        self.key_id = body["key_id"]
        self.role = body["role"]
        return body

    def challenge(self):
        r = requests.post(f"{BASE_URL}/api/devices/challenge",
                          json={"key_id": self.key_id}, timeout=15)
        assert r.status_code == 200, r.text
        return r.json()["nonce"]

    def signed(self, extra=None):
        nonce = self.challenge()
        p = {"key_id": self.key_id, "nonce": nonce,
             "signature": self.sign(nonce)}
        if extra:
            p.update(extra)
        return p


@pytest.fixture(scope="module")
def device_a():
    d = Device()
    d.register("iter57-A")
    return d


@pytest.fixture(scope="module")
def device_b():
    d = Device()
    d.register("iter57-B")
    return d


# ---------------------------------------------------------------------------
# 0. Sanity
# ---------------------------------------------------------------------------
def test_00_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 1. /api/accounts/delete-one signature gate
# ---------------------------------------------------------------------------
def test_01_delete_one_unsigned_rejected():
    r = requests.post(f"{BASE_URL}/api/accounts/delete-one",
                      json={"target_key_id": "anything"}, timeout=15)
    # No key_id/nonce/signature → 4xx
    assert r.status_code in (400, 401, 403, 422), r.text


def test_02_delete_one_non_creator_signed_403(device_a, device_b):
    """Fresh 'pending' device A trying to delete B → must be rejected at the
    creator-signature gate before any branch is evaluated."""
    payload = device_a.signed({"target_key_id": device_b.key_id})
    r = requests.post(f"{BASE_URL}/api/accounts/delete-one",
                      json=payload, timeout=15)
    assert r.status_code == 403, r.text


def test_03_delete_one_non_creator_self_target_still_403(device_a):
    """Even when target == self (which would yield 400 for a creator),
    a non-creator must hit the 403 signature gate first."""
    payload = device_a.signed({"target_key_id": device_a.key_id})
    r = requests.post(f"{BASE_URL}/api/accounts/delete-one",
                      json=payload, timeout=15)
    assert r.status_code == 403, r.text


def test_04_delete_one_non_creator_missing_target_403(device_a):
    """Missing target_key_id but signed by a non-creator → 403 (signature
    gate fires before pydantic-level body checks on optional fields)."""
    payload = device_a.signed()
    r = requests.post(f"{BASE_URL}/api/accounts/delete-one",
                      json=payload, timeout=15)
    # pydantic may also raise 422 if target_key_id required by model
    assert r.status_code in (403, 422), r.text


# ---------------------------------------------------------------------------
# 2. /api/accounts/delete-all signature gate
# ---------------------------------------------------------------------------
def test_05_delete_all_unsigned_rejected():
    r = requests.post(f"{BASE_URL}/api/accounts/delete-all",
                      json={}, timeout=15)
    assert r.status_code in (400, 401, 403, 422), r.text


def test_06_delete_all_non_creator_signed_403(device_a):
    payload = device_a.signed()
    r = requests.post(f"{BASE_URL}/api/accounts/delete-all",
                      json=payload, timeout=15)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 3. Regression — iter56 /api/accounts/remove-creator still creator-gated
# ---------------------------------------------------------------------------
def test_10_remove_creator_non_creator_403(device_a):
    payload = device_a.signed({"password": "whatever"})
    r = requests.post(f"{BASE_URL}/api/accounts/remove-creator",
                      json=payload, timeout=15)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 4. Regression — iter55 /api/ideas/send anonymous still 200
# ---------------------------------------------------------------------------
def test_20_ideas_send_anonymous():
    marker = f"TEST_iter57_anon_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE_URL}/api/ideas/send",
                      json={"content": marker, "kind": "bug"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True


def test_21_ideas_send_signed_attaches_pseudo(device_a):
    """A signed but non-creator device should still be able to send an idea
    (any device is allowed). 200 expected."""
    marker = f"TEST_iter57_signed_{uuid.uuid4().hex[:8]}"
    payload = device_a.signed({"content": marker, "kind": "idea"})
    r = requests.post(f"{BASE_URL}/api/ideas/send",
                      json=payload, timeout=15)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 5. Regression — /api/accounts/list still creator-gated
# ---------------------------------------------------------------------------
def test_30_accounts_list_rejects_non_creator(device_a):
    r = requests.post(f"{BASE_URL}/api/accounts/list",
                      json=device_a.signed(), timeout=15)
    assert r.status_code == 403, r.text
