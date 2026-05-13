"""Iter 44 — Backend tests for new endpoints:
- /api/system/ollama-status
- /api/projects/{id}/duplicate
- /api/projects/{id}/share (enable/disable)
- /api/share/{slug}  (public, no auth)
- /api/share/{slug}/preview (public HTML)
- /api/share/<unknown> -> 404
- Cascade chat resilience with obscure model
- /api/export/github/{id} pushes to Ph1nt0m-oss/save
- Duplicate project appears in GET /api/projects
"""
import os
import pytest
import requests
from urllib.parse import urlparse

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://no-code-builder-25.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")

EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("session_token")
    assert tok, f"no session_token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def seed_project(headers):
    """Create a small web project we can duplicate / share / export.
    POST /api/projects only accepts name/description/project_type — so we
    POST first, then PUT generated_code via /api/projects/{id}.
    """
    create_payload = {
        "name": "TEST_iter44_share_src",
        "description": "Seed project for iter44 tests",
        "project_type": "web",
    }
    r = requests.post(f"{BASE_URL}/api/projects", json=create_payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), f"create project failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    pid = body.get("project_id") or (body.get("project") or {}).get("project_id")
    assert pid, f"no project_id in response: {body}"

    # Attach generated_code via PUT
    files_payload = {
        "generated_code": {
            "files": [
                {"path": "index.html", "content": "<html><body><h1>Hello iter44</h1></body></html>"},
                {"path": "style.css", "content": "h1{color:#0af}"},
                {"path": "main.js", "content": "console.log('iter44');"},
            ]
        }
    }
    up = requests.put(f"{BASE_URL}/api/projects/{pid}", json=files_payload, headers=headers, timeout=20)
    assert up.status_code == 200, f"PUT project failed: {up.status_code} {up.text[:200]}"
    return pid


# --- 1. Ollama status ---------------------------------------------------------
def test_ollama_status_unavailable():
    r = requests.get(f"{BASE_URL}/api/system/ollama-status", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "available" in data and "models" in data
    # Pod n'a pas Ollama installé -> false / []
    assert data["available"] is False
    assert data["models"] == []


# --- 2. Duplicate project -----------------------------------------------------
def test_duplicate_project(headers, seed_project):
    r = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/duplicate", headers=headers, timeout=20
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("success") is True
    new_pid = body.get("project_id")
    assert new_pid and new_pid != seed_project
    clone = body.get("project") or {}
    assert clone.get("name", "").endswith("(copie)")
    assert clone.get("is_public") is False
    assert clone.get("share_slug") in (None, "")
    assert clone.get("project_type") == "web"
    # generated_code / description preserved
    assert (clone.get("generated_code") or {}).get("files"), "files copied"
    # Verify the clone is fetchable
    g = requests.get(f"{BASE_URL}/api/projects/{new_pid}", headers=headers, timeout=15)
    assert g.status_code == 200, g.text[:200]
    # cleanup
    requests.delete(f"{BASE_URL}/api/projects/{new_pid}", headers=headers, timeout=15)


def test_duplicate_appears_in_list(headers, seed_project):
    r = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/duplicate", headers=headers, timeout=20
    )
    assert r.status_code == 200
    new_pid = r.json()["project_id"]
    lst = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=15)
    assert lst.status_code == 200
    ids = [p.get("project_id") for p in lst.json()]
    assert new_pid in ids, f"clone {new_pid} missing from list"
    requests.delete(f"{BASE_URL}/api/projects/{new_pid}", headers=headers, timeout=15)


# --- 3. Share enable / disable ------------------------------------------------
@pytest.fixture(scope="session")
def shared_slug(headers, seed_project):
    r = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/share",
        json={"enable": True},
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("is_public") is True
    assert body.get("slug")
    assert body.get("url")
    # URL must include a host (full url with scheme://host)
    parsed = urlparse(body["url"])
    assert parsed.scheme in ("http", "https"), f"url has no scheme: {body['url']}"
    assert parsed.netloc, f"url missing host: {body['url']}"
    return body["slug"]


