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
export default function SiteModeBadge({ role, siteMode, siteModes, viewMode, guestView, onChange, className = '' }) {
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

  const isCreator = role === 'creator' && viewMode !== 'guest';

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
      const body = await withCreatorProof(API, axios, { modes: next, guest_view: next.includes('guest') ? guestView : null });
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

  const setGuestView = async (gview) => {
    if (!isCreator || saving) return;
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, { modes: activeModes, guest_view: gview });
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
          className="absolute right-0 mt-1.5 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1 max-h-[480px] overflow-y-auto"
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
              {[
                { id: null,       labelKey: 'sm_guest_view_free' },
                { id: 'user',     labelKey: 'sm_guest_view_force_user' },
                { id: 'creator',  labelKey: 'sm_guest_view_force_creator' },
              ].map((opt) => {
                const sel = (guestView || null) === opt.id;
                return (
                  <button
                    key={String(opt.id)}
                    type="button"
                    onClick={() => setGuestView(opt.id)}
                    disabled={saving}
                    data-testid={`guest-view-opt-${opt.id || 'free'}`}
                    className={`w-full text-left text-[11px] px-2 py-1 rounded-sm transition flex items-center gap-2 ${
                      sel ? 'bg-[#E4FF00]/15 text-[#E4FF00]' : 'text-white hover:bg-white/[0.05]'
                    }`}
                  >
                    {sel && <Check className="w-3 h-3 flex-shrink-0" />}
                    {!sel && <span className="w-3 h-3 inline-block flex-shrink-0" />}
                    {t(opt.labelKey)}
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
