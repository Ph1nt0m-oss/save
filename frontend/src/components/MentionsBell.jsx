/**
 * iter150 — MentionsBell (style Discord).
 *
 * REMPLACE l'ancien MentionNotifier (bulle flottante bottom-right).
 * Cette version est un bouton cloche dans la barre supérieure — quand
 * on est mentionné :
 *   - Badge rouge avec compteur (unread) exactement comme Discord.
 *   - Clic → panneau dropdown listant les mentions récentes.
 *   - Chaque mention est cliquable → ouvre la conversation concernée
 *     (dispatche un event `codeforge:open-conversation` avec group_type
 *     ou dm_thread_id) et marque la mention comme lue.
 *   - Règle anonyme préservée (spec iter147) : si `author_hidden=true`,
 *     l'auteur n'est jamais divulgué.
 *
 * Le composant est placé DANS le header (à côté de la cloche « Notifications »)
 * et non plus en floating widget.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { AtSign, X, EyeOff, MessageCircle } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const POLL_MS = 15000;

export default function MentionsBell({ device }) {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const timerRef = useRef(null);
  const wrapRef = useRef(null);
  const enabled = !!(device && device.role && device.role !== 'inactive' && device.role !== 'blocked');

  const fetchCount = useCallback(async () => {
    if (!enabled) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/mentions/unread-count`, body);
      const n = Number(r.data?.unread || 0);
      setCount((prev) => {
        if (n > prev && typeof window !== 'undefined' && window.navigator?.vibrate) {
          try { window.navigator.vibrate([15, 30, 15]); } catch (_) {}
        }
        return n;
      });
    } catch (_) { /* silent */ }
  }, [enabled]);

  const fetchList = useCallback(async () => {
    if (!enabled) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { limit: 25 });
      const r = await axios.post(`${API}/mentions/list`, body);
      setItems(r.data?.notifications || []);
    } catch (_) { setItems([]); }
    finally { setBusy(false); }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    fetchCount();
    timerRef.current = setInterval(fetchCount, POLL_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [enabled, fetchCount]);

  // Ferme le panneau au clic extérieur.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    window.addEventListener('mousedown', onDown);
    return () => window.removeEventListener('mousedown', onDown);
  }, [open]);

  const openPanel = async () => {
    setOpen(true);
    await fetchList();
  };

  const markOneRead = useCallback(async (notification_id) => {
    try {
      const body = await withCreatorProof(API, axios, { notification_ids: [notification_id] });
      await axios.post(`${API}/mentions/mark-read`, body);
    } catch (_) { /* silent */ }
    setItems((prev) => prev.map((n) => n.notification_id === notification_id ? { ...n, read: true } : n));
    setCount((c) => Math.max(0, c - 1));
  }, []);

  const markAllRead = useCallback(async () => {
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/mentions/mark-all-read`, body);
    } catch (_) { /* silent */ }
    setItems((prev) => prev.map((n) => ({ ...n, read: true })));
    setCount(0);
  }, []);

  const openConversation = useCallback((n) => {
    markOneRead(n.notification_id);
    try {
      // Discord-style : dispatch un event global écouté par le Dashboard
      // pour ouvrir le tchat sur le bon salon.
      window.dispatchEvent(new CustomEvent('codeforge:open-conversation', {
        detail: { group_type: n.group_type, message_id: n.message_id, source: 'mention' },
      }));
    } catch (_) { /* silent */ }
    setOpen(false);
  }, [markOneRead]);

  if (!enabled) return null;

  return (
    <div ref={wrapRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openPanel())}
        data-testid="mentions-bell-btn"
        aria-label="Notifications de mentions"
        title={count > 0 ? `${count} mention(s) non lue(s)` : 'Mentions'}
        className="relative text-[#A1A1AA] hover:text-[#E4FF00] transition-colors p-1.5 rounded-sm hover:bg-white/[0.04]"
      >
        <AtSign className="w-4 h-4" />
        {count > 0 && (
          <span
            data-testid="mentions-badge-count"
            className="absolute -top-1 -right-1 text-[10px] font-bold px-1 min-w-[16px] h-[16px] flex items-center justify-center rounded-full bg-red-500 text-white ring-2 ring-[#050505]"
          >
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      {open && (
        <div
          data-testid="mentions-panel-dropdown"
          className="absolute right-0 top-full mt-2 w-[360px] max-w-[90vw] max-h-[70vh] bg-[#050505] border border-white/20 rounded-sm shadow-2xl z-50 flex flex-col"
        >
          <header className="px-3 py-2 border-b border-white/10 flex items-center justify-between">
            <div className="text-[11px] font-bold uppercase tracking-widest text-white/85 inline-flex items-center gap-1.5">
              <AtSign className="w-3.5 h-3.5 text-[#E4FF00]" /> Mentions
              {count > 0 && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-red-500 text-white ml-1">
                  {count}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {count > 0 && (
                <button
                  type="button"
                  onClick={markAllRead}
                  data-testid="mentions-mark-all-read"
                  className="text-[10px] text-[#E4FF00] hover:underline mr-1"
                >
                  Tout marquer lu
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                data-testid="mentions-panel-close"
                className="text-white/60 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </header>
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {busy && <div className="text-[11px] text-white/50 text-center py-4">Chargement…</div>}
            {!busy && items.length === 0 && (
              <div className="text-[11px] text-white/40 text-center py-6">Aucune mention.</div>
            )}
            {!busy && items.map((n, i) => {
              const hidden = !!n.author_hidden;
              return (
                <button
                  key={n.notification_id || i}
                  type="button"
                  onClick={() => openConversation(n)}
                  data-testid={`mention-item-${i}`}
                  className={`w-full text-left p-2.5 rounded-sm border transition-colors group ${
                    n.read
                      ? 'border-white/10 bg-white/[0.02] hover:bg-white/[0.04]'
                      : 'border-[#E4FF00]/40 bg-[#E4FF00]/[0.05] hover:bg-[#E4FF00]/[0.1]'
                  }`}
                >
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {hidden ? (
                      <>
                        <EyeOff className="w-3 h-3 text-white/40" />
                        <span className="text-[11px] text-white/85" data-testid={`mention-item-${i}-anon-label`}>
                          Quelqu&apos;un t&apos;a mentionné
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="text-[11px] text-white font-bold">{n.from_pseudo || '—'}</span>
                        {n.from_public_handle && (
                          <span className="text-[10px] text-white/40 font-mono">@{n.from_public_handle}</span>
                        )}
                        <span className="text-[11px] text-white/60">t&apos;a mentionné</span>
                      </>
                    )}
                    <span className="text-[11px] text-cyan-300 font-mono inline-flex items-center gap-0.5">
                      <MessageCircle className="w-3 h-3" /> #{n.group_type}
                    </span>
                    {!n.read && (
                      <span className="ml-auto text-[9px] uppercase font-bold text-[#E4FF00]">
                        Nouveau
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-white/40 mt-0.5 flex items-center justify-between">
                    <span>{n.ts ? new Date(n.ts).toLocaleString() : ''}</span>
                    <span className="text-[9px] text-cyan-300 opacity-0 group-hover:opacity-100 transition-opacity">
                      → Ouvrir la conversation
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
