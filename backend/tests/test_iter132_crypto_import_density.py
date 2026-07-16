"""iter132 — Tests : chiffrement AES-GCM, import workspace, densité registre."""
from pathlib import Path

ROOT = Path("/app/backend")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


class TestCryptoBox:
    def test_module_exists(self):
        assert (ROOT / "utils/crypto_box.py").is_file()

    def test_roundtrip(self):
        from utils.crypto_box import encrypt_secret, decrypt_secret, is_encrypted
        pt = "sk_test_51234567890abcdef"
        ct = encrypt_secret(pt)
        assert ct != pt
        assert ct.startswith("aesgcm.v1.")
        assert is_encrypted(ct)
        assert decrypt_secret(ct) == pt

    def test_empty(self):
        from utils.crypto_box import encrypt_secret, decrypt_secret
        assert encrypt_secret("") == ""
        assert decrypt_secret("") == ""

    def test_legacy_plaintext_passthrough(self):
        from utils.crypto_box import decrypt_secret, is_encrypted
        assert not is_encrypted("legacy_value_no_prefix")
        assert decrypt_secret("legacy_value_no_prefix") == "legacy_value_no_prefix"

    def test_unique_iv(self):
        from utils.crypto_box import encrypt_secret
        # 2 encryptions du même clair doivent différer (IV aléatoire).
        ct1 = encrypt_secret("same_secret")
        ct2 = encrypt_secret("same_secret")
        assert ct1 != ct2

    def test_tampered_ciphertext_returns_empty(self):
        from utils.crypto_box import encrypt_secret, decrypt_secret
        ct = encrypt_secret("secret")
        tampered = ct[:-4] + "XXXX"
        assert decrypt_secret(tampered) == ""


class TestIntegrationsEncryption:
    def test_uses_crypto_box(self):
        src = _read("routes/integrations_routes.py")
        assert "from utils.crypto_box import" in src
        assert "encrypt_secret" in src
        assert "decrypt_secret" in src

    def test_save_encrypts(self):
        src = _read("routes/integrations_routes.py")
        # dans save : clean_values[k] = encrypt_secret(v)
        assert "encrypt_secret(v)" in src

    def test_status_exposes_encrypted_flag(self):
        src = _read("routes/integrations_routes.py")
        assert '"encrypted"' in src
        assert '"encrypted_at_rest"' in src

    def test_test_endpoint_decrypts(self):
        src = _read("routes/integrations_routes.py")
        # {k: _plain(v) for k, v in raw_values.items()}
        assert "_plain(v)" in src

    def test_save_preserves_existing_unchanged_fields(self):
        src = _read("routes/integrations_routes.py")
        # Champ vide côté client = pas modifié.
        assert "existing_values" in src
        assert "clean_values = dict(existing_values)" in src


class TestWorkspaceImport:
    def test_endpoint_registered(self):
        src = _read("routes/workspace_routes.py")
        assert "@router.post(\"/workspace/import/{project_id}\")" in src

    def test_uploads_zip(self):
        src = _read("routes/workspace_routes.py")
        assert "UploadFile" in src
        assert "zipfile.ZipFile" in src

    def test_path_traversal_blocked(self):
        src = _read("routes/workspace_routes.py")
        assert '".." in name.split("/")' in src or '".." in name' in src
        assert "target_abs.startswith" in src

    def test_max_size_cap(self):
        src = _read("routes/workspace_routes.py")
        assert "50 * 1024 * 1024" in src
        assert "413" in src  # Payload Too Large

    def test_ownership_check(self):
        src = _read("routes/workspace_routes.py")
        # Le import réutilise _ensure_owner.
        assert "_ensure_owner(request, project_id)" in src


class TestFrontendUpdates:
    def test_chat_has_import_button(self):
        src = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
        assert "chat-import-workspace-btn" in src
        assert "chat-import-workspace-input" in src
        assert "/workspace/import/" in src
        assert "importWorkspace" in src

    def test_registry_has_density_toggle(self):
        src = Path("/app/frontend/src/pages/PrivateAgentRegistry.js").read_text(encoding="utf-8")
        assert "registry-density-full" in src
        assert "registry-density-compact" in src
        assert "'compact'" in src
        assert "agent_registry_density" in src  # localStorage
