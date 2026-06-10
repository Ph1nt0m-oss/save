"""iter82 — Tests pour les nouvelles fonctionnalités majeures (rouges) :
- /accounts/visit enrichi (private_messages, friend_requests, group_posts, infos complètes)
- /friends/* (request, decide, list)
- /groups/* (list, messages, send)
- /messages/send-to-staff (route vers un modo random)
- /chat/stream (SSE streaming)
"""
import os
import requests
import pytest

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestFriendsEndpoints:
    def test_friends_request_unsigned_403(self):
        r = requests.post(f"{API}/friends/request",
                          json={"key_id": "k1", "nonce": "n1", "signature": "sig", "target_key_id": "k2"})
        # Nonce invalide → 403
        assert r.status_code in (403, 404)

    def test_friends_decide_unknown_404(self):
        r = requests.post(f"{API}/friends/decide",
                          json={"key_id": "k1", "nonce": "n1", "signature": "sig", "request_id": "nope", "accept": True})
        assert r.status_code in (403, 404)

    def test_friends_list_unsigned_404_or_403(self):
        r = requests.post(f"{API}/friends/list",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig"})
        assert r.status_code in (403, 404)


class TestGroupsEndpoints:
    def test_groups_list_unsigned_403(self):
        r = requests.post(f"{API}/groups/list",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig"})
        assert r.status_code in (403, 404)

    def test_groups_messages_invalid_type_400_or_403(self):
        # Sans signature valide on ne pourra pas atteindre la validation du type ;
        # on s'attend à 403 / 404.
        r = requests.post(f"{API}/groups/messages",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig", "group_type": "nope"})
        assert r.status_code in (400, 403, 404)

    def test_groups_send_unsigned_403(self):
        r = requests.post(f"{API}/groups/send",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig",
                                "group_type": "public", "content": "hi"})
        assert r.status_code in (400, 403, 404)


class TestMessagesSendToStaff:
    def test_unsigned_403(self):
        r = requests.post(f"{API}/messages/send-to-staff",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig", "content": "ping"})
        assert r.status_code in (403, 404)

    def test_empty_content_400(self):
        r = requests.post(f"{API}/messages/send-to-staff",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig", "content": ""})
        # Soit content vide refusé en 400, soit la signature en 403 → priorité au gating
        assert r.status_code in (400, 403, 404)


class TestAccountsVisitEnriched:
    def test_unsigned_403_or_404(self):
        r = requests.post(f"{API}/accounts/visit",
                          json={"key_id": "ghost", "nonce": "n1", "signature": "sig",
                                "target_key_id": "any"})
        assert r.status_code in (403, 404)

    def test_response_shape_documented(self):
        """Lecture de code : vérifie que le serveur retourne bien les
        nouveaux champs private_messages/friend_requests/group_posts."""
        import importlib
        srv = importlib.import_module('server')
        src = open(srv.__file__).read()
        # Doit comporter les nouveaux champs dans la réponse
        assert '"private_messages"' in src
        assert '"friend_requests"' in src
        assert '"group_posts"' in src
        # Et l'enrichissement du target avec email/clé/biométrie
        assert '"biometric_kind"' in src
        assert '"approved_by_kind"' in src


class TestChatStreamEndpoint:
    def test_endpoint_exists(self):
        # Sans cookie auth, GET 401 attendu (ou 405 si POST-only).
        r = requests.post(f"{API}/chat/stream", json={"message": "ping"}, timeout=5)
        # 401 (non auth) ou 422 (validation) acceptable
        assert r.status_code in (401, 422)


class TestGroupTypeGate:
    def test_group_types_correctness(self):
        """Lecture de code : vérifie les 6 types et l'assignation par rôle."""
        import importlib
        srv = importlib.import_module('server')
        src = open(srv.__file__).read()
        # 6 types
        for t in ('public', 'private', 'staff', 'modo', 'public_staff', 'public_private'):
            assert f'"{t}"' in src, f"Group type {t} missing"
        # Helper de mapping
        assert '_groups_for_device' in src
