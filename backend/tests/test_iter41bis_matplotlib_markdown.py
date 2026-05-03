"""iter_41bis: matplotlib base64 image capture + chat run_python with matplotlib
+ regression of cfaction_engine builders + preview/None handling."""

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


# -------------------- Sandbox: matplotlib base64 capture --------------------
class TestSandboxMatplotlib:
    def test_sandbox_matplotlib_returns_base64_image(self, session):
        code = (
            "import matplotlib.pyplot as plt\n"
            "plt.figure()\n"
            "plt.plot([1,2,3,4],[1,4,9,16])\n"
            "plt.title('Test')\n"
            "plt.show()\n"
            "print('done')\n"
        )
        r = session.post(f"{API}/sandbox/python", json={"code": code, "timeout_sec": 20}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["exit_code"] == 0, d
        assert "images" in d, "Response must contain 'images' key"
        assert isinstance(d["images"], list)
        assert len(d["images"]) >= 1, f"Expected at least 1 image, got {len(d['images'])}"
        img = d["images"][0]
        assert "filename" in img
        assert "mime_type" in img and img["mime_type"].startswith("image/")
        assert "data_base64" in img and len(img["data_base64"]) > 100

    def test_sandbox_matplotlib_no_show_still_captured(self, session):
        # atexit hook must dump even without plt.show()
        code = (
            "import matplotlib.pyplot as plt\n"
            "plt.figure()\n"
            "plt.bar(['a','b'], [3, 5])\n"
        )
        r = session.post(f"{API}/sandbox/python", json={"code": code, "timeout_sec": 20}, timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert d["exit_code"] == 0
        assert len(d.get("images", [])) >= 1


# -------------------- Chat: matplotlib via run_python inlined as data URI --------------------
class TestChatMatplotlib:
    def test_chat_matplotlib_inlines_data_uri(self, session):
        pid = f"TEST_mpl_{uuid.uuid4().hex[:8]}"
        prompt = (
            "Exécute ce code Python : "
            "import matplotlib.pyplot as plt; plt.plot([1,2,3],[2,4,1]); plt.title('demo'); plt.show()"
        )
        r = session.post(
            f"{API}/chat/message",
            json={"message": prompt, "mode": "online", "project_id": pid, "language": "fr"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        content = (r.json().get("ai_response") or {}).get("content", "")
        assert "data:image/" in content and "base64," in content, \
            f"Expected inline base64 image data URI in chat response. Got: {content[:600]}"


# -------------------- Regression after cfaction_engine refactor --------------------
class TestCfactionEngineRegression:
    def test_generate_docx_endpoint(self, session):
        r = session.post(
            f"{API}/chat/generate-docx",
            json={"title": "TEST_iter41bis", "sections": [
                {"heading": "Intro", "content": "Bonjour le monde."}
            ]},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        # Could return JSON with download_id or direct binary
        ctype = r.headers.get("content-type", "").lower()
        if "json" in ctype:
            data = r.json()
            assert any(k in data for k in ("download_id", "url", "filename", "data"))
        else:
            assert len(r.content) > 200

    def test_generate_pdf_endpoint(self, session):
        r = session.post(
            f"{API}/chat/generate-pdf",
            json={"title": "TEST_iter41bis", "sections": [
                {"heading": "S1", "content": "Contenu."}
            ]},
            timeout=60,
        )
        assert r.status_code == 200, r.text

    def test_sandbox_still_works(self, session):
        r = session.post(f"{API}/sandbox/python", json={"code": "print('hello')"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["exit_code"] == 0
        assert "hello" in d["stdout"]

    def test_preview_endpoint_handles_none_generated_code(self, session):
        # Create empty project with no generated_code → must still return 200
        cr = session.post(
            f"{API}/projects",
            json={"name": f"TEST_iter41bis_{int(time.time())}", "project_type": "web"},
            timeout=20,
        )
        if cr.status_code in (200, 201):
            pid = cr.json().get("project_id") or cr.json().get("id")
            try:
                pr = session.get(f"{API}/preview/project/{pid}", timeout=30)
                assert pr.status_code == 200, pr.text[:300]
                assert "html" in pr.headers.get("content-type", "").lower()
            finally:
                session.delete(f"{API}/projects/{pid}", timeout=15)
        else:
            pytest.skip("Could not create project")
