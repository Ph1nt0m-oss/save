import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { History, Eye, EyeOff, X } from 'lucide-react';
import { toast } from 'sonner';
import SiteModeBadge from './SiteModeBadge';
import useDeviceIdentity, { setStoredViewMode } from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_META = {
  approve:        { tk: 'dec_approve',        color: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' },
  revoke:         { tk: 'dec_revoke',         color: 'text-red-300 border-red-400/40 bg-red-400/10' },
  disconnect:     { tk: 'dec_disconnect',     color: 'text-amber-300 border-amber-400/40 bg-amber-400/10' },
  promote:        { tk: 'dec_promote',        color: 'text-[#E4FF00] border-[#E4FF00]/40 bg-[#E4FF00]/10' },
  add_by_key:     { tk: 'dec_add_by_key',     color: 'text-sky-300 border-sky-400/40 bg-sky-400/10' },
  request_access: { tk: 'dec_request_access', color: 'text-purple-300 border-purple-400/40 bg-purple-400/10' },
};

/**
 * Top-bar toolbar. Two distinct layouts:
 *  - Creator devices: SiteMode dropdown + History side-panel button.
 *  - Non-creator devices ("guests"): SiteMode read-only badge + a view-mode
 *    toggle ("user view" ↔ "creator preview, read-only") so they can peek
 *    at the admin surface (used as a tutorial). Free to flip anytime.
 */
export default function CreatorToolbar() {
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [decisions, setDecisions] = useState([]);
  const [loadingHist, setLoadingHist] = useState(false);

  const loadDecisions = async () => {
    setLoadingHist(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/devices/decisions`, body);
      setDecisions(r.data?.decisions || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_list_unavailable'));
    } finally { setLoadingHist(false); }
  };

  useEffect(() => { if (historyOpen) loadDecisions(); /* eslint-disable-next-line */ }, [historyOpen]);

  const isCreatorDevice = device.role === 'creator';
  const inGuestView = device.viewMode === 'guest';

  return (
    <div className="inline-flex items-center gap-1.5 sm:gap-2 flex-wrap" data-testid="creator-toolbar">
      <SiteModeBadge
        role={device.role}
        siteMode={device.siteMode}
        viewMode={device.viewMode}
        onChange={() => device.refresh()}
      />

      {/* History side-panel button — creator only */}
      {isCreatorDevice && (
        <button
          type="button"
          onClick={() => setHistoryOpen(true)}
          data-testid="open-history-btn"
          title={t('dm_history')}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-white hover:bg-white/[0.08] transition-colors"
        >
          <History className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">{t('dm_history')}</span>
        </button>
      )}

      {/* Guest-facing view-mode toggle: only for non-creator devices. */}
      {!isCreatorDevice && (
        <button
          type="button"
          onClick={() => setStoredViewMode(inGuestView ? 'creator' : 'guest')}
          data-testid="view-mode-toggle"
          title={inGuestView ? t('vm_back_to_user') : t('vm_preview_as_creator')}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${
            inGuestView
              ? 'bg-amber-400/10 border-amber-400/40 text-amber-300 hover:bg-amber-400/20'
              : 'bg-white/[0.04] border-white/10 text-[#A1A1AA] hover:text-white hover:bg-white/[0.08]'
          }`}
        >
          {inGuestView ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">{inGuestView ? t('vm_preview_label') : t('vm_user_label')}</span>
        </button>
      )}

      {historyOpen && (
        <>
          <div
            className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm"
            onClick={() => setHistoryOpen(false)}
            data-testid="history-backdrop"
          />
          <aside
            data-testid="history-panel"
            className="fixed top-0 right-0 bottom-0 z-[61] w-full sm:w-[420px] bg-[#0A0A0A] border-l border-white/15 shadow-[-20px_0_60px_rgba(0,0,0,0.6)] flex flex-col"
          >
            <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 flex-shrink-0">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-[#E4FF00]" />
                <h2 className="text-base font-['Chivo'] font-bold text-white">{t('dm_history')}</h2>
                {decisions.length > 0 && (
                  <span className="text-[10px] uppercase tracking-widest text-[#71717A]">
                    ({decisions.length})
                  </span>
                )}
              </div>
              <button
                onClick={() => setHistoryOpen(false)}
                data-testid="history-close"
                className="text-[#A1A1AA] hover:text-white"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
              {loadingHist && (
                <div className="text-xs text-[#A1A1AA] px-2 py-3" data-testid="history-loading">
                  {t('dm_loading')}
                </div>
              )}
              {!loadingHist && decisions.length === 0 && (
                <div className="text-xs text-[#A1A1AA] px-2 py-3" data-testid="history-empty">
                  {t('dm_history_empty')}
                </div>
              )}
              {decisions.map((dec, i) => {
                const meta = ACTION_META[dec.action] || { tk: 'dm_op_done', color: 'text-white border-white/20 bg-white/5' };
                return (
                  <div
                    key={`${dec.target_key_id}-${dec.ts}-${i}`}
                    data-testid="history-row"
                    className="bg-black/30 border border-white/10 rounded-sm p-2.5 flex items-center gap-3"
                  >
                    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-1.5 py-0.5 border rounded-sm ${meta.color}`}>
                      {t(meta.tk)}
                    </span>
                    <div className="flex-1 min-w-0">
                      {dec.target_label && (
                        <div className="text-xs text-white truncate">{dec.target_label}</div>
                      )}
                      <code className="block text-[10px] text-[#71717A] truncate">{dec.target_key_id}</code>
                    </div>
                    <div className="text-[10px] text-[#71717A] flex-shrink-0">
                      {new Date(dec.ts).toLocaleString()}
                    </div>
                  </div>
                );
              })}
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
