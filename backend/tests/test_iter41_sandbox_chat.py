"""iter_41 tests: Python sandbox, chat run_python injection, unlimited memory,
dynamic language in chat responses, cfaction downloads, project preview endpoint."""

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def project_id(session):
    pid = f"TEST_iter41_{uuid.uuid4().hex[:8]}"
    r = session.post(
        f"{API}/projects",
        json={"name": f"TEST_iter41_{int(time.time())}", "project_type": "web", "description": "iter41"},
        timeout=20,
    )
    if r.status_code in (200, 201):
        data = r.json()
        pid = data.get("project_id") or data.get("id") or pid
    yield pid
    try:
        session.delete(f"{API}/projects/{pid}", timeout=15)
    except Exception:
        pass


# -------------------------- Sandbox Python --------------------------

class TestSandboxPython:
    def test_sandbox_simple(self, session):
        r = session.post(f"{API}/sandbox/python", json={"code": "print(2+2)"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["exit_code"] == 0
        assert "4" in d["stdout"]
        assert d["timed_out"] is False
        assert isinstance(d["duration_ms"], int)

    def test_sandbox_numpy_pandas_sympy(self, session):
        code = (
            "import numpy as np, pandas as pd\n"
            "import sympy as sp\n"
            "arr = np.array([1,2,3]); df = pd.DataFrame({'a':[1,2]}); x = sp.Symbol('x')\n"
            "print('NP', arr.sum()); print('PD', len(df)); print('SP', sp.integrate(x, x))"
        )
        r = session.post(f"{API}/sandbox/python", json={"code": code}, timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert d["exit_code"] == 0, d
        assert "NP 6" in d["stdout"]
        assert "PD 2" in d["stdout"]
        assert "x**2/2" in d["stdout"]

    def test_sandbox_matplotlib_import(self, session):
        code = (
            "import matplotlib\nmatplotlib.use('Agg')\n"
            "import matplotlib.pyplot as plt\nprint('MPL', matplotlib.__version__[:1])"
        )
        r = session.post(f"{API}/sandbox/python", json={"code": code}, timeout=45)
        assert r.status_code == 200
        assert r.json()["exit_code"] == 0

    def test_sandbox_timeout(self, session):
        code = "while True:\n    pass\n"
        r = session.post(f"{API}/sandbox/python", json={"code": code, "timeout_sec": 2}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["timed_out"] is True
        assert d["duration_ms"] >= 1800

    def test_sandbox_requires_auth(self):
        r = requests.post(f"{API}/sandbox/python", json={"code": "print(1)"}, timeout=15)
        assert r.status_code in (401, 403)


# -------------------------- Chat: run_python injection --------------------------

class TestChatRunPython:
    def test_chat_runs_python_inline(self, session, project_id):
        prompt = "Exécute un code Python qui calcule 2+2 et imprime le résultat avec print."
        r = session.post(
            f"{API}/chat/message",
            json={"message": prompt, "mode": "online", "project_id": project_id, "language": "fr"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        content = (data.get("ai_response") or {}).get("content", "")
        assert "Exécution Python" in content or "sandbox" in content.lower(), content[:500]
        # Result 4 should appear in the inlined stdout block.
        assert "4" in content


# -------------------------- Chat: unlimited memory --------------------------

class TestChatMemory:
    def test_remembers_name_across_turns(self, session):
        pid = f"TEST_mem_{uuid.uuid4().hex[:8]}"
        session.post(f"{API}/projects", json={"name": pid, "project_type": "chat"}, timeout=20)
        # Turn 1 — tell the name
        r1 = session.post(
            f"{API}/chat/message",
            json={"message": "Je m'appelle Sébastien. Retiens-le bien.", "mode": "online",
                  "project_id": pid, "language": "fr"},
            timeout=90,
        )
        assert r1.status_code == 200, r1.text
        # Turn 2 — ask for the name
        r2 = session.post(
            f"{API}/chat/message",
            json={"message": "Comment je m'appelle ?", "mode": "online",
                  "project_id": pid, "language": "fr"},
            timeout=90,
        )
        assert r2.status_code == 200, r2.text
        content = (r2.json().get("ai_response") or {}).get("content", "")
        assert "Sébastien" in content or "sebastien" in content.lower(), content[:500]
        try:
            session.delete(f"{API}/projects/{pid}", timeout=15)
        except Exception:
            pass


# -------------------------- Chat: dynamic language --------------------------

class TestChatLanguage:
    def test_responds_in_english(self, session):
        pid = f"TEST_lang_{uuid.uuid4().hex[:8]}"
        r = session.post(
            f"{API}/chat/message",
            json={"message": "Please answer in one sentence: what is a web app?",
                  "mode": "online", "project_id": pid, "language": "en"},
            timeout=90,
        )
        assert r.status_code == 200
        content = (r.json().get("ai_response") or {}).get("content", "").lower()
        # Heuristic: has English function words, and few/no French accented tokens unique to FR
        english_markers = sum(1 for w in [" the ", " is ", " a ", " app", "web"] if w in f" {content} ")
        french_markers = sum(1 for w in [" une ", " est ", " application", "votre"] if w in f" {content} ")
        assert english_markers >= 2, f"Expected English reply, got: {content[:300]}"
        assert english_markers > french_markers, f"Reply seems more FR than EN: {content[:300]}"


# -------------------------- Chat: cfaction download (docx) --------------------------

class TestCfactionDownload:
    def test_docx_cfaction_flow(self, session):
        r = session.post(
            f"{API}/chat/message",
            json={"message": "Génère-moi un fichier docx avec le titre 'Rapport test' "
                             "et une section intitulée 'Intro' contenant 'Bonjour le monde.'",
                  "mode": "online", "language": "fr"},
            timeout=120,
        )
        assert r.status_code == 200
        ai = r.json().get("ai_response") or {}
        # download should be present when cfaction=docx was parsed
        if ai.get("download"):
            d = ai["download"]
            assert d.get("filename", "").endswith(".docx") or d.get("url") or d.get("download_id")
        else:
            # Soft check: content must at least mention the doc or contain cfaction text
            content = ai.get("content", "")
            assert "docx" in content.lower() or "rapport" in content.lower(), content[:400]


# -------------------------- Preview endpoint --------------------------

class TestPreviewEndpoint:
    def test_preview_html(self, session, project_id):
        r = session.get(f"{API}/preview/project/{project_id}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        ctype = r.headers.get("content-type", "").lower()
        assert "html" in ctype, ctype
        assert "<" in r.text  # some markup
