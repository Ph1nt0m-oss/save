"""
Iter_29 backend tests — POST /api/chat/message
- online (fr) → Emergent GPT-4o short friendly response, no Ollama mentions
- online (en) → English response
- offline (no Ollama) → short localized fallback with ai_source='fallback'
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"

# Forbidden strings from previous long Ollama install prompt
FORBIDDEN_SUBSTRINGS = [
    "Ollama",
    "OLLAMA_SETUP",
    "ollama.com",
    "ollama pull",
    "curl -fsSL https://ollama",
]


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed {r.status_code}: {r.text[:200]}")
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestChatOnlineFr:
    """Online mode FR → GPT-4o conversational"""

    def test_bonjour_fr_is_short_friendly_no_ollama(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            headers=auth_headers,
            json={"message": "Bonjour", "mode": "online", "language": "fr"},
            timeout=20,
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert "ai_response" in body
        ai = body["ai_response"]
        content = ai.get("content", "")
        assert content, "Empty ai_response.content"
        # no Ollama/install leakage
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden.lower() not in content.lower(), f"Forbidden '{forbidden}' in response: {content[:200]}"
        # short-ish
        assert len(content) < 800, f"Response too long ({len(content)} chars): {content[:200]}"
        # ai_source preferred to be emergent:* (any provider/model) but fallback acceptable if key missing
        src = ai.get("ai_source", "")
        assert src.startswith("emergent") or src == "fallback", f"Unexpected source: {src}"
        print(f"[FR online] source={ai.get('ai_source')} len={len(content)} content={content[:120]!r}")


class TestChatOnlineEn:
    """Online mode EN → English response"""

    def test_hello_en_returns_english(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            headers=auth_headers,
            json={"message": "Hello, how are you?", "mode": "online", "language": "en"},
            timeout=20,
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
        ai = r.json().get("ai_response", {})
        content = ai.get("content", "")
        assert content, "Empty content"
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden.lower() not in content.lower()
        # Heuristic: english words expected
        lower = content.lower()
        english_hint = any(w in lower for w in ["hello", "hi", "help", "how", "i'm", "i am", "today", "you"])
        assert english_hint or ai.get("ai_source") == "fallback", f"Doesn't look English: {content[:200]!r}"
        print(f"[EN online] source={ai.get('ai_source')} content={content[:120]!r}")


class TestChatOfflineFallback:
    """Offline mode on a host without Ollama → short localized fallback, ai_source='fallback'"""

    def test_offline_fr_returns_localized_fallback(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            headers=auth_headers,
            json={"message": "Bonjour", "mode": "offline", "language": "fr"},
            timeout=35,
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
        ai = r.json().get("ai_response", {})
        content = ai.get("content", "")
        assert content
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden.lower() not in content.lower(), f"Long install message leaked: {content[:200]}"
        # Should be short fallback message
        assert len(content) < 400, f"Fallback too long ({len(content)}): {content[:200]}"
        assert ai.get("ai_source") == "fallback", f"Expected fallback, got {ai.get('ai_source')}"
        # Must contain french text
        assert any(tok in content.lower() for tok in ["je", "n'arrive", "réessaie", "instant"]), f"Not FR: {content!r}"
        print(f"[FR offline] source={ai.get('ai_source')} content={content!r}")

    def test_offline_en_returns_localized_fallback(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            headers=auth_headers,
            json={"message": "Hello", "mode": "offline", "language": "en"},
            timeout=35,
        )
        assert r.status_code == 200
        ai = r.json().get("ai_response", {})
        content = ai.get("content", "")
        assert len(content) < 400
        assert ai.get("ai_source") == "fallback"
        assert any(tok in content.lower() for tok in ["trouble", "try", "moment"]), f"Not EN fallback: {content!r}"
        print(f"[EN offline] content={content!r}")


class TestChatAuthGate:
    def test_unauth_returns_401(self):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={"message": "Bonjour", "mode": "online", "language": "fr"},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"
