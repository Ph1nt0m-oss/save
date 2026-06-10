import React, { useState } from 'react';
import { ChevronDown, Crown, User, Shield, ShieldCheck, EyeOff, Check } from 'lucide-react';
import { setStoredViewMode } from '../hooks/useDeviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * iter86 — ViewModePicker (refonte : cases à cocher décochables)
 *
 * Bug user iter85 : "j'arrive pas à décocher" → bloquée en vue modo.
 * Fix : remplace le dropdown radio par 5 cases à cocher, UNE seule active
 * à la fois. Cliquer sur la case active = la décocher = retour vue créa
 * ('creator' par défaut). Cliquer sur une autre case = bascule sur celle-là.
 *
 * Visible uniquement pour les devices créatrice (early return sinon).
 */
const VIEW_META = {
  creator: { Icon: Crown, labelKey: 'view_creator', color: 'text-[#E4FF00]', desc: 'Accès total (par défaut)' },
  user:    { Icon: User, labelKey: 'view_user', color: 'text-sky-300', desc: 'Comme un membre approved' },
  modo:    { Icon: Shield, labelKey: 'view_modo', color: 'text-cyan-300', desc: 'Comme un modérateur' },
  admin:   { Icon: ShieldCheck, labelKey: 'view_admin', color: 'text-orange-300', desc: 'Comme un administrateur' },
  guest:   { Icon: EyeOff, labelKey: 'view_guest', color: 'text-amber-300', desc: 'Comme un visiteur public' },
};

const ORDER = ['user', 'modo', 'admin', 'guest'];  // 'creator' = défaut implicite, pas dans les cases

export default function ViewModePicker({ role, viewMode }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  if (role !== 'creator') return null;

  const current = VIEW_META[viewMode] || VIEW_META.creator;
  const CIcon = current.Icon;
  const isSimulating = viewMode && viewMode !== 'creator';

  const toggle = (mode) => {
    // Cliquer sur la case déjà active = décocher (retour creator)
    if (mode === viewMode) {
      setStoredViewMode('creator');
    } else {
      setStoredViewMode(mode);
    }
    setOpen(false);
  };

  return (
    <div className="relative inline-block" data-testid="view-mode-picker">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        data-testid="view-mode-picker-toggle"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${
          isSimulating
            ? `bg-white/[0.04] border-white/15 ${current.color} hover:bg-white/[0.08]`
            : 'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20'
        }`}
      >
        <CIcon className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{t(current.labelKey)}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          data-testid="view-mode-picker-dropdown"
          className="absolute right-0 mt-1.5 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Simuler une vue (1 à la fois)
          </div>
          {ORDER.map((m) => {
            const meta = VIEW_META[m];
            const Mi = meta.Icon;
            const active = m === viewMode;
            return (
              <button
                key={m}
                type="button"
                onClick={() => toggle(m)}
                data-testid={`view-mode-pick-${m}`}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  active ? `${meta.color} bg-white/[0.04]` : 'text-white'
                }`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center transition ${
                  active ? `border-current ${meta.color.replace('text-', 'bg-').replace(']', ']/20')}` : 'border-white/30'
                }`}>
                  {active && <Check className={`w-2.5 h-2.5 ${meta.color}`} />}
                </span>
                <Mi className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${meta.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="font-['Chivo'] font-bold">{t(meta.labelKey)}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{meta.desc}</div>
                </div>
              </button>
            );
          })}
          {isSimulating && (
            <div className="border-t border-white/10 mt-1 px-3 py-2 space-y-1.5">
              <div className="text-[10px] text-amber-200">
                ⚠ Simulation active. Clique sur la case active pour la décocher et revenir à la vue créa.
              </div>
              <button
                type="button"
                onClick={() => { setStoredViewMode('creator'); setOpen(false); }}
                data-testid="view-mode-revert-creator"
                className="w-full px-2 py-1 text-[11px] bg-[#E4FF00]/15 text-[#E4FF00] border border-[#E4FF00]/40 rounded-sm hover:bg-[#E4FF00]/25"
              >
                Revenir à la vue Créatrice
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
