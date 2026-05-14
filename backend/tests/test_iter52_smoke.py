"""
Iter52 backend smoke test.

Covers ONLY the new/regression claims relevant to iter52. Endpoints that
require an ECDSA-signed creator request (/system/site-mode PUT, /messages/*,
/devices/verify) are validated for CONTRACT (expected HTTP shape / 401-403
on missing signature) only — full WebCrypto round-trips are out of scope
for a smoke pass.

What we DO validate end-to-end:
  - /api/auth/me with the active test user → 200 (regression smoke)
  - /api/chat/message wrapper (asyncio.shield) returns a valid AI response
  - /api/auth/session-decide error contract (unknown id + bad decision)
  - /api/messages/inbox endpoint exists and refuses unsigned (auth contract)
  - Static contract: kick_reason strings 'kick_creator_only' and
    'kick_private' in server.py match translation keys in
    LanguageContext.js (kick_creator_only_body + kick_private_body present).
"""
import os
import re
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

TEST_EMAIL = "test_dash_1777658375@gmail.com"
TEST_PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"Cannot login as test user: {r.status_code} {r.text[:200]}")
    body = r.json()
    return body.get("session_token") or body.get("token"), body.get("user")


def test_01_auth_me_smoke(auth):
    token, _ = auth
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    me = r.json()
    assert me.get("email") == TEST_EMAIL


def test_02_chat_message_wrapper_smoke(auth):
    """Endpoint is wrapped by _run_in_background+asyncio.shield. Smoke: returns
    200 and an AI content payload — confirms the wrapper did NOT regress the
    parameter handling (user_id extracted in wrapper, no Request param leaked
    into _impl)."""
    token, _ = auth
    r = requests.post(
        f"{BASE_URL}/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Ping smoke iter52", "history": []},
        timeout=180,
    )
    assert r.status_code == 200, f"chat/message failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    # Shape returned by current server.py: {ai_response: {content, ...}, user_message: {...}, project_id}
    ai = body.get("ai_response") or {}
    assert ai.get("content"), f"missing ai_response.content: {body}"
    assert body.get("user_message"), f"missing user_message: {body}"


def test_03_messages_inbox_contract(auth):
    """The endpoint is creator-only (ECDSA signature). Without signature → the
    endpoint must reject (401/403/422), NOT return 405 or 500. This confirms
    it's still wired up after iter52 refactors."""
    token, _ = auth
    r = requests.post(
        f"{BASE_URL}/api/messages/inbox",
        headers={"Authorization": f"Bearer {token}"},
        json={},  # missing key_id/nonce/signature
        timeout=15,
    )
    assert r.status_code in (401, 403, 422), f"unexpected: {r.status_code} {r.text[:200]}"


def test_04_session_decide_error_contract(auth):
    """Unknown request_id → 404 'introuvable ou déjà traitée' (iter51 idempotency).
    Bad decision value → 400."""
    token, _ = auth
    r = requests.post(
        f"{BASE_URL}/api/auth/session-decide",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_id": "TEST_iter52_unknown", "decision": "deny"},
        timeout=15,
    )
    assert r.status_code in (404, 400), f"deny smoke: {r.status_code} {r.text[:200]}"

    r2 = requests.post(
        f"{BASE_URL}/api/auth/session-decide",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_id": "x", "decision": "garbage"},
        timeout=15,
    )
    assert r2.status_code == 400, f"bad-decision: {r2.status_code} {r2.text[:200]}"


def test_05_kick_reason_keys_match_translation_keys():
    """Static contract check: the EXACT kick_reason strings emitted by the
    backend in /api/devices/verify (lines ~4193, 4197 of server.py) must
    correspond to translation keys (kick_<reason>_body) declared in
    LanguageContext.js for BOTH 'fr' and 'en' locales. This is what makes
    feature #3 of the review-request work."""
    with open("/app/backend/server.py") as f:
        srv = f.read()
    with open("/app/frontend/src/contexts/LanguageContext.js") as f:
        lang = f.read()

    backend_reasons = set(re.findall(r'kick_reason\s*=\s*"([a-z_]+)"', srv))
    # Sanity: the two new ones we care about exist in backend
    assert "kick_creator_only" in backend_reasons, backend_reasons
    assert "kick_private" in backend_reasons, backend_reasons

    # Each reason needs a _body translation key in fr AND en
    for reason in backend_reasons:
        body_key = f"{reason}_body"
        # Count occurrences (should be at least 2 — one per locale)
        occ = len(re.findall(rf"\b{re.escape(body_key)}:", lang))
        assert occ >= 2, (
            f"Translation key '{body_key}' for backend kick_reason '{reason}' "
            f"missing or only present in 1 locale (found {occ})"
        )

    # The new private/creator_only messages must contain the literal phrasing
    # the review request demands.
    assert "La personne qui a créé ce site souhaite être en privé." in lang
    assert "La personne qui a créé ce site procède à quelques modifications" in lang


def test_06_pwd_suggest_translation_keys_exist():
    """SessionRequestNotifier (deny → suggest password change) requires
    sess_denied_pwd_suggest in both locales."""
    with open("/app/frontend/src/contexts/LanguageContext.js") as f:
        lang = f.read()
    occ = len(re.findall(r"\bsess_denied_pwd_suggest:", lang))
    assert occ >= 2, f"sess_denied_pwd_suggest missing/incomplete (found {occ})"


def test_07_header_buttons_have_required_testids():
    """Static check: MessageButton 'icon' variant uses data-testid
    'message-creator-icon-btn' (mounted in Landing+Dashboard headers), and
    TheftButton uses 'theft-icon-btn'."""
    msg = open("/app/frontend/src/components/MessageButton.jsx").read()
    theft = open("/app/frontend/src/components/TheftButton.jsx").read()
    assert 'data-testid="message-creator-icon-btn"' in msg
    assert 'data-testid="theft-icon-btn"' in theft

    landing = open("/app/frontend/src/pages/Landing.js").read()
    dashboard = open("/app/frontend/src/pages/Dashboard.js").read()
    assert 'MessageButton variant="icon"' in landing
    assert "<TheftButton" in landing
    assert 'MessageButton variant="icon"' in dashboard
    assert "<TheftButton" in dashboard


def test_08_no_capital_creator_string_in_fr():
    """agent_to_agent_context_note: 'Créateur' (capital, masculine) must be
    fully replaced by 'Créatrice' in the FR locale block."""
    with open("/app/frontend/src/contexts/LanguageContext.js") as f:
        lang = f.read()
    # Find the FR block boundaries (very rough — the file declares fr first)
    # and check no 'Créateur' substring within it. Allow 'créateur' lowercase
    # (technical term sometimes); we only ban the capitalised form.
    assert "Créateur" not in lang, "'Créateur' (capital) still present in LanguageContext.js"
