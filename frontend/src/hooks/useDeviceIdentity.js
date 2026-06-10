import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { attestDevice, withCreatorProof, signNonce, getCachedKeyId } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// View mode is a CLIENT-SIDE preference: creators can preview the app as a
// guest, user, modo, admin or creator would see it.
// iter87 — Si AUCUNE case n'est cochée, viewMode = null (mode écriture).
const VIEW_MODE_KEY = 'codeforge_view_mode';
const VALID_VIEW_MODES = ['creator', 'user', 'modo', 'admin', 'guest'];
function readViewMode() {
  try {
    const v = localStorage.getItem(VIEW_MODE_KEY);
    return VALID_VIEW_MODES.includes(v) ? v : null;
  } catch (_) { return null; }
}
export function setStoredViewMode(mode) {
  try {
    if (mode === null || mode === undefined || mode === '') {
      localStorage.removeItem(VIEW_MODE_KEY);
    } else {
      const safe = VALID_VIEW_MODES.includes(mode) ? mode : null;
      if (safe) localStorage.setItem(VIEW_MODE_KEY, safe);
      else localStorage.removeItem(VIEW_MODE_KEY);
    }
  } catch (_) { /* silent */ }
  try { window.dispatchEvent(new Event('codeforge:view-mode-changed')); } catch (_) { /* silent */ }
}

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
    viewMode: readViewMode(),
    error: null,
  });
  const sseRef = useRef(null);

  // Listen for view-mode changes broadcast by setStoredViewMode().
  useEffect(() => {
    const onChange = () => setState((s) => ({ ...s, viewMode: readViewMode() }));
    window.addEventListener('codeforge:view-mode-changed', onChange);
    return () => window.removeEventListener('codeforge:view-mode-changed', onChange);
  }, []);

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
        siteModes: Array.isArray(result.site_modes) ? result.site_modes : (result.site_mode ? [result.site_mode] : ['public']),
        guestView: result.guest_view || null,
        canAccess: !!result.can_access,
        kickReason: result.kick_reason || null,
        forceVisitor: !!result.force_visitor,  // iter77
        staffKind: result.staff_kind || null,  // iter77
        pendingCount,
        viewMode: readViewMode(),
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

  // canWrite — rules per site_mode:
  //  - 'public'  : everyone can write (creator, approved, pending, anonymous)
  //  - 'guest'   : nobody can write (read-only preview for the whole site)
  //  - 'private' : only creator + approved can write
  //  - 'creator' : only creator can write (others are blocked by SiteLockedOverlay)
  // Plus: any NON-creator visitor who toggles "preview creator view" sees
  // the admin surface in read-only mode — canWrite becomes false in that view.
  // iter77 — `force_visitor` côté backend = la créa a mis ce device en lecture seule.
  // iter87 — viewMode = null = mode ÉCRITURE (créa par défaut). Toute autre
  // valeur = simulation. canWrite recalculé en conséquence.
  const inSimulation = state.role === 'creator' && state.viewMode && state.viewMode !== 'creator';
  let canWrite;
  if (state.forceVisitor && state.role !== 'creator') {
    canWrite = false;
  } else if (state.viewMode === 'guest') {
    canWrite = false;
  } else if (inSimulation) {
    if (state.siteMode === 'creator') {
      canWrite = false;
    } else {
      canWrite = true;
    }
  } else if (state.siteMode === 'public') {
    canWrite = true;
  } else if (state.siteMode === 'guest') {
    canWrite = false;
  } else if (state.siteMode === 'private') {
    canWrite = state.role === 'creator' || state.role === 'approved';
  } else if (state.siteMode === 'creator') {
    canWrite = state.role === 'creator';
  } else {
    canWrite = false;
  }

  // iter85/87 — effectiveStaffKind : si créa simule modo/admin, expose ce kind.
  let effectiveStaffKind = state.staffKind || null;
  if (state.role === 'creator') {
    if (state.viewMode === 'modo') effectiveStaffKind = 'modo';
    else if (state.viewMode === 'admin') effectiveStaffKind = 'admin';
    else if (state.viewMode === 'user' || state.viewMode === 'guest') effectiveStaffKind = null;
    else effectiveStaffKind = state.staffKind || null;  // creator-view ou null
  }

  const isRealCreator = state.role === 'creator';
  // iter87 — Vue créa = null OU 'creator' (les deux signifient mode écriture créa).
  const isCreatorView = isRealCreator && (!state.viewMode || state.viewMode === 'creator');

  return { ...state, canWrite, isCreatorView, isRealCreator, effectiveStaffKind, refresh };
}
