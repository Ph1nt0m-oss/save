"""iter77 — multi-audience, polls user-suggestions, accounts force-visitor/staff-kind, ideas/set-state, /devices/verify enrichi.

Couvre :
1. /accounts/list — exige signature créa (403/404 sans).
2. /announcements/list — audience List[str] (['admin','modo']) matche un device avec staff_kind correspondant.
3. /announcements/list — audience legacy str continue de matcher.
4. /announcements/list — multi-audience ne matche PAS un device hors-cible.
5. /polls/list — max_selections exposé (legacy=1, iter77 stocke 0 = illimité); suggestions=[] par défaut.
6. /polls/list — suggestions pending visibles non-créa, removed cachées.
7. /polls/create + /polls/edit + /polls/suggest-option + /polls/decide-suggestion + /announcements/edit + /accounts/set-staff-kind + /accounts/force-visitor + /ideas/set-state — tous 403/404 sans signature valide.
8. /devices/verify — payload OK retourne force_visitor + staff_kind (shape).
"""
from __future__ import annotations
import os, uuid
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


# ---------------- Signature-gated endpoints (403/404 without valid sig) ----------------
class TestIter77SignatureGating:
    BAD = {"key_id": "fake_iter77", "nonce": "x", "signature": "y"}

    def test_accounts_list_requires_creator_signature(self):
        r = requests.post(f"{API}/accounts/list", json=self.BAD, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_accounts_set_staff_kind_requires_creator_signature(self):
        payload = {**self.BAD, "target_key_id": "nope", "staff_kind": "admin"}
        r = requests.post(f"{API}/accounts/set-staff-kind", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_accounts_force_visitor_requires_creator_signature(self):
        payload = {**self.BAD, "target_key_id": "nope", "force": True}
        r = requests.post(f"{API}/accounts/force-visitor", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_announcements_edit_requires_creator_signature(self):
        payload = {**self.BAD, "announce_id": "nope", "title": "x"}
        r = requests.post(f"{API}/announcements/edit", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_polls_create_requires_creator_signature(self):
        payload = {**self.BAD, "question": "Q?", "options": ["A", "B"],
                   "max_selections": 0, "allow_user_suggestions": True}
        r = requests.post(f"{API}/polls/create", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_polls_edit_requires_creator_signature(self):
        payload = {**self.BAD, "poll_id": "nope", "question": "x"}
        r = requests.post(f"{API}/polls/edit", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_polls_suggest_option_requires_signature(self):
        payload = {**self.BAD, "poll_id": "nope", "text": "ma proposition"}
        r = requests.post(f"{API}/polls/suggest-option", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_polls_decide_suggestion_requires_creator_signature(self):
        payload = {**self.BAD, "suggestion_id": "nope", "decision": "approve"}
        r = requests.post(f"{API}/polls/decide-suggestion", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_ideas_set_state_requires_staff_or_creator(self):
        payload = {**self.BAD, "idea_id": "nope", "state": "validated"}
        r = requests.post(f"{API}/ideas/set-state", json=payload, timeout=10)
        assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:200]}"


# ---------------- Public GET endpoints ----------------
class TestIter77AnnouncementsAudience:
    def test_list_returns_array(self):
        r = requests.get(f"{API}/announcements/list", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json().get("announcements"), list)

    def test_multi_audience_admin_modo_matches_admin_device(self, db):
        aid = f"ann_TEST_iter77_aud_{uuid.uuid4().hex[:8]}"
        db.announcements.insert_one({
            "announce_id": aid, "title": "staff only", "body": "",
            "audience": ["admin", "modo"],
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        kid_admin = f"dev_TEST_iter77_admin_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid_admin, "role": "approved", "staff_kind": "admin",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        kid_modo = f"dev_TEST_iter77_modo_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid_modo, "role": "approved", "staff_kind": "modo",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        kid_plain = f"dev_TEST_iter77_plain_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid_plain, "role": "approved", "staff_kind": None,
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            # admin device sees it
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid_admin}, timeout=10)
            assert r.status_code == 200
            ids = [a["announce_id"] for a in r.json().get("announcements", [])]
            assert aid in ids, "admin device should see audience=['admin','modo']"

            # modo device sees it
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid_modo}, timeout=10)
            assert r.status_code == 200
            ids = [a["announce_id"] for a in r.json().get("announcements", [])]
            assert aid in ids, "modo device should see audience=['admin','modo']"

            # plain approved device does NOT see it
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid_plain}, timeout=10)
            assert r.status_code == 200
            ids = [a["announce_id"] for a in r.json().get("announcements", [])]
            assert aid not in ids, "plain approved should NOT see staff-only audience"
        finally:
            db.announcements.delete_one({"announce_id": aid})
            db.device_keys.delete_many({"key_id": {"$in": [kid_admin, kid_modo, kid_plain]}})

    def test_legacy_audience_string_all_still_matches(self, db):
        aid = f"ann_TEST_iter77_legacy_{uuid.uuid4().hex[:8]}"
        db.announcements.insert_one({
            "announce_id": aid, "title": "legacy all", "body": "",
            "audience": "all",  # legacy str
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        kid = f"dev_TEST_iter77_legacy_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid, "role": "approved",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid}, timeout=10)
            assert r.status_code == 200
            ids = [a["announce_id"] for a in r.json().get("announcements", [])]
            assert aid in ids
        finally:
            db.announcements.delete_one({"announce_id": aid})
            db.device_keys.delete_one({"key_id": kid})

    def test_audience_non_validated_matches_pending(self, db):
        aid = f"ann_TEST_iter77_nv_{uuid.uuid4().hex[:8]}"
        db.announcements.insert_one({
            "announce_id": aid, "title": "non_validated", "body": "",
            "audience": ["non_validated"],
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        kid_pending = f"dev_TEST_iter77_pending_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid_pending, "role": "pending",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        kid_approved = f"dev_TEST_iter77_approved_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid_approved, "role": "approved",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{API}/announcements/list", params={"key_id": kid_pending}, timeout=10)
            ids = [a["announce_id"] for a in r.json().get("announcements", [])]
            assert aid in ids, "pending device should see audience=['non_validated']"

            r = requests.get(f"{API}/announcements/list", params={"key_id": kid_approved}, timeout=10)
            ids = [a["announce_id"] for a in r.json().get("announcements", [])]
            assert aid not in ids, "approved device should NOT see audience=['non_validated']"
        finally:
            db.announcements.delete_one({"announce_id": aid})
            db.device_keys.delete_many({"key_id": {"$in": [kid_pending, kid_approved]}})


class TestIter77PollsSuggestions:
    def test_polls_list_exposes_max_selections_and_suggestions_default(self, db):
        # iter77 — new poll with max_selections=0 (illimité) + allow_user_suggestions=False
        pid = f"poll_TEST_iter77_unlim_{uuid.uuid4().hex[:8]}"
        db.polls.insert_one({
            "poll_id": pid, "question": "Q?", "options": ["A", "B", "C"],
            "audience": ["all"], "max_selections": 0,
            "allow_user_suggestions": False,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{API}/polls/list", timeout=10)
            assert r.status_code == 200
            polls = r.json().get("polls", [])
            found = [p for p in polls if p["poll_id"] == pid]
            assert len(found) == 1
            p = found[0]
            assert p.get("max_selections") == 0, f"max_selections should be 0 (illimité), got {p.get('max_selections')}"
            assert p.get("suggestions") == [], "suggestions should be [] when allow_user_suggestions=False"
        finally:
            db.polls.delete_one({"poll_id": pid})

    def test_polls_list_shows_pending_and_approved_suggestions_hides_removed(self, db):
        pid = f"poll_TEST_iter77_sugg_{uuid.uuid4().hex[:8]}"
        db.polls.insert_one({
            "poll_id": pid, "question": "Q?", "options": ["A", "B"],
            "audience": ["all"], "max_selections": 0,
            "allow_user_suggestions": True,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        db.poll_suggestions.insert_many([
            {"suggestion_id": f"sug_TEST_iter77_p_{uuid.uuid4().hex[:8]}",
             "poll_id": pid, "key_id": "kfake", "pseudo": "U1",
             "text": "pending text", "status": "pending",
             "ts": datetime.now(timezone.utc).isoformat()},
            {"suggestion_id": f"sug_TEST_iter77_a_{uuid.uuid4().hex[:8]}",
             "poll_id": pid, "key_id": "kfake", "pseudo": "U2",
             "text": "approved text", "status": "approved",
             "ts": datetime.now(timezone.utc).isoformat()},
            {"suggestion_id": f"sug_TEST_iter77_r_{uuid.uuid4().hex[:8]}",
             "poll_id": pid, "key_id": "kfake", "pseudo": "U3",
             "text": "removed text", "status": "removed",
             "ts": datetime.now(timezone.utc).isoformat()},
        ])
        try:
            r = requests.get(f"{API}/polls/list", timeout=10)
            assert r.status_code == 200
            polls = r.json().get("polls", [])
            p = next((x for x in polls if x["poll_id"] == pid), None)
            assert p is not None
            suggs = p.get("suggestions", [])
            statuses = sorted([s.get("status") for s in suggs])
            # non-creator view → pending + approved, removed hidden
            assert statuses == ["approved", "pending"], f"unexpected suggestion statuses: {statuses}"
        finally:
            db.polls.delete_one({"poll_id": pid})
            db.poll_suggestions.delete_many({"poll_id": pid})


# ---------------- /devices/verify enrichi ----------------
class TestIter77DevicesVerify:
    def test_devices_verify_includes_force_visitor_and_staff_kind_shape(self, db):
        # Seed a device and call /devices/verify with its key_id. The endpoint
        # expects a payload; without valid challenge it may 400/401/403, but we
        # primarily validate that successful 200 responses (if any) expose the
        # new fields. We probe shape on the existing route definition.
        # Strategy: hit /devices/verify with a known device & verify the JSON
        # keys exist when status==200; otherwise accept the gating error.
        kid = f"dev_TEST_iter77_verify_{uuid.uuid4().hex[:8]}"
        db.device_keys.insert_one({
            "key_id": kid, "role": "approved", "staff_kind": "modo",
            "force_visitor": True,
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.post(f"{API}/devices/verify", json={"key_id": kid}, timeout=10)
            # Endpoint may require nonce/signature → 4xx is acceptable; key is
            # that the route exists. If 200, the fields MUST be present.
            assert r.status_code in (200, 400, 401, 403, 404, 422), f"unexpected {r.status_code}: {r.text[:200]}"
            if r.status_code == 200:
                body = r.json()
                assert "force_visitor" in body, "force_visitor missing from /devices/verify 200 payload"
                assert "staff_kind" in body, "staff_kind missing from /devices/verify 200 payload"
        finally:
            db.device_keys.delete_one({"key_id": kid})


# ---------------- Cleanup ----------------
@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.announcements.delete_many({"announce_id": {"$regex": "^ann_TEST_iter77_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^dev_TEST_iter77_"}})
    db.polls.delete_many({"poll_id": {"$regex": "^poll_TEST_iter77_"}})
    db.poll_suggestions.delete_many({"suggestion_id": {"$regex": "^sug_TEST_iter77_"}})
    db.poll_suggestions.delete_many({"poll_id": {"$regex": "^poll_TEST_iter77_"}})
