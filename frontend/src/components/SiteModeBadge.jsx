import React, { useState } from 'react';
import axios from 'axios';
import { Globe, Lock, Crown, EyeOff, Check, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * 4-state site mode toggle.
 * - If `role === 'creator'`: interactive dropdown that PUTs /system/site-mode.
 * - Otherwise: read-only badge showing current mode.
 */
export default function SiteModeBadge({ role, siteMode, viewMode, guestView, onChange, className = '' }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const MODES = [
    { id: 'public',  icon: Globe,  labelKey: 'sm_public',  hintKey: 'sm_public_hint'  },
    { id: 'private', icon: Lock,   labelKey: 'sm_private', hintKey: 'sm_private_hint' },
    { id: 'creator', icon: Crown,  labelKey: 'sm_creator', hintKey: 'sm_creator_hint' },
    { id: 'guest',   icon: EyeOff, labelKey: 'sm_guest',   hintKey: 'sm_guest_hint'   },
  ];

  const current = MODES.find((m) => m.id === siteMode) || MODES[0];
  const Icon = current.icon;
  const isCreator = role === 'creator' && viewMode !== 'guest';

  const setMode = async (mode, gview = null) => {
    if (!isCreator || saving) { setOpen(false); return; }
    if (mode === siteMode && (mode !== 'guest' || gview === guestView)) { setOpen(false); return; }
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, { mode, guest_view: gview });
      const r = await axios.put(`${API}/system/site-mode`, body);
      const resolvedMode = r.data?.mode || mode;
      const resolved = MODES.find((m) => m.id === resolvedMode);
      const label = resolved ? t(resolved.labelKey) : resolvedMode;
      toast.success(t('sm_changed_to').replace('{mode}', label));
      onChange?.(resolvedMode);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('sm_change_failed'));
    } finally {
      setSaving(false);
      setOpen(false);
    }
  };

  if (!isCreator) {
    // Non-creator devices only see the site-mode badge when they have
    // explicitly opted into the "preview as creator" view AND the current
    // site mode is not "creator-only" (which would already kick them out).
    // In all other cases, the selector is completely hidden.
    if (viewMode !== 'creator' || siteMode === 'creator') return null;

    // Read-only — but still informative. Clicking opens the same dropdown
    // with all 4 modes visible (so users can read the hints), but every
    // option is disabled. Locked icon on the trigger makes the gating
    // crystal-clear.
    return (
      <div className={`relative inline-block ${className}`} data-testid="site-mode-readonly">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:bg-white/[0.06] transition-colors"
          title={t('sm_tooltip')}
          data-testid="site-mode-readonly-toggle"
        >
          <Lock className="w-3 h-3" />
          <Icon className="w-3.5 h-3.5" />
          <span>{t(current.labelKey)}</span>
          <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && (
          <div
            data-testid="site-mode-readonly-dropdown"
            className="absolute right-0 mt-1.5 w-56 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1"
          >
            <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
              {t('sm_creator_only_label')}
            </div>
            {MODES.map((m) => {
              const Mi = m.icon;
              const active = m.id === siteMode;
              return (
                <div
                  key={m.id}
                  data-testid={`site-mode-readonly-option-${m.id}`}
                  className={`px-3 py-2 text-xs flex items-start gap-2 cursor-not-allowed opacity-60 ${
                    active ? 'text-[#E4FF00]' : 'text-white'
                  }`}
                >
                  <Mi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <div className="font-['Chivo'] font-bold">{t(m.labelKey)}</div>
                    <div className="text-[10px] text-[#A1A1AA]">{t(m.hintKey)}</div>
                  </div>
                  {active && <Check className="w-3 h-3 ml-auto flex-shrink-0" />}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

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
        <Icon className="w-3.5 h-3.5" />
        <span>{t(current.labelKey)}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          data-testid="site-mode-dropdown"
          className="absolute right-0 mt-1.5 w-56 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1"
        >
          {MODES.map((m) => {
            const Mi = m.icon;
            const active = m.id === siteMode;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id, m.id === 'guest' ? guestView : null)}
                disabled={saving}
                data-testid={`site-mode-option-${m.id}`}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  active ? 'text-[#E4FF00]' : 'text-white'
                }`}
              >
                <Mi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="font-['Chivo'] font-bold">{t(m.labelKey)}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{t(m.hintKey)}</div>
                </div>
                {active && <Check className="w-3 h-3 ml-auto flex-shrink-0" />}
              </button>
            );
          })}
          {/* Guest sub-views: pick which view visitors see (or leave free). */}
          {siteMode === 'guest' && (
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
                    onClick={() => setMode('guest', opt.id)}
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
