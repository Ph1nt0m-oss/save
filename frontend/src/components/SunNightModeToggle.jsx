/**
 * iter141/iter142 — Toggle Soleil/Nuit pour Modo/Admin/Créa.
 *
 *  - Soleil (enabled=true)  : force la révélation des vrais pseudos, handles
 *                             et couleurs des utilisateurs anonymes.
 *  - Nuit   (enabled=false) : respecte l'anonymat comme les autres.
 *
 * iter142 — Créa peut activer librement. Modo/Admin ne peuvent activer
 * QUE si les bots ont détecté une suspicion active dans un groupe. Le
 * toggle affiche un badge "Bot autorisé" quand c'est le cas.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Sun, Moon, ShieldAlert } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SunNightModeToggle({ role, staffKind, className = '' }) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [suspicionActive, setSuspicionActive] = useState(false);
  const canUse =
    role === 'creator' || staffKind === 'admin' || staffKind === 'modo';
  const isCreator = role === 'creator';

  useEffect(() => {
    if (!canUse) return undefined;
    let cancelled = false;
    const tick = async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const [modes, susp] = await Promise.all([
          axios.post(`${API}/social/modes/state`, body).then((r) => r.data).catch(() => null),
          axios.post(`${API}/social/suspicion-state`, body).then((r) => r.data).catch(() => null),
        ]);
        if (cancelled) return;
        if (modes) setEnabled(!!modes.sun_mode);
        if (susp) setSuspicionActive((susp.groups || []).length > 0);
      } catch (_e) { /* silent */ }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, [canUse]);

  if (!canUse) return null;

  // Modo/Admin ne peuvent activer que si suspicion active. La Créa
  // passe outre.
  const canActivate = isCreator || suspicionActive || enabled;

  const flip = async () => {
    if (!canActivate) {
      toast.error('Mode Soleil dispo uniquement quand les bots détectent une suspicion.');
      return;
    }
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { enabled: !enabled });
      await axios.put(`${API}/social/sun-mode`, body);
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
      {suspicionActive && !isCreator && (
        <span
          className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-red-400/60 text-red-300 bg-red-500/15 rounded-sm inline-flex items-center gap-1"
          data-testid="sun-suspicion-badge"
          title="Les bots ont détecté une situation suspecte — Soleil temporairement autorisé."
        >
          <ShieldAlert className="w-2.5 h-2.5" />
          Bot alerte
        </span>
      )}
      <button
        type="button"
        onClick={flip}
        disabled={busy || !canActivate}
        title={
          !canActivate ? 'Mode Soleil verrouillé (pas de suspicion active).' :
          enabled ? 'Passer en mode Nuit' : 'Passer en mode Soleil'
        }
        data-testid="sun-mode-toggle"
        aria-pressed={enabled}
        className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${
          enabled ? 'bg-amber-400' : 'bg-black border border-white/20'
        } ${(!canActivate || busy) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
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
