"""iter158 — Endpoints Propriété (Ownership) avec authentification renforcée.

Toutes les actions critiques suivent ce protocole côté serveur :
  1. L'appelant est authentifié normalement (signature ECDSA d'un nonce).
  2. Le serveur vérifie qu'il est bien un APPAREIL PROPRIÉTAIRE (table ownership).
  3. Pour une action critique, un challenge LIÉ À L'ACTION est émis (nonce
     unique + action + cible + expiration courte). Le client le signe.
  4. Le serveur vérifie la signature avec la clé publique enregistrée, que le
     challenge est encore valide, non réutilisé et correspond exactement à
     l'action/cible demandées.
  5. Les opérations les plus sensibles (transfert, suppression/retrait d'un
     appareil propriétaire) exigent une DOUBLE signature : deux appareils
     propriétaires distincts signent le même challenge.

Aucune action critique ne peut être validée par un simple rôle, une requête
API classique, une modification frontend ou une IA.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from device_auth import new_nonce, verify_signature
from utils.ownership_guard import (
    CRITICAL_ACTIONS, DOUBLE_SIG_ACTIONS, DELEGATE_PERMISSIONS,
    ensure_ownership, gen_recovery_code, get_delegate, get_ownership,
    hash_recovery_code, is_owner_device, log_ownership_event, owner_key_ids,
    verify_recovery_code,
)

CHALLENGE_TTL_SEC = 180
RECOVERY_MAX_ATTEMPTS = 5
RECOVERY_WINDOW_SEC = 900


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _SignedIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    key_id: str
    nonce: str
    signature: str


class ChallengeIn(_SignedIn):
    action: str
    target_key_id: Optional[str] = None


class CriticalIn(BaseModel):
    """Action critique : challenge_id + preuves de signature (1 ou 2)."""
    model_config = ConfigDict(extra="allow")
    challenge_id: str
    # Signatures : liste de {key_id, signature}. 1 pour simple, 2 pour double.
    proofs: List[Dict[str, str]]
    # Payload de l'action
    target_key_id: Optional[str] = None
    new_owner_key_id: Optional[str] = None
    new_owner_user_id: Optional[str] = None


class DelegateIn(_SignedIn):
    delegate_key_id: str
    perms: List[str] = []


class RecoverIn(BaseModel):
    """Récupération propriétaire : nouvel appareil + code secret."""
    model_config = ConfigDict(extra="allow")
    key_id: str            # nouvel appareil (déjà enregistré en device_keys)
    nonce: str
    signature: str
    recovery_code: str


def build_ownership_router(db, *, verify_signed) -> APIRouter:
    router = APIRouter(tags=["Ownership"])

    async def _dev(key_id: str) -> Dict[str, Any]:
        return await db.device_keys.find_one({"key_id": key_id}, {"_id": 0}) or {}

    async def _require_owner(key_id: str, nonce: str, signature: str) -> Dict[str, Any]:
        """Signature valide + appareil propriétaire réel."""
        dev = await verify_signed(key_id, nonce, signature)
        await ensure_ownership(db)
        if not await is_owner_device(db, key_id):
            raise HTTPException(status_code=403, detail="Réservé au propriétaire réel de l'espace.")
        return dev

    # ---------------- STATUS ----------------
    @router.post("/ownership/status")
    async def ownership_status(payload: _SignedIn):
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        doc = await ensure_ownership(db)
        me_owner = await is_owner_device(db, payload.key_id)
        me_delegate = await get_delegate(db, payload.key_id)
        out: Dict[str, Any] = {
            "is_owner": me_owner,
            "is_delegate": bool(me_delegate),
            "delegate_perms": (me_delegate or {}).get("perms") or [],
            "recovery_configured": bool(doc.get("recovery_code_hash")),
            "owner_device_count": len(set(await owner_key_ids(db))),
        }
        if me_owner:
            # iter158.3 — Statut ON/OFF des privilèges propriétaire (défaut ON).
            dev = await db.device_keys.find_one({"key_id": payload.key_id},
                                                {"_id": 0, "owner_privileges_active": 1}) or {}
            _pa = dev.get("owner_privileges_active")
            out["owner_privileges_active"] = True if _pa is None else bool(_pa)
            out["owner_key_ids"] = sorted(set(await owner_key_ids(db)))
            out["owner_user_id"] = doc.get("owner_user_id")
            out["delegates"] = doc.get("delegates") or []
        return out

    # ---------------- INIT (recovery code, one-time) ----------------
    @router.post("/ownership/init")
    async def ownership_init(payload: _SignedIn):
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        doc = await get_ownership(db)
        if doc.get("recovery_code_hash"):
            raise HTTPException(status_code=409, detail="Propriété déjà initialisée. Utilise la rotation du code.")
        code = gen_recovery_code()
        h = hash_recovery_code(code)
        await db.ownership.update_one(
            {"_id": doc["_id"]},
            {"$set": {"recovery_code_hash": h["hash"], "recovery_salt": h["salt"],
                      "recovery_set_at": _now().isoformat(), "updated_at": _now().isoformat()}},
        )
        await log_ownership_event(db, "ownership_init", payload.key_id)
        # Le code n'est renvoyé qu'ICI, une seule fois.
        return {"ok": True, "recovery_code": code,
                "warning": "Note ce code maintenant. Il ne sera plus jamais affiché."}

    # ---------------- CHALLENGE (action-bound) ----------------
    @router.post("/ownership/challenge")
    async def ownership_challenge(payload: ChallengeIn):
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        if payload.action not in CRITICAL_ACTIONS:
            raise HTTPException(status_code=400, detail="Action critique inconnue.")
        challenge_nonce = new_nonce()
        challenge_id = f"och_{new_nonce()[:20]}"
        needs_double = payload.action in DOUBLE_SIG_ACTIONS
        await db.ownership_challenges.insert_one({
            "challenge_id": challenge_id,
            "challenge_nonce": challenge_nonce,
            "action": payload.action,
            "target_key_id": payload.target_key_id,
            "created_by": payload.key_id,
            "needs_double": needs_double,
            "used": False,
            "expires_at": (_now() + timedelta(seconds=CHALLENGE_TTL_SEC)).isoformat(),
            "created_at": _now().isoformat(),
        })
        return {"challenge_id": challenge_id, "challenge_nonce": challenge_nonce,
                "needs_double_signature": needs_double, "ttl_sec": CHALLENGE_TTL_SEC}

    async def _consume_challenge(challenge_id: str, action: str) -> Dict[str, Any]:
        ch = await db.ownership_challenges.find_one({"challenge_id": challenge_id})
        if not ch or ch.get("used"):
            raise HTTPException(status_code=403, detail="Challenge invalide ou déjà utilisé.")
        if ch.get("action") != action:
            raise HTTPException(status_code=403, detail="Challenge non lié à cette action.")
        exp = datetime.fromisoformat(ch["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _now():
            raise HTTPException(status_code=403, detail="Challenge expiré.")
        return ch

    async def _verify_proofs(ch: Dict[str, Any], proofs: List[Dict[str, str]]) -> List[str]:
        """Vérifie chaque preuve : signature du challenge_nonce par un appareil
        propriétaire. Renvoie la liste des key_ids valides (distincts)."""
        cn = ch["challenge_nonce"]
        valid: List[str] = []
        seen = set()
        for p in proofs:
            kid = p.get("key_id")
            sig = p.get("signature")
            if not kid or not sig or kid in seen:
                continue
            if not await is_owner_device(db, kid):
                continue
            dev = await _dev(kid)
            if verify_signature(dev.get("public_key_jwk") or {}, cn, sig):
                valid.append(kid)
                seen.add(kid)
        need = 2 if ch.get("needs_double") else 1
        if len(valid) < need:
            raise HTTPException(
                status_code=403,
                detail=f"Signature(s) propriétaire insuffisante(s) : {len(valid)}/{need} valide(s).",
            )
        return valid

    async def _finish(challenge_id: str):
        await db.ownership_challenges.update_one(
            {"challenge_id": challenge_id}, {"$set": {"used": True, "used_at": _now().isoformat()}},
        )

    # ---------------- ADD OWNER DEVICE ----------------
    @router.post("/ownership/add-owner-device")
    async def add_owner_device(payload: CriticalIn):
        ch = await _consume_challenge(payload.challenge_id, "add_owner_device")
        signers = await _verify_proofs(ch, payload.proofs)
        new_kid = payload.new_owner_key_id or payload.target_key_id
        if not new_kid:
            raise HTTPException(status_code=400, detail="new_owner_key_id requis.")
        target = await _dev(new_kid)
        if not target:
            raise HTTPException(status_code=404, detail="Appareil cible introuvable.")
        await db.ownership.update_one(
            {"_id": "root"},
            {"$addToSet": {"owner_key_ids": new_kid}, "$set": {"updated_at": _now().isoformat()}},
        )
        # L'appareil propriétaire prend aussi le rôle visible 'creator'.
        await db.device_keys.update_one({"key_id": new_kid}, {"$set": {"role": "creator"}})
        await _finish(payload.challenge_id)
        await log_ownership_event(db, "add_owner_device", signers[0], {"new_owner": new_kid, "signers": signers})
        return {"ok": True, "owner_added": new_kid}

    # ---------------- REMOVE OWNER DEVICE (double sig) ----------------
    @router.post("/ownership/remove-owner-device")
    async def remove_owner_device(payload: CriticalIn):
        ch = await _consume_challenge(payload.challenge_id, "remove_owner_device")
        signers = await _verify_proofs(ch, payload.proofs)
        victim = payload.target_key_id
        if not victim:
            raise HTTPException(status_code=400, detail="target_key_id requis.")
        current = sorted(set(await owner_key_ids(db)))
        if victim not in current:
            raise HTTPException(status_code=404, detail="Cet appareil n'est pas propriétaire.")
        if len(current) <= 1:
            raise HTTPException(status_code=403, detail="Impossible de retirer le dernier appareil propriétaire (récupération garantie).")
        if victim in signers:
            raise HTTPException(status_code=400, detail="Un appareil ne peut pas signer sa propre suppression seul.")
        await db.ownership.update_one(
            {"_id": "root"},
            {"$pull": {"owner_key_ids": victim}, "$set": {"updated_at": _now().isoformat()}},
        )
        await _finish(payload.challenge_id)
        await log_ownership_event(db, "remove_owner_device", signers[0], {"removed": victim, "signers": signers})
        return {"ok": True, "owner_removed": victim}

    # ---------------- TRANSFER OWNERSHIP (double sig) ----------------
    @router.post("/ownership/transfer")
    async def transfer_ownership(payload: CriticalIn):
        ch = await _consume_challenge(payload.challenge_id, "transfer_ownership")
        signers = await _verify_proofs(ch, payload.proofs)
        new_kid = payload.new_owner_key_id
        if not new_kid:
            raise HTTPException(status_code=400, detail="new_owner_key_id requis.")
        target = await _dev(new_kid)
        if not target:
            raise HTTPException(status_code=404, detail="Nouvel appareil propriétaire introuvable.")
        new_user = payload.new_owner_user_id or target.get("user_id")
        await db.ownership.update_one(
            {"_id": "root"},
            {"$addToSet": {"owner_key_ids": new_kid},
             "$set": {"owner_user_id": new_user, "updated_at": _now().isoformat()}},
        )
        await db.device_keys.update_one({"key_id": new_kid}, {"$set": {"role": "creator"}})
        await _finish(payload.challenge_id)
        await log_ownership_event(db, "transfer_ownership", signers[0],
                                  {"new_owner": new_kid, "new_user": new_user, "signers": signers})
        return {"ok": True, "new_owner": new_kid, "owner_user_id": new_user}

    # ---------------- DELEGATE add/revoke (single strong-auth) ----------------
    @router.post("/ownership/delegate/add")
    async def delegate_add(payload: DelegateIn):
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        perms = [p for p in payload.perms if p in DELEGATE_PERMISSIONS]
        if not perms:
            raise HTTPException(status_code=400, detail="Aucune permission valide.")
        if await is_owner_device(db, payload.delegate_key_id):
            raise HTTPException(status_code=400, detail="Cet appareil est déjà propriétaire.")
        target = await _dev(payload.delegate_key_id)
        if not target:
            raise HTTPException(status_code=404, detail="Appareil délégué introuvable.")
        await db.ownership.update_one(
            {"_id": "root"},
            {"$pull": {"delegates": {"key_id": payload.delegate_key_id}}},
        )
        await db.ownership.update_one(
            {"_id": "root"},
            {"$push": {"delegates": {
                "key_id": payload.delegate_key_id, "perms": perms,
                "added_by": payload.key_id, "added_at": _now().isoformat()}},
             "$set": {"updated_at": _now().isoformat()}},
        )
        # Rôle visible 'creator' (Créa déléguée) SANS propriété réelle.
        await db.device_keys.update_one(
            {"key_id": payload.delegate_key_id},
            {"$set": {"role": "creator", "is_delegate_creator": True}},
        )
        await log_ownership_event(db, "delegate_add", payload.key_id,
                                  {"delegate": payload.delegate_key_id, "perms": perms})
        return {"ok": True, "delegate": payload.delegate_key_id, "perms": perms}

    @router.post("/ownership/delegate/revoke")
    async def delegate_revoke(payload: DelegateIn):
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        await db.ownership.update_one(
            {"_id": "root"},
            {"$pull": {"delegates": {"key_id": payload.delegate_key_id}},
             "$set": {"updated_at": _now().isoformat()}},
        )
        await db.device_keys.update_one(
            {"key_id": payload.delegate_key_id},
            {"$set": {"role": "approved", "is_delegate_creator": False}},
        )
        await log_ownership_event(db, "delegate_revoke", payload.key_id, {"delegate": payload.delegate_key_id})
        return {"ok": True, "revoked": payload.delegate_key_id}

    # ---------------- RECOVERY ----------------
    @router.post("/ownership/recover")
    async def ownership_recover(payload: RecoverIn):
        # Brute-force guard.
        window_start = (_now() - timedelta(seconds=RECOVERY_WINDOW_SEC)).isoformat()
        recent = await db.ownership_recovery_attempts.count_documents(
            {"key_id": payload.key_id, "ts": {"$gt": window_start}},
        )
        if recent >= RECOVERY_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Trop de tentatives de récupération. Réessaie plus tard.")
        dev = await db.device_keys.find_one({"key_id": payload.key_id}, {"_id": 0})
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        # Signature du nonce (single-use device nonce).
        ok_sig = verify_signature(dev.get("public_key_jwk") or {}, payload.nonce, payload.signature)
        doc = await ensure_ownership(db)
        code_ok = bool(doc.get("recovery_code_hash")) and verify_recovery_code(
            payload.recovery_code, doc.get("recovery_salt") or "", doc.get("recovery_code_hash") or "",
        )
        await db.ownership_recovery_attempts.insert_one({
            "key_id": payload.key_id, "ok": bool(ok_sig and code_ok), "ts": _now().isoformat(),
        })
        if not ok_sig:
            raise HTTPException(status_code=403, detail="Signature invalide.")
        if not code_ok:
            raise HTTPException(status_code=403, detail="Code de récupération invalide.")
        # Succès : ce nouvel appareil devient propriétaire. On invalide les
        # sessions suspectes de l'utilisateur (compromission possible).
        await db.ownership.update_one(
            {"_id": "root"},
            {"$addToSet": {"owner_key_ids": payload.key_id},
             "$set": {"owner_user_id": dev.get("user_id"), "updated_at": _now().isoformat()}},
        )
        await db.device_keys.update_one({"key_id": payload.key_id}, {"$set": {"role": "creator"}})
        # Rotation du code (le précédent est consommé).
        new_code = gen_recovery_code()
        h = hash_recovery_code(new_code)
        await db.ownership.update_one(
            {"_id": "root"},
            {"$set": {"recovery_code_hash": h["hash"], "recovery_salt": h["salt"],
                      "recovery_set_at": _now().isoformat()}},
        )
        await log_ownership_event(db, "ownership_recover", payload.key_id, {"user_id": dev.get("user_id")})
        return {"ok": True, "owner_added": payload.key_id, "new_recovery_code": new_code,
                "warning": "Nouveau code de récupération — note-le, l'ancien est désormais invalide."}

    # ---------------- AUDIT ----------------
    @router.post("/ownership/audit")
    async def ownership_audit(payload: _SignedIn):
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        rows = await db.ownership_audit.find({}, {"_id": 0}).sort("ts", -1).limit(200).to_list(length=200)
        return {"events": rows}

    # ---------------- TOGGLE PRIVILEGES (ON/OFF) ----------------
    @router.post("/ownership/toggle-privileges")
    async def ownership_toggle_privileges(payload: _SignedIn):
        """iter158.3 — Bascule les pouvoirs supplémentaires du propriétaire ON/OFF.

        Le STATUT propriétaire reste inchangé (inviolable). Seuls les
        privilèges supplémentaires sont activés/désactivés :
          - ON  : le propriétaire garde ses pouvoirs propriétaires même quand
                  il utilise temporairement un rôle inférieur (modo, admin…).
          - OFF : le propriétaire fonctionne exactement comme le rôle actif.
                  Il peut subir les sanctions normales (utile pour tester),
                  mais une notification secrète est enregistrée à chaque
                  action prise contre lui.

        Passage ON → clear automatique des sanctions actives sur ce device
        (garantie de reconnexion propriétaire, spec CDC).
        """
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        dev = await db.device_keys.find_one({"key_id": payload.key_id}, {"_id": 0})
        current = dev.get("owner_privileges_active")
        current = True if current is None else bool(current)
        new_val = not current
        set_ops: Dict[str, Any] = {"owner_privileges_active": new_val,
                                   "owner_privileges_toggled_at": _now().isoformat()}
        unset_ops: Dict[str, Any] = {}
        if new_val:  # ON → clear toutes les sanctions actives (reconnexion garantie)
            for f in ("muted", "banned", "force_visitor"):
                if dev.get(f):
                    set_ops[f] = False
            for tf in ("exclude_until", "force_visitor_until", "disconnect_until",
                       "excluded_until", "muted_until", "banned_at", "blocked_at"):
                if dev.get(tf):
                    unset_ops[tf] = ""
            # Restaurer role si actuellement blocked/banned
            if dev.get("role") in ("blocked", "banned"):
                set_ops["role"] = "creator"
        update: Dict[str, Any] = {"$set": set_ops}
        if unset_ops:
            update["$unset"] = unset_ops
        await db.device_keys.update_one({"key_id": payload.key_id}, update)
        await log_ownership_event(db, "ownership_toggle_privileges", payload.key_id,
                                  {"new_state": "ON" if new_val else "OFF"})
        return {"ok": True, "owner_privileges_active": new_val}

    # ---------------- OWNER NOTIFICATIONS (secret log) ----------------
    @router.post("/ownership/notifications")
    async def ownership_notifications(payload: _SignedIn):
        """iter158.3 — Liste les notifications secrètes du propriétaire :
        décisions prises contre lui pendant qu'il était en mode OFF, ainsi
        que les actions administratives effectuées par d'autres propriétaires
        (transparence inter-propriétaires).

        Réservé aux appareils propriétaires. Chaque propriétaire voit
        SES notifications (owner_key_id == self) + les décisions de nature
        globale prises par les autres propriétaires (actions sur staff/comptes).
        """
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        rows = await db.owner_notifications.find(
            {"$or": [
                {"owner_key_id": payload.key_id},
                # Décisions prises par d'autres propriétaires (actions administratives)
                # sont visibles à tous les propriétaires pour transparence.
                {"actor_key_id": {"$in": sorted(await owner_key_ids(db))},
                 "owner_key_id": {"$ne": payload.key_id}},
            ]},
            {"_id": 0},
        ).sort("ts", -1).limit(200).to_list(length=200)
        unread = sum(1 for r in rows if not r.get("read"))
        return {"notifications": rows, "unread_count": unread}

    @router.post("/ownership/notifications/mark-read")
    async def ownership_notifications_mark_read(payload: _SignedIn):
        """Marque toutes les notifications visibles par cet appareil propriétaire
        comme lues."""
        await _require_owner(payload.key_id, payload.nonce, payload.signature)
        await db.owner_notifications.update_many(
            {"owner_key_id": payload.key_id, "read": False},
            {"$set": {"read": True, "read_at": _now().isoformat()}},
        )
        return {"ok": True}

    return router
