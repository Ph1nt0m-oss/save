"""Chantier iter161 — passe 4 (diagnostic finaux).

Tests :
- ViewSimulationBanner affiche TOUJOURS la croix de sortie (y compris en
  vue créa en prévisualisation) — bug cycle des vues simulées.
- La croix ramène viewMode à null (mode écriture réel), pas à 'creator'
  qui est elle-même une simulation.
- /ai/generate-complete-app retourne un job_id en <5s (architecture
  async, évite le timeout Cloudflare 60s).
- GET /ai/generate-job/{id} renvoie l'état du job.
"""
from __future__ import annotations
from pathlib import Path


def test_view_simulation_banner_has_persistent_close():
    """iter161 §simulation — La croix doit être présente sur TOUTE vue
    simulée (y compris isCreatorSelfView). L'ancienne version
    `!isCreatorSelfView && (<button ...>)` empêchait la sortie quand
    l'utilisateur était ramené en vue créa (truthy)."""
    src = Path("/app/frontend/src/components/ViewSimulationBanner.jsx").read_text(encoding="utf-8")
    # Plus de conditionnel `!isCreatorSelfView` autour du bouton.
    assert "!isCreatorSelfView && (" not in src, (
        "La croix de sortie ne doit PAS être conditionnée à !isCreatorSelfView — "
        "elle doit être présente sur toute vue simulée."
    )
    # Le click doit ramener au mode écriture réel (null), pas 'creator'.
    assert "setStoredViewMode(null)" in src, (
        "La croix doit faire setStoredViewMode(null) pour sortir de toute simulation."
    )
    assert 'data-testid="view-simulation-revert"' in src


def test_view_simulation_banner_no_longer_sets_creator():
    """La croix NE DOIT PLUS setStoredViewMode('creator') — c'était la
    cause du bug (viewMode='creator' est truthy donc le bandeau reste
    affiché, mais isCreatorSelfView=true donc pas de croix)."""
    src = Path("/app/frontend/src/components/ViewSimulationBanner.jsx").read_text(encoding="utf-8")
    # Spécifiquement, le onClick de la croix ne doit pas faire ...('creator').
    # On vérifie qu'il n'y a plus de pattern setStoredViewMode('creator') dans
    # le JSX du bandeau (il peut rester ailleurs si lié à une autre action).
    import re
    assert not re.search(r"setStoredViewMode\(\s*['\"]creator['\"]\s*\)", src), (
        "La croix ne doit plus setStoredViewMode('creator') — remplacer par null."
    )


def test_generate_complete_app_is_async_job():
    """iter161 §diag Création — L'endpoint doit créer un job et retourner
    immédiatement {job_id, status: 'pending'} au lieu de bloquer sur
    l'appel LLM (qui dépasse systématiquement les 60s de Cloudflare)."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    # Section de l'endpoint POST /ai/generate-complete-app.
    assert '@api_router.post("/ai/generate-complete-app")' in src
    # L'endpoint doit créer un job_id.
    endpoint_block = src.split('@api_router.post("/ai/generate-complete-app")')[1].split("@api_router")[0]
    assert "generation_jobs.insert_one" in endpoint_block, (
        "L'endpoint doit créer un document dans generation_jobs."
    )
    assert 'return {"job_id"' in endpoint_block or '"job_id":' in endpoint_block, (
        "L'endpoint doit retourner un job_id."
    )
    assert "asyncio.create_task" in endpoint_block, (
        "Le travail LLM doit être lancé en vraie tâche de fond asyncio."
    )


def test_generate_job_status_endpoint_exists():
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert '@api_router.get("/ai/generate-job/{job_id}")' in src, (
        "L'endpoint GET /ai/generate-job/{job_id} doit exister pour le polling."
    )


def test_frontend_create_uses_polling():
    """iter161 §diag Création — Create.js doit poller /ai/generate-job/{id}
    au lieu d'attendre une réponse synchrone de /ai/generate-complete-app."""
    src = Path("/app/frontend/src/pages/Create.js").read_text(encoding="utf-8")
    assert "/ai/generate-job/" in src, (
        "Create.js doit poller /ai/generate-job/{job_id}."
    )
    assert "job_id" in src
    # Plus de timeout 180000 synchrone.
    assert "timeout: 180000" not in src, (
        "Le timeout 3-min synchrone doit avoir disparu (remplacé par polling)."
    )
