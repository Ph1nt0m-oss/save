import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Eye, X } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** iter125 — localStorage key holding the IDs the créa already dismissed
 *  with the X button. Polling continues but won't re-pop the modal for
 *  these IDs; she can reopen the queue via the blue history icon in
 *  AccountsButton.
 */
const DISMISS_LS_KEY = 'cf_dismissed_export_requests_v1';

function readDismissed() {
  try {
    const v = JSON.parse(localStorage.getItem(DISMISS_LS_KEY) || '[]');
    return Array.isArray(v) ? new Set(v) : new Set();
  } catch (_) { return new Set(); }
}
function writeDismissed(set) {
  try { localStorage.setItem(DISMISS_LS_KEY, JSON.stringify(Array.from(set))); }
  catch (_) {}
}

/** Shared store : queue of pending requests, plus a forced-open trigger from
 *  the history icon. AccountsButton's history icon dispatches the custom
 *  event 'cf:open-export-requests' which we listen to here. */
function broadcastPending(count) {
  try { window.dispatchEvent(new CustomEvent('cf:export-requests-count', { detail: count })); } catch (_) {}
}

// FR date/time helpers — explicit per user request (iter125).
function frDate(iso) {
  try { return new Date(iso).toLocaleDateString('fr-FR'); } catch (_) { return ''; }
}
function frTime(iso) {
  try { return new Date(iso).toLocaleTimeString('fr-FR', { hour12: false }); } catch (_) { return ''; }
}

function displayKind(rawKind) {
  // iter125 — Always hide "+github". Push to GitHub is silent and only
  // happens after the créa approves; the user-visible export format is
  // always ZIP / APK / EXE.
  if (!rawKind) return '—';
  const k = rawKind.toLowerCase();
  if (k.startsWith('zip')) return 'ZIP';
  if (k === 'apk') return 'APK';
  if (k === 'exe') return 'EXE';
  if (k === 'source') return 'ZIP';
  return k.toUpperCase();
}

/**
 * Creator-side modal that surfaces pending export requests one at a time,
 * lets the creator open the related account for review, then approve/reject.
 *
 * iter125 changes:
 *  - 6 friendly fields (Pseudo, Type d'appareil, Nom du projet, Type
 *    d'export, Date, Heure) with FR formatting + i18n labels.
 *  - "+github" suffix hidden — always shows ZIP.
 *  - X button now DISMISSES the request (stores ID in localStorage); the
 *    modal stops popping for that ID until the créa re-opens it via the
 *    blue history button in AccountsButton.
 *  - Polls every 8 s but only shows modal if there is at least one
 *    non-dismissed pending request.
 */
