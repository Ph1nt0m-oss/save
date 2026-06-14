"""Auto-load env files + shared fixtures for backend tests.

iter121 — Adds `seed_verified_user` helper that bypasses /auth/register
(now requires pseudo + device_capture + biometric) by inserting users
directly into MongoDB. Used by pre-existing tests written before the
mandatory enrollment fields were added.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import bcrypt
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")


def _api_base() -> str:
    base = (
        os.environ.get("REACT_APP_BACKEND_URL_PUBLIC")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "http://localhost:8001"
    )
    return base.rstrip("/") + "/api"


def _mongo():
    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _hash(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def seed_verified_user(
    email: Optional[str] = None,
    password: str = "Pass1234",
    pseudo: Optional[str] = None,
    verified: bool = True,
) -> Tuple[str, str, str]:
    """Insert a user straight into MongoDB to bypass mandatory enrollment
    fields (device capture + biometric) added to /auth/register.

    Returns (email, password, user_id).
    """
    db = _mongo()
    email = (email or f"seed-{uuid.uuid4().hex[:10]}@codeforge.test").lower()
    pseudo = pseudo or email.split("@")[0]
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "password_hash": _hash(password),
        "name": pseudo,
        "pseudo": pseudo,
        "pseudo_lower": pseudo.lower(),
        "verified": verified,
        "created_at": now,
        "last_login": now,
    })
    return email, password, user_id


def seed_session_for(user_id: str, *, auth_type: str = "email") -> str:
    """Create a 7-day session_token in DB for a seeded user."""
    db = _mongo()
    token = "test_sess_" + uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "auth_type": auth_type,
        "created_at": now.isoformat(),
        "last_seen_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })
    return token


@pytest.fixture
def api_base() -> str:
    return _api_base()


@pytest.fixture
def seeded_user():
    """Yield (email, password, user_id) for a freshly seeded verified user."""
    email, pwd, uid = seed_verified_user()
    yield email, pwd, uid
    # Cleanup
    db = _mongo()
    db.users.delete_one({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})


@pytest.fixture
def seeded_session(seeded_user):
    """Yield (email, password, user_id, session_token) for a logged-in user."""
    email, pwd, uid = seeded_user
    token = seed_session_for(uid)
    yield email, pwd, uid, token
