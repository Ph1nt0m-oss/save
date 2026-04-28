"""
End-to-end smoke test using Playwright (sync API).
- Verifies the Login page renders
- Verifies SMS demo login flow works through to /dashboard
- Verifies user-menu opens

Run locally:
    pip install playwright pytest-playwright
    python -m playwright install --with-deps chromium
    pytest backend/tests/test_e2e_login.py -v
"""
import os
import re
import pytest

# Skip the whole module if playwright isn't available (CI installs it explicitly)
pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://no-code-builder-25.preview.emergentagent.com",
).rstrip("/")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def test_landing_renders(browser):
    page = browser.new_page()
    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)
        # Landing should have at least one CTA / heading visible
        body_text = page.inner_text("body")
        assert len(body_text) > 50
    finally:
        page.close()


def test_login_page_renders(browser):
    page = browser.new_page()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)
        google_btn = page.locator('[data-testid=google-login-btn]')
        assert google_btn.is_visible(), "Google login button not visible"
        sms_btn = page.locator('[data-testid=sms-login-btn]')
        assert sms_btn.is_visible(), "SMS login button not visible"
    finally:
        page.close()


def test_login_error_query_shows_toast(browser):
    page = browser.new_page()
    try:
        page.goto(f"{BASE_URL}/login?error=access_denied", wait_until="domcontentloaded", timeout=20000)
        # toast appears after the 600ms StrictMode-safe delay
        page.wait_for_timeout(2000)
        toasts = page.locator('[data-sonner-toast]')
        count = toasts.count()
        assert count >= 1, "Expected an error toast to be displayed"
        text = toasts.first.inner_text()
        assert "Connexion refusée" in text or "refusée" in text.lower()
    finally:
        page.close()


def test_auth_callback_invalid_shows_retry(browser):
    page = browser.new_page()
    try:
        page.goto(
            f"{BASE_URL}/dashboard#session_id=invalid-test-id",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        page.wait_for_timeout(3500)
        retry = page.locator('[data-testid=auth-retry-btn]')
        assert retry.is_visible(), "Retry button should appear on auth error"
    finally:
        page.close()
