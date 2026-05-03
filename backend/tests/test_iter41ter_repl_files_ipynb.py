"""iter_41ter — Tests for REPL persistent, file uploads, .ipynb export.

Covers:
- POST /api/sandbox/python with session_id (persistent namespace)
- POST /api/sandbox/python without session_id (ephemeral)
- POST /api/sandbox/python with files=[{filename,data_base64}] (pandas/CSV)
- POST /api/sandbox/reset
- Response shape: stdout, stderr, exit_code, timed_out, duration_ms, images, variables, session_id
- GET /api/chat/export-ipynb/{project_id}: happy path + empty messages edge case
"""
import base64
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def auth_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Auth failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- REPL persistent session ---------------------------------------------------
class TestReplPersistent:
    def test_repl_retains_variable_between_calls(self, auth_client):
        sid = f"TEST_iter41ter_{uuid.uuid4().hex[:8]}"
        # call 1: set x
        r1 = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "x = 42\nprint('set')", "session_id": sid},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1.get("exit_code") == 0, d1
        assert d1.get("session_id") == sid
        assert "x" in (d1.get("variables") or []) or any(
            v == "x" or (isinstance(v, dict) and v.get("name") == "x") for v in (d1.get("variables") or [])
        ), f"variables list should contain 'x': {d1.get('variables')}"

        # call 2: use x
        r2 = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "print(x * 2)", "session_id": sid},
            timeout=30,
        )
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2.get("exit_code") == 0, d2
        assert "84" in (d2.get("stdout") or ""), f"stdout did not contain 84: {d2.get('stdout')}"

        # cleanup
        auth_client.post(
            f"{BASE_URL}/api/sandbox/reset", json={"session_id": sid}, timeout=10
        )

    def test_ephemeral_does_not_persist(self, auth_client):
        # Two ephemeral calls — `x` from first must NOT leak into second
        r1 = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "y_ephem = 7\nprint('ok')"},
            timeout=30,
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1.get("exit_code") == 0
        assert d1.get("session_id") in (None, ""), f"ephemeral response should have no session_id: {d1.get('session_id')}"

        r2 = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "print(y_ephem)"},
            timeout=30,
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("exit_code") != 0 or "NameError" in (d2.get("stderr") or ""), (
            f"ephemeral should NOT retain y_ephem, got stdout={d2.get('stdout')} stderr={d2.get('stderr')}"
        )

    def test_response_shape(self, auth_client):
        sid = f"TEST_iter41ter_{uuid.uuid4().hex[:8]}"
        r = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "a=1\nb='hello'\nprint(a,b)", "session_id": sid},
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        # required keys per spec
        for k in ["stdout", "stderr", "exit_code", "timed_out", "duration_ms", "images", "variables", "session_id"]:
            assert k in d, f"missing key {k} in response: {list(d.keys())}"
        assert isinstance(d["images"], list)
        assert isinstance(d["variables"], list)
        assert isinstance(d["duration_ms"], (int, float))
        assert d["session_id"] == sid
        auth_client.post(f"{BASE_URL}/api/sandbox/reset", json={"session_id": sid}, timeout=10)


# --- File upload --------------------------------------------------------------
class TestSandboxFileUpload:
    def test_csv_read_with_pandas(self, auth_client):
        csv_content = b"name,age\nalice,30\nbob,25\n"
        b64 = base64.b64encode(csv_content).decode()
        code = (
            "import pandas as pd\n"
            "df = pd.read_csv('data.csv')\n"
            "print('rows=', len(df))\n"
            "print('first=', df.iloc[0]['name'])\n"
        )
        r = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={
                "code": code,
                "files": [{"filename": "data.csv", "data_base64": b64}],
            },
            timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("exit_code") == 0, f"stderr={d.get('stderr')}"
        out = d.get("stdout") or ""
        assert "rows= 2" in out, out
        assert "first= alice" in out, out


