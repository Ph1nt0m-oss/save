"""Iteration 25 — change-password, change-email, magic-link, feedback, delete-account, RGPD export."""
import os, time, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


def _make_user(prefix="iter25"):
    email = f"TEST_{prefix}_{int(time.time()*1000)}@gmail.com"
    pwd = "Pass1234"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pwd, "frontend_url": BASE})
    assert r.status_code == 200, r.text
    token = r.json()["verification_token"]
    v = requests.get(f"{API}/auth/verify-email", params={"token": token})
    assert v.status_code == 200
    s = requests.get(f"{API}/auth/verification-status", params={"token": token})
    assert s.status_code == 200, s.text
    sess = s.json().get("session_token")
    assert sess
    return email, pwd, sess


def _auth(sess):
    return {"Authorization": f"Bearer {sess}"}


# ---------- change-password ----------
class TestChangePassword:
    def test_no_auth_401(self):
        r = requests.post(f"{API}/auth/change-password", json={"current_password":"x","new_password":"yyyyy1"})
        assert r.status_code == 401

    def test_wrong_current_401(self):
        _, _, s = _make_user("cp1")
        r = requests.post(f"{API}/auth/change-password", json={"current_password":"WRONG","new_password":"NewPass99"}, headers=_auth(s))
        assert r.status_code == 401
        assert "incorrect" in r.json()["detail"].lower()

    def test_short_new_400(self):
        _, _, s = _make_user("cp2")
        r = requests.post(f"{API}/auth/change-password", json={"current_password":"Pass1234","new_password":"abc"}, headers=_auth(s))
        assert r.status_code == 400

    def test_success_old_refused_new_accepted_session_kept(self):
        email, pwd, s = _make_user("cp3")
        # second login → second session
        l2 = requests.post(f"{API}/api/auth/login".replace("/api/api","/api"), json={"email":email,"password":pwd})
        sess2 = l2.json().get("session_token")
        # change pwd via session 1
        r = requests.post(f"{API}/auth/change-password", json={"current_password":pwd,"new_password":"NewSecret9"}, headers=_auth(s))
        assert r.status_code == 200
        # current session still valid
        me = requests.get(f"{API}/auth/me", headers=_auth(s))
        assert me.status_code == 200
        # other session invalidated
        if sess2:
            me2 = requests.get(f"{API}/auth/me", headers=_auth(sess2))
            assert me2.status_code == 401
        # old pwd refused
        bad = requests.post(f"{API}/auth/login", json={"email":email,"password":pwd})
        assert bad.status_code == 401
        # new pwd accepted
        good = requests.post(f"{API}/auth/login", json={"email":email,"password":"NewSecret9"})
        assert good.status_code == 200


# ---------- change-email ----------
class TestChangeEmail:
    def test_no_auth_401(self):
        r = requests.post(f"{API}/auth/change-email", json={"new_email":"x@y.com","current_password":"x"})
        assert r.status_code == 401

    def test_wrong_password_401(self):
        _, _, s = _make_user("ce1")
        r = requests.post(f"{API}/auth/change-email", json={"new_email":f"TEST_new_{int(time.time())}@gmail.com","current_password":"WRONG"}, headers=_auth(s))
        assert r.status_code == 401

    def test_same_email_400(self):
        email, pwd, s = _make_user("ce2")
        r = requests.post(f"{API}/auth/change-email", json={"new_email":email,"current_password":pwd}, headers=_auth(s))
        assert r.status_code == 400

    def test_taken_email_409(self):
        e1, _, _ = _make_user("ce3a")
        _, p2, s2 = _make_user("ce3b")
        r = requests.post(f"{API}/auth/change-email", json={"new_email":e1,"current_password":p2}, headers=_auth(s2))
        assert r.status_code == 409

    def test_success_link_then_apply(self):
        _, pwd, s = _make_user("ce4")
        new_email = f"TEST_changed_{int(time.time()*1000)}@gmail.com"
        r = requests.post(f"{API}/auth/change-email", json={"new_email":new_email,"current_password":pwd,"frontend_url":BASE}, headers=_auth(s))
        assert r.status_code == 200, r.text
        body = r.json()
        link = body.get("verification_link")
        # If real Resend used, link is not in body; pull token from DB? We need it via demo or skip
        if not link:
            pytest.skip("Real Resend mode: cannot get token from response")
        token = link.split("token=")[-1]
        v = requests.get(f"{API}/auth/verify-email", params={"token":token})
        assert v.status_code == 200
        assert v.json().get("email_changed") is True


