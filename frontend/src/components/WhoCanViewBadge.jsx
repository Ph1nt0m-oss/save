/**
 * iter136 — WhoCanViewBadge (créa-only)
 *
 * Nouvel onglet demandé par l'utilisateur : "Qui peut voir ?"
 * Placé entre le TYPE DE SITE (SiteModeBadge) et le MODE DE CHOIX DE VUE
 * (WhoCanVisitBadge). Multi-sélection obligatoire (min 1) des 6 clés dans
 * l'ordre exact : privé, public, guest, modo, admin, créa.
 *
 * Écrit sur PUT /api/system/who-can-visit en n'envoyant QUE `visit_modes`
 * (le champ `view_forcing` reste piloté par WhoCanVisitBadge).
 */
import React, { useState } from 'react';
import axios from 'axios';
import { Eye, Check, ChevronDown, ShieldQuestion } from 'lucide-react';
import { SITE_MODE_KEYS } from '../lib/siteModeKeys';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter138 — Source unique partagée. Voir /app/frontend/src/lib/siteModeKeys.js
const VIEW_KEYS = SITE_MODE_KEYS;

export default function WhoCanViewBadge({
  role, visitModes = ['public'], viewForcing = 'free',
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
  const active = Array.isArray(visitModes) && visitModes.length ? visitModes : ['public'];
  const isForced = viewForcing === 'forced';

  const save = async (nextModes) => {
    if (!isCreator || saving) return;
    let finalModes = nextModes.filter((m) => VIEW_KEYS.some((v) => v.id === m));
    if (finalModes.length === 0) {
      toast.error('Au moins une case doit rester cochée.');
      return;
    }
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, { visit_modes: finalModes });
      await axios.put(`${API}/system/who-can-visit`, body);
      toast.success(`Qui peut voir : ${finalModes.join(', ')}`);
      onChange?.(finalModes);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec de la mise à jour.');
    } finally {
      setSaving(false);
    }
  };

  const toggle = (id) => {
    const isActive = active.includes(id);
    if (isActive && active.length === 1) {
      toast.error('Impossible de tout décocher : au moins une case doit rester cochée.');
      return;
    }
    const next = isActive ? active.filter((m) => m !== id) : [...active, id];
    save(next);
  };

  if (!isCreator) return null;

  const displayLabel = active.length === 1
    ? (VIEW_KEYS.find((m) => m.id === active[0])?.label || active[0])
    : active.length <= 2
      ? active.map((a) => VIEW_KEYS.find((m) => m.id === a)?.label || a).join(' · ')
      : `${active.length} vues`;

  // Coloration jaune quand la vue est forcée (cohérent avec WhoCanVisitBadge).
  const btnColor = isForced
    ? 'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20'
    : 'bg-fuchsia-500/10 border-fuchsia-400/40 text-fuchsia-300 hover:bg-fuchsia-500/20';

  return (
    <div className={`relative inline-block ${className}`} data-testid="who-can-view-creator">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={saving}
        data-testid="who-can-view-toggle"
        title="Qui peut voir le site (multi-sélection obligatoire)"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${btnColor}`}
      >
        <Eye className="w-3.5 h-3.5" />
        <span>{displayLabel}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          data-testid="who-can-view-dropdown"
          className="absolute right-0 mt-1.5 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1 max-h-[520px] overflow-y-auto"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Qui peut voir ? (multi-sélection, minimum 1)
          </div>
          {VIEW_KEYS.map((m) => {
            const Mi = m.icon;
            const isActive = active.includes(m.id);
            const isLastActive = isActive && active.length === 1;
            // Cases actives : jaune si "Vue forcée" globale, fuchsia sinon.
            const activeText = isForced ? 'text-[#E4FF00]' : 'text-fuchsia-300';
            const activeBg = isForced ? 'bg-[#E4FF00]/5' : 'bg-fuchsia-500/5';
            const activeBorder = isForced ? 'border-[#E4FF00] bg-[#E4FF00]/20' : 'border-fuchsia-300 bg-fuchsia-300/20';
            const activeCheck = isForced ? 'text-[#E4FF00]' : 'text-fuchsia-300';
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => toggle(m.id)}
                disabled={saving || isLastActive}
                data-testid={`who-view-option-${m.id}`}
                title={isLastActive ? 'Au moins une case doit rester cochée' : m.hint}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  isActive ? `${activeText} ${activeBg}` : 'text-white'
                } ${isLastActive ? 'cursor-not-allowed' : ''}`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center ${
                  isActive ? activeBorder : 'border-white/30'
                }`}>
                  {isActive && <Check className={`w-2.5 h-2.5 ${activeCheck}`} />}
                </span>
                <Mi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-['Chivo'] font-bold inline-flex items-center gap-1">
                    {m.label}
                    {isLastActive && (
                      <span
                        data-testid={`who-view-locked-${m.id}`}
                        title="Minimum une case obligatoire"
                        className="inline-flex items-center gap-0.5 text-[8px] uppercase tracking-widest text-amber-300 border border-amber-400/40 bg-amber-400/10 rounded-sm px-1"
                      >
                        <ShieldQuestion className="w-2.5 h-2.5" /> verrouillé
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-[#A1A1AA]">{m.hint}</div>
                </div>
              </button>
            );
          })}

          <div className="px-3 py-2 border-t border-white/10 text-[10px] text-[#71717A] italic">
            {isForced
              ? '⚠ Mode "Vue forcée" activé — les visiteurs seront restreints aux vues cochées ci-dessus.'
              : 'Mode libre — les visiteurs pourront choisir librement parmi ces vues.'}
          </div>
        </div>
      )}
    </div>
  );
}
