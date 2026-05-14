"""
Iter56 backend smoke — /api/accounts/remove-creator new branches.

Scope:
- Endpoint requires creator signature → non-creator device receives 403.
- Endpoint requires `password` field on body (validated only after signature
  check). Without creator role we cannot reach the bcrypt branch from a
  black-box test.
- Regression: /api/ideas/send anonymous still 200 (iter55 contract).
- Regression: /api/accounts/list still creator-gated (iter54 contract).

Note (per review_request): we can't promote a device to "creator" from this
environment, so the new self/other/wrong-password/non-creator branches are
covered statically by code review. This file only validates the gate
contract and the regressions.
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
    """ECDSA-P256 WebCrypto-compatible device identity."""

    def __init__(self):
        self.priv = ec.generate_private_key(ec.SECP256R1())
        pn = self.priv.public_key().public_numbers()
        self.jwk = {"kty": "EC", "crv": "P-256",
                    "x": _int_to_b64u(pn.x), "y": _int_to_b64u(pn.y)}
        self.key_id = None
        self.role = None

    def sign(self, nonce_b64u):
        sig_der = self.priv.sign(_b64u_decode(nonce_b64u), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(sig_der)
        return _b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))

    def register(self, label="iter56-test"):
        r = requests.post(f"{BASE_URL}/api/devices/register",
                          json={"public_key_jwk": self.jwk, "label": label}, timeout=20)
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
        p = {"key_id": self.key_id, "nonce": nonce, "signature": self.sign(nonce)}
        if extra:
            p.update(extra)
        return p


@pytest.fixture(scope="module")
def device_a():
    d = Device()
    d.register("iter56-A")
    return d


# ---------------------------------------------------------------------------
# 0. Sanity
# ---------------------------------------------------------------------------
def test_00_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 1. /api/accounts/remove-creator signature gate
# ---------------------------------------------------------------------------
def test_01_remove_creator_no_signature_rejected():
    r = requests.post(f"{BASE_URL}/api/accounts/remove-creator",
                      json={"password": "whatever"}, timeout=15)
    # missing key_id/nonce/signature → 422 (pydantic) or 401/403
    assert r.status_code in (400, 401, 403, 422), r.text


def test_02_remove_creator_non_creator_signed_403(device_a):
    """device_a is a fresh 'pending' device — must be rejected at the
    creator-signature gate before any branch is evaluated."""
    payload = device_a.signed({"password": "Pass1234"})
    r = requests.post(f"{BASE_URL}/api/accounts/remove-creator",
                      json=payload, timeout=15)
    assert r.status_code == 403, r.text


def test_03_remove_creator_non_creator_with_target_403(device_a):
    payload = device_a.signed({"password": "Pass1234",
                               "target_key_id": device_a.key_id})
    r = requests.post(f"{BASE_URL}/api/accounts/remove-creator",
                      json=payload, timeout=15)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 2. Regression — /api/ideas/send anonymous (iter55 contract)
# ---------------------------------------------------------------------------
def test_10_ideas_send_anonymous_iter56_regression():
    marker = f"TEST_iter56_anon_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE_URL}/api/ideas/send",
                      json={"content": marker, "kind": "bug"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True


def test_11_ideas_send_anonymous_empty_content():
    r = requests.post(f"{BASE_URL}/api/ideas/send",
                      json={"content": "", "kind": "idea"}, timeout=15)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 3. Regression — /api/accounts/list still creator-gated (iter54)
# ---------------------------------------------------------------------------
def test_20_accounts_list_rejects_non_creator(device_a):
    r = requests.post(f"{BASE_URL}/api/accounts/list",
                      json=device_a.signed(), timeout=15)
    assert r.status_code == 403, r.text


def test_21_accounts_list_unsigned_rejected():
    r = requests.post(f"{BASE_URL}/api/accounts/list", json={}, timeout=15)
    assert r.status_code in (400, 401, 403, 422), r.text
