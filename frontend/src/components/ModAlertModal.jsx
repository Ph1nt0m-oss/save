/**
 * iter143 — Popup mi-écran de modération.
 *
 * Détecte via polling si le staff (modo/admin/créa) a une assignation
 * active dans mod_assignments. Affiche une popup CENTRÉE avec :
 *   État PENDING → boutons Accepter / Refuser (délégation auto)
 *   État ACCEPTED → l'analyse détaillée + boutons Sanctionner /
 *                   Pas une infraction / Déléguer.
 *
 * Après SANCTION : le composant force Sun mode (via /social/sun-mode),
 * puis revient en Nuit à la clôture de la décision.
 *
 * Note : les MP privés (1-1) ne déclenchent JAMAIS d'alerte — seuls les
 * groupes ≥ 3 participants sont surveillés côté backend.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { AlertTriangle, Check, X, Gavel, UserMinus, Send } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const POLL_MS = 8000;

export default function ModAlertModal() {
  const device = useDeviceIdentity();
  const [payload, setPayload] = useState(null); // { assignment, alert }
  const [busy, setBusy] = useState(false);
  const [notInfraction, setNotInfraction] = useState(false);
  const [delegate, setDelegate] = useState(false);

  const isStaff =
    device.role === 'creator' ||
    device.staffKind === 'admin' ||
    device.staffKind === 'modo';

  const fetchMine = useCallback(async () => {
    if (!isStaff || !device.keyId) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/moderation/assignments/mine`, body);
      setPayload(r.data?.assignment ? r.data : null);
    } catch (_e) { /* silent */ }
  }, [isStaff, device.keyId]);

  useEffect(() => {
    if (!isStaff) return undefined;
    fetchMine();
    const id = setInterval(fetchMine, POLL_MS);
    return () => clearInterval(id);
  }, [isStaff, fetchMine]);

  if (!isStaff || !payload?.assignment) return null;
  const a = payload.assignment;
  const alert = payload.alert || {};
  const isPending = a.state === 'pending';
  const isAccepted = a.state === 'accepted';

  const act = async (action, note = '') => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {
        assignment_id: a.assignment_id, action, note,
      });
      // iter143 — Sun mode auto lors d'une sanction.
      if (action === 'sanction') {
        try {
          const sunBody = await withCreatorProof(API, axios, { enabled: true });
          await axios.put(`${API}/social/sun-mode`, sunBody);
        } catch (_e) { /* silent */ }
      }
      await axios.post(`${API}/moderation/assignments/action`, body);
      // Après sanction/décision, remet Nuit.
      if (action === 'sanction' || action === 'not_infraction' || action === 'delegate') {
        try {
          const nightBody = await withCreatorProof(API, axios, { enabled: false });
          await axios.put(`${API}/social/sun-mode`, nightBody);
        } catch (_e) { /* silent */ }
      }
      // Refresh.
      setPayload(null);
      setNotInfraction(false);
      setDelegate(false);
      fetchMine();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impossible');
    } finally {
      setBusy(false);
    }
  };

  const chooseNotSanction = () => {
    if (!notInfraction && !delegate) {
      toast.error('Coche « pas une infraction » ou « je délègue ».');
      return;
    }
    if (delegate) return act('delegate');
    return act('not_infraction');
  };

  return (
    <div
      className="fixed inset-0 z-[95] bg-black/85 backdrop-blur-md flex items-center justify-center p-4"
      data-testid="mod-alert-modal"
    >
      <div className="max-w-lg w-full bg-[#0A0A0A] border border-amber-400/60 rounded-sm shadow-2xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-300 animate-pulse" />
          <h2 className="text-sm font-['Chivo'] font-bold text-white">
            Intervention modération requise
          </h2>
        </div>

        <div className="bg-black/40 border border-white/10 rounded-sm p-3 text-xs space-y-1">
          <div className="text-white/70">
            Groupe : <span className="text-white font-mono">{alert.group_type || '—'}</span>
          </div>
          <div className="text-white/70">
            Score bot : <span className="text-amber-300 font-bold">{alert.score || 0} / 100</span>
          </div>
          <div className="text-white/70">
            Motifs : <span className="text-white">{(alert.reasons || []).join(', ') || '—'}</span>
          </div>
          <div className="text-white/50 text-[10px]">
            Détectée : {alert.created_at ? new Date(alert.created_at).toLocaleString() : '—'}
          </div>
        </div>

        {isPending && (
          <div className="flex flex-col gap-2" data-testid="mod-alert-pending">
            <p className="text-[11px] text-white/60">
              Une situation nécessite ton attention. Accepte pour voir l&apos;analyse
              détaillée (pseudos, messages, date/heure).
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => act('accept')}
                disabled={busy}
                data-testid="mod-alert-accept"
                className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/50 text-emerald-200 rounded-sm font-['Chivo'] font-bold text-sm transition disabled:opacity-40"
              >
                <Check className="w-4 h-4" /> Accepter
              </button>
              <button
                type="button"
                onClick={() => act('refuse')}
                disabled={busy}
                data-testid="mod-alert-refuse"
                className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 bg-white/[0.04] hover:bg-white/[0.08] border border-white/15 text-white/80 rounded-sm text-sm transition disabled:opacity-40"
              >
                <X className="w-4 h-4" /> Refuser (déléguer)
              </button>
            </div>
          </div>
        )}

        {isAccepted && (
          <div className="space-y-3" data-testid="mod-alert-accepted">
            <div className="bg-black/40 border border-cyan-400/30 rounded-sm p-3 text-xs">
              <div className="text-cyan-300 font-bold mb-1">Analyse du bot</div>
              <div className="text-white/80">
                Les messages ci-dessous ont été flaggés. Utilise le mode Soleil
                temporaire pour identifier les utilisateurs concernés, puis
                applique la sanction adaptée.
              </div>
              {(alert.message_ids || []).length > 0 && (
                <div className="mt-2 text-[10px] text-white/50">
                  Messages ciblés : {alert.message_ids.length}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => act('sanction')}
                disabled={busy}
                data-testid="mod-alert-sanction"
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 bg-red-500/20 hover:bg-red-500/30 border border-red-400/50 text-red-200 rounded-sm font-['Chivo'] font-bold text-sm transition disabled:opacity-40"
              >
                <Gavel className="w-4 h-4" /> Je sanctionne (Soleil temporaire)
              </button>
              <div className="border border-white/10 rounded-sm p-2 space-y-1.5">
                <div className="text-[11px] text-white/60 mb-1">Je ne sanctionne pas :</div>
                <label className="flex items-center gap-2 text-xs text-white/80 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notInfraction}
                    onChange={(e) => { setNotInfraction(e.target.checked); if (e.target.checked) setDelegate(false); }}
                    data-testid="mod-alert-not-infraction"
                  />
                  Ce n&apos;est pas une infraction
                </label>
                <label className="flex items-center gap-2 text-xs text-white/80 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={delegate}
                    onChange={(e) => { setDelegate(e.target.checked); if (e.target.checked) setNotInfraction(false); }}
                    data-testid="mod-alert-delegate"
                  />
                  Je délègue cette tâche à un autre membre du staff
                </label>
                <button
                  type="button"
                  onClick={chooseNotSanction}
                  disabled={busy}
                  data-testid="mod-alert-submit-nosanction"
                  className="w-full inline-flex items-center justify-center gap-2 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/15 text-white/80 rounded-sm text-xs transition disabled:opacity-40"
                >
                  <Send className="w-3.5 h-3.5" /> Valider
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="text-[10px] text-white/40 border-t border-white/10 pt-2">
          Chaque décision est consignée dans le journal Créa+Admin. Absence
          de réponse dans les 2 min → transfert automatique.
        </div>
      </div>
    </div>
  );
}
