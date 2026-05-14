"""
Device-bound cryptographic identity (browser WebCrypto ↔ server).

Architecture:
 - Each device generates an ECDSA P-256 key pair in the browser with
   `extractable=false`, stored in IndexedDB (closest browser equivalent
   to a hardware secure-element binding).
 - Public key (JWK) is sent to the server on first visit → `device_keys`.
 - To prove possession, server issues a single-use random nonce; device
   signs it; server verifies signature with the stored public key.
 - First device ever registered is auto-promoted to role='creator'.
 - Subsequent devices land in role='pending' and need creator approval.

Roles: 'creator' | 'approved' | 'pending' | 'revoked'

Site modes:
 - 'public'    : anyone can use the site (login optional). The site-mode
                 toggle is frozen — even the creator cannot flip while public.
                 Wait — per spec the creator CAN flip. We honor that.
 - 'private'   : only approved/creator devices can authenticate.
 - 'creator'   : only creator devices can authenticate.
 - 'guest'     : anyone can browse a read-only preview, but writes (chat,
                 generation, project edit) require auth.
"""

from __future__ import annotations
import base64
import hashlib
import json
import secrets
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicNumbers, SECP256R1, ECDSA
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives import hashes


def _b64url_to_int(s: str) -> int:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(s + pad), "big")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def canonical_jwk(jwk: dict) -> str:
    """Stable JSON serialization of the public JWK for hashing into a key_id."""
    keep = {k: jwk[k] for k in ("kty", "crv", "x", "y") if k in jwk}
    return json.dumps(keep, sort_keys=True, separators=(",", ":"))


def compute_key_id(jwk: dict) -> str:
    """key_id = sha256(canonical_jwk). Stable, public-safe identifier."""
    h = hashlib.sha256(canonical_jwk(jwk).encode("utf-8")).hexdigest()
    return f"dev_{h[:32]}"


def new_nonce() -> str:
    """Cryptographically random 32-byte nonce (URL-safe base64)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def verify_signature(jwk: dict, nonce_b64url: str, signature_b64url: str) -> bool:
    """Verify the device's ECDSA-P256 signature over the raw nonce bytes.

    The browser uses WebCrypto with algorithm `{name: 'ECDSA', hash: 'SHA-256'}`
    which produces an IEEE-P1363 (r||s) raw signature, NOT a DER one. We
    convert it before passing to `cryptography`.
    """
    try:
        if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
            return False
        x = _b64url_to_int(jwk["x"])
        y = _b64url_to_int(jwk["y"])
        pub_numbers = EllipticCurvePublicNumbers(x, y, SECP256R1())
        pub_key = pub_numbers.public_key()

        nonce_bytes = _b64url_decode(nonce_b64url)
        sig_raw = _b64url_decode(signature_b64url)
        if len(sig_raw) != 64:
            return False
        r = int.from_bytes(sig_raw[:32], "big")
        s = int.from_bytes(sig_raw[32:], "big")
        sig_der = encode_dss_signature(r, s)
        pub_key.verify(sig_der, nonce_bytes, ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False