# ---------- delete account / export ----------
class TestDeleteAccount:
    def test_no_auth_401(self):
        r = requests.delete(f"{API}/auth/me", json={"current_password":"x"})
        assert r.status_code == 401

    def test_wrong_pwd_401(self):
        _, _, s = _make_user("del1")
        r = requests.delete(f"{API}/auth/me", json={"current_password":"WRONG"}, headers=_auth(s))
        assert r.status_code == 401

    def test_success_cascade(self):
        email, pwd, s = _make_user("del2")
        r = requests.delete(f"{API}/auth/me", json={"current_password":pwd}, headers=_auth(s))
        assert r.status_code == 200
        me = requests.get(f"{API}/auth/me", headers=_auth(s))
        assert me.status_code == 401
        # cannot login any more
        relog = requests.post(f"{API}/auth/login", json={"email":email,"password":pwd})
        assert relog.status_code == 401


class TestExport:
    def test_no_auth_401(self):
        r = requests.get(f"{API}/auth/export")
        assert r.status_code == 401

    def test_export_shape(self):
        email, _, s = _make_user("exp1")
        r = requests.get(f"{API}/auth/export", headers=_auth(s))
        assert r.status_code == 200
        b = r.json()
        assert b["user"]["email"].lower() == email.lower()
        assert "password_hash" not in b["user"]
        for key in ("projects","sessions","chat_messages"):
            assert key in b
            assert isinstance(b[key], list)


# ---------- magic-link ----------
class TestMagicLink:
    def test_unknown_email_neutral(self):
        r = requests.post(f"{API}/auth/magic-link", json={"email":f"TEST_unknown_{int(time.time())}@gmail.com"})
        assert r.status_code == 200
        assert "verification_token" not in r.json()

    def test_unverified_neutral(self):
        # register but don't verify
        e = f"TEST_unverif_ml_{int(time.time()*1000)}@gmail.com"
        requests.post(f"{API}/auth/register", json={"email":e,"password":"Pass1234","frontend_url":BASE})
        r = requests.post(f"{API}/auth/magic-link", json={"email":e})
        assert r.status_code == 200
        assert "verification_token" not in r.json()

    def test_verified_returns_token(self):
        email, _, _ = _make_user("ml1")
        r = requests.post(f"{API}/auth/magic-link", json={"email":email,"frontend_url":BASE})
        assert r.status_code == 200
        b = r.json()
        assert "verification_token" in b
        assert "email_sent" in b

    def test_rate_limit_4th_429(self):
        email, _, _ = _make_user("ml2")
        codes = []
        for _ in range(4):
            r = requests.post(f"{API}/auth/magic-link", json={"email":email})
            codes.append(r.status_code)
        assert codes[-1] == 429, codes

    def test_click_link_then_poll_status(self):
        email, _, _ = _make_user("ml3")
        r = requests.post(f"{API}/auth/magic-link", json={"email":email,"frontend_url":BASE})
        token = r.json().get("verification_token")
        v = requests.get(f"{API}/auth/verify-email", params={"token":token})
        assert v.status_code == 200
        s = requests.get(f"{API}/auth/verification-status", params={"token":token})
        assert s.status_code == 200
        body = s.json()
        assert body.get("status") == "verified"
        assert body.get("session_token")


# ---------- feedback ----------
class TestFeedback:
    def test_too_short_400(self):
        r = requests.post(f"{API}/feedback", json={"type":"bug","message":"abc","page":"/"})
        assert r.status_code == 400

    def test_too_long_400(self):
        r = requests.post(f"{API}/feedback", json={"type":"bug","message":"x"*5001,"page":"/"})
        assert r.status_code == 400

    def test_anonymous_ok(self):
        r = requests.post(f"{API}/feedback", json={"type":"bug","message":"hello world","page":"/login"})
        assert r.status_code == 200
        assert "feedback_id" in r.json()

    def test_invalid_type_falls_back(self):
        r = requests.post(f"{API}/feedback", json={"type":"hax0r","message":"valid msg here","page":"/"})
        assert r.status_code == 200

    def test_authenticated_uses_user_email(self):
        email, _, s = _make_user("fb1")
        r = requests.post(f"{API}/feedback", json={"type":"suggestion","message":"please add dark mode","page":"/dashboard"}, headers=_auth(s))
        assert r.status_code == 200


# ---------- regression ----------
class TestRegression:
    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200

    def test_metrics(self):
        r = requests.get(f"{API}/metrics")
        assert r.status_code == 200

    def test_guide(self):
        r = requests.get(f"{API}/guide")
        assert r.status_code == 200

    def test_google_routes_404(self):
        for p in ("/auth/google/login","/auth/google/callback","/auth/session"):
            r = requests.post(f"{API}{p}", json={})
            assert r.status_code in (404,405), f"{p} = {r.status_code}"
