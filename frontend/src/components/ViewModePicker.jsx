import React, { useState } from 'react';
import { ChevronDown, Crown, User, Shield, ShieldCheck, EyeOff, Eye, Check } from 'lucide-react';
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
  creator: { Icon: Crown, labelKey: 'view_creator', color: 'text-[#E4FF00]', desc: 'Comme la créatrice' },
  user:    { Icon: User, labelKey: 'view_user', color: 'text-lime-300', desc: 'Comme un membre approved' },
  modo:    { Icon: Shield, labelKey: 'view_modo', color: 'text-cyan-300', desc: 'Comme un modérateur' },
  admin:   { Icon: ShieldCheck, labelKey: 'view_admin', color: 'text-orange-300', desc: 'Comme un administrateur' },
  guest:   { Icon: EyeOff, labelKey: 'view_guest', color: 'text-violet-300', desc: 'Comme un visiteur public' },
};

// iter87 — Toutes les vues (y compris creator) sont coches optionnelles.
// Si AUCUNE n'est cochée → mode "écriture" (pas en simulation).
const ORDER = ['creator', 'user', 'modo', 'admin', 'guest'];

export default function ViewModePicker({ role, viewMode, guestView, guestViews, controlledOpen = undefined, onOpenChange }) {
  const { t } = useLanguage();
  const [internalOpen, setInternalOpen] = useState(false);
  // iter113 — Coordination dropdown : si controlledOpen est fourni par le
  // parent, un seul dropdown ouvert à la fois dans la toolbar.
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setOpen = (v) => {
    const next = typeof v === 'function' ? v(open) : v;
    if (onOpenChange) onOpenChange(next);
    else setInternalOpen(next);
  };

  // iter105 — Le picker est désormais visible aussi pour les visiteurs et
  // utilisateurs/modos/admins, MAIS avec un comportement différent :
  // - Créa : peut basculer librement entre toutes les vues (simulation)
  // - Visiteurs non-créa : peuvent choisir UNIQUEMENT parmi les vues forcées
  //   par la créa via guest_views. Si aucune vue forcée → free (libre choix).
  const isCreator = role === 'creator';
  const forced = Array.isArray(guestViews) && guestViews.length > 0
    ? guestViews
    : (guestView ? [guestView] : []);
  // iter107 — Quand des vues sont forcées, le picker est contraint à ce sous-ensemble
  // pour tout le monde (créa incluse, pour cohérence). La créa garde l'option 'creator'
  // pour revenir au mode écriture.
  const hasForcedConstraint = forced.length > 0;

  // Cacher le picker si: pas créa ET aucune vue forcée (rien à choisir).
  if (!isCreator && forced.length === 0) return null;

  // iter115 — Modèle simplifié : viewMode est exactement la valeur active.
  //   - viewMode === null/undefined → AUCUNE vue active (aucune case cochée)
  //   - viewMode === 'creator' → case "Vue créatrice" cochée (cliquable + recliquable pour décocher)
  //   - viewMode === 'user'|'modo'|'admin'|'guest' → simulation active
  // Cliquer sur la case déjà active la décoche → retour à "Aucune vue active".
  const isActive = !!viewMode && viewMode !== '';
  const isSimulating = isActive && viewMode !== 'creator';
  const current = isActive ? VIEW_META[viewMode] : VIEW_META.creator;
  const CIcon = current ? current.Icon : Eye;

  const toggle = (mode) => {
    // iter115 — Toggle universel : si la case cliquée est DÉJÀ active, on
    // décoche (retour à "Aucune vue active"). Sinon on active la vue cliquée.
    if (mode === viewMode) {
      setStoredViewMode(null);
    } else {
      // 'creator' est stocké explicitement (et plus comme null) pour
      // matérialiser la case cochée.
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
            ? `bg-cyan-500/10 border-cyan-400/40 ${current.color} hover:bg-cyan-500/20`
            : 'bg-cyan-500/10 border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/20'
        }`}
      >
        <CIcon className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{isActive ? t(current.labelKey) : 'Aucune vue active'}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          data-testid="view-mode-picker-dropdown"
          className="absolute right-0 top-full mt-1.5 w-72 max-h-[70vh] overflow-y-auto bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Simuler une vue (1 à la fois)
          </div>
          {ORDER.map((m) => {
            const meta = VIEW_META[m];
            const Mi = meta.Icon;
            // iter115 — Toggle universel : active = case correspond exactement à viewMode.
            const active = m === viewMode;
            // iter115 — Dimming : vues NON actives sont grisées si une vue est active (sauf 'creator' jamais dimmed).
            const dimmedByForced = hasForcedConstraint && m !== 'creator' && !forced.includes(m);
            const dimmed = isCreator
              ? (isActive && !active && m !== 'creator')
              : dimmedByForced;
            const disabled = dimmedByForced;  // visiteur ne peut pas cocher les vues non-forcées
            return (
              <button
                key={m}
                type="button"
                onClick={() => !disabled && toggle(m)}
                disabled={disabled}
                data-testid={`view-mode-pick-${m}`}
                className={`w-full text-left px-3 py-2 text-xs flex items-start gap-2 transition-opacity ${
                  disabled ? 'cursor-not-allowed' : 'hover:bg-white/[0.05]'
                } ${
                  active ? `${meta.color} bg-white/[0.04]`
                         : dimmed ? 'text-white/40'
                         : 'text-white'
                }`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center transition ${
                  active ? `border-current ${meta.color.replace('text-', 'bg-').replace(']', ']/20')}`
                         : dimmed ? 'border-white/15'
                         : 'border-white/30'
                }`}>
                  {active && <Check className={`w-2.5 h-2.5 ${meta.color}`} />}
                </span>
                <Mi className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${dimmed ? 'opacity-50' : ''} ${meta.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="font-['Chivo'] font-bold">{t(meta.labelKey)}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{meta.desc}</div>
                  {isCreator && m === 'guest' && forced.length > 0 && (
                    <div className="text-[10px] text-amber-300 mt-0.5">
                      ↳ Forcée vers : {forced.join(', ')}
                    </div>
                  )}
                  {disabled && (
                    <div className="text-[10px] text-amber-300/70 mt-0.5">
                      🔒 Non autorisé par la créatrice
                    </div>
                  )}
                </div>
              </button>
            );
          })}
          {isSimulating && (
            <div className="border-t border-white/10 mt-1 px-3 py-2 space-y-1.5">
              <div className="text-[10px] text-amber-200">
                ⚠ Simulation active. Clique sur la case active pour la décocher (aucune vue = mode écriture).
              </div>
              <button
                type="button"
                onClick={() => { setStoredViewMode(null); setOpen(false); }}
                data-testid="view-mode-revert-creator"
                className="w-full px-2 py-1 text-[11px] bg-[#E4FF00]/15 text-[#E4FF00] border border-[#E4FF00]/40 rounded-sm hover:bg-[#E4FF00]/25"
              >
                Désactiver toutes les vues (mode écriture)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
