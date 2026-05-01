"""
iter_31 tests:
1) Project CRUD — PUT /api/projects/{id} (rename) + DELETE /api/projects/{id}
2) Chat tone — /api/chat/message must be conversational, never technical on greetings
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"

# Words the AI MUST NOT emit on greetings (tech + provider names)
FORBIDDEN_TECH = ["React", "PWA", "LocalStorage", "composant", "hooks", "Ollama", "GPT", "OpenAI"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ==================== Project CRUD ====================

class TestProjectCrud:
    def test_create_rename_and_delete_project(self, session):
        # CREATE
        payload = {"name": "TEST_iter31_proj", "description": "iter31 ctx-menu test"}
        r = session.post(f"{BASE_URL}/api/projects", json=payload, timeout=15)
        assert r.status_code in (200, 201), f"create failed {r.status_code} {r.text}"
        proj = r.json()
        pid = proj.get("project_id") or proj.get("id")
        assert pid, f"no project_id in {proj}"
        assert proj.get("name") == "TEST_iter31_proj"

        # RENAME (PUT)
        new_name = "TEST_iter31_renamed"
        r2 = session.put(f"{BASE_URL}/api/projects/{pid}", json={"name": new_name}, timeout=15)
        assert r2.status_code == 200, f"rename failed {r2.status_code} {r2.text}"
        assert r2.json().get("name") == new_name

        # GET list → verify persisted
        r3 = session.get(f"{BASE_URL}/api/projects", timeout=15)
        assert r3.status_code == 200
        names = [p.get("name") for p in r3.json()]
        assert new_name in names, f"renamed project missing from list: {names}"

        # DELETE
        r4 = session.delete(f"{BASE_URL}/api/projects/{pid}", timeout=15)
        assert r4.status_code in (200, 204), f"delete failed {r4.status_code} {r4.text}"

        # VERIFY removal
        r5 = session.get(f"{BASE_URL}/api/projects", timeout=15)
        ids = [p.get("project_id") for p in r5.json()]
        assert pid not in ids, f"project still present after delete: {ids}"

    def test_delete_nonexistent_returns_404(self, session):
        r = session.delete(f"{BASE_URL}/api/projects/nope_does_not_exist_xyz", timeout=15)
        assert r.status_code == 404

    def test_rename_nonexistent_returns_404(self, session):
        r = session.put(f"{BASE_URL}/api/projects/nope_does_not_exist_xyz",
                        json={"name": "whatever"}, timeout=15)
        assert r.status_code == 404


# ==================== Chat Tone ====================

def _reply(session, message, language):
    r = session.post(f"{BASE_URL}/api/chat/message",
                     json={"message": message, "mode": "online", "language": language},
                     timeout=45)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    data = r.json()
    # try both common field names
    # Response shape: {user_message:{...}, ai_response:{content,...}}
    text = ""
    ai = data.get("ai_response")
    if isinstance(ai, dict):
        text = ai.get("content") or ""
    if not text:
        text = data.get("response") or data.get("message") or ""
    assert text, f"empty chat response: {data}"
    return text


def _assert_no_tech(text):
    lowered = text.lower()
    hit = [w for w in FORBIDDEN_TECH if w.lower() in lowered]
    assert not hit, f"Forbidden tech keyword(s) leaked in greeting reply: {hit} → {text!r}"


def _word_count(s):
    return len(re.findall(r"\w+", s))


class TestChatTone:
    @pytest.mark.parametrize("msg,lang", [
        ("Bonjour", "fr"),
        ("salut", "fr"),
        ("hello", "en"),
        ("hi", "en"),
    ])
    def test_greetings_are_short_and_nontechnical(self, session, msg, lang):
        text = _reply(session, msg, lang)
        _assert_no_tech(text)
        wc = _word_count(text)
        assert wc <= 100, f"greeting too long ({wc} words): {text!r}"
        # ≤ 2 sentences (allow a question mark)
        sentences = [x for x in re.split(r"[.!?]+", text) if x.strip()]
        assert len(sentences) <= 3, f"too many sentences ({len(sentences)}): {text!r}"

    def test_real_tech_question_allowed(self, session):
        text = _reply(session, "comment créer un site de recettes", "fr")
        lowered = text.lower()
        # These specific provider names MUST never appear.
        for banned in ["ollama", "gpt", "openai"]:
            assert banned not in lowered, f"{banned} mentioned on real tech question: {text!r}"
        # Non-empty & reasonable length (not the tiny greeting response)
        assert len(text) > 10
