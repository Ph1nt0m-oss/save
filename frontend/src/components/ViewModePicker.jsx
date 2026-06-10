import React, { useState, useEffect } from 'react';
import { Eye, ChevronDown, Crown, User, Shield, ShieldCheck, EyeOff, Check, Lock } from 'lucide-react';
import { setStoredViewMode } from '../hooks/useDeviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * iter85 — ViewModePicker
 *
 * Permet à la CRÉATRICE de prévisualiser l'app comme la verrait un :
 *   - User (rôle 'approved' normal)
 *   - Modo
 *   - Admin
 *   - Guest (visiteur public)
 *   - Creator (vue par défaut, accès total)
 *
 * Visible uniquement pour les devices creator. Si la créatrice a verrouillé
 * un guest_view côté site (via SiteModeBadge → guest mode + guest_view), le
 * toggle est désactivé (Lock icon).
 *
 * Pour les non-créatrices : ce composant ne s'affiche pas. Le verrou
 * guest_view s'applique automatiquement via le hook useDeviceIdentity
 * (setStoredViewMode(targetMode) dans l'effect CreatorToolbar).
 */
const VIEW_META = {
  creator: { Icon: Crown, label: 'Vue Créatrice', labelKey: 'view_creator', color: 'text-[#E4FF00]', desc: 'Accès total (par défaut)' },
  user:    { Icon: User, label: 'Vue Utilisateur', labelKey: 'view_user', color: 'text-sky-300', desc: 'Comme un membre approved' },
  modo:    { Icon: Shield, label: 'Vue Modo', labelKey: 'view_modo', color: 'text-cyan-300', desc: 'Comme un modérateur' },
  admin:   { Icon: ShieldCheck, label: 'Vue Admin', labelKey: 'view_admin', color: 'text-orange-300', desc: 'Comme un administrateur' },
  guest:   { Icon: EyeOff, label: 'Vue Invitée', labelKey: 'view_guest', color: 'text-amber-300', desc: 'Comme un visiteur public' },
};

const ORDER = ['creator', 'user', 'modo', 'admin', 'guest'];

export default function ViewModePicker({ role, viewMode, siteMode, guestView }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  // Verrou : si la créatrice a forcé un guest_view depuis le site_mode badge,
  // les non-créa ne peuvent pas changer. Mais la créa peut toujours simuler.
  const isCreator = role === 'creator';
  const locked = !isCreator && siteMode === 'guest' && !!guestView;

  // Seul un device créatrice voit ce picker.
  if (!isCreator) {
    return null;
  }

  const current = VIEW_META[viewMode] || VIEW_META.creator;
  const CIcon = current.Icon;

  const select = (mode) => {
    setStoredViewMode(mode);
    setOpen(false);
  };

  return (
    <div className="relative inline-block" data-testid="view-mode-picker">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={locked}
        data-testid="view-mode-picker-toggle"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${
          viewMode === 'creator'
            ? 'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20'
            : `bg-white/[0.04] border-white/15 ${current.color} hover:bg-white/[0.08]`
        } ${locked ? 'opacity-60 cursor-not-allowed' : ''}`}
      >
        {locked ? <Lock className="w-3.5 h-3.5" /> : <CIcon className="w-3.5 h-3.5" />}
        <span className="hidden sm:inline">{t(current.labelKey) || current.label}</span>
        {!locked && <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>
      {open && !locked && (
        <div
          data-testid="view-mode-picker-dropdown"
          className="absolute right-0 mt-1.5 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Prévisualiser comme…
          </div>
          {ORDER.map((m) => {
            const meta = VIEW_META[m];
            const Mi = meta.Icon;
            const active = m === viewMode;
            return (
              <button
                key={m}
                type="button"
                onClick={() => select(m)}
                data-testid={`view-mode-pick-${m}`}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  active ? `${meta.color} bg-white/[0.04]` : 'text-white'
                }`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${active ? meta.color : 'text-transparent'}`}>
                  {active && <Check className="w-3.5 h-3.5" />}
                </span>
                <Mi className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${meta.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="font-['Chivo'] font-bold">{t(meta.labelKey) || meta.label}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{meta.desc}</div>
                </div>
              </button>
            );
          })}
          {viewMode !== 'creator' && (
            <div className="border-t border-white/10 mt-1 px-3 py-2">
              <div className="text-[10px] text-amber-200">
                ⚠ Tu es actuellement en simulation. Les changements/écritures sont désactivés.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
