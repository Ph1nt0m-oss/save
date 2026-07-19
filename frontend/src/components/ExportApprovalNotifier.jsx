import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Eye, X, Bot } from 'lucide-react';
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
  const [botReportOpen, setBotReportOpen] = useState(false);
  const [botReport, setBotReport] = useState(null);

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

  // iter143 — Charger le rapport du bot validateur à la demande. Hooks
  // DOIVENT être avant les early returns pour respecter les règles React.
  const loadBotReport = useCallback(async (rid) => {
    if (!rid) return;
    setBotReport(null);
    try {
      const body = await withCreatorProof(API, axios, { request_id: rid });
      const r = await axios.post(`${API}/exports/bot-report`, body);
      setBotReport(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Rapport indisponible');
    }
  }, []);

  // What request should be visible right now ?
  // - In forced-open mode (history button click) → first dismissed pending.
  // - Otherwise → first NON-dismissed pending.
  const visibleQueue = forcedOpen
    ? pending
    : pending.filter((p) => !dismissed.has(p.request_id));
  const currentReq = visibleQueue[0] || null;

  useEffect(() => {
    if (botReportOpen && currentReq?.request_id) {
      loadBotReport(currentReq.request_id);
    }
  }, [botReportOpen, currentReq?.request_id, loadBotReport]);

  if (!isCreator) return null;

  if (visibleQueue.length === 0) {
    if (forcedOpen) setForcedOpen(false);
    return null;
  }
  const req = currentReq;

  const dismissCurrent = () => {
    // iter127 — Quand le modal a été ouvert manuellement via l'icône
    // historique bleue (forcedOpen=true), le bouton X ferme purement et
    // simplement le modal sans modifier la liste des dismissed. Le
    // créateur peut alors le rouvrir à tout moment via l'icône.
    if (forcedOpen) {
      setForcedOpen(false);
      return;
    }
    const next = new Set(dismissed);
    next.add(req.request_id);
    setDismissed(next);
    writeDismissed(next);
    broadcastPending(pending.filter((x) => next.has(x.request_id)).length);
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

  // iter143 — (bloc loadBotReport / useEffect déplacés au-dessus du early
  // return pour respecter les rules-of-hooks React).

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
            <span className="text-[#71717A] min-w-[140px]">Identité publique</span>
            <span className="text-white truncate font-mono" data-testid="exp-field-handle">
              @{req.public_handle || req.key_id?.slice(0, 12) || '—'}
            </span>
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
        {/* iter143 — Icône rapport bot validateur (remplace l'ancien
            historique). Ouvre un panneau avec l'analyse pré-validation. */}
        <button
          type="button"
          onClick={() => setBotReportOpen(true)}
          data-testid="exp-bot-report-btn"
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 border border-cyan-400/40 text-cyan-300 hover:bg-cyan-400/10 rounded-sm text-xs transition"
          title="Voir le rapport du bot validateur"
        >
          <Bot className="w-3.5 h-3.5" /> Rapport du bot validateur
        </button>
        <button
          type="button"
          onClick={() => {
            // iter134 — Ouvrir le compte cible = même bascule que
            // AccountsButton.onVisitAccount → simulation dashboard (photo 2),
            // JAMAIS le modal "Infos brutes". La créa peut refermer via la
            // barre de simulation et revenir à ses tâches.
            onOpenAccount?.({
              key_id: req.key_id,
              project_id: req.project_id,
              pseudo: req.pseudo,
              device_label: req.device_label,
              role: req.target_role,
              staff_kind: req.target_staff_kind,
            });
          }}
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
      {/* iter143 — Panneau rapport bot validateur */}
      {botReportOpen && (
        <div
          className="fixed inset-0 z-[90] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setBotReportOpen(false)}
          data-testid="bot-report-overlay"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-lg w-full max-h-[80vh] bg-[#0A0A0A] border border-cyan-400/40 rounded-sm p-4 overflow-y-auto space-y-3"
          >
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-cyan-300" />
              <h3 className="text-sm font-bold text-white">Rapport bot validateur</h3>
              <button onClick={() => setBotReportOpen(false)} data-testid="bot-report-close" className="ml-auto text-[#A1A1AA] hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            {!botReport && <div className="text-xs text-[#A1A1AA]">Analyse en cours…</div>}
            {botReport && (
              <>
                <div className="bg-black/30 border border-white/10 rounded-sm p-3 text-xs space-y-1">
                  {/* Format uniforme aux demandes d'export */}
                  <div className="flex gap-2"><span className="text-[#71717A] min-w-[120px]">Pseudo :</span><span className="text-white">{botReport.header?.pseudo}</span></div>
                  <div className="flex gap-2"><span className="text-[#71717A] min-w-[120px]">Identité publique :</span><span className="text-white font-mono">@{botReport.header?.public_handle || '—'}</span></div>
                  <div className="flex gap-2"><span className="text-[#71717A] min-w-[120px]">Projet :</span><span className="text-white">{botReport.header?.project_name}</span></div>
                  <div className="flex gap-2"><span className="text-[#71717A] min-w-[120px]">Type d&apos;export :</span><span className="text-[#E4FF00]">{botReport.header?.export_kind}</span></div>
                  <div className="flex gap-2"><span className="text-[#71717A] min-w-[120px]">Date :</span><span className="text-white">{botReport.header?.date}</span></div>
                  <div className="flex gap-2"><span className="text-[#71717A] min-w-[120px]">Heure :</span><span className="text-white">{botReport.header?.time}</span></div>
                </div>
                <div className={`border rounded-sm p-3 ${botReport.report?.ok ? 'border-emerald-400/40 bg-emerald-500/[0.06]' : 'border-red-400/40 bg-red-500/[0.06]'}`}>
                  <div className={`text-xs font-bold ${botReport.report?.ok ? 'text-emerald-300' : 'text-red-300'}`} data-testid="bot-report-summary">
                    {botReport.report?.summary}
                  </div>
                  {botReport.report?.anomalies?.length > 0 && (
                    <ul className="list-disc pl-4 mt-2 space-y-0.5 text-xs text-white/80">
                      {botReport.report.anomalies.map((a, i) => (
                        <li key={i} data-testid={`bot-report-anomaly-${i}`}>{a}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <details className="text-[11px] text-[#A1A1AA]">
                  <summary className="cursor-pointer">Voir les couches d&apos;analyse</summary>
                  <pre className="mt-2 bg-black/40 p-2 rounded-sm overflow-x-auto text-[10px] text-white/60">
                    {JSON.stringify(botReport.report?.layers, null, 2)}
                  </pre>
                </details>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