# --- Sandbox reset ------------------------------------------------------------
class TestSandboxReset:
    def test_reset_returns_shape(self, auth_client):
        sid = f"TEST_iter41ter_reset_{uuid.uuid4().hex[:6]}"
        # create a session
        auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "z=99", "session_id": sid},
            timeout=30,
        )
        r = auth_client.post(
            f"{BASE_URL}/api/sandbox/reset",
            json={"session_id": sid},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("session_id") == sid
        assert d.get("reset") is True

        # Verify z no longer exists
        r2 = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "print(z)", "session_id": sid},
            timeout=30,
        )
        d2 = r2.json()
        assert d2.get("exit_code") != 0 or "NameError" in (d2.get("stderr") or "")
        auth_client.post(f"{BASE_URL}/api/sandbox/reset", json={"session_id": sid}, timeout=10)


# --- Export .ipynb ------------------------------------------------------------
class TestExportIpynb:
    @pytest.fixture(scope="class")
    def project_with_messages(self, auth_client):
        """Create a project + 2 chat messages for export tests."""
        pname = f"TEST_iter41ter_ipynb_{int(time.time())}"
        r = auth_client.post(
            f"{BASE_URL}/api/projects",
            json={"name": pname, "description": "ipynb export test"},
            timeout=15,
        )
        if r.status_code not in (200, 201):
            pytest.skip(f"Cannot create project: {r.status_code} {r.text[:200]}")
        pid = r.json().get("project_id") or r.json().get("id")
        assert pid
        # seed messages directly via chat/message endpoint (or fallback to direct DB-less? we'll use /chat/message if available)
        # Use a lightweight seeding via /api/chat/message if present; else skip.
        # Try /api/chat/seed-messages; fallback: we rely on /api/chat/message? Use simple approach: POST /api/chat/message
        try:
            for content in ["Bonjour, comment vas-tu ?", "Code Python please"]:
                auth_client.post(
                    f"{BASE_URL}/api/chat/message",
                    json={"project_id": pid, "message": content, "mode": "online", "language": "fr"},
                    timeout=90,
                )
        except Exception:
            pass
        yield pid
        # cleanup project
        try:
            auth_client.delete(f"{BASE_URL}/api/projects/{pid}", timeout=15)
        except Exception:
            pass

    def test_export_ipynb_happy_path(self, auth_client, project_with_messages):
        pid = project_with_messages
        r = auth_client.get(f"{BASE_URL}/api/chat/export-ipynb/{pid}", timeout=30)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "application/x-ipynb+json" in ct, ct
        import json as _json
        nb = _json.loads(r.content.decode("utf-8"))
        assert nb.get("nbformat") == 4
        cells = nb.get("cells") or []
        assert len(cells) > 0
        # first cell markdown with project title
        first = cells[0]
        assert first.get("cell_type") == "markdown"
        src = "".join(first.get("source") or [])
        assert "TEST_iter41ter_ipynb_" in src, f"title missing in first cell: {src[:200]}"

    def test_export_ipynb_no_messages_returns_400(self, auth_client):
        # create a bare project without messages
        pname = f"TEST_iter41ter_empty_{int(time.time())}"
        r = auth_client.post(
            f"{BASE_URL}/api/projects",
            json={"name": pname, "description": "empty"},
            timeout=15,
        )
        if r.status_code not in (200, 201):
            pytest.skip("cannot create project")
        pid = r.json().get("project_id") or r.json().get("id")
        try:
            resp = auth_client.get(f"{BASE_URL}/api/chat/export-ipynb/{pid}", timeout=20)
            assert resp.status_code == 400, f"expected 400 for empty messages, got {resp.status_code}: {resp.text[:200]}"
            body = resp.json()
            detail = body.get("detail") or ""
            assert "Aucun message" in detail or "exporter" in detail.lower(), detail
        finally:
            try:
                auth_client.delete(f"{BASE_URL}/api/projects/{pid}", timeout=15)
            except Exception:
                pass

    def test_export_ipynb_unknown_project_404(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/chat/export-ipynb/does-not-exist-xyz", timeout=15)
        assert r.status_code == 404


# --- Regression: basic sandbox --------------------------------------------------
class TestBasicSandboxRegression:
    def test_basic_print(self, auth_client):
        r = auth_client.post(
            f"{BASE_URL}/api/sandbox/python",
            json={"code": "print('hello-world')"},
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d.get("exit_code") == 0
        assert "hello-world" in (d.get("stdout") or "")
