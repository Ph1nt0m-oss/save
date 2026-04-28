"""
Phase 4 backend tests:
- /api/health healthy
- /api/user/stats unauth -> 401
- /api/user/stats with SMS session cookie -> {project_count, member_since, last_login, plan}
- /api/admin/redeploy without secret -> 401
"""
import os
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://no-code-builder-25.preview.emergentagent.com",
).rstrip("/")


def test_health_healthy():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


def test_user_stats_requires_auth():
    r = requests.get(f"{BASE_URL}/api/user/stats", timeout=15)
    assert r.status_code == 401, r.text


def test_admin_redeploy_no_secret_401():
    r = requests.post(f"{BASE_URL}/api/admin/redeploy", timeout=15)
    assert r.status_code == 401


def test_user_stats_with_sms_session():
    phone = "+33612345678"
    s = requests.Session()

    send = s.post(f"{BASE_URL}/api/auth/sms/send",
                  json={"phone_number": phone}, timeout=15)
    assert send.status_code == 200, send.text
    body = send.json()
    assert "code" in body, "Demo mode should return code"
    code = body["code"]

    verify = s.post(f"{BASE_URL}/api/auth/sms/verify",
                    json={"phone_number": phone, "code": code}, timeout=15)
    assert verify.status_code == 200, verify.text
    user = verify.json()
    assert "user_id" in user

    # session_token cookie should now be set on session s
    assert "session_token" in s.cookies.get_dict(), s.cookies.get_dict()

    stats = s.get(f"{BASE_URL}/api/user/stats", timeout=15)
    assert stats.status_code == 200, stats.text
    data = stats.json()
    assert "project_count" in data
    assert "member_since" in data
    assert "last_login" in data
    assert "plan" in data
    assert isinstance(data["project_count"], int)
    assert data["plan"] == "Gratuit illimité"
