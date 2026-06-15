"""iter127 — Vérifie la centralisation des modèles Pydantic.

Les modèles `CreatorSigIn` et `TargetCreatorSigIn` étaient dupliqués
dans 5 fichiers de routes. Désormais ils vivent dans
`/app/backend/models/auth_signatures.py` et sont importés.
"""
from __future__ import annotations

from pathlib import Path


ROUTES = Path("/app/backend/routes")


def test_central_models_module_exists():
    p = Path("/app/backend/models/auth_signatures.py")
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    assert "class CreatorSigIn(BaseModel)" in src
    assert "class TargetCreatorSigIn(CreatorSigIn)" in src
    assert "class SignedIn(BaseModel)" in src
    assert "extra=\"allow\"" in src


def test_models_can_be_imported():
    from models.auth_signatures import CreatorSigIn, TargetCreatorSigIn, SignedIn  # noqa: F401
    assert set(CreatorSigIn.model_fields.keys()) == {"key_id", "nonce", "signature"}
    assert set(SignedIn.model_fields.keys()) == {"key_id", "nonce", "signature"}
    assert "target_key_id" in TargetCreatorSigIn.model_fields


def test_route_files_no_longer_redefine_creator_sig_in():
    """Aucun fichier route ne doit redéfinir `_CreatorSigIn` en local."""
    offenders = []
    for f in ROUTES.glob("*.py"):
        if f.name == "__init__.py":
            continue
        src = f.read_text(encoding="utf-8")
        if "class _CreatorSigIn(BaseModel):" in src or "class CreatorSigIn(BaseModel):" in src:
            offenders.append(f.name)
    assert offenders == [], (
        f"Ces fichiers redéfinissent CreatorSigIn alors qu'il doit être "
        f"importé depuis models.auth_signatures : {offenders}"
    )


def test_route_files_import_central_model():
    """Les fichiers principaux importent désormais depuis models."""
    expected = {
        "accounts_routes.py",
        "announcements_routes.py",
        "exports_routes.py",
        "ideas_routes.py",
        "system_routes.py",
        "community_bots_routes.py",
        "devices_routes.py",
        "messages_routes.py",
        "caly_routes.py",
    }
    missing = []
    for name in expected:
        src = (ROUTES / name).read_text(encoding="utf-8")
        if "from models.auth_signatures import" not in src:
            missing.append(name)
    assert missing == [], f"Import central manquant dans : {missing}"


def test_signed_models_no_longer_redeclare_three_fields():
    """Les modèles spécialisés ne doivent plus redéclarer le triplet
    key_id/nonce/signature ; ils héritent de SignedIn ou _CreatorSigIn."""
    # Liste de modèles dont on a vérifié manuellement la migration.
    expected_files = [
        "messages_routes.py",
        "community_bots_routes.py",
    ]
    for name in expected_files:
        src = (ROUTES / name).read_text(encoding="utf-8")
        # Aucun "key_id: str" ne doit subsister DANS UNE CLASSE LOCALE.
        # On exige juste : pas de "BaseModel)" suivi de 3 champs sig.
        # Approche simple : compter les triplets key_id+nonce+signature.
        triplets = src.count("    key_id: str\n    nonce: str\n    signature: str")
        assert triplets == 0, (
            f"{name} contient encore {triplets} triplets key_id/nonce/signature "
            "non centralisés."
        )
