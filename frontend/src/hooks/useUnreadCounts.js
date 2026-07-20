/**
 * iter150 — Hook + composants « unread counter » par conversation.
 *
 * `useUnreadCounts()` retourne :
 *   {
 *     groups: { public: 3, ... },
 *     dms:    { "<thread>": 5 },
 *     total: 8,
 *     markRead: async (scope, conv_id) => void,
 *     refresh: async () => void,
 *   }
 *
 * Poll toutes les 15 s pour rafraîchir. Écoute aussi l'event global
 * `codeforge:conversation-read` pour update local instantané après
 * un mark-read côté UI.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const POLL_MS = 15000;

export function useUnreadCounts(device) {
  const [state, setState] = useState({ groups: {}, dms: {}, total: 0 });
  const timerRef = useRef(null);
  const enabled = !!(device && device.role && device.role !== 'inactive' && device.role !== 'blocked');

  const refresh = useCallback(async () => {
    if (!enabled) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/social/unread-counts`, body);
      setState({
        groups: r.data?.groups || {},
        dms: r.data?.dms || {},
        total: Number(r.data?.total || 0),
      });
    } catch (_) { /* silent */ }
  }, [enabled]);

  const markRead = useCallback(async (scope, conv_id) => {
    if (!enabled || !conv_id) return;
    try {
      const body = await withCreatorProof(API, axios, { scope, conv_id });
      await axios.post(`${API}/social/mark-read`, body);
    } catch (_) { /* silent */ }
    // Update local instantané.
    setState((prev) => {
      const next = { ...prev };
      if (scope === 'group') {
        next.groups = { ...prev.groups };
        const was = next.groups[conv_id] || 0;
        delete next.groups[conv_id];
        next.total = Math.max(0, prev.total - was);
      } else if (scope === 'dm') {
        next.dms = { ...prev.dms };
        const was = next.dms[conv_id] || 0;
        delete next.dms[conv_id];
        next.total = Math.max(0, prev.total - was);
      }
      return next;
    });
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    refresh();
    timerRef.current = setInterval(refresh, POLL_MS);
    const onEvent = () => refresh();
    window.addEventListener('codeforge:conversation-read', onEvent);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      window.removeEventListener('codeforge:conversation-read', onEvent);
    };
  }, [enabled, refresh]);

  return { ...state, markRead, refresh };
}


/**
 * UnreadBadge — mini pastille rouge Discord-style à côté d'un item.
 * `count` = 0 → rendu vide.
 */
export function UnreadBadge({ count, testId = 'unread-badge', className = '' }) {
  if (!count) return null;
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center justify-center text-[10px] font-bold px-1 min-w-[16px] h-[16px] rounded-full bg-red-500 text-white ${className}`}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}
