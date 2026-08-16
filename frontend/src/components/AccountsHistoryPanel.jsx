/**
 * iter158.5 — Panneau Historique des actions comptes.
 *
 * Spec CDC (Chantier 2) :
 *   - Historique détaillé par action (event_id, target, acteur, timestamp).
 *   - Recherche.
 *   - Sélection multiple + « Tout sélectionner ».
 *   - Annulation groupée (batch undo) via /accounts/history/undo-multi.
 *   - Aucun bouton « vider l'historique » (retiré par CDC → 410 Gone).
 *
 * Permissions : appelle /accounts/history qui applique la matrice serveur
 * (créa=tout, admin=admin+modo, modo=self).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Search, Undo2, CheckSquare, Square, History as HistoryIcon, X } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EVENT_LABEL = {
  rename: 'Renommage',
  mute: 'Mute',
  unmute: 'Unmute',
  ban: 'Bannissement',
  unban: 'Débannissement',
  exclude: 'Exclusion',
  disconnect: 'Déconnexion',
  force_visitor_on: 'Mode visiteur ON',
  force_visitor_off: 'Mode visiteur OFF',
  staff_kind_admin: 'Promu admin',
  staff_kind_modo: 'Promu modo',
  staff_kind_clear: 'Rétrogradé',
  delete_project: 'Projet supprimé',
  delete_account: 'Compte supprimé',
  delete_all_accounts: 'Tous comptes supprimés',
  remove_creator_self: 'Créa retiré (self)',
  remove_creator_other: 'Créa retiré (other)',
};

function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
  } catch (_) { return iso; }
}

export default function AccountsHistoryPanel({ open, onClose }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/accounts/history`, body);
      setRows(r.data?.history || []);
      setSelected(new Set());
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Historique indisponible');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (open) refresh(); }, [open, refresh]);

  const filtered = useMemo(() => {
    const q = (search || '').trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => {
      const parts = [
        r.event, r.target_label, r.target_key_id,
        r.actor_key_id, r.actor_label, r.actor_kind,
      ].filter(Boolean).map((s) => String(s).toLowerCase());
      return parts.some((s) => s.includes(q));
    });
  }, [rows, search]);

  const allSelected = filtered.length > 0 && filtered.every((r) => selected.has(r.event_id));

  const toggle = (r) => {
    const next = new Set(selected);
    if (next.has(r.event_id)) next.delete(r.event_id);
    else next.add(r.event_id);
    setSelected(next);
  };

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map((r) => r.event_id)));
  };

  const undoSelected = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Quelles actions choisies par cette clé doivent être annulées ?\n\n${selected.size} action(s) sélectionnée(s). Confirmer ?`)) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { event_ids: Array.from(selected) });
      const r = await axios.post(`${API}/accounts/history/undo-multi`, body);
      const okc = r.data?.ok_count || 0;
      const nfail = (r.data?.failed || []).length;
      toast.success(`${okc} annulation(s) réussie(s)${nfail ? ` · ${nfail} échec(s)` : ''}`);
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Annulation impossible');
    } finally { setBusy(false); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[85] flex items-start justify-center bg-black/80 p-3 overflow-y-auto" onClick={onClose} data-testid="accounts-history-panel">
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-3xl bg-[#0A0A0A] border border-white/15 rounded-sm p-4 space-y-3 mt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HistoryIcon className="w-4 h-4 text-[#E4FF00]" />
            <h3 className="text-sm font-['Chivo'] font-bold uppercase tracking-widest text-white">
              Historique des comptes
            </h3>
          </div>
          <button onClick={onClose} data-testid="accounts-history-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#71717A]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              data-testid="accounts-history-search"
              placeholder="Rechercher (event, target, acteur…)"
              className="w-full bg-black/40 border border-white/10 rounded-sm pl-7 pr-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
            />
          </div>
          <button
            onClick={toggleAll}
            data-testid="accounts-history-select-all"
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm"
          >
            {allSelected ? <CheckSquare className="w-3 h-3" /> : <Square className="w-3 h-3" />}
            Tout
          </button>
          <button
            onClick={undoSelected}
            disabled={busy || selected.size === 0}
            data-testid="accounts-history-undo-multi"
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-amber-400/60 text-amber-300 hover:bg-amber-400/10 rounded-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Undo2 className="w-3 h-3" />
            Annuler ({selected.size})
          </button>
        </div>

        <div className="space-y-1 max-h-[60vh] overflow-y-auto">
          {loading && <div className="text-xs text-[#A1A1AA] py-2 text-center">Chargement…</div>}
          {!loading && filtered.length === 0 && (
            <div className="text-xs text-[#A1A1AA] py-4 text-center" data-testid="accounts-history-empty">
              {search ? 'Aucun résultat.' : 'Aucun événement enregistré.'}
            </div>
          )}
          {filtered.map((r) => {
            const isSel = selected.has(r.event_id);
            return (
              <div
                key={r.event_id}
                data-testid={`accounts-history-row-${r.event_id}`}
                onClick={() => toggle(r)}
                className={`bg-black/30 border rounded-sm p-2 cursor-pointer transition ${
                  isSel ? 'border-amber-400/60 bg-amber-400/5' : 'border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 flex-shrink-0">
                    {isSel ? <CheckSquare className="w-3.5 h-3.5 text-amber-300" /> : <Square className="w-3.5 h-3.5 text-[#52525B]" />}
                  </div>
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex items-center gap-2 flex-wrap text-[11px]">
                      <span className="uppercase tracking-widest px-1.5 py-0.5 border border-white/15 rounded-sm text-white/80">
                        {EVENT_LABEL[r.event] || r.event}
                      </span>
                      {r.target_label && (
                        <span className="text-white/80">→ {r.target_label}</span>
                      )}
                      {r.actor_label && (
                        <span className="text-[#71717A]">par {r.actor_label}</span>
                      )}
                      {r.actor_kind && (
                        <span className="text-[10px] uppercase text-[#52525B]">({r.actor_kind})</span>
                      )}
                    </div>
                    <div className="text-[10px] text-[#71717A] font-['IBM_Plex_Mono'] truncate">
                      Cible : {r.target_key_id}
                    </div>
                    <div className="text-[10px] text-[#71717A]">{fmtDate(r.ts)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