def test_share_enable(shared_slug):
    # fixture asserts already; sanity check
    assert isinstance(shared_slug, str) and len(shared_slug) > 0


def test_share_disable(headers, seed_project, shared_slug):
    r = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/share",
        json={"enable": False},
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("is_public") is False
    assert body.get("slug") is None
    assert body.get("url") is None
    # Re-enable for downstream tests
    r2 = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/share",
        json={"enable": True},
        headers=headers,
        timeout=15,
    )
    assert r2.status_code == 200 and r2.json().get("is_public") is True


# --- 4. Public share endpoints ------------------------------------------------
def test_public_share_metadata(seed_project, headers):
    # ensure project is shared
    r = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/share",
        json={"enable": True},
        headers=headers,
        timeout=15,
    )
    slug = r.json()["slug"]

    # call WITHOUT auth header
    pub = requests.get(f"{BASE_URL}/api/share/{slug}", timeout=15)
    assert pub.status_code == 200, pub.text[:300]
    data = pub.json()
    # required fields
    for k in ("name", "description", "project_type", "files", "created_at"):
        assert k in data, f"missing {k} in public share payload"
    # sensitive fields stripped
    assert "user_id" not in data
    assert "ai_source" not in data
    assert isinstance(data["files"], list) and len(data["files"]) >= 1


def test_public_share_preview_html(seed_project, headers):
    r = requests.post(
        f"{BASE_URL}/api/projects/{seed_project}/share",
        json={"enable": True},
        headers=headers,
        timeout=15,
    )
    slug = r.json()["slug"]

    prev = requests.get(f"{BASE_URL}/api/share/{slug}/preview", timeout=15)
    assert prev.status_code == 200, prev.text[:300]
    ctype = prev.headers.get("content-type", "")
    assert "text/html" in ctype, f"unexpected content-type: {ctype}"
    body = prev.text
    assert "<html" in body.lower()
    assert "Hello iter44" in body  # content from index.html injected


def test_public_share_unknown_slug_404():
    r = requests.get(f"{BASE_URL}/api/share/this-slug-does-not-exist-zzz-9999", timeout=10)
    assert r.status_code == 404


# --- 5. Cascade chat with obscure model ---------------------------------------
def test_chat_cascade_obscure_model(headers):
    payload = {
        "message": "TEST_iter44 reply with the single word OK",
        "model": "inexistant",  # obscure / unknown -> cascade fallback
    }
    r = requests.post(
        f"{BASE_URL}/api/chat/message", json=payload, headers=headers, timeout=90
    )
    # Must NEVER 500. Acceptable: 200 with a response body
    assert r.status_code == 200, f"chat 5xx with obscure model: {r.status_code} {r.text[:400]}"
    data = r.json()
    # Cascade response shape: { user_message, ai_response: {content, ai_source, ...}, project_id }
    text = (
        (data.get("ai_response") or {}).get("content")
        or data.get("response")
        or data.get("message")
        or data.get("content")
        or ""
    )
    assert text, f"empty cascade response: {data}"
    # Cleanup the auto-created project if any
    pid = data.get("project_id")
    if pid:
        requests.delete(f"{BASE_URL}/api/projects/{pid}", headers=headers, timeout=10)


# --- 6. GitHub export uses Ph1nt0m-oss/save -----------------------------------
def test_github_export_pushes_to_save(headers, seed_project):
    r = requests.post(
        f"{BASE_URL}/api/export/github/{seed_project}", headers=headers, timeout=120
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    assert body.get("success") is True, f"github export not success: {body}"
    # Repository must be Ph1nt0m-oss/save now
    repo = body.get("repository", "")
    assert repo.endswith("/save"), f"repo not /save: {repo}"
    assert "Ph1nt0m-oss" in repo, f"owner not Ph1nt0m-oss: {repo}"
    # pushed list non-empty
    pushed = body.get("pushed") or body.get("files_pushed") or body.get("files") or []
    assert pushed, f"pushed list empty: {body}"


# --- cleanup ------------------------------------------------------------------
def test_zz_cleanup_seed(headers, seed_project):
    requests.delete(f"{BASE_URL}/api/projects/{seed_project}", headers=headers, timeout=15)
