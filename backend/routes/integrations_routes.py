"""iter131 — Routes /private/integrations/* (Créa+admin only) :
gestion des branchements externes (Stripe / Google / ChatGPT / …).

Version gratuite : slot UI + statut de connexion. AUCUN paiement réel n'est
déclenché ; les clés saisies sont stockées dans la collection MongoDB
`site_integrations` (non chiffrée — usage démo uniquement).

Endpoints :
  - POST /private/integrations/status  : renvoie l'état de chaque intégration
  - POST /private/integrations/save    : upsert une config d'intégration
  - POST /private/integrations/test    : vérifie qu'un couple clé/token est valide

Chaque endpoint exige la signature ECDSA de la créatrice.
"""
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


SUPPORTED_INTEGRATIONS = {
    "stripe": {
        "id": "stripe", "name": "Stripe",
        "description": "Paiements — mode démo (slot UI, aucun paiement réel).",
        "fields": [
            {"key": "publishable_key", "label": "Clé publique (pk_test_…)", "type": "text"},
            {"key": "secret_key", "label": "Clé secrète (sk_test_…)", "type": "password"},
        ],
        "env_hint": "STRIPE_API_KEY",
    },
    "google": {
        "id": "google", "name": "Google (OAuth + Gmail)",
        "description": "Connexion Google et envoi email Gmail (déjà branché via Emergent).",
        "fields": [
            {"key": "client_id", "label": "OAuth Client ID", "type": "text"},
            {"key": "client_secret", "label": "OAuth Client Secret", "type": "password"},
        ],
        "env_hint": "GMAIL_USER",
    },
    "chatgpt": {
        "id": "chatgpt", "name": "ChatGPT (OpenAI)",
        "description": "Modèles GPT-5.2 / GPT-4o via Emergent LLM Key (déjà actif).",
        "fields": [
            {"key": "api_key", "label": "Clé API (sk-…)", "type": "password"},
            {"key": "org_id", "label": "Organization ID (optionnel)", "type": "text"},
        ],
        "env_hint": "EMERGENT_LLM_KEY",
    },
}


class _CreatorSigIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class IntegrationSaveIn(_CreatorSigIn):
    integration_id: str
    values: dict  # {field_key: value}
    enabled: Optional[bool] = True


class IntegrationTestIn(_CreatorSigIn):
    integration_id: str


def _mask(v: str) -> str:
    if not v:
        return ""
    v = str(v)
    if len(v) <= 6:
        return "•" * len(v)
    return f"{v[:3]}{'•' * (len(v) - 6)}{v[-3:]}"


def build_integrations_router(db, *, require_creator_signature):
    router = APIRouter()

    async def _load_configs():
        rows = await db.site_integrations.find({}, {"_id": 0}).to_list(length=50)
        return {r["integration_id"]: r for r in rows if r.get("integration_id")}

    @router.post("/private/integrations/status")
    async def integrations_status(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        configs = await _load_configs()
        out = []
        for iid, spec in SUPPORTED_INTEGRATIONS.items():
            cfg = configs.get(iid) or {}
            values = cfg.get("values") or {}
            fields = []
            for f in spec["fields"]:
                v = values.get(f["key"], "")
                fields.append({
                    **f, "has_value": bool(v),
                    "masked": _mask(v) if v and f["type"] == "password" else (v[:30] if v else ""),
                })
            # Statut auto : détection env ou config MongoDB.
            env_present = bool(os.environ.get(spec.get("env_hint") or ""))
            has_saved = any(f["has_value"] for f in fields)
            enabled = bool(cfg.get("enabled", True))
            status = "connected" if (env_present or has_saved) and enabled else ("configured" if has_saved else "disconnected")
            out.append({
                "id": iid, "name": spec["name"], "description": spec["description"],
                "fields": fields, "enabled": enabled, "status": status,
                "env_present": env_present, "env_hint": spec.get("env_hint"),
                "updated_at": cfg.get("updated_at"),
            })
        return {"integrations": out}

    @router.post("/private/integrations/save")
    async def integrations_save(payload: IntegrationSaveIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        spec = SUPPORTED_INTEGRATIONS.get(payload.integration_id)
        if not spec:
            raise HTTPException(status_code=404, detail="Intégration inconnue.")
        allowed_keys = {f["key"] for f in spec["fields"]}
        clean_values = {k: str(v)[:500] for k, v in (payload.values or {}).items() if k in allowed_keys}
        doc = {
            "integration_id": payload.integration_id,
            "values": clean_values,
            "enabled": bool(payload.enabled),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.site_integrations.update_one(
            {"integration_id": payload.integration_id},
            {"$set": doc},
            upsert=True,
        )
        return {"saved": True, "integration_id": payload.integration_id}

    @router.post("/private/integrations/test")
    async def integrations_test(payload: IntegrationTestIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        iid = payload.integration_id
        spec = SUPPORTED_INTEGRATIONS.get(iid)
        if not spec:
            raise HTTPException(status_code=404, detail="Intégration inconnue.")
        cfg = await db.site_integrations.find_one({"integration_id": iid}, {"_id": 0}) or {}
        values = cfg.get("values") or {}

        # Version gratuite : vérifications syntaxiques + présence d'env.
        if iid == "stripe":
            pk = values.get("publishable_key") or ""
            sk = values.get("secret_key") or ""
            ok = pk.startswith(("pk_test_", "pk_live_")) and sk.startswith(("sk_test_", "sk_live_"))
            msg = "Format des clés valide (mode démo, aucun appel Stripe réel effectué)." if ok else "Format de clé invalide."
        elif iid == "chatgpt":
            k = values.get("api_key") or ""
            env_ok = bool(os.environ.get("EMERGENT_LLM_KEY"))
            ok = env_ok or k.startswith("sk-")
            msg = "Clé Emergent active — ChatGPT opérationnel." if env_ok else ("Format sk- valide." if ok else "Clé absente ou format invalide.")
        elif iid == "google":
            ci = values.get("client_id") or ""
            env_ok = bool(os.environ.get("GMAIL_USER"))
            ok = env_ok or bool(ci and "." in ci)
            msg = "Gmail SMTP actif via env." if env_ok else ("Client ID renseigné." if ok else "Aucune configuration.")
        else:
            ok, msg = False, "Non testé."
        return {"ok": ok, "integration_id": iid, "message": msg}

    return router
