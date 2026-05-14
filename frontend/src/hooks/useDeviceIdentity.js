import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { attestDevice } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * useDeviceIdentity — ensures a device key exists, attests it on mount,
 * and exposes the current role + site mode + access permission.
 *
 * Roles:    'creator' | 'approved' | 'pending' | 'revoked'
 * Modes:    'public'  | 'private'  | 'creator' | 'guest'
 */
export default function useDeviceIdentity() {
  const [state, setState] = useState({
    loading: true,
    keyId: null,
    role: null,
    siteMode: 'public',
    canAccess: true,
    error: null,
  });

  const refresh = useCallback(async () => {
    try {
      const result = await attestDevice(API, axios);
      setState({
        loading: false,
        keyId: result.keyId,
        role: result.role || null,
        siteMode: result.site_mode || 'public',
        canAccess: !!result.can_access,
        error: null,
      });
    } catch (e) {
      setState((s) => ({ ...s, loading: false, error: e?.message || 'identity error' }));
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { ...state, refresh };
}
