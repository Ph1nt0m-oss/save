import React, { useState } from 'react';
import axios from 'axios';
import { Globe, Lock, Crown, EyeOff, Check, ChevronDown, Shield, ShieldAlert, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter83 C11 — Site-mode multi-checkbox.
 *
 * Avant : un seul mode (public | private | creator | guest).
 * Maintenant : N modes simultanés. La créatrice coche les audiences à laisser
 * entrer (ex: public + staff). Le backend gère le gating via le helper
 * `_device_matches_mode` (au moins UN mode actif doit matcher).
 *
 * Ajouts iter83 : 'staff' (admin+modo), 'admin' (admins seuls), 'modo'
 * (modos seuls). Les 3 nouvelles audiences sont identifiées par l'icône
 * Shield/ShieldCheck/ShieldAlert.
 */
export default function SiteModeBadge({ role, siteMode, siteModes, viewMode, guestView, guestViews, onChange, className = '' }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const MODES = [
    { id: 'public',  icon: Globe,       labelKey: 'sm_public',  hintKey: 'sm_public_hint'  },
    { id: 'private', icon: Lock,        labelKey: 'sm_private', hintKey: 'sm_private_hint' },
    { id: 'creator', icon: Crown,       labelKey: 'sm_creator', hintKey: 'sm_creator_hint' },
    { id: 'guest',   icon: EyeOff,      labelKey: 'sm_guest',   hintKey: 'sm_guest_hint'   },
    { id: 'staff',   icon: Shield,      label: 'Staff',         hint: 'Admins + Modos uniquement' },
    { id: 'admin',   icon: ShieldCheck, label: 'Admins',        hint: 'Admins uniquement' },
    { id: 'modo',    icon: ShieldAlert, label: 'Modos',         hint: 'Modos uniquement' },
  ];

  // Source de vérité : siteModes (array) ; fallback à siteMode (legacy str)
  const activeModes = Array.isArray(siteModes) && siteModes.length > 0
    ? siteModes
    : (siteMode ? [siteMode] : ['public']);

  // iter99 — Fix utilisatrice : la créatrice physique (par sa clé) doit TOUJOURS
  // pouvoir modifier le site mode et le guest_view, même quand elle simule une
  // autre vue. La simulation est juste un mode d'affichage local, pas un retrait
  // de pouvoirs côté backend (signature ECDSA reste la créa).
  const isCreator = role === 'creator';

  const display = activeModes.length === 1
    ? (MODES.find((m) => m.id === activeModes[0]) || MODES[0])
    : null;
  const DisplayIcon = display ? display.icon : Globe;
  const displayLabel = display
    ? (display.labelKey ? t(display.labelKey) : display.label)
    : `${activeModes.length} audiences`;

  const toggleMode = async (modeId) => {
    if (!isCreator || saving) return;
    let next = [...activeModes];
    if (next.includes(modeId)) {
      next = next.filter((m) => m !== modeId);
    } else {
      next.push(modeId);
    }
    if (next.length === 0) next = ['public']; // Au moins 1 mode
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, {
        modes: next,
        guest_views: next.includes('guest') ? (activeGuestViews.length > 0 ? activeGuestViews : []) : [],
      });
      const r = await axios.put(`${API}/system/site-mode`, body);
      const resolved = Array.isArray(r.data?.modes) ? r.data.modes : next;
      toast.success(`Audiences : ${resolved.join(', ')}`);
      onChange?.(resolved[0], resolved);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('sm_change_failed'));
    } finally {
      setSaving(false);
    }
  };

  // iter103 — Source de vérité guest_views (multi). Fallback legacy guest_view str.
  const activeGuestViews = Array.isArray(guestViews) && guestViews.length > 0
    ? guestViews
    : (guestView ? [guestView] : []);

  const toggleGuestView = async (gview) => {
    if (!isCreator || saving) return;
    let next = [...activeGuestViews];
    if (gview === null) {
      next = [];  // "Au choix du visiteur" = aucune vue forcée
    } else if (next.includes(gview)) {
      next = next.filter((v) => v !== gview);
    } else {
      next.push(gview);
    }
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, {
        modes: activeModes,
        guest_views: next,
      });
      await axios.put(`${API}/system/site-mode`, body);
      onChange?.(activeModes[0], activeModes);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('sm_change_failed'));
    } finally {
      setSaving(false);
    }
  };

  if (!isCreator) return null;

  return (
    <div className={`relative inline-block ${className}`} data-testid="site-mode-creator">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={saving}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm bg-[#E4FF00]/10 border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20 transition-colors"
        data-testid="site-mode-toggle"
      >
        <Crown className="w-3.5 h-3.5" />
        <DisplayIcon className="w-3.5 h-3.5" />
        <span>{displayLabel}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          data-testid="site-mode-dropdown"
          className="absolute right-[10cm] mt-1.5 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1 max-h-[480px] overflow-y-auto"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Audiences actives (multi-sélection)
          </div>
          {MODES.map((m) => {
            const Mi = m.icon;
            const active = activeModes.includes(m.id);
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => toggleMode(m.id)}
                disabled={saving}
                data-testid={`site-mode-option-${m.id}`}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  active ? 'text-[#E4FF00] bg-[#E4FF00]/5' : 'text-white'
                }`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center ${
                  active ? 'border-[#E4FF00] bg-[#E4FF00]/20' : 'border-white/30'
                }`}>
                  {active && <Check className="w-2.5 h-2.5 text-[#E4FF00]" />}
                </span>
                <Mi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-['Chivo'] font-bold">{m.labelKey ? t(m.labelKey) : m.label}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{m.hintKey ? t(m.hintKey) : m.hint}</div>
                </div>
              </button>
            );
          })}
          {activeModes.includes('guest') && (
            <div className="border-t border-white/10 mt-1 pt-1 px-3 py-2 space-y-1.5" data-testid="guest-view-options">
              <div className="text-[10px] uppercase tracking-widest text-[#71717A]">{t('sm_guest_view_lock')}</div>
              <div className="text-[10px] text-amber-200/80 mb-1">
                Coche plusieurs vues — le visiteur choisira parmi ce sous-ensemble. Aucune coche = libre.
              </div>
              {[
                { id: null,       labelKey: 'sm_guest_view_free',          label: 'Au choix du visiteur (libre)' },
                { id: 'user',     labelKey: 'sm_guest_view_force_user',    label: 'Forcer la vue utilisateur (lecture seule)' },
                { id: 'modo',     labelKey: 'sm_guest_view_force_modo',    label: 'Forcer la vue modo (lecture seule)' },
                { id: 'admin',    labelKey: 'sm_guest_view_force_admin',   label: 'Forcer la vue admin (lecture seule)' },
                { id: 'creator',  labelKey: 'sm_guest_view_force_creator', label: 'Forcer la vue créatrice (lecture seule)' },
              ].map((opt) => {
                const sel = opt.id === null
                  ? activeGuestViews.length === 0
                  : activeGuestViews.includes(opt.id);
                // iter105 — Sur la badge créa : aucun dimming. La créa peut sélectionner librement.
                // Le dimming est appliqué côté ViewModePicker du visiteur uniquement.
                return (
                  <button
                    key={String(opt.id)}
                    type="button"
                    onClick={() => toggleGuestView(opt.id)}
                    disabled={saving}
                    data-testid={`guest-view-opt-${opt.id || 'free'}`}
                    className={`w-full text-left text-[11px] px-2 py-1 rounded-sm transition flex items-center gap-2 ${
                      sel ? 'bg-[#E4FF00]/15 text-[#E4FF00]' : 'text-white hover:bg-white/[0.05]'
                    }`}
                  >
                    <span className={`w-3.5 h-3.5 flex-shrink-0 border rounded-sm flex items-center justify-center transition ${
                      sel ? 'border-[#E4FF00] bg-[#E4FF00]/20' : 'border-white/30'
                    }`}>
                      {sel && <Check className="w-2.5 h-2.5 text-[#E4FF00]" />}
                    </span>
                    {t(opt.labelKey) || opt.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
