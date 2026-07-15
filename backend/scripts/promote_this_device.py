"""iter128.9 — Script d'administration : promouvoir cet appareil en créa
et supprimer l'ancien créateur.

Usage (depuis /app/backend) :
    python -m scripts.promote_this_device --new-key <KEY_ID_NOUVEAU> --old-key <KEY_ID_ANCIEN>

Où trouver les key_id :
    * Ouvre la Landing/Dashboard sur le nouvel appareil.
    * Bouton "Copier ma clé d'appareil" (icône clé, top-right).
    * Colle la valeur (base64 JWK) et cherche dans la DB via :
        mongosh --eval 'db.device_keys.find({}, {key_id:1, label:1, role:1}).limit(20)'
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


async def main(new_key: str, old_key: str | None):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc).isoformat()

    # 1. Vérifier que le nouveau device existe
    new_dev = await db.device_keys.find_one({"key_id": new_key})
    if not new_dev:
        print(f"❌ Nouveau device introuvable : {new_key}")
        return
    print(f"✅ Nouveau device trouvé : {new_dev.get('label')} ({new_dev.get('role')})")

    # 2. Promouvoir le nouveau en créa
    await db.device_keys.update_one(
        {"key_id": new_key},
        {"$set": {"role": "creator", "promoted_at": now, "staff_kind": None, "force_visitor": False}},
    )
    print(f"✅ {new_key[:14]}… promu en 'creator'")

    # 3. Supprimer/rétrograder l'ancien
    if old_key:
        old_dev = await db.device_keys.find_one({"key_id": old_key})
        if not old_dev:
            print(f"⚠️  Ancien device introuvable : {old_key} — étape ignorée")
        else:
            # Soft-delete cohérent avec iter127
            await db.device_keys.update_one(
                {"key_id": old_key},
                {"$set": {
                    "role": "inactive",
                    "deleted": True,
                    "deleted_at": now,
                    "note": "Auto-demoted iter128.9 (court-circuit hardware)",
                }},
            )
            print(f"✅ Ancien {old_key[:14]}… soft-deleted (role=inactive, deleted=true)")

    # 4. Vérifier qu'il ne reste qu'une seule créa active
    remaining = await db.device_keys.count_documents({"role": "creator", "deleted": {"$ne": True}})
    print(f"ℹ️  Créateurs actifs restants : {remaining}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--new-key", required=True, help="key_id du nouvel appareil à promouvoir")
    p.add_argument("--old-key", required=False, default=None, help="key_id de l'ancien créa à supprimer")
    args = p.parse_args()
    asyncio.run(main(args.new_key, args.old_key))
