import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { attestDevice, withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * useDeviceIdentity — ensures a device key exists, attests it on mount,
 * and exposes the current role + site mode + access permission.
 *
 * Roles:           'creator' | 'approved' | 'pending' | 'revoked'
 * Effective roles: same set + 'guest' (server downgrades unknown/pending
 *                  to 'guest' under private/guest site modes — read-only).
 * Modes:           'public'  | 'private'  | 'creator' | 'guest'
 *
 * `canWrite` is the authoritative client gate for any write action: only
 * 'creator' and 'approved' may write; everyone else is read-only.
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

  // canWrite: only creator/approved devices may perform write actions.
  // Authenticated cookie-based users are handled separately by the API itself,
  // but the UI also disables buttons proactively for guests.
  const canWrite = state.effectiveRole === 'creator' || state.effectiveRole === 'approved';

  return { ...state, canWrite, refresh };
}
