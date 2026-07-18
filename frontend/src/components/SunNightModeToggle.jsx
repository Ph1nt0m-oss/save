/**
 * iter141 — Toggle Soleil/Nuit pour Modo/Admin/Créa.
 *
 *  - Soleil (enabled=true)  : force la révélation des vrais pseudos, handles
 *                             et couleurs des utilisateurs anonymes.
 *  - Nuit   (enabled=false) : respecte l'anonymat comme les autres.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Sun, Moon } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SunNightModeToggle({ role, staffKind, className = '' }) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const canUse =
    role === 'creator' || staffKind === 'admin' || staffKind === 'modo';

  useEffect(() => {
    if (!canUse) return;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/social/modes/state`, body);
        setEnabled(!!r.data?.sun_mode);
      } catch (_e) { /* silent */ }
    })();
  }, [canUse]);

  if (!canUse) return null;

  const flip = async () => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { enabled: !enabled });
      await axios.put(`${API}/social/sun-mode`, body);
      setEnabled(!enabled);
      toast.success(`Mode ${!enabled ? 'Soleil' : 'Nuit'} activé`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impossible');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`inline-flex items-center gap-2 text-xs ${className}`}
      data-testid="sun-mode-toggle-wrap"
    >
      {enabled ? (
        <Sun className="w-3.5 h-3.5 text-amber-300" />
      ) : (
        <Moon className="w-3.5 h-3.5 text-white/50" />
      )}
      <span className={enabled ? 'text-amber-300' : 'text-white/70'}>
        {enabled ? 'Soleil' : 'Nuit'}
      </span>
      <button
        type="button"
        onClick={flip}
        disabled={busy}
        title={enabled ? 'Passer en mode Nuit' : 'Passer en mode Soleil'}
        data-testid="sun-mode-toggle"
        aria-pressed={enabled}
        className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 cursor-pointer ${
          enabled ? 'bg-amber-400' : 'bg-black border border-white/20'
        }`}
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
