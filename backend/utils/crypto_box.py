"""iter132 — Chiffrement AES-GCM des secrets stockés en base.

Utilisation :
    from utils.crypto_box import encrypt_secret, decrypt_secret, is_encrypted
    ct = encrypt_secret("sk_test_...")
    pt = decrypt_secret(ct)

La clé maître provient de l'env `INTEGRATIONS_SECRET_KEY` (32 octets base64url).
Si absente, une clé stable est générée depuis SECRET_KEY / MONGO_URL (fallback
démo) — pour prod, définir explicitement `INTEGRATIONS_SECRET_KEY`.
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAGIC = "aesgcm.v1."


def _derive_master_key() -> bytes:
    """Retourne 32 octets. Priorité env `INTEGRATIONS_SECRET_KEY`, sinon
    fallback stable dérivé de SECRET_KEY (base64) — usage démo."""
    raw = os.environ.get("INTEGRATIONS_SECRET_KEY", "").strip()
    if raw:
        try:
            key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
            if len(key) == 32:
                return key
        except Exception:
            pass
    # Fallback : dérive de SECRET_KEY (fixe entre redémarrages).
    seed = (os.environ.get("SECRET_KEY", "") or os.environ.get("MONGO_URL", "codeforge-fallback"))
    return hashlib.sha256(("codeforge-integrations::" + seed).encode()).digest()


_MASTER = _derive_master_key()


def encrypt_secret(plaintext: str) -> str:
    """Retourne une chaîne préfixée `aesgcm.v1.<b64(iv+ct)>` prête pour Mongo."""
    if plaintext is None:
        return ""
    plaintext = str(plaintext)
    if not plaintext:
        return ""
    aes = AESGCM(_MASTER)
    iv = os.urandom(12)
    ct = aes.encrypt(iv, plaintext.encode("utf-8"), None)
    payload = base64.urlsafe_b64encode(iv + ct).decode("ascii").rstrip("=")
    return _MAGIC + payload


def decrypt_secret(token: str) -> str:
    """Retourne le clair. Si le token n'est pas chiffré (legacy), le renvoie tel quel."""
    if not token or not isinstance(token, str):
        return ""
    if not token.startswith(_MAGIC):
        return token  # rétro-compat legacy plaintext
    b64 = token[len(_MAGIC):]
    try:
        raw = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
        iv, ct = raw[:12], raw[12:]
        aes = AESGCM(_MASTER)
        pt = aes.decrypt(iv, ct, None)
        return pt.decode("utf-8")
    except Exception:
        return ""


def is_encrypted(token: str) -> bool:
    return isinstance(token, str) and token.startswith(_MAGIC)
