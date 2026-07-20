"""iter150 — Runtime tests for unread_routes (compteurs par conversation).

Utilise un DB mock async léger pour vérifier le comportement des endpoints.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def _make_mock_db(existing_states=None, group_messages=None, direct_messages=None):
    """Construit un mock minimal de la base pour tester les endpoints."""
    db = SimpleNamespace()

    # conversation_read_state
    rs = MagicMock()
    async def _rs_find(*_a, **_kw):
        # find(...).to_list(length=X) → chain
        cursor = SimpleNamespace()
        cursor.to_list = AsyncMock(return_value=existing_states or [])
        return cursor
    rs.find = MagicMock(side_effect=lambda *a, **k: SimpleNamespace(
        to_list=AsyncMock(return_value=existing_states or []),
    ))
    rs.update_one = AsyncMock(return_value=MagicMock(upserted_id=None, modified_count=1))
    db.conversation_read_state = rs

    # group_messages
    gm = MagicMock()
    gm.distinct = AsyncMock(return_value=list((group_messages or {}).keys()))
    async def _gm_count(q):
        gname = q.get("group_type")
        cutoff = None
        if isinstance(q.get("ts"), dict):
            cutoff = q["ts"].get("$gt")
        msgs = (group_messages or {}).get(gname, [])
        # filtre : key_id ne matche pas + ts > cutoff (si présent).
        excl = q.get("key_id", {}).get("$ne") if isinstance(q.get("key_id"), dict) else None
        n = 0
        for m in msgs:
            if excl and m.get("key_id") == excl:
                continue
            if cutoff and m.get("ts", "") <= cutoff:
                continue
            n += 1
        return n
    gm.count_documents = AsyncMock(side_effect=_gm_count)
    db.group_messages = gm

    # direct_messages
    dm = MagicMock()
    dm.distinct = AsyncMock(return_value=list((direct_messages or {}).keys()))
    async def _dm_count(q):
        tid = q.get("thread_id")
        target_key = q.get("to_key_id")
        cutoff = None
        if isinstance(q.get("ts"), dict):
            cutoff = q["ts"].get("$gt")
        msgs = (direct_messages or {}).get(tid, [])
        n = 0
        for m in msgs:
            if target_key and m.get("to_key_id") != target_key:
                continue
            if cutoff and m.get("ts", "") <= cutoff:
                continue
            n += 1
        return n
    dm.count_documents = AsyncMock(side_effect=_dm_count)
    db.direct_messages = dm

    return db


def _build_router_with_signed_verifier():
    """Construit le router avec un verify_signed no-op pour les tests."""
    from routes.unread_routes import build_unread_router
    async def _verify(_kid, _n, _s):
        return True
    return build_unread_router(_make_mock_db(), verify_signed=_verify)


def test_router_builds_without_crash():
    router = _build_router_with_signed_verifier()
    routes = [r.path for r in router.routes]
    assert any('/social/unread-counts' in p for p in routes)
    assert any('/social/mark-read' in p for p in routes)


def test_unread_counts_returns_zero_when_all_read():
    from routes.unread_routes import build_unread_router

    db = _make_mock_db(
        existing_states=[
            {"scope": "group", "conv_id": "public", "last_read_ts": "2026-02-19T23:00:00+00:00"},
        ],
        group_messages={"public": [
            {"key_id": "other", "ts": "2026-02-19T22:00:00+00:00"},  # avant last_read
        ]},
    )

    async def _verify(_kid, _n, _s):
        return True

    router = build_unread_router(db, verify_signed=_verify)
    # Extract handler
    handler = None
    for route in router.routes:
        if 'unread-counts' in route.path:
            handler = route.endpoint
            break
    assert handler is not None

    from routes.unread_routes import _Signed
    payload = _Signed(key_id="me", nonce="x", signature="y")
    result = asyncio.run(handler(payload))
    assert result["total"] == 0
    assert "public" not in result["groups"]


def test_unread_counts_returns_count_when_new_messages():
    from routes.unread_routes import build_unread_router

    db = _make_mock_db(
        existing_states=[
            {"scope": "group", "conv_id": "public", "last_read_ts": "2026-02-19T20:00:00+00:00"},
        ],
        group_messages={"public": [
            {"key_id": "alice", "ts": "2026-02-19T21:00:00+00:00"},
            {"key_id": "bob", "ts": "2026-02-19T22:00:00+00:00"},
            {"key_id": "me", "ts": "2026-02-19T23:00:00+00:00"},  # ignoré (self)
        ]},
    )

    async def _verify(_kid, _n, _s):
        return True

    router = build_unread_router(db, verify_signed=_verify)
    handler = None
    for route in router.routes:
        if 'unread-counts' in route.path:
            handler = route.endpoint
            break

    from routes.unread_routes import _Signed
    payload = _Signed(key_id="me", nonce="x", signature="y")
    result = asyncio.run(handler(payload))
    assert result["groups"]["public"] == 2, f"Attendu 2, obtenu {result['groups']}"
    assert result["total"] == 2


def test_mark_read_persists_state():
    from routes.unread_routes import build_unread_router, MarkReadIn

    db = _make_mock_db()

    async def _verify(_kid, _n, _s):
        return True

    router = build_unread_router(db, verify_signed=_verify)
    handler = None
    for route in router.routes:
        if 'mark-read' in route.path:
            handler = route.endpoint
            break

    payload = MarkReadIn(key_id="me", nonce="n", signature="s",
                        scope="group", conv_id="public")
    result = asyncio.run(handler(payload))
    assert result["ok"] is True
    assert result["scope"] == "group"
    assert result["conv_id"] == "public"
    db.conversation_read_state.update_one.assert_called_once()


def test_mark_read_rejects_invalid_scope():
    from routes.unread_routes import build_unread_router, MarkReadIn
    from fastapi import HTTPException

    db = _make_mock_db()

    async def _verify(_kid, _n, _s):
        return True

    router = build_unread_router(db, verify_signed=_verify)
    handler = None
    for route in router.routes:
        if 'mark-read' in route.path:
            handler = route.endpoint
            break

    payload = MarkReadIn(key_id="me", nonce="n", signature="s",
                        scope="oops", conv_id="public")
    try:
        asyncio.run(handler(payload))
        assert False, "Devait lever HTTPException"
    except HTTPException as e:
        assert e.status_code == 400
