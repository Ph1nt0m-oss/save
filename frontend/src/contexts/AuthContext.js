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
