/**
 * iter134/136 — WhoCanVisitBadge (créa-only) — SIMPLIFIÉ.
 *
 * Onglet "Mode de choix de vue" : Libre / Vue forcée par la créa.
 * Les vues autorisées (multi-select des 6 clés) sont désormais gérées dans
 * `WhoCanViewBadge` (onglet dédié à gauche de celui-ci).
 *
 * Écrit sur PUT /api/system/who-can-visit en n'envoyant QUE `view_forcing`.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { ChevronDown, UserCog, Radio } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WhoCanVisitBadge({
  role, viewForcing = 'free', visitModes = [],
  onChange, className = '',
  controlledOpen, onOpenChange,
} = {}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setOpen = (v) => {
    const next = typeof v === 'function' ? v(open) : v;
    if (onOpenChange) onOpenChange(next);
    else setInternalOpen(next);
  };
  const [saving, setSaving] = useState(false);

  const isCreator = role === 'creator';
  const forcing = viewForcing === 'forced' ? 'forced' : 'free';

  const setForcing = async (mode) => {
    if (!isCreator || saving || mode === forcing) return;
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, { view_forcing: mode });
      await axios.put(`${API}/system/who-can-visit`, body);
      toast.success(mode === 'forced' ? 'Vue forcée activée' : 'Libre choix activé');
      onChange?.(mode);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec de la mise à jour.');
    } finally {
      setSaving(false);
    }
  };

  if (!isCreator) return null;

  const btnColor = forcing === 'forced'
    ? 'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20'
    : 'bg-cyan-500/10 border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/20';

  return (
    <div className={`relative inline-block ${className}`} data-testid="who-can-visit-creator">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={saving}
        data-testid="who-can-visit-toggle"
        title="Mode de choix de vue (Libre / Forcée)"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${btnColor}`}
      >
        <UserCog className="w-3.5 h-3.5" />
        <span>{forcing === 'forced' ? 'Vue forcée' : 'Libre choix'}</span>
        {forcing === 'forced' && Array.isArray(visitModes) && visitModes.length > 0 && (
          <span className="text-[9px] uppercase tracking-widest opacity-80">
            {visitModes.length === 1 ? visitModes[0] : `${visitModes.length}`}
          </span>
        )}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          data-testid="who-can-visit-dropdown"
          className="absolute right-0 mt-1.5 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1 max-h-[380px] overflow-y-auto"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Mode de choix de vue
          </div>
          <div className="p-2 space-y-1">
            <button
              type="button"
              onClick={() => setForcing('free')}
              disabled={saving}
              data-testid="who-visit-forcing-free"
              className={`w-full text-left px-2 py-1.5 rounded-sm text-xs flex items-start gap-2 transition ${
                forcing === 'free' ? 'bg-cyan-500/15 text-cyan-300' : 'text-white hover:bg-white/[0.05]'
              }`}
            >
              <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-full flex items-center justify-center ${
                forcing === 'free' ? 'border-cyan-300 bg-cyan-300/25' : 'border-white/30'
              }`}>
                {forcing === 'free' && <span className="w-1.5 h-1.5 rounded-full bg-cyan-300" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-['Chivo'] font-bold">Libre choix</div>
                <div className="text-[10px] text-[#A1A1AA]">L&apos;utilisateur décide de la vue qu&apos;il souhaite parmi les vues cochées dans « Qui peut voir »</div>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setForcing('forced')}
              disabled={saving}
              data-testid="who-visit-forcing-forced"
              className={`w-full text-left px-2 py-1.5 rounded-sm text-xs flex items-start gap-2 transition ${
                forcing === 'forced' ? 'bg-[#E4FF00]/15 text-[#E4FF00]' : 'text-white hover:bg-white/[0.05]'
              }`}
            >
              <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-full flex items-center justify-center ${
                forcing === 'forced' ? 'border-[#E4FF00] bg-[#E4FF00]/25' : 'border-white/30'
              }`}>
                {forcing === 'forced' && <span className="w-1.5 h-1.5 rounded-full bg-[#E4FF00]" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-['Chivo'] font-bold">Vue forcée par la créa</div>
                <div className="text-[10px] text-[#A1A1AA]">L&apos;utilisateur ne peut sélectionner qu&apos;une vue cochée dans « Qui peut voir »</div>
              </div>
            </button>
          </div>
          <div className="px-3 py-2 border-t border-white/10 text-[10px] text-[#71717A] italic flex items-start gap-1.5">
            <Radio className="w-3 h-3 mt-0.5 flex-shrink-0" />
            <span>
              {forcing === 'forced'
                ? 'Les vues autorisées se configurent dans l\'onglet « Qui peut voir ».'
                : 'Les vues visibles se configurent dans l\'onglet « Qui peut voir ».'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
