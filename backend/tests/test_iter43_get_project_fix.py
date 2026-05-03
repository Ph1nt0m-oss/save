"""
Session 43 RETEST — targeted tests for GET /api/projects/{project_id} fix
after the KeyError: 'updated_at' crash on auto-created chat projects.

Scope:
  1. Login with test_dash_1777658375@gmail.com / Pass1234
  2. GET /api/projects -> find a chat-type auto-created project (or create one)
  3. GET /api/projects/{id} on the chat project -> expect 200 with:
        ai_mode=='online', updated_at non-null, project_type=='chat'
  4. GET /api/projects/{id} on a legacy web project -> 200 with ai_mode backfilled
  5. GET /api/projects/{id} on a non-existent project -> 404 clean (not 500)
  6. GET /api/projects -> no crash on mixed legacy/new projects
  7. POST /api/chat/message without project_id -> returns project_id
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    token = data.get("session_token")
    assert token, "No session_token returned"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def all_projects(session):
    r = session.get(f"{BASE_URL}/api/projects", timeout=20)
    assert r.status_code == 200, f"GET /api/projects failed: {r.status_code} {r.text[:300]}"
    projects = r.json()
    assert isinstance(projects, list)
    return projects


# ==================== TEST 1: Reconfirm GET /api/projects no-crash ====================

def test_get_projects_list_no_crash(all_projects):
    assert isinstance(all_projects, list)
    # Each project MUST have updated_at + ai_mode after backfill
    for p in all_projects:
        assert p.get("updated_at"), f"updated_at missing on {p.get('project_id')}"
        assert p.get("ai_mode") in ("online", "offline"), f"ai_mode invalid on {p.get('project_id')}: {p.get('ai_mode')}"


# ==================== TEST 2: POST chat without project_id returns project_id ====================

def test_post_chat_without_project_id_returns_project_id(session):
    r = session.post(
        f"{BASE_URL}/api/chat/message",
        json={"message": "TEST_iter43 hello", "mode": "online", "language": "fr"},
        timeout=90,  # LLM can be slow
    )
    assert r.status_code == 200, f"chat failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert data.get("project_id"), f"No project_id in chat response: {data}"
    # Stash it for next tests
    pytest.chat_project_id = data["project_id"]


# ==================== TEST 3: GET /api/projects/{id} on the JUST-created chat project ====================

def test_get_project_chat_auto_created(session):
    proj_id = getattr(pytest, "chat_project_id", None)
    assert proj_id, "Previous test did not set chat_project_id"
    r = session.get(f"{BASE_URL}/api/projects/{proj_id}", timeout=20)
    assert r.status_code == 200, f"GET chat project 500/crash regression: {r.status_code} {r.text[:500]}"
    data = r.json()
    assert data.get("project_id") == proj_id
    assert data.get("updated_at"), "updated_at is null/missing after backfill"
    assert data.get("ai_mode") == "online", f"ai_mode expected 'online', got {data.get('ai_mode')}"
    assert data.get("project_type") == "chat", f"project_type expected 'chat', got {data.get('project_type')}"


# ==================== TEST 4: GET /api/projects/{id} on the pre-existing chat project proj_1884e5250775 ====================

def test_get_project_prod_reported_chat_id(session, all_projects):
    """Re-hit the exact project_id the user reported (if it still exists)."""
    target = "proj_1884e5250775"
    exists = any(p.get("project_id") == target for p in all_projects)
    if not exists:
        pytest.skip(f"{target} not in this user's projects — skipping (still covered by test_3)")
    r = session.get(f"{BASE_URL}/api/projects/{target}", timeout=20)
    assert r.status_code == 200, f"Reported chat project still 500: {r.status_code} {r.text[:500]}"
    data = r.json()
    assert data.get("updated_at"), "updated_at still missing on reported project"
    assert data.get("ai_mode") == "online"
    assert data.get("project_type") == "chat"


# ==================== TEST 5: GET /api/projects/{id} on a legacy web project ====================

def test_get_project_legacy_web(session, all_projects):
    web_projects = [p for p in all_projects if p.get("project_type") == "web"]
    if not web_projects:
        pytest.skip("No web-type project available for this user")
    target = web_projects[0]["project_id"]
    r = session.get(f"{BASE_URL}/api/projects/{target}", timeout=20)
    assert r.status_code == 200, f"GET legacy web project failed: {r.status_code} {r.text[:500]}"
    data = r.json()
    assert data.get("updated_at"), "updated_at missing on legacy web project"
    assert data.get("ai_mode") in ("online", "offline")
    assert data.get("project_type") == "web"


# ==================== TEST 6: GET /api/projects/{id} non-existent -> 404 clean ====================

def test_get_project_not_found_returns_404(session):
    r = session.get(f"{BASE_URL}/api/projects/proj_doesnotexist_zzzz", timeout=20)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert "detail" in data
