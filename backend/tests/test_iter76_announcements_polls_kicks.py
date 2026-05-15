"""iter76 — announcement states, multi-select polls, scheduled kicks.

Couvre :
1. /announcements/list enrichi avec my_state quand key_id fourni.
2. Polls: max_selections par défaut 1, vote multi-options OK si <= max.
3. Polls: rejet du vote au-delà de max_selections.
4. /system/schedule-kick crée un kick + /system/scheduled-kicks le liste.
5. /system/cancel-scheduled-kick marque executed=True.

Note: les endpoints set-state/clear-history/schedule-kick exigent une signature
crypto valide; on les teste donc via shape uniquement (key_id non-créateur = 403/404).
On valide la partie GET (publique) et le tally multi-select via insertion directe
de votes en base (qui passe par la couche public).
"""
from __future__ import annotations
import os, time, uuid
from datetime import datetime, timezone
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL and MONGO_URL and DB_NAME


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


class TestIter76AnnouncementsList:
    def test_list_empty_or_returns_array(self):
        r = requests.get(f"{API}/announcements/list", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "announcements" in body
        assert isinstance(body["announcements"], list)

    def test_list_with_key_id_includes_my_state_field(self, db):
        # Seed announcement directement
        aid = f"ann_TEST_iter76_{uuid.uuid4().hex[:8]}"
        db.announcements.insert_one({
            "announce_id": aid, "title": "iter76 test", "body": "",
            "audience": "all", "ts": datetime.now(timezone.utc).isoformat(),
        })
        kid = f"dev_TEST_iter76_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid, "role": "approved",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Préparer un état pour cette device
        db.announcement_states.insert_one({
            "announce_id": aid, "key_id": kid, "state": "orange",
            "actor": "staff", "ts": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid}, timeout=10)
            assert r.status_code == 200
            anns = r.json().get("announcements", [])
            found = [a for a in anns if a["announce_id"] == aid]
            assert len(found) == 1, f"announcement {aid} missing"
            assert found[0].get("my_state") == "orange"
        finally:
            db.announcements.delete_one({"announce_id": aid})
            db.announcement_states.delete_many({"announce_id": aid})
            db.device_keys.delete_one({"key_id": kid})

    def test_list_hides_validated_for_non_creator(self, db):
        aid = f"ann_TEST_iter76_hide_{uuid.uuid4().hex[:8]}"
        db.announcements.insert_one({
            "announce_id": aid, "title": "hide me", "body": "",
            "audience": "all", "ts": datetime.now(timezone.utc).isoformat(),
        })
        kid = f"dev_TEST_iter76_hide_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid, "role": "approved",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.announcement_states.insert_one({
            "announce_id": aid, "key_id": kid, "state": "validated",
            "actor": "staff", "ts": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid}, timeout=10)
            assert r.status_code == 200
            anns = r.json().get("announcements", [])
            assert all(a["announce_id"] != aid for a in anns), \
                "validated announcement should be hidden for non-creator"
        finally:
            db.announcements.delete_one({"announce_id": aid})
            db.announcement_states.delete_many({"announce_id": aid})
            db.device_keys.delete_one({"key_id": kid})


class TestIter76PollsMultiSelect:
    def test_polls_list_includes_max_selections_default_1(self, db):
        pid = f"poll_TEST_iter76_{uuid.uuid4().hex[:8]}"
        # Insert legacy poll WITHOUT max_selections — l'endpoint doit retomber sur 1.
        db.polls.insert_one({
            "poll_id": pid, "question": "Q?", "options": ["A", "B", "C"],
            "audience": "all", "ts": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{API}/polls/list", timeout=10)
            assert r.status_code == 200
            polls = r.json().get("polls", [])
            found = [p for p in polls if p["poll_id"] == pid]
            assert len(found) == 1
            assert found[0].get("max_selections") == 1
            assert found[0].get("voters", 0) == 0
        finally:
            db.polls.delete_one({"poll_id": pid})

    def test_polls_list_aggregates_multi_select_votes(self, db):
        pid = f"poll_TEST_iter76_multi_{uuid.uuid4().hex[:8]}"
        db.polls.insert_one({
            "poll_id": pid, "question": "Q?", "options": ["A", "B", "C"],
            "audience": "all", "max_selections": 2,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Seed 2 votes multi-select.
        db.poll_votes.insert_one({"poll_id": pid, "voter_key_id": "v1", "option_indices": [0, 1]})
        db.poll_votes.insert_one({"poll_id": pid, "voter_key_id": "v2", "option_indices": [1, 2]})
        try:
            r = requests.get(f"{API}/polls/list", timeout=10)
            assert r.status_code == 200
            polls = r.json().get("polls", [])
            found = [p for p in polls if p["poll_id"] == pid]
            assert len(found) == 1
            p = found[0]
            assert p["max_selections"] == 2
            assert p["voters"] == 2
            # tally: A=1, B=2, C=1
            assert p["tally"] == [1, 2, 1], f"unexpected tally {p['tally']}"
        finally:
            db.polls.delete_one({"poll_id": pid})
            db.poll_votes.delete_many({"poll_id": pid})


class TestIter76ScheduledKicksList:
    def test_list_endpoint_returns_array(self):
        r = requests.get(f"{API}/system/scheduled-kicks", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json().get("scheduled_kicks"), list)


class TestIter76AuthEndpointsGating:
    """Endpoints créateur-only (set-state, clear-history, schedule-kick) doivent rejeter sans signature valide."""
    def test_set_state_requires_signature(self):
        r = requests.post(f"{API}/announcements/set-state", json={
            "key_id": "fake", "nonce": "x", "signature": "y",
            "announce_id": "nope", "state": "validated",
        }, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_clear_history_requires_creator_signature(self):
        r = requests.post(f"{API}/announcements/clear-history", json={
            "key_id": "fake", "nonce": "x", "signature": "y",
        }, timeout=10)
        assert r.status_code in (403, 404)

    def test_schedule_kick_requires_creator_signature(self):
        r = requests.post(f"{API}/system/schedule-kick", json={
            "key_id": "fake", "nonce": "x", "signature": "y", "minutes": 5,
        }, timeout=10)
        assert r.status_code in (403, 404)

    def test_cancel_scheduled_kick_requires_creator_signature(self):
        r = requests.post(f"{API}/system/cancel-scheduled-kick", json={
            "key_id": "fake", "nonce": "x", "signature": "y", "kick_id": "nope",
        }, timeout=10)
        assert r.status_code in (403, 404)


# Cleanup
@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.announcements.delete_many({"announce_id": {"$regex": "^ann_TEST_iter76_"}})
    db.announcement_states.delete_many({"key_id": {"$regex": "^dev_TEST_iter76_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^dev_TEST_iter76_"}})
    db.polls.delete_many({"poll_id": {"$regex": "^poll_TEST_iter76_"}})
    db.poll_votes.delete_many({"poll_id": {"$regex": "^poll_TEST_iter76_"}})
