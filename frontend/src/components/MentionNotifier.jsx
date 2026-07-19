/**
 * iter147 — MentionNotifier
 *
 * Bulle discrète en bas à droite qui affiche le nombre de mentions
 * @handle non lues (polling 20s). Cliquer ouvre un mini-panneau
 * déroulant qui liste les 10 dernières mentions.
 *
 * RÈGLE ANONYMOUS-SAFE : lorsque `author_hidden=true`, on affiche
 * strictement « Quelqu'un t'a mentionné dans #<group> » — jamais de
 * pseudo, handle ou rôle. Le backend garantit déjà que ces champs ne
 * sont pas envoyés dans ce cas, on double-check ici.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { AtSign, X, EyeOff } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const POLL_MS = 20000;

export default function MentionNotifier({ device }) {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const timerRef = useRef(null);
  const enabled = !!(device && device.role && device.role !== 'inactive' && device.role !== 'blocked');

  const fetchCount = useCallback(async () => {
    if (!enabled) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/mentions/unread-count`, body);
      const n = Number(r.data?.unread || 0);
      setCount(n);
      // Vibrate discretely on new mention arrival.
      if (n > 0 && typeof window !== 'undefined' && window.navigator?.vibrate) {
        try { window.navigator.vibrate([25, 40, 25]); } catch (_e) { /* ignore */ }
      }
    } catch (_e) { /* silent */ }
  }, [enabled]);

  const fetchList = useCallback(async () => {
    if (!enabled) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { limit: 15 });
      const r = await axios.post(`${API}/mentions/list`, body);
      setItems(r.data?.notifications || []);
    } catch (_e) {
      setItems([]);
    } finally { setBusy(false); }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    fetchCount();
    timerRef.current = setInterval(fetchCount, POLL_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [enabled, fetchCount]);

  const openPanel = async () => {
    setOpen(true);
    await fetchList();
    // Marque tout comme lu à l'ouverture.
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/mentions/mark-all-read`, body);
      setCount(0);
    } catch (_e) { /* silent */ }
  };

  if (!enabled) return null;

  return (
    <>
      <button
        type="button"
        onClick={openPanel}
        data-testid="mentions-bell-btn"
        aria-label="Notifications de mentions"
        className="fixed bottom-4 right-4 z-30 inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-black/70 backdrop-blur border border-white/15 text-white/90 hover:border-[#E4FF00]/50 hover:text-[#E4FF00] transition"
      >
        <AtSign className="w-4 h-4" />
        <span className="text-xs font-bold">Mentions</span>
        {count > 0 && (
          <span
            data-testid="mentions-badge-count"
            className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#E4FF00] text-[#050505] min-w-[18px] text-center"
          >
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="mentions-panel-overlay"
          className="fixed inset-0 z-40 flex items-end justify-end p-4 pointer-events-none"
        >
          <div className="w-full max-w-sm max-h-[70vh] bg-[#050505] border border-white/20 rounded-sm shadow-2xl overflow-hidden pointer-events-auto flex flex-col">
            <header className="px-3 py-2 border-b border-white/10 flex items-center justify-between">
              <div className="text-[11px] font-bold uppercase tracking-widest text-white/80 inline-flex items-center gap-1">
                <AtSign className="w-3.5 h-3.5 text-[#E4FF00]" /> Mentions récentes
              </div>
              <button
                onClick={() => setOpen(false)}
                data-testid="mentions-panel-close"
                className="text-white/50 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
              {busy && <div className="text-[11px] text-white/50 text-center py-4">Chargement…</div>}
              {!busy && items.length === 0 && (
                <div className="text-[11px] text-white/40 text-center py-4">Aucune mention.</div>
              )}
              {!busy && items.map((n, i) => {
                const hidden = !!n.author_hidden;
                return (
                  <div
                    key={n.notification_id || i}
                    data-testid={`mention-item-${i}`}
                    className={`text-[11px] p-2 rounded-sm border ${
                      n.read ? 'border-white/10 bg-white/[0.02]' : 'border-[#E4FF00]/40 bg-[#E4FF00]/[0.05]'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {hidden ? (
                        <>
                          <EyeOff className="w-3 h-3 text-white/40" />
                          <span className="text-white/80" data-testid={`mention-item-${i}-anon-label`}>
                            Quelqu&apos;un t&apos;a mentionné dans
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="text-white/90 font-bold">{n.from_pseudo || '—'}</span>
                          {n.from_public_handle && (
                            <span className="text-white/40 font-mono">@{n.from_public_handle}</span>
                          )}
                          <span className="text-white/60">t&apos;a mentionné dans</span>
                        </>
                      )}
                      <span className="text-cyan-300 font-mono">#{n.group_type}</span>
                    </div>
                    <div className="text-[10px] text-white/40 mt-0.5">
                      {n.ts ? new Date(n.ts).toLocaleString() : ''}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
