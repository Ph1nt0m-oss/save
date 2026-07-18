/**
 * iter142 — Journal d'anonymat (créa only).
 *
 * Affiche l'historique horodaté des activations Nuit/Soleil par les modos
 * et admins, avec leur identité publique unique. Permet à la Créa de
 * repérer les comportements suspects.
 *
 * Filtres :
 *  - Tous / Sun on / Sun off / Anonymous on/off
 *  - Par rôle (modo/admin/créa)
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { X, Sun, Moon, VenetianMask, ShieldCheck, ShieldAlert, Crown } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODE_META = {
  sun_mode: { label: 'Soleil', Icon: Sun, color: 'text-amber-300' },
  anonymous: { label: 'Anonyme', Icon: VenetianMask, color: 'text-fuchsia-300' },
  auto_sun: { label: 'Auto Soleil (bot)', Icon: Sun, color: 'text-cyan-300' },
};

const ROLE_META = {
  creator: { label: 'Créa', Icon: Crown, color: 'text-[#E4FF00]' },
  admin: { label: 'Admin', Icon: ShieldCheck, color: 'text-orange-300' },
  modo: { label: 'Modo', Icon: ShieldAlert, color: 'text-cyan-300' },
};

export default function AnonymityJournalPanel({ open, onClose }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/social/anonymity-journal`, body);
        setEntries(r.data?.entries || []);
      } catch (_e) {
        setEntries([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [open]);

  if (!open) return null;

  const filtered = entries.filter((e) => {
    if (filter === 'all') return true;
    if (filter === 'sun_on') return e.mode === 'sun_mode' && e.enabled;
    if (filter === 'sun_off') return e.mode === 'sun_mode' && !e.enabled;
    if (filter === 'staff') return ['admin', 'modo'].includes(e.actor_role);
    return true;
  });

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" data-testid="anonymity-journal-overlay">
      <div className="w-full max-w-3xl max-h-[80vh] bg-[#050505] border border-white/20 rounded-sm flex flex-col overflow-hidden">
        <header className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-['Chivo'] font-bold text-white">Journal d&apos;anonymat</h3>
            <p className="text-[11px] text-[#A1A1AA]">
              Historique des activations Nuit/Soleil (staff)
            </p>
          </div>
          <button onClick={onClose} data-testid="anonymity-journal-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </header>
        <div className="px-3 py-2 border-b border-white/10 flex items-center gap-1.5 flex-wrap">
          {[
            { k: 'all', label: 'Tous' },
            { k: 'staff', label: 'Staff seulement' },
            { k: 'sun_on', label: 'Soleil ON' },
            { k: 'sun_off', label: 'Soleil OFF' },
          ].map((f) => (
            <button
              key={f.k}
              type="button"
              onClick={() => setFilter(f.k)}
              data-testid={`journal-filter-${f.k}`}
              className={`text-[11px] px-2 py-1 rounded-sm border transition ${
                filter === f.k
                  ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00]'
                  : 'text-[#A1A1AA] border-white/15 hover:border-white/30'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {loading && <div className="text-xs text-[#A1A1AA] text-center py-6">Chargement…</div>}
          {!loading && filtered.length === 0 && (
            <div className="text-xs text-[#71717A] text-center py-6">Aucun événement.</div>
          )}
          {filtered.map((e, i) => {
            const mm = MODE_META[e.mode] || { label: e.mode, Icon: Moon, color: 'text-white/60' };
            const rm = ROLE_META[e.actor_role] || null;
            const MIcon = mm.Icon;
            return (
              <div
                key={`${e.actor_key_id}-${e.ts}-${i}`}
                data-testid={`journal-entry-${i}`}
                className="bg-black/30 border border-white/10 rounded-sm p-2.5 flex items-center gap-3 flex-wrap"
              >
                <MIcon className={`w-4 h-4 ${mm.color}`} />
                <span className={`text-[11px] font-bold uppercase ${mm.color}`}>{mm.label}</span>
                <span className={`text-[11px] px-1.5 py-0.5 rounded-sm border ${e.enabled ? 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' : 'text-red-300 border-red-400/40 bg-red-400/10'}`}>
                  {e.enabled ? 'ACTIVÉ' : 'DÉSACTIVÉ'}
                </span>
                {rm && (
                  <span className={`text-[10px] uppercase inline-flex items-center gap-1 ${rm.color}`}>
                    <rm.Icon className="w-3 h-3" />
                    {rm.label}
                  </span>
                )}
                <span className="text-xs text-white truncate max-w-[180px]">
                  {e.actor_pseudo || '—'}
                </span>
                {e.actor_public_handle && (
                  <span className="text-[10px] text-white/40 font-mono">@{e.actor_public_handle}</span>
                )}
                <span className="text-[10px] text-[#71717A] ml-auto">
                  {new Date(e.ts).toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
