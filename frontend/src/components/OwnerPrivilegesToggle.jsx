/**
 * iter158.3 — Bouton bascule des PRIVILÈGES PROPRIÉTAIRE (ON/OFF).
 *
 * Visible UNIQUEMENT sur un appareil propriétaire réel (is_owner=true).
 * Le STATUT propriétaire lui-même reste inviolable — ce bouton ne modifie
 * QUE les pouvoirs supplémentaires (spec CDC iter158.3).
 *
 *  - ON  : le propriétaire garde tous ses pouvoirs même en simulation de rôle.
 *  - OFF : le propriétaire fonctionne comme le rôle actif (test réel).
 *          Les actions prises contre lui sont notifiées secrètement et
 *          annulables ; la reconnexion propriétaire reste garantie.
 *
 * Le clic bascule et déclenche un refresh du device (pour repositionner
 * les permissions).
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Crown, CrownIcon } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OwnerPrivilegesToggle() {
  const device = useDeviceIdentity();
  const [isOwner, setIsOwner] = useState(false);
  const [privActive, setPrivActive] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (device.role !== 'creator') {
      setIsOwner(false);
      return;
    }
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/ownership/status`, body);
      setIsOwner(!!r.data?.is_owner);
      if (r.data?.is_owner) {
        setPrivActive(r.data?.owner_privileges_active !== false);
      }
    } catch (_) {
      setIsOwner(false);
    }
  }, [device.role]);

  useEffect(() => { load(); }, [load]);

  if (!isOwner) return null;

  const toggle = async () => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/ownership/toggle-privileges`, body);
      const nextState = !!r.data?.owner_privileges_active;
      setPrivActive(nextState);
      toast.success(nextState
        ? 'Pouvoirs propriétaires : ACTIVÉS'
        : 'Pouvoirs propriétaires : DÉSACTIVÉS (test rôle actif)');
      try { device.refresh?.(); } catch (_) {}
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bascule impossible');
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={toggle}
      disabled={busy}
      data-testid="owner-privileges-toggle"
      title={privActive
        ? 'Pouvoirs propriétaires ACTIVÉS — cliquer pour désactiver et tester le rôle actif'
        : 'Pouvoirs propriétaires DÉSACTIVÉS — cliquer pour restaurer'}
      className={`relative z-[5] transition-colors p-1.5 rounded-sm ml-1 flex-shrink-0 border ${
        privActive
          ? 'border-[#E4FF00]/60 bg-[#E4FF00]/10 text-[#E4FF00] hover:bg-[#E4FF00]/20'
          : 'border-white/15 bg-white/[0.02] text-[#A1A1AA] hover:text-white/70'
      } ${busy ? 'opacity-50 cursor-wait' : ''}`}
      aria-label="Bascule pouvoirs propriétaires"
    >
      <Crown className="w-4 h-4" />
      <span className={`absolute -bottom-1 -right-1 text-[7px] leading-none px-0.5 rounded-sm font-bold ${
        privActive ? 'bg-[#E4FF00] text-black' : 'bg-white/20 text-white/70'
      }`}>
        {privActive ? 'ON' : 'OFF'}
      </span>
    </button>
  );
}
