import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Idle timeout: 1 hour of total inactivity (no mouse, no keyboard, no
// scroll, no touch) => auto-logout and redirect to /login.
const IDLE_TIMEOUT_MS = 60 * 60 * 1000; // 1h
const IDLE_CHECK_INTERVAL_MS = 30 * 1000; // check every 30s

// Global axios interceptor: attach session_token from localStorage as Bearer
// header on every API call. This guarantees auth works even when cross-site
// cookies are blocked (Brave shields, VPN, Safari ITP, .static. subdomain).
axios.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem('session_token');
    if (token && config.url && config.url.includes(BACKEND_URL || '')) {
      config.headers = config.headers || {};
      if (!config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch (_) {}
  return config;
});

// Response interceptor: if any authenticated API call returns 401
// (server-side session expired/revoked), clean up local state so the
// user is redirected to /login instead of seeing a broken UI.
// We skip this handling for the auth endpoints themselves (login/register
// returning 401 is part of the normal flow there).
axios.interceptors.response.use(
  (resp) => resp,
  (error) => {
    try {
      const status = error?.response?.status;
      const url = error?.config?.url || '';
      const isAuthEndpoint = (
        url.includes('/api/auth/login') ||
        url.includes('/api/auth/register') ||
        url.includes('/api/auth/verify-email') ||
        url.includes('/api/auth/verification-status') ||
        url.includes('/api/auth/forgot-password') ||
        url.includes('/api/auth/reset-password') ||
        url.includes('/api/auth/me') ||
        url.includes('/api/auth/sms/')
      );
      // Also exempt public pages where being a guest is normal — no
      // "session expired" redirect should ever happen here.
      const path = window.location.pathname || '';
      const onPublicPage = (
        path === '/' ||
        path.startsWith('/login') ||
        path.startsWith('/sms-login') ||
        path.startsWith('/verify-email') ||
        path.startsWith('/reset-password')
      );
      if (status === 401 && !isAuthEndpoint && !onPublicPage && url.includes('/api/')) {
        // iter63/64: while a session-approval is being polled from another
        // device, the local user is NOT yet logged in. Suppress the 401-
        // redirect so we never replace their "request in progress" UI with
        // a misleading "session expired" banner. iter64: switched to
        // localStorage (with TTL) so mobile tab-closes don't wipe the flag.
        let pendingApproval = false;
        try {
          const raw = localStorage.getItem('codeforge_session_pending');
          if (raw) {
            const j = JSON.parse(raw);
            if (j && j.until && Date.now() < j.until) pendingApproval = true;
            else localStorage.removeItem('codeforge_session_pending');
          }
        } catch (_) {}
        if (pendingApproval) {
          return Promise.reject(error);
        }
        // Grace window: when the user has JUST been issued a fresh session
        // (e.g. via the 2-device approval flow), suppress the 401-redirect
        // for 5 seconds. Mobile networks + Mongo replica lag can cause one
        // or two early 401s right after login before /auth/me settles.
        let inGrace = false;
        try {
          const gAt = parseInt(sessionStorage.getItem('codeforge_session_grace_at') || '0', 10);
          if (gAt && (Date.now() - gAt) < 5000) inGrace = true;
        } catch (_) {}
        if (!inGrace) {
          try { localStorage.removeItem('session_token'); } catch (_) {}
          const onLogin = window.location.pathname.startsWith('/login');
          if (!onLogin) {
            window.location.assign('/login?reason=session_expired');
          }
        }
      }
    } catch (_) {}
    return Promise.reject(error);
  }
);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const lastActivityRef = useRef(Date.now());
  const idleCheckRef = useRef(null);

  const checkAuth = useCallback(async () => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    if (window.location.hash?.includes('session_id=')) {
      setLoading(false);
      return;
    }

    try {
      // No withCredentials: Cloudflare injects ACAO:* which conflicts with
      // credentialed requests. We rely on the Bearer header set by the axios
      // interceptor from localStorage instead.
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch (error) {
      setUser(null);
      try { localStorage.removeItem('session_token'); } catch (_) {}
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const logout = useCallback(async (reason = 'manual') => {
    try {
      await axios.post(`${API}/auth/logout`, {});
    } catch (error) {
      // best-effort — clear client state regardless
    }
    setUser(null);
    try { localStorage.removeItem('session_token'); } catch (_) {}
    if (reason === 'idle') {
      // Let /login show a friendly banner; don't force a full reload.
      try {
        window.location.assign('/login?reason=idle');
      } catch (_) {}
    }
  }, []);

  // ---- IDLE TIMEOUT ----
  // Tracks any user activity; auto-logs out after 1h of pure inactivity.
  // We don't count background tab time — if the tab is hidden and the
  // user returns within 1h, their session stays alive.
  useEffect(() => {
    if (!user) return; // only arm the watchdog for authenticated users

    const onActivity = () => {
      lastActivityRef.current = Date.now();
    };

    // Fine-grained activity: covers mouse, keyboard, touch, scroll.
    const events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'wheel'];
    events.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));

    // Also bump the timer when the tab becomes visible again (user came
    // back to this tab after switching away — count that as activity).
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        lastActivityRef.current = Date.now();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    idleCheckRef.current = setInterval(() => {
      const idleMs = Date.now() - lastActivityRef.current;
      if (idleMs > IDLE_TIMEOUT_MS) {
        // 1h01 idle → bye
        clearInterval(idleCheckRef.current);
        idleCheckRef.current = null;
        logout('idle');
      }
    }, IDLE_CHECK_INTERVAL_MS);

    return () => {
      events.forEach((e) => window.removeEventListener(e, onActivity));
      document.removeEventListener('visibilitychange', onVisibility);
      if (idleCheckRef.current) {
        clearInterval(idleCheckRef.current);
        idleCheckRef.current = null;
      }
    };
  }, [user, logout]);

  return (
    <AuthContext.Provider value={{ user, setUser, loading, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
