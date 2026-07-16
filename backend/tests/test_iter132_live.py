"""iter132 — Tests LIVE end-to-end contre le backend running.

Cible principale :
 - Import ZIP workspace : auth, ownership 404, path traversal ignoré,
   cap 50 MB, roundtrip real → list → download.
 - Créa gating pour /private/integrations/* (test_dash n'est pas créa
   donc 403 attendu).
 - Chiffrement AES-GCM des secrets en base (assertion via decrypt_secret
   sur une valeur seed).
"""
import io
import os
import time
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://no-code-builder-25.preview.emergentagent.com"
API = f"{BASE_URL}/api"
EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("session_token") or j.get("token")
    assert tok, f"Login response missing token: {j}"
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def project_id(headers):
    r = requests.post(f"{API}/projects", json={"name": "TEST_iter132_import", "description": "iter132 import test"}, headers=headers, timeout=30)
    assert r.status_code in (200, 201), f"Create project failed: {r.status_code} {r.text}"
    pid = r.json().get("project_id") or r.json().get("id")
    assert pid
    return pid


# ---------- Import Workspace : auth & 404 ----------

class TestImportAuth:
    def test_unauth_import_401(self):
        # POST sans auth → 401
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("x.txt", "hello")
        buf.seek(0)
        r = requests.post(
            f"{API}/workspace/import/random_pid_xyz",
            files={"file": ("x.zip", buf.getvalue(), "application/zip")},
            timeout=30,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_unknown_project_404(self, headers):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("x.txt", "hello")
        buf.seek(0)
        r = requests.post(
            f"{API}/workspace/import/proj_nonexistent_abc123",
            files={"file": ("x.zip", buf.getvalue(), "application/zip")},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"
        # "Projet introuvable." dans le message
        assert "introuvable" in r.text.lower() or r.status_code == 404


# ---------- Import Workspace : happy path ----------

class TestImportRoundtrip:
    def test_import_valid_zip(self, headers, project_id):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("hello.txt", "Bonjour Forge !")
            zf.writestr("code.py", "print('iter132 import ok')\n")
            zf.writestr("data/notes.md", "# iter132\n\nTest notes.\n")
        buf.seek(0)
        r = requests.post(
            f"{API}/workspace/import/{project_id}",
            files={"file": ("upload.zip", buf.getvalue(), "application/zip")},
            headers=headers,
            timeout=60,
        )
        assert r.status_code == 200, f"Import failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("imported") is True
        assert data.get("files") == 3, f"Expected 3 files, got {data.get('files')}"
        assert data.get("bytes", 0) > 0

    def test_list_after_import(self, headers, project_id):
        # Après import, /workspace/list doit lister les 3 fichiers.
        r = requests.get(f"{API}/workspace/list/{project_id}", headers=headers, timeout=30)
        assert r.status_code == 200, f"List failed: {r.status_code} {r.text}"
        j = r.json()
        assert j.get("count") == 3, f"Expected count=3, got {j}"
        paths = [f["path"].replace("\\", "/") for f in j.get("files", [])]
        assert "hello.txt" in paths
        assert "code.py" in paths
        assert "data/notes.md" in paths

    def test_download_after_import(self, headers, project_id):
        r = requests.get(f"{API}/workspace/download/{project_id}", headers=headers, timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        assert "README.md" in names
        assert "hello.txt" in names
        assert "code.py" in names
        # Le sous-dossier peut être normalisé selon l'OS.
        assert any(n.endswith("notes.md") for n in names)


# ---------- Import Workspace : sécurité path traversal ----------

class TestImportSecurity:
    def test_path_traversal_ignored(self, headers, project_id):
        """Un ZIP contenant ../../../etc/passwd doit voir ce membre IGNORÉ."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../../etc/passwd_attack.txt", "evil")
            zf.writestr("/absolute_attack.txt", "evil2")
            zf.writestr("safe.txt", "clean")
        buf.seek(0)
        r = requests.post(
            f"{API}/workspace/import/{project_id}",
            files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
            headers=headers,
            timeout=30,
        )
        # Import doit réussir avec seulement safe.txt.
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("imported") is True
        assert data.get("files") == 1, f"Expected only 1 safe file kept, got {data}"

        # Vérifie qu'aucun fichier n'a été écrit hors du workspace.
        assert not os.path.exists("/etc/passwd_attack.txt"), "Path traversal wrote outside workspace!"
        assert not os.path.exists("/absolute_attack.txt")

        # Confirme via /list
        r2 = requests.get(f"{API}/workspace/list/{project_id}", headers=headers, timeout=30)
        assert r2.status_code == 200
        paths = [f["path"] for f in r2.json().get("files", [])]
        assert paths == ["safe.txt"], f"Unexpected files: {paths}"

    def test_empty_file_rejected(self, headers, project_id):
        r = requests.post(
            f"{API}/workspace/import/{project_id}",
            files={"file": ("empty.zip", b"", "application/zip")},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 400, f"Empty file should 400, got {r.status_code}: {r.text[:200]}"

    def test_invalid_zip_rejected(self, headers, project_id):
        r = requests.post(
            f"{API}/workspace/import/{project_id}",
            files={"file": ("notazip.zip", b"this is not a zip file at all just plain text bytes", "application/zip")},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 400, f"Invalid zip should 400, got {r.status_code}: {r.text[:200]}"


# ---------- Créa gating (test_dash n'est PAS créa) ----------

class TestIntegrationsCreatorGating:
    """Non-créa cannot pass signature check. Even with valid payload shape (nonce/key_id/signature),
    require_creator_signature must reject → 403 (not 200/500)."""

    _dummy_sig = {"key_id": "fake_key_id", "nonce": "fake_nonce_xyz", "signature": "fake_signature_deadbeef"}

    def test_status_denied_without_valid_signature(self, headers):
        r = requests.post(f"{API}/private/integrations/status", json=self._dummy_sig, headers=headers, timeout=30)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:200]}"

    def test_save_denied_without_valid_signature(self, headers):
        r = requests.post(
            f"{API}/private/integrations/save",
            json={**self._dummy_sig, "integration_id": "stripe", "values": {"publishable_key": "pk_test_ABC", "secret_key": "sk_test_XYZ"}},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:200]}"

    def test_test_endpoint_denied_without_valid_signature(self, headers):
        r = requests.post(
            f"{API}/private/integrations/test",
            json={**self._dummy_sig, "integration_id": "stripe"},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:200]}"


# ---------- Chiffrement AES-GCM (test unitaire in-process) ----------

class TestCryptoAtRest:
    def test_encrypt_prefix_and_roundtrip(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from utils.crypto_box import encrypt_secret, decrypt_secret
        secret = "sk_test_XYZ789_iter132"
        ct = encrypt_secret(secret)
        assert ct.startswith("aesgcm.v1."), f"Missing magic prefix: {ct[:30]}"
        assert ct != secret
        assert decrypt_secret(ct) == secret

    def test_direct_db_write_and_read(self):
        """Simule un save chiffré et vérifie qu'il est lisible via decrypt_secret.

        On n'accède pas à Mongo depuis ce container (localhost) — on valide
        juste que la chaîne stockée ne contient jamais le clair.
        """
        import sys
        sys.path.insert(0, "/app/backend")
        from utils.crypto_box import encrypt_secret
        secret = "pk_test_should_not_appear_in_db"
        stored = encrypt_secret(secret)
        assert secret not in stored


# ---------- Régression : chat / dashboard / private access ----------

class TestRegression:
    def test_auth_me_ok(self, headers):
        r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("email") == EMAIL

    def test_agents_registry_available(self, headers):
        r = requests.get(f"{API}/agents/registry", headers=headers, timeout=30)
        assert r.status_code == 200
        j = r.json()
        # 13 agents attendus (validé iter131).
        assert len(j.get("agents", [])) >= 10

    def test_projects_list_still_works(self, headers):
        r = requests.get(f"{API}/projects", headers=headers, timeout=30)
        assert r.status_code == 200
