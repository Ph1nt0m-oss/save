import React, { useState } from 'react';
import axios from 'axios';
import { Globe, Lock, Crown, EyeOff, Check, ChevronDown } from 'lucide-react';import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODES = [
  { id: 'public',  label: 'Public',   icon: Globe,  hint: "Tout le monde peut accéder au site." },
  { id: 'private', label: 'Privé',    icon: Lock,   hint: "Seuls les appareils approuvés." },
  { id: 'creator', label: 'Créateur', icon: Crown,  hint: "Seuls les appareils créateurs." },
  { id: 'guest',   label: 'Invité',   icon: EyeOff, hint: "Lecture seule pour les visiteurs." },
];

/**
 * 4-state site mode toggle.
 * - If `role === 'creator'`: interactive dropdown that PUTs /system/site-mode.
 * - Otherwise: read-only badge showing current mode.
 */
export default function SiteModeBadge({ role, siteMode, onChange, className = '' }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const current = MODES.find((m) => m.id === siteMode) || MODES[0];
  const Icon = current.icon;
  const isCreator = role === 'creator';

  const setMode = async (mode) => {
    if (!isCreator || saving || mode === siteMode) { setOpen(false); return; }
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, { mode });
      const r = await axios.put(`${API}/system/site-mode`, body);
      toast.success(`Mode du site : ${MODES.find((m) => m.id === r.data?.mode)?.label || mode}`);
      onChange?.(r.data?.mode || mode);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Changement de mode impossible');
    } finally {
      setSaving(false);
      setOpen(false);
    }
  };

  if (!isCreator) {
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
          title="Mode du site — seul le créateur peut le changer"
          data-testid="site-mode-readonly-toggle"
        >
          <Lock className="w-3 h-3" />
          <Icon className="w-3.5 h-3.5" />
          <span>{current.label}</span>
          <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && (
          <div
            data-testid="site-mode-readonly-dropdown"
            className="absolute right-0 mt-1.5 w-56 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1"
          >
            <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
              Réservé au créateur
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
                    <div className="font-['Chivo'] font-bold">{m.label}</div>
                    <div className="text-[10px] text-[#A1A1AA]">{m.hint}</div>
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
        <span>{current.label}</span>
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
                onClick={() => setMode(m.id)}
                disabled={saving}
                data-testid={`site-mode-option-${m.id}`}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  active ? 'text-[#E4FF00]' : 'text-white'
                }`}
              >
                <Mi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="font-['Chivo'] font-bold">{m.label}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{m.hint}</div>
                </div>
                {active && <Check className="w-3 h-3 ml-auto flex-shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
