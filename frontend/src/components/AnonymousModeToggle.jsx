/**
 * iter141 — Toggle Mode Anonyme (disponible pour tout le monde).
 * Masque pseudo, identité publique et couleur du rôle dans les groupes,
 * listes de membres et messages. Un staff (modo/admin/créa) en Mode
 * Soleil peut néanmoins voir à travers.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { VenetianMask } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AnonymousModeToggle({ className = '' }) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/social/modes/state`, body);
        setEnabled(!!r.data?.anonymous);
      } catch (_e) { /* silent */ }
    })();
  }, []);

  const flip = async () => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { enabled: !enabled });
      await axios.put(`${API}/social/anonymous`, body);
      setEnabled(!enabled);
      // iter142 — Silencieux : le toggle visuel confirme l'état
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impossible');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`inline-flex items-center gap-2 text-xs ${className}`}
      data-testid="anonymous-toggle-wrap"
    >
      <VenetianMask className={`w-3.5 h-3.5 ${enabled ? 'text-fuchsia-300' : 'text-white/50'}`} />
      <span className={enabled ? 'text-fuchsia-300' : 'text-white/70'}>
        anonyme {enabled ? 'on' : 'off'}
      </span>
      <button
        type="button"
        onClick={flip}
        disabled={busy}
        title={enabled ? 'Désactiver le mode anonyme' : 'Activer le mode anonyme'}
        data-testid="anonymous-toggle"
        aria-pressed={enabled}
        className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 cursor-pointer ${
          enabled ? 'bg-fuchsia-500' : 'bg-black border border-white/20'
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
