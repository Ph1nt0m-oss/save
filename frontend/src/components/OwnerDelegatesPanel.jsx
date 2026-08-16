/**
 * iter158.6 — Panneau propriétaire : gestion des délégués (Apprentice Creator).
 *
 * Owner-only. Permet :
 *   - Voir tous les délégués actuels avec leurs perms (permanent + temp actives).
 *   - Grant temp (perm + durée en minutes).
 *   - Grant permanent (progressive promotion).
 *   - Revoke une perm spécifique.
 *   - Lock (« véritable créateur » — quand toutes les perms canoniques sont
 *     permanentes).
 *   - Unlock.
 *   - Historique complet d'un délégué.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { X, Crown, Clock, Lock, Unlock, Undo2, ScrollText } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OwnerDelegatesPanel({ open, onClose }) {
  const [delegates, setDelegates] = useState([]);
  const [canonicalPerms, setCanonicalPerms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [historyOf, setHistoryOf] = useState(null); // {key_id, history}
  const [addKeyId, setAddKeyId] = useState('');
  const [addPerm, setAddPerm] = useState('approve_key');
  const [addMinutes, setAddMinutes] = useState(60);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/ownership/delegate/list`, body);
      setDelegates(r.data?.delegates || []);
      setCanonicalPerms(r.data?.canonical_perms || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Liste indisponible');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (open) refresh(); }, [open, refresh]);

  const grantTemp = async (kid, perm, minutes) => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {
        delegate_key_id: kid, perm, duration_minutes: minutes,
      });
      const r = await axios.post(`${API}/ownership/delegate/grant-temp`, body);
      toast.success(`Temp accordée : ${perm} (expire ${new Date(r.data?.expires_at).toLocaleString('fr-FR')})`);
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Grant temp impossible');
    } finally { setBusy(false); }
  };

  const grantPerm = async (kid, perm) => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {
        delegate_key_id: kid, perm,
      });
      await axios.post(`${API}/ownership/delegate/grant-permanent`, body);
      toast.success(`Permanente accordée : ${perm}`);
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Grant permanent impossible');
    } finally { setBusy(false); }
  };

  const revokePerm = async (kid, perm) => {
    if (!window.confirm(`Révoquer « ${perm} » pour ce délégué ?`)) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {
        delegate_key_id: kid, perm,
      });
      await axios.post(`${API}/ownership/delegate/revoke-perm`, body);
      toast.success(`Révoquée : ${perm}`);
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Révocation impossible');
    } finally { setBusy(false); }
  };

  const toggleLock = async (kid, isLocked) => {
    const endpoint = isLocked ? 'unlock' : 'lock';
    if (!window.confirm(isLocked
      ? 'Déverrouiller ce délégué (redevient révocable) ?'
      : 'Verrouiller ce délégué en véritable créateur (irréversible sauf unlock) ?')) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { delegate_key_id: kid });
      await axios.post(`${API}/ownership/delegate/${endpoint}`, body);
      toast.success(isLocked ? 'Déverrouillé' : 'Verrouillé — véritable créateur');
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Opération impossible');
    } finally { setBusy(false); }
  };

  const loadHistory = async (kid) => {
    try {
      const body = await withCreatorProof(API, axios, { delegate_key_id: kid });
      const r = await axios.post(`${API}/ownership/delegate/history`, body);
      setHistoryOf({ key_id: kid, ...r.data });
    } catch (e) {
      toast.error('Historique indisponible');
    }
  };

  const addNewDelegate = async () => {
    if (!addKeyId.trim()) return;
    await grantTemp(addKeyId.trim(), addPerm, Number(addMinutes) || 60);
    setAddKeyId('');
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[86] bg-black/80 flex items-start justify-center p-3 overflow-y-auto"
      onClick={onClose}
      data-testid="owner-delegates-panel"
    >
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-4xl bg-[#0A0A0A] border border-[#E4FF00]/40 rounded-sm p-4 space-y-3 mt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Crown className="w-4 h-4 text-[#E4FF00]" />
            <h3 className="text-sm font-['Chivo'] font-bold uppercase tracking-widest text-white">
              Apprentice Creator — Délégations
            </h3>
          </div>
          <button onClick={onClose} data-testid="owner-delegates-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Ajout rapide (grant temp initial) */}
        <div className="bg-white/[0.03] border border-white/10 rounded-sm p-3 space-y-2">
          <div className="text-xs uppercase tracking-widest text-[#71717A]">Ajouter/promouvoir un délégué</div>
          <div className="flex gap-2 flex-wrap items-center">
            <input
              value={addKeyId}
              onChange={(e) => setAddKeyId(e.target.value)}
              data-testid="delegate-add-keyid"
              placeholder="key_id du délégué"
              className="flex-1 min-w-[200px] bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 text-xs text-white font-['IBM_Plex_Mono'] focus:outline-none focus:border-[#E4FF00]"
            />
            <select
              value={addPerm}
              onChange={(e) => setAddPerm(e.target.value)}
              data-testid="delegate-add-perm"
              className="bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
            >
              {canonicalPerms.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <input
              type="number"
              value={addMinutes}
              onChange={(e) => setAddMinutes(e.target.value)}
              data-testid="delegate-add-minutes"
              min={1} max={60 * 24 * 30}
              className="w-20 bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
              title="Durée en minutes (1 → 43200)"
            />
            <button
              onClick={addNewDelegate}
              disabled={busy || !addKeyId.trim()}
              data-testid="delegate-add-submit"
              className="text-xs px-3 py-1.5 border border-[#E4FF00]/60 text-[#E4FF00] hover:bg-[#E4FF00]/10 rounded-sm disabled:opacity-40"
            >
              Grant temp
            </button>
          </div>
        </div>

        {/* Liste délégués */}
        <div className="space-y-2 max-h-[55vh] overflow-y-auto">
          {loading && <div className="text-xs text-[#A1A1AA] py-2 text-center">Chargement…</div>}
          {!loading && delegates.length === 0 && (
            <div className="text-xs text-[#A1A1AA] py-4 text-center" data-testid="owner-delegates-empty">
              Aucun délégué actif.
            </div>
          )}
          {delegates.map((d) => {
            const perms = d.perms || [];
            const tempPerms = d.temp_perms || [];
            const activePerms = d.active_perms || [];
            const canLock = (d.canonical_perms_missing || []).length === 0;
            return (
              <div
                key={d.key_id}
                data-testid={`delegate-row-${d.key_id}`}
                className={`bg-black/30 border rounded-sm p-3 space-y-2 ${
                  d.locked ? 'border-[#E4FF00]/50' : 'border-white/10'
                }`}
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-['IBM_Plex_Mono'] text-white/80 truncate max-w-[300px]">
                    {d.key_id}
                  </span>
                  {d.locked ? (
                    <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-[#E4FF00]/60 text-[#E4FF00] bg-[#E4FF00]/10 rounded-sm inline-flex items-center gap-1">
                      <Lock className="w-2.5 h-2.5" />véritable créateur
                    </span>
                  ) : (
                    <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-white/20 text-[#A1A1AA] rounded-sm">
                      apprenti
                    </span>
                  )}
                  <div className="flex-1" />
                  <button
                    onClick={() => loadHistory(d.key_id)}
                    data-testid={`delegate-history-${d.key_id}`}
                    className="text-[10px] px-2 py-1 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm inline-flex items-center gap-1"
                  >
                    <ScrollText className="w-3 h-3" />
                    Historique
                  </button>
                  <button
                    onClick={() => toggleLock(d.key_id, d.locked)}
                    disabled={busy || (!d.locked && !canLock)}
                    data-testid={`delegate-toggle-lock-${d.key_id}`}
                    title={d.locked ? 'Déverrouiller' : (canLock ? 'Verrouiller' : 'Toutes les perms canoniques doivent être permanentes')}
                    className={`text-[10px] px-2 py-1 border rounded-sm inline-flex items-center gap-1 disabled:opacity-40 ${
                      d.locked
                        ? 'border-amber-400/60 text-amber-300 hover:bg-amber-400/10'
                        : 'border-[#E4FF00]/60 text-[#E4FF00] hover:bg-[#E4FF00]/10'
                    }`}
                  >
                    {d.locked ? <Unlock className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                    {d.locked ? 'Unlock' : 'Lock'}
                  </button>
                </div>
                <div className="text-[10px] uppercase text-[#71717A] tracking-widest">Perms permanentes</div>
                <div className="flex gap-1 flex-wrap">
                  {perms.length === 0 && <span className="text-[10px] text-[#52525B]">aucune</span>}
                  {perms.map((p) => (
                    <span key={p} className="text-[10px] px-1.5 py-0.5 border border-emerald-400/40 text-emerald-300 bg-emerald-400/10 rounded-sm inline-flex items-center gap-1">
                      {p}
                      <button
                        onClick={() => revokePerm(d.key_id, p)}
                        disabled={busy || d.locked}
                        title="Révoquer"
                        className="text-emerald-300/70 hover:text-red-300 disabled:opacity-30"
                      >×</button>
                    </span>
                  ))}
                </div>
                {tempPerms.length > 0 && (
                  <>
                    <div className="text-[10px] uppercase text-[#71717A] tracking-widest">Perms temporaires</div>
                    <div className="flex gap-1 flex-wrap">
                      {tempPerms.map((tp) => (
                        <span key={tp.perm} className="text-[10px] px-1.5 py-0.5 border border-amber-400/40 text-amber-300 bg-amber-400/10 rounded-sm inline-flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {tp.perm}
                          <span className="text-amber-200/60">jusqu'à {new Date(tp.expires_at).toLocaleTimeString('fr-FR')}</span>
                          <button
                            onClick={() => revokePerm(d.key_id, tp.perm)}
                            disabled={busy}
                            className="text-amber-300/70 hover:text-red-300"
                          >×</button>
                        </span>
                      ))}
                    </div>
                  </>
                )}
                <div className="flex gap-2 flex-wrap pt-1">
                  <select
                    onChange={(e) => { if (e.target.value) { grantPerm(d.key_id, e.target.value); e.target.value = ''; } }}
                    disabled={busy || d.locked}
                    data-testid={`delegate-grant-perm-${d.key_id}`}
                    className="text-[10px] bg-black/40 border border-emerald-400/40 rounded-sm px-2 py-1 text-emerald-200 focus:outline-none disabled:opacity-40"
                  >
                    <option value="">+ Perm permanente…</option>
                    {canonicalPerms.filter((p) => !perms.includes(p)).map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                  <select
                    onChange={(e) => { if (e.target.value) { grantTemp(d.key_id, e.target.value, 60); e.target.value = ''; } }}
                    disabled={busy || d.locked}
                    data-testid={`delegate-grant-temp-${d.key_id}`}
                    className="text-[10px] bg-black/40 border border-amber-400/40 rounded-sm px-2 py-1 text-amber-200 focus:outline-none disabled:opacity-40"
                  >
                    <option value="">+ Perm temp 60 min…</option>
                    {canonicalPerms.filter((p) => !perms.includes(p)).map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>

        {/* Historique modal */}
        {historyOf && (
          <div className="fixed inset-0 z-[87] bg-black/85 flex items-center justify-center p-3" onClick={() => setHistoryOf(null)}>
            <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg bg-[#0A0A0A] border border-white/15 rounded-sm p-3 space-y-2 max-h-[70vh] overflow-y-auto" data-testid="delegate-history-modal">
              <div className="flex items-center justify-between">
                <div className="text-xs uppercase tracking-widest text-[#71717A]">Historique</div>
                <button onClick={() => setHistoryOf(null)} className="text-[#A1A1AA] hover:text-white"><X className="w-4 h-4" /></button>
              </div>
              <div className="text-[11px] text-white/70 font-['IBM_Plex_Mono'] truncate">{historyOf.key_id}</div>
              <div className="space-y-1">
                {(historyOf.history || []).length === 0 && (
                  <div className="text-xs text-[#A1A1AA] py-2 text-center">Aucun événement.</div>
                )}
                {(historyOf.history || []).slice().reverse().map((h, i) => (
                  <div key={i} className="bg-black/40 border border-white/10 rounded-sm p-2 text-[11px]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="uppercase tracking-widest text-white/80">{h.action}</span>
                      {h.perm && <span className="text-emerald-300">{h.perm}</span>}
                      {h.duration_minutes && <span className="text-amber-300">{h.duration_minutes} min</span>}
                    </div>
                    <div className="text-[10px] text-[#71717A]">{new Date(h.ts).toLocaleString('fr-FR')} · par {h.actor?.slice(0, 14)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