export default function ExportApprovalNotifier({ onOpenAccount }) {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const isCreator = device.role === 'creator' && device.viewMode !== 'guest';
  const [pending, setPending] = useState([]);
  const [dismissed, setDismissed] = useState(() => readDismissed());
  const [forcedOpen, setForcedOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!isCreator || !device.keyId) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/exports/pending`, body);
      const rows = r.data?.requests || [];
      setPending(rows);
      broadcastPending(rows.filter((x) => dismissed.has(x.request_id)).length);
    } catch (_) {}
  }, [isCreator, device.keyId, dismissed]);

  // Polling
  useEffect(() => {
    if (!isCreator || !device.keyId) return undefined;
    let cancelled = false;
    const tick = async () => { if (!cancelled) await refresh(); };
    tick();
    const id = setInterval(tick, 8000);
    return () => { cancelled = true; clearInterval(id); };
  }, [isCreator, device.keyId, refresh]);

  // Listen for forced-open events from the AccountsButton history icon.
  useEffect(() => {
    const onOpen = () => { setForcedOpen(true); refresh(); };
    window.addEventListener('cf:open-export-requests', onOpen);
    return () => window.removeEventListener('cf:open-export-requests', onOpen);
  }, [refresh]);

  if (!isCreator) return null;

  // What request should be visible right now ?
  // - In forced-open mode (history button click) → first dismissed pending.
  // - Otherwise → first NON-dismissed pending.
  const visibleQueue = forcedOpen
    ? pending
    : pending.filter((p) => !dismissed.has(p.request_id));

  if (visibleQueue.length === 0) {
    // Nothing to show. If user just forced-open but no items, close.
    if (forcedOpen) setForcedOpen(false);
    return null;
  }
  const req = visibleQueue[0];

  const dismissCurrent = () => {
    const next = new Set(dismissed);
    next.add(req.request_id);
    setDismissed(next);
    writeDismissed(next);
    broadcastPending(pending.filter((x) => next.has(x.request_id)).length);
    // If forced-open mode, hop to next item ; else next render hides this one.
    if (forcedOpen && visibleQueue.length <= 1) setForcedOpen(false);
  };

  const decide = async (decision) => {
    try {
      const body = await withCreatorProof(API, axios, { request_id: req.request_id, decision });
      await axios.post(`${API}/exports/decide`, body);
      // Forget the dismissed state for this id since it's now resolved.
      const next = new Set(dismissed);
      next.delete(req.request_id);
      setDismissed(next);
      writeDismissed(next);
      setPending((ps) => ps.filter((p) => p.request_id !== req.request_id));
      toast.success(decision === 'approve' ? t('exp_approved_title') : t('exp_rejected_title'));
      if (forcedOpen && visibleQueue.length <= 1) setForcedOpen(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  return (
    <div className="fixed inset-0 z-[88] flex items-center justify-center bg-black/70 p-4" data-testid="export-approval-modal">
      <div className="max-w-md w-full bg-[#0A0A0A] border border-amber-400/40 rounded-sm p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Eye className="w-5 h-5 text-amber-300" />
          <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('exp_review_title')}</h2>
          <button
            onClick={dismissCurrent}
            data-testid="exp-dismiss-btn"
            className="ml-auto text-[#A1A1AA] hover:text-white"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="bg-black/30 border border-white/10 rounded-sm p-3 text-xs space-y-1.5">
          <div className="flex gap-2">
            <span className="text-[#71717A] min-w-[140px]">{t('exp_field_pseudo')}</span>
            <span className="text-white truncate" data-testid="exp-field-pseudo">{req.pseudo || '—'}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-[#71717A] min-w-[140px]">{t('exp_field_device')}</span>
            <span className="text-white truncate" data-testid="exp-field-device">{req.device_label || '—'}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-[#71717A] min-w-[140px]">{t('exp_field_project')}</span>
            <span className="text-white truncate" data-testid="exp-field-project">{req.project_name || req.project_id}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-[#71717A] min-w-[140px]">{t('exp_field_kind')}</span>
            <span className="text-[#E4FF00]" data-testid="exp-field-kind">{displayKind(req.export_kind)}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-[#71717A] min-w-[140px]">{t('exp_field_date')}</span>
            <span className="text-white" data-testid="exp-field-date">{frDate(req.created_at)}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-[#71717A] min-w-[140px]">{t('exp_field_time')}</span>
            <span className="text-white" data-testid="exp-field-time">{frTime(req.created_at)}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => { onOpenAccount?.({ key_id: req.key_id, project_id: req.project_id }); }}
          data-testid="exp-review-open"
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/10 rounded-sm font-['Chivo'] font-bold text-xs transition"
        >
          <Eye className="w-3.5 h-3.5" />{t('exp_review_open')}
        </button>
        <div className="flex flex-col gap-2">
          <button onClick={() => decide('approve')} data-testid="exp-approve-btn" className="w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/40 text-emerald-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition">
            <CheckCircle className="w-4 h-4" />{t('exp_review_approve')}
          </button>
          <button onClick={() => decide('reject')} data-testid="exp-reject-btn" className="w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 bg-red-500/15 hover:bg-red-500/25 border border-red-400/40 text-red-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition">
            <XCircle className="w-4 h-4" />{t('exp_review_reject')}
          </button>
        </div>
      </div>
    </div>
  );
}
