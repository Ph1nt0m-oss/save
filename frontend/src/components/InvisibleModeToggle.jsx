/**
 * iter140 Phase 3 — Toggle "Mode invisible" pour admin/créa
 *
 * Slider gauche→droite : noir off (mode invisible off) ↔ jaune on
 * (mode invisible on). Visible uniquement pour admin + créa.
 * Créa dans le groupe 'staff' : présence obligatoire → toggle désactivé
 * (le backend refuse aussi de mettre enabled=true).
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { EyeOff } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function InvisibleModeToggle({
  role, staffKind, groupType, className = '',
}) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const isCreator = role === 'creator';
  const isAdmin = staffKind === 'admin';
  const visible = isCreator || isAdmin;
  const staffLock = isCreator && groupType === 'staff';

  useEffect(() => {
    if (!visible) return;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/social/invisible/state`, body);
        setEnabled((r.data?.invisible_in || []).includes(groupType));
      } catch (_e) { /* silent */ }
    })();
  }, [visible, groupType]);

  if (!visible) return null;

  const flip = async () => {
    if (staffLock) {
      toast.warning('La créa doit rester visible dans le tchat Staff.');
      return;
    }
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { group_type: groupType, enabled: !enabled });
      await axios.put(`${API}/social/invisible`, body);
      setEnabled(!enabled);
      // iter142 — Toast retiré pour cette action de routine (état visible sur toggle)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impossible');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`inline-flex items-center gap-2 text-xs ${className}`}
      data-testid={`invisible-toggle-wrap-${groupType}`}
    >
      <EyeOff className={`w-3.5 h-3.5 ${enabled ? 'text-[#E4FF00]' : 'text-white/50'}`} />
      <span className={enabled ? 'text-[#E4FF00]' : 'text-white/70'}>
        mode invisible {enabled ? 'on' : 'off'}
      </span>
      <button
        type="button"
        onClick={flip}
        disabled={busy || staffLock}
        title={staffLock ? 'La créa doit rester visible dans Staff' : (enabled ? 'Désactiver' : 'Activer')}
        data-testid={`invisible-toggle-${groupType}`}
        aria-pressed={enabled}
        className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${
          enabled ? 'bg-[#E4FF00]' : 'bg-black border border-white/20'
        } ${staffLock ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
            enabled ? 'left-[calc(100%-1.125rem)] bg-black' : 'left-0.5 bg-white/70'
          }`}
        />
      </button>
    </div>
  );
}
