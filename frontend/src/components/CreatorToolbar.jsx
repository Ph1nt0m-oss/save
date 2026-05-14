import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { History, Eye, EyeOff, X, Download, Trash2, RefreshCw, Undo2, ShieldOff, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import SiteModeBadge from './SiteModeBadge';
import useDeviceIdentity, { setStoredViewMode } from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_META = {
  approve:        { tk: 'dec_approve',        color: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' },
  revoke:         { tk: 'dec_revoke',         color: 'text-red-300 border-red-400/40 bg-red-400/10' },
  promote:        { tk: 'dec_promote',        color: 'text-amber-300 border-amber-400/40 bg-amber-400/10' },
};

function downloadText(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Top-bar toolbar. Two distinct layouts:
 *  - Creator devices: SiteMode dropdown + History side-panel button.
 *  - Non-creator devices ("guests"): SiteMode read-only badge + a view-mode
 *    toggle. The History button is creator-only.
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

  const undoFromHistory = async (target_key_id, decision_ts) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id, decision_ts });
      const r = await axios.post(`${API}/devices/decisions/undo`, body);
      if (r.data?.success === false) {
        toast.error(t('hist_undo_not_supported'));
      } else {
        toast.success(t('hist_undo_done'));
      }
      loadDecisions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_op_failed'));
    }
  };

  const blockFromHistory = async (target_key_id) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id });
      await axios.post(`${API}/devices/block`, body);
      toast.success(t('hist_blocked'));
      loadDecisions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_op_failed'));
    }
  };

  const unblockFromHistory = async (target_key_id) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id });
      await axios.post(`${API}/devices/unblock`, body);
      toast.success(t('hist_unblocked'));
      loadDecisions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_op_failed'));
    }
  };

  const clearHistory = async () => {
    if (!window.confirm(t('hist_clear_confirm'))) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/devices/decisions/clear`, body);
      toast.success(t('hist_cleared').replace('{n}', String(r.data?.deleted || 0)));
      setDecisions([]);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_op_failed'));
    }
  };

  const exportHistory = () => {
    const ts = new Date();
    const ymd = ts.toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const header = [
      '# CodeForge AI — Historique des décisions',
      `# Exporté le ${ts.toLocaleString()}`,
      `# Total entrées: ${decisions.length}`,
      '#',
      '# Format: [date]  ACTION  cle_appareil  (label)',
      ''.padEnd(80, '-'),
      '',
    ].join('\n');
    const labelMap = {
      approve: 'ACCEPTÉ',
      revoke: 'REFUSÉ',
      promote: 'CRÉATRICE',
    };
    const body = decisions.map((d) => {
      const action = labelMap[d.action] || d.action.toUpperCase();
      const label = d.target_label ? `  (${d.target_label})` : '';
      const when = new Date(d.ts).toLocaleString();
      return `[${when}]  ${action.padEnd(18)}  ${d.target_key_id}${label}`;
    }).join('\n');
    downloadText(`codeforge-history-${ymd}.txt`, header + body + '\n');
    toast.success(t('hist_exported'));
  };

  const isCreatorDevice = device.role === 'creator';
  const inGuestView = device.viewMode === 'guest';
  // If creator forced a specific guest_view, sync localStorage so the
  // visitor's view toggle reflects that locked state. Non-creator devices
  // also lose the ability to toggle.
  React.useEffect(() => {
    if (device.siteMode === 'guest' && device.guestView) {
      const targetMode = device.guestView === 'creator' ? 'guest' : 'creator';
      setStoredViewMode(targetMode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device.siteMode, device.guestView]);
  const viewLocked = device.siteMode === 'guest' && !!device.guestView;

  return (
    <div className="inline-flex items-center gap-1.5 sm:gap-2 flex-wrap" data-testid="creator-toolbar">
      <SiteModeBadge
        role={device.role}
        siteMode={device.siteMode}
        viewMode={device.viewMode}
        guestView={device.guestView}
        onChange={() => device.refresh()}
      />

      {/* History panel removed in iter57: the right-side panel is now
          reserved for the Messages drawer. */}

      {!isCreatorDevice && !viewLocked && (
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
            className="fixed top-0 right-0 bottom-0 z-[61] w-full sm:w-[460px] bg-[#0A0A0A] border-l border-white/15 shadow-[-20px_0_60px_rgba(0,0,0,0.6)] flex flex-col"
          >
            <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 flex-shrink-0 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <History className="w-5 h-5 text-[#E4FF00] flex-shrink-0" />
                <h2 className="text-base font-['Chivo'] font-bold text-white truncate">{t('dm_history')}</h2>
                {decisions.length > 0 && (
                  <span className="text-[10px] uppercase tracking-widest text-[#71717A] flex-shrink-0">
                    ({decisions.length})
                  </span>
                )}
              </div>
              <button
                onClick={() => setHistoryOpen(false)}
                data-testid="history-close"
                className="text-[#A1A1AA] hover:text-white flex-shrink-0"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </header>

            <div className="px-4 py-2 border-b border-white/10 flex items-center gap-2 flex-shrink-0 flex-wrap">
              <button
                onClick={loadDecisions}
                data-testid="history-refresh"
                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] border border-white/15 text-[#A1A1AA] hover:text-white hover:border-white/30 rounded-sm transition"
              >
                <RefreshCw className="w-3 h-3" />
                {t('dm_refresh')}
              </button>
              <button
                onClick={exportHistory}
                disabled={decisions.length === 0}
                data-testid="history-export"
                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] border border-sky-400/40 text-sky-300 hover:bg-sky-400/10 rounded-sm transition disabled:opacity-40"
              >
                <Download className="w-3 h-3" />
                {t('hist_export')}
              </button>
              <button
                onClick={clearHistory}
                disabled={decisions.length === 0}
                data-testid="history-clear"
                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] border border-red-400/40 text-red-300 hover:bg-red-400/10 rounded-sm transition disabled:opacity-40 ml-auto"
              >
                <Trash2 className="w-3 h-3" />
                {t('hist_clear')}
              </button>
            </div>

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
                // Count how many "revoke" entries this same key has → after
                // 2+ refusals show the BLOCK button prominently.
                const refusedCount = decisions.filter(
                  (x) => x.target_key_id === dec.target_key_id && x.action === 'revoke',
                ).length;
                return (
                  <div
                    key={`${dec.target_key_id}-${dec.ts}-${i}`}
                    data-testid="history-row"
                    className="bg-black/30 border border-white/10 rounded-sm p-2.5 space-y-1.5"
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-1.5 py-0.5 border rounded-sm ${meta.color}`}>
                        {t(meta.tk)}
                      </span>
                      <div className="text-[10px] text-[#71717A]">
                        {new Date(dec.ts).toLocaleString()}
                      </div>
                      <div className="ml-auto flex items-center gap-1">
                        {dec.action === 'revoke' && refusedCount >= 2 && (
                          <button
                            onClick={() => blockFromHistory(dec.target_key_id)}
                            data-testid={`history-block-${dec.target_key_id}`}
                            title={t('hist_block')}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] border border-red-500/60 text-red-200 hover:bg-red-500/30 rounded-sm transition"
                          >
                            <ShieldOff className="w-3 h-3" />
                            {t('hist_block')}
                          </button>
                        )}
                        {dec.action === 'revoke' && refusedCount < 2 && (
                          <button
                            onClick={() => blockFromHistory(dec.target_key_id)}
                            data-testid={`history-block-${dec.target_key_id}`}
                            title={t('hist_block')}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] border border-red-400/30 text-red-300/70 hover:bg-red-400/10 hover:text-red-200 rounded-sm transition"
                          >
                            <ShieldOff className="w-3 h-3" />
                            {t('hist_block')}
                          </button>
                        )}
                        <button
                          onClick={() => unblockFromHistory(dec.target_key_id)}
                          data-testid={`history-unblock-${dec.target_key_id}`}
                          title={t('hist_unblock')}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] border border-emerald-400/30 text-emerald-300/70 hover:bg-emerald-400/10 hover:text-emerald-200 rounded-sm transition"
                        >
                          <ShieldCheck className="w-3 h-3" />
                          {t('hist_unblock')}
                        </button>
                        <button
                          onClick={() => undoFromHistory(dec.target_key_id, dec.ts)}
                          data-testid={`history-undo-${dec.target_key_id}`}
                          title={t('hist_undo')}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] border border-amber-400/40 text-amber-300 hover:bg-amber-400/20 rounded-sm transition"
                        >
                          <Undo2 className="w-3 h-3" />
                          {t('hist_undo')}
                        </button>
                      </div>
                    </div>
                    {dec.target_label && (
                      <div className="text-xs text-white truncate">{dec.target_label}</div>
                    )}
                    <code className="block text-[10px] text-[#71717A] break-all">{dec.target_key_id}</code>
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
