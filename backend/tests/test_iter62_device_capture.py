"""iter62 — Mandatory device-capture screenshot during registration.

Tests:
  - /api/auth/ocr-device-info accepts a base64 image and returns expected shape
  - /api/auth/register validates device_capture_* fields
  - Regression: existing email/password login still works
"""
import os
import time
import base64
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

# 1x1 transparent PNG (tiny but a valid image, Gemini will likely return unknown)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- /auth/ocr-device-info ----------

def test_ocr_empty_payload_rejected(s):
    r = s.post(f"{API}/auth/ocr-device-info", json={"image_base64": ""})
    assert r.status_code == 400


def test_ocr_valid_image_returns_shape(s):
    """The endpoint must return the expected shape (kind/product/model/device_name/confidence).
    Content correctness is NOT asserted — the tiny PNG is unrecognizable, the kind
    will likely be 'unknown'. We only validate the contract."""
    payload = {"image_base64": f"data:image/png;base64,{TINY_PNG_B64}"}
    r = s.post(f"{API}/auth/ocr-device-info", json=payload, timeout=60)
    # Either 200 with proper shape OR 502 if Gemini upstream errors
    assert r.status_code in (200, 502), f"unexpected status={r.status_code} body={r.text[:200]}"
    if r.status_code == 502:
        pytest.skip("Gemini upstream returned an error (transient)")
    data = r.json()
    for k in ("kind", "product", "model", "device_name", "confidence"):
        assert k in data, f"missing key {k} in response: {data}"
    assert data["kind"] in ("phone", "computer", "unknown")
    assert isinstance(data["confidence"], (int, float))


def test_ocr_bare_b64_also_accepted(s):
    """data URL prefix is optional — bare b64 must also work."""
    r = s.post(f"{API}/auth/ocr-device-info", json={"image_base64": TINY_PNG_B64}, timeout=60)
    assert r.status_code in (200, 502)


# ---------- /auth/register validation ----------

def _fresh_email():
    return f"TEST_iter62_{int(time.time()*1000)}_{os.urandom(2).hex()}@example.com"


def _base_payload(**override):
    p = {
        "email": _fresh_email(),
        "password": "Pass1234",
        "pseudo": "tester",
        "frontend_url": BASE_URL,
    }
    p.update(override)
    return p


def test_register_rejected_without_device_capture(s):
    p = _base_payload()  # no device_capture_* fields
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 400
    assert "appareil" in r.text.lower() or "capture" in r.text.lower()


def test_register_phone_missing_product_and_model(s):
    p = _base_payload(device_capture_kind="phone")  # no product, no model
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 400


def test_register_computer_missing_name(s):
    p = _base_payload(device_capture_kind="computer")  # no device_capture_name
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 400


def test_register_pseudo_missing(s):
    p = _base_payload(
        pseudo="",
        device_capture_kind="phone",
        device_capture_product="Galaxy S21 5G",
        device_capture_model="SM-G991U1",
    )
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 400


def test_register_pseudo_too_short(s):
    p = _base_payload(
        pseudo="ab",
        device_capture_kind="phone",
        device_capture_product="Galaxy S21 5G",
        device_capture_model="SM-G991U1",
    )
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 400


def test_register_phone_valid_returns_link(s):
    p = _base_payload(
        device_capture_kind="phone",
        device_capture_product="Galaxy S21 5G",
        device_capture_model="SM-G991U1",
    )
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 200, r.text
    data = r.json()
    # iter59 contract: verification_link always exposed
    assert data.get("verification_link"), f"no verification_link in {data}"
    assert "verify-email?token=" in data["verification_link"]


def test_register_computer_valid_returns_link(s):
    p = _base_payload(
        device_capture_kind="computer",
        device_capture_name="DESKTOP-ABC123",
    )
    r = s.post(f"{API}/auth/register", json=p)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("verification_link")


# ---------- End-to-end regression: register → verify → login ----------

def test_full_flow_register_verify_login(s):
    """Critical regression: ensure the existing login flow still works after iter62.
    Creates a brand-new user with valid phone capture, confirms via the verification
    link, then logs in with email+password."""
    email = _fresh_email()
    pwd = "Pass1234"
    reg = s.post(f"{API}/auth/register", json={
        "email": email,
        "password": pwd,
        "pseudo": "regr62",
        "frontend_url": BASE_URL,
        "device_capture_kind": "phone",
        "device_capture_product": "Galaxy S21 5G",
        "device_capture_model": "SM-G991U1",
    })
    assert reg.status_code == 200, reg.text
    link = reg.json().get("verification_link")
    assert link
    # Extract token from link
    token = link.split("token=", 1)[1].split("&", 1)[0]

    # Hit the verify endpoint
    v = s.get(f"{API}/auth/verify-email", params={"token": token}, allow_redirects=False)
    # The endpoint may redirect, return JSON, or 200 HTML — accept 2xx/3xx
    assert v.status_code in (200, 302, 303, 307), f"verify failed: {v.status_code} {v.text[:200]}"

    # Login
    lg = s.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    assert lg.status_code == 200, lg.text
    data = lg.json()
    # Token may be in different keys depending on implementation
    assert any(k in data for k in ("token", "session_token", "access_token")) or data.get("user")
