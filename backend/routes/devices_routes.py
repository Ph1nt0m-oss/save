"""iter116 — Routes devices/* extraites de server.py.

17 endpoints couvrant l'authentification par appareil WebCrypto ECDSA :
  - /devices/register, /challenge, /verify (public)
  - /devices/list, /decisions, /decisions/clear, /decisions/undo (créa)
  - /devices/pending-count, /pending-stream (créa SSE)
  - /devices/approve (staff + tiered), /revoke, /disconnect (créa)
  - /devices/promote-creator, /add-by-key (créa)
  - /devices/send-to-creator (public, nudge)
  - /devices/block, /unblock (staff)

Factory : `build_devices_router(db, deps...)` retourne un APIRouter inclus
avec `prefix='/api'` dans server.py.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class DeviceRegisterIn(BaseModel):
    public_key_jwk: Dict[str, Any]
    label: Optional[str] = None
    product: Optional[str] = None
    model: Optional[str] = None


class DeviceChallengeIn(BaseModel):
    key_id: str


class DeviceVerifyIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class CreatorOnlyIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


class DecisionUndoIn(BaseModel):
    key_id: str
    nonce: str
    signature: str
    target_key_id: str
    decision_ts: str


class DeviceTargetIn(CreatorOnlyIn):
    target_key_id: str


class DeviceApproveIn(DeviceTargetIn):
    """iter111 — Tiered approval : le staff/créa peut approuver en
    spécifiant un rôle cible. Hiérarchie stricte :
      - Modo → User uniquement
      - Admin → User ou Modo
      - Créa → User, Modo ou Admin
    """
    as_role: Optional[str] = "user"


class PromoteCreatorIn(CreatorOnlyIn):
    target_key_id: str
    password: str


class AddByKeyIn(CreatorOnlyIn):
    public_key_jwk: Dict[str, Any]
    label: Optional[str] = None
    role: Optional[str] = "approved"


class SendToCreatorIn(BaseModel):
    key_id: str
    nonce: str
    signature: str


def build_devices_router(
    db,
    *,
    compute_key_id,
    new_nonce,
    verify_signature,
    verify_password,
    device_by_key,
    consume_nonce,
    require_creator_signature,
    require_staff_signature,
    log_decision,
    get_site_mode,
    normalize_modes,
    device_matches_mode,
):
    """Factory pour l'APIRouter /devices/* + helper /system/* utilisés par devices."""
    router = APIRouter()

    @router.post("/devices/register")
    async def device_register(payload: DeviceRegisterIn):
        """Register a fresh device. Public — anyone can call this. The first
        device EVER registered is auto-promoted to 'creator'. All subsequent
        registrations are 'pending' until the creator approves them."""
        jwk = payload.public_key_jwk or {}
        if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
            raise HTTPException(status_code=400, detail="Clé publique invalide (EC P-256 attendu).")
        key_id = compute_key_id(jwk)
        product = (payload.product or "")[:60] or None
        model = (payload.model or "")[:60] or None
        label = (payload.label or "")[:60] or None

        matches = await db.device_keys.find({"key_id": key_id}, {"_id": 0}).to_list(length=5)
        if matches:
            priority = {"creator": 4, "approved": 3, "pending": 2, "revoked": 1}
            best_role = max((m.get("role") for m in matches), key=lambda r: priority.get(r, 0))
            existing = matches[0]
            await db.device_keys.delete_many({"key_id": key_id})
            await db.device_keys.insert_one({
                "key_id": key_id,
                "public_key_jwk": jwk,
                "role": best_role,
                "label": label or existing.get("label"),
                "product": product or existing.get("product"),
                "model": model or existing.get("model"),
                "created_at": existing.get("created_at") or datetime.now(timezone.utc).isoformat(),
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"key_id": key_id, "role": best_role, "already_registered": True}

        distinct_ids = await db.device_keys.distinct("key_id")
        role = "creator" if len(distinct_ids) == 0 else "inactive"
        doc = {
            "key_id": key_id,
            "public_key_jwk": jwk,
            "role": role,
            "label": label,
            "product": product,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.device_keys.insert_one(doc)
        return {"key_id": key_id, "role": role, "already_registered": False}

    @router.post("/devices/challenge")
    async def device_challenge(payload: DeviceChallengeIn):
        """Issue a single-use nonce for the given key_id."""
        dev = await device_by_key(payload.key_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        nonce = new_nonce()
        await db.device_nonces.insert_one({
            "key_id": payload.key_id,
            "nonce": nonce,
            "created_at": datetime.now(timezone.utc),
        })
        return {"nonce": nonce, "expires_in_seconds": 120}

    @router.post("/devices/verify")
    async def device_verify(payload: DeviceVerifyIn):
        """Verify the signature → return device role + whether access is granted."""
        dev = await device_by_key(payload.key_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        if not await consume_nonce(payload.key_id, payload.nonce):
            raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
        ok = verify_signature(dev.get("public_key_jwk") or {}, payload.nonce, payload.signature)
        if not ok:
            return {"verified": False, "role": dev.get("role"), "can_access": False}

        await db.device_keys.update_one(
            {"key_id": payload.key_id},
            {"$set": {"last_seen_at": datetime.now(timezone.utc).isoformat()}},
        )

        site_mode = await get_site_mode()
        role = dev.get("role")
        effective_role = role
        can_access = True
        kick_reason = None

        excluded_until = dev.get("excluded_until")
        if excluded_until:
            try:
                exp = datetime.fromisoformat(excluded_until.replace("Z", "+00:00"))
                if exp <= datetime.now(timezone.utc):
                    await db.device_keys.update_one(
                        {"key_id": payload.key_id},
                        {"$unset": {"excluded_until": "", "excluded_reason": ""}},
                    )
                    excluded_until = None
            except Exception:
                excluded_until = None
        if dev.get("banned"):
            can_access = False; kick_reason = "kick_banned"
        elif excluded_until:
            can_access = False; kick_reason = "kick_excluded"
        elif role == "blocked":
            can_access = False; kick_reason = "kick_blocked"
        elif role == "revoked":
            can_access = False; kick_reason = "kick_revoked"
        else:
            modes_active = normalize_modes(site_mode)
            if not device_matches_mode(dev, modes_active):
                can_access = False
                if "creator" in modes_active:
                    kick_reason = "kick_creator_only"
                elif "admin" in modes_active or "modo" in modes_active or "staff" in modes_active:
                    kick_reason = "kick_staff_only"
                elif "private" in modes_active:
                    kick_reason = "kick_private"; effective_role = "guest"
                else:
                    kick_reason = "kick_blocked"
            elif "guest" in modes_active and role not in ("creator", "approved"):
                effective_role = "guest"

        site_modes_list = normalize_modes(site_mode)
        sm_doc = await db.site_config.find_one(
            {"_id": "site_mode"}, {"_id": 0, "guest_view": 1, "guest_views": 1}
        ) or {}
        gv_list = sm_doc.get("guest_views")
        if not isinstance(gv_list, list) or not gv_list:
            gv_list = [sm_doc.get("guest_view")] if sm_doc.get("guest_view") else []
        return {
            "verified": True, "role": role, "effective_role": effective_role,
            "can_access": can_access,
            "site_mode": site_modes_list[0],
            "site_modes": site_modes_list,
            "guest_view": gv_list[0] if gv_list else None,
            "guest_views": gv_list,
            "kick_reason": kick_reason,
            "excluded_until": excluded_until,
            "force_visitor": bool(dev.get("force_visitor", False)),
            "staff_kind": dev.get("staff_kind"),
        }

    @router.post("/devices/list")
    async def devices_list(payload: CreatorOnlyIn):
        """Creator-only — list all registered devices."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        devices = await db.device_keys.find(
            {"role": {"$ne": "inactive"}}, {"_id": 0, "public_key_jwk": 0},
        ).sort("created_at", -1).to_list(length=500)
        return {"devices": devices}

    @router.post("/devices/decisions")
    async def devices_decisions(payload: CreatorOnlyIn):
        """Creator-only — return the history of past decisions."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        rows = await db.device_decisions.find({}, {"_id": 0}).sort("ts", -1).to_list(length=200)
        return {"decisions": rows}

    @router.post("/devices/decisions/clear")
    async def devices_decisions_clear(payload: CreatorOnlyIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        res = await db.device_decisions.delete_many({})
        return {"deleted": res.deleted_count}

    @router.post("/devices/decisions/undo")
    async def devices_decisions_undo(payload: DecisionUndoIn):
        """Creator-only — undo a specific decision."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        dec = await db.device_decisions.find_one(
            {"target_key_id": payload.target_key_id, "ts": payload.decision_ts},
            {"_id": 0},
        )
        if not dec:
            raise HTTPException(status_code=404, detail="Décision introuvable.")
        action = dec.get("action")
        snapshot = dec.get("snapshot") or {}

        if action == "approve":
            await db.device_keys.update_one(
                {"key_id": payload.target_key_id}, {"$set": {"role": "pending"}},
            )
        elif action in ("revoke", "disconnect"):
            existing = await device_by_key(payload.target_key_id)
            if existing:
                await db.device_keys.update_one(
                    {"key_id": payload.target_key_id}, {"$set": {"role": "pending"}},
                )
            else:
                new_row = {
                    "key_id": payload.target_key_id,
                    "public_key_jwk": snapshot.get("public_key_jwk", {}),
                    "label": snapshot.get("label") or dec.get("target_label"),
                    "role": "pending",
                    "created_at": snapshot.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    "last_seen_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.device_keys.insert_one(new_row)
        elif action == "promote":
            await db.device_keys.update_one(
                {"key_id": payload.target_key_id}, {"$set": {"role": "approved"}},
            )
        elif action == "add_by_key":
            await db.device_keys.delete_one({"key_id": payload.target_key_id})
        else:
            return {"success": False, "reason": "non_undoable_action"}

        await log_decision("undo", payload.target_key_id, payload.key_id, dec.get("target_label"))
        return {"success": True}

    @router.post("/devices/pending-count")
    async def devices_pending_count(payload: CreatorOnlyIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        count = await db.device_keys.count_documents({"role": "pending"})
        return {"pending_count": count}

    @router.get("/devices/pending-stream/{key_id}/{nonce}/{signature}")
    async def devices_pending_stream(key_id: str, nonce: str, signature: str):
        """Creator-only SSE stream — emits pending count every 5s."""
        await require_creator_signature(key_id, nonce, signature)

        async def gen():
            last = -1
            try:
                while True:
                    dev = await device_by_key(key_id)
                    if not dev or dev.get("role") != "creator":
                        yield "event: closed\ndata: revoked\n\n"
                        return
                    count = await db.device_keys.count_documents({"role": "pending"})
                    if count != last:
                        yield f"data: {{\"pending_count\": {count}}}\n\n"
                        last = count
                    else:
                        yield ": keepalive\n\n"
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                return

        return StreamingResponse(gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive",
        })

    @router.post("/devices/approve")
    async def devices_approve(payload: DeviceApproveIn):
        """iter111 — Tiered approval. Staff/créa peut approuver avec un rôle cible."""
        actor = await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        target = await device_by_key(payload.target_key_id)
        actor_role = actor.get("role")
        actor_sk = actor.get("staff_kind")
        requested = (payload.as_role or "user").strip().lower()
        if requested not in {"user", "modo", "admin"}:
            raise HTTPException(status_code=400, detail="as_role invalide ('user'|'modo'|'admin').")
        if actor_role == "creator":
            allowed = {"user", "modo", "admin"}
        elif actor_sk == "admin":
            allowed = {"user", "modo"}
        elif actor_sk == "modo":
            allowed = {"user"}
        else:
            allowed = set()
        if requested not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Tu ne peux pas approuver en tant que '{requested}'. Niveaux autorisés : {sorted(allowed)}.",
            )
        target_staff_kind = None if requested == "user" else requested
        update_set = {
            "role": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by_key_id": payload.key_id,
            "approved_by_kind": "creator" if actor_role == "creator" else actor_sk,
            "approved_as": requested,
        }
        update_set["staff_kind"] = target_staff_kind  # None pour user, sinon role
        res = await db.device_keys.update_one(
            {"key_id": payload.target_key_id, "role": "pending"},
            {"$set": update_set},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Aucun appareil en attente avec cette clé.")
        await log_decision("approve", payload.target_key_id, payload.key_id, (target or {}).get("label"))
        return {
            "success": True,
            "approved_by_kind": "creator" if actor_role == "creator" else actor_sk,
            "approved_as": requested,
            "staff_kind": target_staff_kind,
        }

    @router.post("/devices/revoke")
    async def devices_revoke(payload: DeviceTargetIn):
        """Creator hard-revokes a device."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        if payload.target_key_id == payload.key_id:
            raise HTTPException(status_code=400, detail="Tu ne peux pas révoquer ton propre appareil créateur.")
        target = await device_by_key(payload.target_key_id)
        target_label = (target or {}).get("label")
        await db.device_keys.delete_one({"key_id": payload.target_key_id})
        await db.device_nonces.delete_many({"key_id": payload.target_key_id})
        await db.user_sessions.delete_many({"device_key_id": payload.target_key_id})
        await log_decision("revoke", payload.target_key_id, payload.key_id, target_label, snapshot=target)
        return {"success": True, "existed": target is not None}

    @router.post("/devices/disconnect")
    async def devices_disconnect(payload: DeviceTargetIn):
        """Creator force-disconnects a device."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        if payload.target_key_id == payload.key_id:
            raise HTTPException(status_code=400, detail="Tu ne peux pas te déconnecter toi-même via cette action.")
        target = await device_by_key(payload.target_key_id)
        if not target:
            raise HTTPException(status_code=404, detail="Appareil introuvable.")
        await db.device_nonces.delete_many({"key_id": payload.target_key_id})
        await db.user_sessions.delete_many({"device_key_id": payload.target_key_id})
        await db.device_keys.delete_one({"key_id": payload.target_key_id})
        await log_decision("disconnect", payload.target_key_id, payload.key_id, (target or {}).get("label"), snapshot=target)
        return {"success": True}

    @router.post("/devices/promote-creator")
    async def devices_promote_creator(payload: PromoteCreatorIn):
        """Creator promotes another device to 'creator' role."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        users = await db.users.find({}, {"_id": 0, "email": 1, "password_hash": 1}).to_list(length=200)
        matched = False
        for u in users:
            ph = u.get("password_hash") or ""
            try:
                if ph and verify_password(payload.password, ph):
                    matched = True; break
            except Exception:
                continue
        if not matched:
            raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
        res = await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"role": "creator", "promoted_at": datetime.now(timezone.utc).isoformat()}},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Appareil introuvable.")
        target = await device_by_key(payload.target_key_id)
        await log_decision("promote", payload.target_key_id, payload.key_id, (target or {}).get("label"))
        return {"success": True}

    @router.post("/devices/add-by-key")
    async def devices_add_by_key(payload: AddByKeyIn):
        """Creator pastes another device's public key to whitelist it directly."""
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        jwk = payload.public_key_jwk or {}
        if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
            raise HTTPException(status_code=400, detail="Clé publique invalide.")
        target_id = compute_key_id(jwk)
        role = payload.role if payload.role in ("approved", "creator") else "approved"
        existing = await device_by_key(target_id)
        if existing:
            await db.device_keys.update_one(
                {"key_id": target_id},
                {"$set": {"role": role, "label": payload.label or existing.get("label")}},
            )
        else:
            await db.device_keys.insert_one({
                "key_id": target_id,
                "public_key_jwk": jwk,
                "role": role,
                "label": (payload.label or "")[:60] or None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "added_by_creator": True,
            })
        await log_decision("add_by_key", target_id, payload.key_id, payload.label)
        return {"key_id": target_id, "role": role}

    @router.post("/devices/send-to-creator")
    async def devices_send_to_creator(payload: SendToCreatorIn):
        """Anyone with a valid registered device can nudge the creator. Cool-down 10 min."""
        dev = await device_by_key(payload.key_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Appareil inconnu.")
        if dev.get("role") == "blocked":
            raise HTTPException(
                status_code=403,
                detail="Votre demande a été formulée de nombreuses fois. Veuillez contacter le créateur.",
            )
        last_at_iso = dev.get("last_nudge_at")
        if last_at_iso:
            try:
                last_at = datetime.fromisoformat(last_at_iso)
                if (datetime.now(timezone.utc) - last_at) < timedelta(minutes=10):
                    raise HTTPException(
                        status_code=429,
                        detail="Tu as déjà envoyé une demande récemment. Réessaie dans quelques minutes.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass
        if not await consume_nonce(payload.key_id, payload.nonce):
            raise HTTPException(status_code=403, detail="Nonce invalide ou expiré.")
        if not verify_signature(dev.get("public_key_jwk") or {}, payload.nonce, payload.signature):
            raise HTTPException(status_code=403, detail="Signature invalide.")
        now_iso = datetime.now(timezone.utc).isoformat()
        if dev.get("role") in ("creator", "approved", "pending"):
            await db.device_keys.update_one(
                {"key_id": payload.key_id},
                {"$set": {"last_seen_at": now_iso, "last_nudge_at": now_iso}},
            )
        else:
            await db.device_keys.update_one(
                {"key_id": payload.key_id},
                {"$set": {"role": "pending", "last_seen_at": now_iso, "last_nudge_at": now_iso}},
            )
        return {"sent": True, "role": dev.get("role")}

    @router.post("/devices/block")
    async def devices_block(payload: DeviceTargetIn):
        """iter79 — Block. Ouvert au staff."""
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        if payload.target_key_id == payload.key_id:
            raise HTTPException(status_code=400, detail="Tu ne peux pas te bloquer toi-même.")
        target = await device_by_key(payload.target_key_id)
        target_label = (target or {}).get("label")
        if target:
            await db.device_keys.update_one(
                {"key_id": payload.target_key_id},
                {"$set": {"role": "blocked", "blocked_at": datetime.now(timezone.utc).isoformat()}},
            )
        else:
            await db.device_keys.insert_one({
                "key_id": payload.target_key_id,
                "public_key_jwk": {},
                "label": target_label,
                "role": "blocked",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "blocked_at": datetime.now(timezone.utc).isoformat(),
            })
        await db.device_nonces.delete_many({"key_id": payload.target_key_id})
        await db.user_sessions.delete_many({"device_key_id": payload.target_key_id})
        await log_decision("revoke", payload.target_key_id, payload.key_id, target_label, snapshot=target)
        return {"success": True, "blocked": True}

    @router.post("/devices/unblock")
    async def devices_unblock(payload: DeviceTargetIn):
        """iter79 — Unblock. Ouvert au staff."""
        await require_staff_signature(payload.key_id, payload.nonce, payload.signature)
        target = await device_by_key(payload.target_key_id)
        if not target or target.get("role") != "blocked":
            raise HTTPException(status_code=404, detail="Appareil non bloqué.")
        await db.device_keys.update_one(
            {"key_id": payload.target_key_id},
            {"$set": {"role": "pending"}, "$unset": {"blocked_at": ""}},
        )
        return {"success": True}

    return router
