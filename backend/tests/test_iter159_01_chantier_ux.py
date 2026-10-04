"""Chantier iter159 — UX / Dashboard / IA / Autres comptes.

Backend tests dedicated to §3 (auto-title + title_manual) and §5 (rank
model inference — vérifié indirectement par stabilité de /accounts/list).

Tests via HTTP contre le backend en cours (pattern iter158_supplement).

§1 (dashboard 67 %), §2 (états IA réels), §4 (actions always-visible),
§5 (libellé Rang) sont strictement frontend — Playwright + inspection
visuelle hors du périmètre de pytest.
"""
from __future__ import annotations

import os
import uuid
import secrets
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture()
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture()
def session(mongo):
    """Crée un user_sessions pour hitter les endpoints /projects/*."""
    user_id = f"TEST_u159_{uuid.uuid4().hex[:8]}"
    token = f"TEST_sess_{secrets.token_urlsafe(24)}"
    mongo.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield user_id, token
    mongo.user_sessions.delete_many({"session_token": token})
    mongo.projects.delete_many({"user_id": user_id})
    mongo.chat_messages.delete_many({"user_id": user_id})


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# §3.1 — PUT /projects/{id} marque title_manual=True.
# ---------------------------------------------------------------------------

def test_put_project_sets_title_manual_flag(session, mongo):
    user_id, token = session
    r = requests.post(
        f"{API}/projects",
        headers=_headers(token),
        json={"name": "Avant", "project_type": "chat"},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["project_id"]

    doc_before = mongo.projects.find_one({"project_id": pid}, {"_id": 0, "title_manual": 1})
    assert not doc_before.get("title_manual")

    r2 = requests.put(
        f"{API}/projects/{pid}",
        headers=_headers(token),
        json={"name": "Après rename"},
        timeout=15,
    )
    assert r2.status_code == 200, r2.text
    doc_after = mongo.projects.find_one({"project_id": pid}, {"_id": 0, "title_manual": 1, "name": 1})
    assert doc_after["title_manual"] is True
    assert doc_after["name"] == "Après rename"


# ---------------------------------------------------------------------------
# §3.2 — /projects/{id}/auto-title : 404 si inconnu.
# ---------------------------------------------------------------------------

def test_auto_title_404_on_unknown_project(session):
    _, token = session
    r = requests.post(
        f"{API}/projects/proj_unknown_xxx/auto-title",
        headers=_headers(token),
        timeout=15,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# §3.3 — Pas de message user ⇒ noop.
# ---------------------------------------------------------------------------

def test_auto_title_noop_on_empty_project(session):
    _, token = session
    r = requests.post(
        f"{API}/projects",
        headers=_headers(token),
        json={"name": "Vide", "project_type": "chat"},
        timeout=15,
    )
    pid = r.json()["project_id"]

    r2 = requests.post(
        f"{API}/projects/{pid}/auto-title",
        headers=_headers(token),
        timeout=15,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["applied"] is False
    assert body["source"] == "empty"


# ---------------------------------------------------------------------------
# §3.4 — Verrou title_manual : auto-title ne doit JAMAIS écraser un titre
# renommé manuellement, même si on insère ensuite un message user.
# ---------------------------------------------------------------------------

def test_auto_title_respects_title_manual_lock(session, mongo):
    user_id, token = session
    r = requests.post(
        f"{API}/projects",
        headers=_headers(token),
        json={"name": "init", "project_type": "chat"},
        timeout=15,
    )
    pid = r.json()["project_id"]

    # Rename manuel ⇒ verrou.
    requests.put(
        f"{API}/projects/{pid}",
        headers=_headers(token),
        json={"name": "Nom choisi"},
        timeout=15,
    )

    # Insert d'un message user pour que l'auto-title ait matière à travailler.
    mongo.chat_messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "user_id": user_id, "project_id": pid, "role": "user",
        "content": "Peux-tu m'aider à créer une app de recettes ?",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    r2 = requests.post(
        f"{API}/projects/{pid}/auto-title",
        headers=_headers(token),
        timeout=20,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["applied"] is False
    assert body["source"] == "locked"
    assert body["reason"] == "title_manual"

    doc = mongo.projects.find_one({"project_id": pid}, {"_id": 0, "name": 1})
    assert doc["name"] == "Nom choisi"


# ---------------------------------------------------------------------------
# §3.5 — Fallback truncation : sans EMERGENT_LLM_KEY (ou si LLM échoue), on
# obtient toujours un titre court et correctement coupé sur mot entier.
# ---------------------------------------------------------------------------

def test_auto_title_fallback_truncation(session, mongo):
    user_id, token = session
    r = requests.post(
        f"{API}/projects",
        headers=_headers(token),
        json={"name": "Nouveau chat", "project_type": "chat"},
        timeout=15,
    )
    pid = r.json()["project_id"]

    long_msg = (
        "Bonjour, j'aimerais discuter avec toi des bonnes pratiques pour "
        "construire une application web moderne avec FastAPI et React, "
        "c'est volontairement long."
    )
    mongo.chat_messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "user_id": user_id, "project_id": pid, "role": "user",
        "content": long_msg,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    r2 = requests.post(
        f"{API}/projects/{pid}/auto-title",
        headers=_headers(token),
        timeout=30,  # LLM peut mettre quelques secondes.
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    # LLM OU truncation — l'important est qu'un titre court et sain est produit.
    assert body["source"] in ("llm", "truncation")
    assert body["applied"] is True
    assert 1 <= len(body["title"]) <= 60
    assert not body["title"].endswith((" ", ",", ".", ";", ":", "!", "?", "-", "—", "…"))

    doc = mongo.projects.find_one({"project_id": pid}, {"_id": 0, "name": 1, "title_manual": 1})
    assert doc["name"] == body["title"]
    # L'auto-title ne verrouille PAS le titre (title_manual reste falsy).
    assert not doc.get("title_manual")
