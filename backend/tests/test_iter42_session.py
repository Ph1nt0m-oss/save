"""
Session 42 regression tests:
- Auto-create chat project on first message
- ai_mode/preview_image surfaced in Project responses
- Backfill for legacy projects without ai_mode / updated_at
- Moved internal markdown files must return 404 publicly
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TEST_EMAIL = "test_dash_1777658375@gmail.com"
TEST_PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def auth_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def test_login_credentials(auth_client):
    r = auth_client.get(f"{API}/auth/me")
    assert r.status_code == 200, f"auth/me failed {r.status_code}"
    me = r.json()
    assert me.get("email") == TEST_EMAIL


def test_chat_auto_creates_project(auth_client):
    """POST /api/chat/message without project_id must auto-create a chat project."""
    r = auth_client.post(f"{API}/chat/message", json={
        "message": "TEST_iter42 bonjour quelle est la capitale de la France ?",
        "mode": "online",
        "language": "fr",
    })
    assert r.status_code == 200, f"chat/message failed {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "project_id" in data and data["project_id"], f"project_id missing in response: {data}"
    pid = data["project_id"]

    # Verify project now exists in GET /api/projects
    rp = auth_client.get(f"{API}/projects")
    assert rp.status_code == 200
    projects = rp.json()
    match = [p for p in projects if p.get("project_id") == pid]
    assert match, f"Auto-created project {pid} not found in list"
    proj = match[0]
    assert proj.get("project_type") == "chat"
    assert proj.get("ai_mode") == "online"

    # Generalist answer should NOT push app/site creation (soft check — budget may fallback)
    resp_text = (data.get("response") or "").lower()
    if resp_text and "n'arrive pas à répondre" not in resp_text and "fallback" not in resp_text:
        for kw in ["créer une app", "créer un site", "générer un projet", "veux-tu que je"]:
            assert kw not in resp_text, f"GPT still pushes app creation: found '{kw}' in response"


def test_chat_with_existing_project_id_no_new_project(auth_client):
    """Sending with an existing project_id must not create a new one."""
    # Step 1: auto-create project
    r1 = auth_client.post(f"{API}/chat/message", json={
        "message": "TEST_iter42 premier message",
        "mode": "online", "language": "fr",
    })
    assert r1.status_code == 200
    pid = r1.json()["project_id"]

    # Count before
    before = auth_client.get(f"{API}/projects").json()
    n_before = len(before)

    # Step 2: send with project_id
    r2 = auth_client.post(f"{API}/chat/message", json={
        "message": "TEST_iter42 suite",
        "project_id": pid,
        "mode": "online", "language": "fr",
    })
    assert r2.status_code == 200
    assert r2.json().get("project_id") == pid

    after = auth_client.get(f"{API}/projects").json()
    assert len(after) == n_before, f"Expected same number of projects, got {n_before} → {len(after)}"


def test_get_projects_no_crash_backfill(auth_client):
    """GET /api/projects must not 500 and every project must have ai_mode."""
    r = auth_client.get(f"{API}/projects")
    assert r.status_code == 200, f"GET /projects crashed: {r.status_code} {r.text[:300]}"
    projects = r.json()
    for p in projects:
        assert p.get("ai_mode") in ("online", "offline"), f"Missing ai_mode on {p.get('project_id')}"
        assert p.get("created_at"), "Missing created_at"
        assert p.get("updated_at"), "Missing updated_at (backfill failed)"


def test_project_detail_has_preview_image_and_ai_mode(auth_client):
    """GET /api/projects/{id} returns preview_image (can be None) and ai_mode."""
    # Create a chat project by sending a message
    r = auth_client.post(f"{API}/chat/message", json={
        "message": "TEST_iter42 detail",
        "mode": "online", "language": "fr",
    })
    pid = r.json()["project_id"]

    rd = auth_client.get(f"{API}/projects/{pid}")
    assert rd.status_code == 200
    proj = rd.json()
    assert "preview_image" in proj  # key exists (may be None)
    assert proj.get("ai_mode") in ("online", "offline")


def test_moved_markdown_files_return_404():
    """AMELIORER_LES_IA.md / ENTRAINER_CODEFORGE.md moved to /app/memory — must be 404 publicly."""
    for path in ["/AMELIORER_LES_IA.md", "/ENTRAINER_CODEFORGE.md",
                 "/AMÉLIORER_LES_IA.md", "/ENTRAÎNER_CODEFORGE.md"]:
        r = requests.get(f"{BASE_URL}{path}", allow_redirects=False)
        # SPA fallback may return 200 with index.html. Real success = not serving MD content.
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            assert "html" in ct.lower(), f"{path} still served as MD/plain (ct={ct})"
            # also ensure body is not raw markdown
            body = r.text[:500].lower()
            assert "# am" not in body and "# entra" not in body, f"{path} body looks like raw MD"
        else:
            assert r.status_code in (404, 403), f"{path} unexpected {r.status_code}"
