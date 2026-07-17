import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { History, Eye, EyeOff, X, Download, Trash2, RefreshCw, Undo2, ShieldOff, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import SiteModeBadge from './SiteModeBadge';
import WhoCanVisitBadge from './WhoCanVisitBadge';
import ViewModePicker from './ViewModePicker';
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
export default function CreatorToolbar({ hideSiteModeBadge = false } = {}) {
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [decisions, setDecisions] = useState([]);
  const [loadingHist, setLoadingHist] = useState(false);
  // iter113 — Un seul dropdown ouvert à la fois (SiteMode ou ViewMode) pour
  // éviter la superposition visuelle observée par l'utilisatrice.
  const [openDropdown, setOpenDropdown] = useState(null);  // null | 'site' | 'view'
  // iter128.11 — SiteModeBadge visible pour créa PHYSIQUE (signature ECDSA)
  // même en simulation de vue. La créa peut ainsi continuer à changer le
  // mode du site tout en simulant une vue. hideSiteModeBadge=true peut
  // le forcer caché ailleurs (jamais utilisé actuellement).
  const showSiteModeBadge =
    !hideSiteModeBadge && device.role === 'creator';

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
    <div className="inline-flex items-center gap-2 sm:gap-8 flex-wrap" data-testid="creator-toolbar">
      {/* iter128.1 — SiteModeBadge visible UNIQUEMENT pour créa physique
          ET hors simulation de vue (showSiteModeBadge le centralise). */}
      {showSiteModeBadge && (
      <SiteModeBadge
        role={device.role}
        siteMode={device.siteMode}
        siteModes={device.siteModes}
        viewMode={device.viewMode}
        guestView={device.guestView}
        guestViews={device.guestViews}
        onChange={() => device.refresh()}
        controlledOpen={openDropdown === 'site'}
        onOpenChange={(v) => setOpenDropdown(v ? 'site' : null)}
      />
      )}

      {/* iter134 — Onglet "Qui peut visiter ?" — entre le type de site et le
          type de vue. Multi-sélection des 6 clés + toggle Libre/Forcé.
          Visible uniquement pour la créa physique.
          iter135 — Reçoit siteModes pour désactiver "Vue forcée" si 'guest'
          est coché dans le TYPE DE SITE (règle métier utilisateur). */}
      {showSiteModeBadge && (
      <WhoCanVisitBadge
        role={device.role}
        visitModes={device.visitModes}
        viewForcing={device.viewForcing}
        siteModes={device.siteModes}
        onChange={() => device.refresh()}
        controlledOpen={openDropdown === 'visit'}
        onOpenChange={(v) => setOpenDropdown(v ? 'visit' : null)}
      />
      )}

      {/* iter85 — Pour la créatrice : picker pour simuler n'importe quelle vue
          (user / modo / admin / guest). Pour les non-créa : le toggle
          original visible/locked selon guest_view. */}
      <ViewModePicker
        role={device.role}
        viewMode={device.viewMode}
        siteMode={device.siteMode}
        guestView={device.guestView}
        guestViews={device.guestViews}
        canSimulateViews={device.canSimulateViews}
        viewSimulationConstraint={device.viewSimulationConstraint}
        visitModes={device.visitModes}
        viewForcing={device.viewForcing}
        controlledOpen={openDropdown === 'view'}
        onOpenChange={(v) => setOpenDropdown(v ? 'view' : null)}
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
              ? 'bg-violet-400/10 border-violet-400/40 text-violet-300 hover:bg-violet-400/20'
              : 'bg-lime-400/10 border-lime-400/40 text-lime-300 hover:bg-lime-400/20'
          }`}
        >
          {inGuestView ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">{inGuestView ? t('vm_preview_label') : t('vm_user_label')}</span>
        </button>
      )}

      {/* History panel removed in iter57 — entire JSX dropped, including
          historyOpen state & decisions list (kept in CreatorToolbar code
          only as no-ops in case re-enabled later). */}
    </div>
  );
}
