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
  approve:    { tk: 'dec_approve',    color: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' },
  revoke:     { tk: 'dec_revoke',     color: 'text-red-300 border-red-400/40 bg-red-400/10' },
  disconnect: { tk: 'dec_disconnect', color: 'text-amber-300 border-amber-400/40 bg-amber-400/10' },
  promote:    { tk: 'dec_promote',    color: 'text-[#E4FF00] border-[#E4FF00]/40 bg-[#E4FF00]/10' },
  add_by_key: { tk: 'dec_add_by_key', color: 'text-sky-300 border-sky-400/40 bg-sky-400/10' },
};

/**
 * Top-bar toolbar grouping the site-mode toggle, the decisions history
 * button and the view-mode toggle. Designed to live in headers next to
 * the user menu.
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

      {/* History button — visible only to the actual creator device, but
          also visible in guest-preview-view (so creator can come back). */}
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

      {/* View-mode toggle — only for creator devices */}
      {isCreatorDevice && (
        <button
          type="button"
          onClick={() => setStoredViewMode(inGuestView ? 'creator' : 'guest')}
          data-testid="view-mode-toggle"
          title={inGuestView ? t('vm_back_to_creator') : t('vm_preview_as_guest')}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${
            inGuestView
              ? 'bg-amber-400/10 border-amber-400/40 text-amber-300 hover:bg-amber-400/20'
              : 'bg-white/[0.04] border-white/10 text-[#A1A1AA] hover:text-white hover:bg-white/[0.08]'
          }`}
        >
          {inGuestView ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">{inGuestView ? t('vm_guest_view') : t('vm_creator_view')}</span>
        </button>
      )}

      {historyOpen && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => setHistoryOpen(false)}
          data-testid="history-modal"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-xl w-full max-h-[80vh] overflow-y-auto bg-[#0A0A0A] border border-white/15 rounded-sm p-5 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-[#E4FF00]" />
                <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('dm_history')}</h2>
              </div>
              <button onClick={() => setHistoryOpen(false)} data-testid="history-close" className="text-[#A1A1AA] hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            {loadingHist && <div className="text-xs text-[#A1A1AA]">{t('dm_loading')}</div>}
            {!loadingHist && decisions.length === 0 && (
              <div className="text-xs text-[#A1A1AA]" data-testid="history-empty">{t('dm_history_empty')}</div>
            )}
            <div className="space-y-1.5">
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
          </div>
        </div>
      )}
    </div>
  );
}
