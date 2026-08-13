/**
 * iter158.4 — Onglet Historique des décisions sur les clés (Autres identifiants).
 *
 * Fonctionnalités (spec CDC finalisation) :
 *   - Liste triée par date (récent en premier).
 *   - Recherche par pseudo unique (public_handle) ou par action.
 *   - Sélection multiple (checkbox par ligne + « Tout sélectionner »).
 *   - Annulation groupée (batch undo) via /devices/decisions/undo-multi.
 *   - Aucun bouton « vider l'historique » (retiré par CDC).
 *   - Permissions serveur : créa voit tout, admin voit admin+modo, modo
 *     voit ses propres décisions uniquement.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Search, Undo2, CheckSquare, Square, History as HistoryIcon } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
  } catch (_) { return iso; }
}

const ACTION_LABEL = {
  approve: 'Approbation',
  revoke: 'Révocation',
  disconnect: 'Déconnexion',
  promote: 'Promotion créa',
  add_by_key: 'Ajout par clé',
  undo: 'Annulation',
};

export default function KeysHistoryTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/devices/decisions`, body);
      setRows(r.data?.decisions || []);
      setSelected(new Set());
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Historique indisponible');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const filtered = useMemo(() => {
    const q = (search || '').trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((d) => {
      const parts = [
        d.target_label, d.target_pseudo, d.target_public_handle,
        d.target_key_id, d.action, d.actor_key_id,
      ].filter(Boolean).map((s) => String(s).toLowerCase());
      return parts.some((s) => s.includes(q));
    });
  }, [rows, search]);

  const allSelected = filtered.length > 0 && filtered.every((d) => selected.has(`${d.target_key_id}|${d.ts}`));

  const toggle = (d) => {
    const key = `${d.target_key_id}|${d.ts}`;
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setSelected(next);
  };

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map((d) => `${d.target_key_id}|${d.ts}`)));
  };

  const undoSelected = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Quelles actions choisies par cette clé doivent être annulées ?\n\n${selected.size} action(s) sélectionnée(s). Confirmer ?`)) return;
    setBusy(true);
    try {
      const decisions = Array.from(selected).map((k) => {
        const [target_key_id, ...rest] = k.split('|');
        return { target_key_id, decision_ts: rest.join('|') };
      });
      const body = await withCreatorProof(API, axios, { decisions });
      const r = await axios.post(`${API}/devices/decisions/undo-multi`, body);
      const okc = r.data?.ok_count || 0;
      const nfail = (r.data?.failed || []).length;
      toast.success(`${okc} annulation(s) réussie(s)${nfail ? ` · ${nfail} échec(s)` : ''}`);
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Annulation impossible');
    } finally { setBusy(false); }
  };

  return (
    <section data-testid="keys-history-tab" className="bg-white/[0.03] border border-white/10 rounded-sm p-3 space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <HistoryIcon className="w-4 h-4 text-[#A1A1AA]" />
          <span className="text-xs uppercase tracking-widest text-[#71717A]">Historique des décisions</span>
        </div>
        <div className="flex items-center gap-2 flex-1 min-w-0 justify-end">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#71717A]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              data-testid="keys-history-search"
              placeholder="Rechercher (pseudo, action, clé…)"
              className="w-full bg-black/40 border border-white/10 rounded-sm pl-7 pr-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
            />
          </div>
          <button
            onClick={toggleAll}
            data-testid="keys-history-select-all"
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm"
            title="Tout sélectionner"
          >
            {allSelected ? <CheckSquare className="w-3 h-3" /> : <Square className="w-3 h-3" />}
            Tout
          </button>
          <button
            onClick={undoSelected}
            disabled={busy || selected.size === 0}
            data-testid="keys-history-undo-multi"
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-amber-400/60 text-amber-300 hover:bg-amber-400/10 rounded-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Undo2 className="w-3 h-3" />
            Annuler ({selected.size})
          </button>
        </div>
      </div>

      <div className="space-y-1 max-h-72 overflow-y-auto">
        {loading && <div className="text-xs text-[#A1A1AA] py-2 text-center">Chargement…</div>}
        {!loading && filtered.length === 0 && (
          <div className="text-xs text-[#A1A1AA] py-4 text-center" data-testid="keys-history-empty">
            {search ? 'Aucun résultat.' : 'Aucune décision enregistrée.'}
          </div>
        )}
        {filtered.map((d) => {
          const key = `${d.target_key_id}|${d.ts}`;
          const isSel = selected.has(key);
          return (
            <div
              key={key}
              data-testid={`keys-history-row-${d.ts}`}
              onClick={() => toggle(d)}
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
                      {ACTION_LABEL[d.action] || d.action}
                    </span>
                    {d.target_public_handle && (
                      <span className="text-white/70 font-['IBM_Plex_Mono']">@{d.target_public_handle}</span>
                    )}
                    {d.target_label && (
                      <span className="text-white/80">{d.target_label}</span>
                    )}
                  </div>
                  <div className="text-[10px] text-[#71717A] font-['IBM_Plex_Mono'] truncate">
                    Clé : {d.target_key_id}
                  </div>
                  <div className="text-[10px] text-[#71717A]">
                    {fmtDate(d.ts)} · par {d.actor_key_id?.slice(0, 14) || 'inconnu'}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
