import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { attestDevice, withCreatorProof, signNonce, getCachedKeyId } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * useDeviceIdentity — ensures a device key exists, attests it on mount,
 * and exposes the current role + site mode + access permission.
 *
 * Real-time: when role==='creator', subscribes to a Server-Sent Events
 * stream that pushes `pending_count` updates every 5s (or whenever the
 * count changes). Falls back to the cached value on disconnect.
 */
export default function useDeviceIdentity() {
  const [state, setState] = useState({
    loading: true,
    keyId: null,
    role: null,
    effectiveRole: null,
    siteMode: 'public',
    canAccess: true,
    pendingCount: 0,
    error: null,
  });
  const sseRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const result = await attestDevice(API, axios);
      const effective = result.effective_role || result.role || null;
      let pendingCount = 0;
      if (result.role === 'creator') {
        try {
          const body = await withCreatorProof(API, axios, {});
          const r = await axios.post(`${API}/devices/pending-count`, body);
          pendingCount = r.data?.pending_count || 0;
        } catch (_) { pendingCount = 0; }
      }
      setState({
        loading: false,
        keyId: result.keyId,
        role: result.role || null,
        effectiveRole: effective,
        siteMode: result.site_mode || 'public',
        canAccess: !!result.can_access,
        pendingCount,
        error: null,
      });
    } catch (e) {
      setState((s) => ({ ...s, loading: false, error: e?.message || 'identity error' }));
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Real-time SSE subscription for the creator's pending-count badge.
  useEffect(() => {
    if (state.role !== 'creator') return;
    let cancelled = false;

    (async () => {
      try {
        const keyId = getCachedKeyId();
        if (!keyId) return;
        // Get a fresh nonce + signature pair for the SSE auth path-args.
        const ch = await axios.post(`${API}/devices/challenge`, { key_id: keyId });
        const nonce = ch.data?.nonce;
        if (!nonce) return;
        const signature = await signNonce(nonce);
        if (cancelled) return;

        const url = `${API}/devices/pending-stream/${encodeURIComponent(keyId)}/${encodeURIComponent(nonce)}/${encodeURIComponent(signature)}`;
        const es = new EventSource(url);
        sseRef.current = es;
        es.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            if (typeof data.pending_count === 'number') {
              setState((s) => ({ ...s, pendingCount: data.pending_count }));
            }
          } catch (_) {}
        };
        es.addEventListener('closed', () => { try { es.close(); } catch (_) {} });
        es.onerror = () => { try { es.close(); } catch (_) {} };
      } catch (_) { /* swallow — fall back to polling */ }
    })();

    return () => {
      cancelled = true;
      try { sseRef.current?.close(); } catch (_) {}
      sseRef.current = null;
    };
  }, [state.role]);

  // canWrite: only creator/approved devices may perform write actions.
  const canWrite = state.effectiveRole === 'creator' || state.effectiveRole === 'approved';

  return { ...state, canWrite, refresh };
}
