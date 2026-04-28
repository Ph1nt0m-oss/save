import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import confetti from 'canvas-confetti';
import { motion } from 'framer-motion';
import { CheckCircle2, AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Phase: 'processing' | 'success' | 'error'
export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);
  const [phase, setPhase] = useState('processing');
  const [error, setError] = useState(null);
  const [userName, setUserName] = useState(null);

  const fireConfetti = () => {
    // Subtle, on-brand confetti (yellow + green) — ~1s
    const colors = ['#E4FF00', '#00FF66', '#ffffff'];
    const end = Date.now() + 900;
    (function frame() {
      confetti({
        particleCount: 3,
        angle: 60,
        spread: 55,
        startVelocity: 45,
        origin: { x: 0, y: 0.7 },
        colors,
      });
      confetti({
        particleCount: 3,
        angle: 120,
        spread: 55,
        startVelocity: 45,
        origin: { x: 1, y: 0.7 },
        colors,
      });
      if (Date.now() < end) requestAnimationFrame(frame);
    })();
  };

  useEffect(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      try {
        // Parse session_id from URL fragment robustly:
        // 1. Strip leading "#"
        // 2. Use URLSearchParams (handles multiple params, URL-decodes properly)
        // 3. Trim whitespace + any trailing slash that some proxies append
        const fragment = (location.hash || '').replace(/^#/, '');
        const params = new URLSearchParams(fragment);
        const rawSid = params.get('session_id');
        const sessionId = rawSid ? rawSid.trim().replace(/\/+$/, '') : '';

        if (!sessionId) {
          setError("Aucun session_id trouvé dans l'URL");
          setPhase('error');
          return;
        }

        // NOTE: We do NOT use withCredentials here because Cloudflare/ingress
        // injects "Access-Control-Allow-Origin: *" which is incompatible with
        // credentialed requests. Auth is carried via session_token in the
        // response body + localStorage + Bearer header (set by axios interceptor).
        const response = await axios.post(`${API}/auth/session`, { session_id: sessionId });

        const name = response.data?.name || response.data?.email || 'utilisateur';
        setUserName(name);

        if (response.data?.session_token) {
          try {
            localStorage.setItem('session_token', response.data.session_token);
          } catch (_) {}
        }

        setUser(response.data);
        setPhase('success');
        fireConfetti();
        toast.success('Connexion réussie !');

        window.history.replaceState(null, '', window.location.pathname);
        // Brief moment so the success animation + confetti are visible
        setTimeout(() => {
          navigate('/dashboard', { state: { user: response.data }, replace: true });
        }, 1100);
      } catch (err) {
        console.error('AuthCallback: Auth error:', err.response?.data || err.message);
        setError(err.response?.data?.detail || "Erreur d'authentification");
        setPhase('error');
        toast.error('Erreur de connexion Google.');
      }
    };

    processSession();
  }, [location, navigate, setUser]);

  const handleRetry = () => {
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center relative overflow-hidden">
      <div className="fixed inset-0 noise-bg"></div>
      <div className="fixed inset-0 grid-bg opacity-20"></div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <div className="bg-white/[0.03] border border-white/10 rounded-sm p-12 backdrop-blur-xl text-center">
          {phase === 'processing' && (
            <div data-testid="auth-processing">
              <Loader2 className="w-12 h-12 text-[#E4FF00] mx-auto animate-spin" />
              <p className="mt-6 text-white font-['IBM_Plex_Sans'] text-lg">
                {userName ? (
                  <>Bienvenue, <span className="text-[#E4FF00] font-bold">{userName}</span>...</>
                ) : (
                  'Authentification en cours...'
                )}
              </p>
              <p className="mt-2 text-[#A1A1AA] text-sm font-['IBM_Plex_Sans']">
                On t'ouvre les portes de CodeForge.
              </p>
            </div>
          )}

          {phase === 'success' && (
            <motion.div
              data-testid="auth-success"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 220, damping: 18 }}
            >
              <div className="w-20 h-20 bg-[#00FF66] rounded-full flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(0,255,102,0.5)]">
                <CheckCircle2 className="w-12 h-12 text-[#050505]" strokeWidth={2.5} />
              </div>
              <h2 className="mt-6 text-2xl font-['Chivo'] font-black text-white">
                {userName ? `Bienvenue, ${userName} !` : 'Connecté !'}
              </h2>
              <p className="mt-2 text-[#A1A1AA] font-['IBM_Plex_Sans']">
                Redirection vers ton dashboard...
              </p>
            </motion.div>
          )}

          {phase === 'error' && (
            <motion.div
              data-testid="auth-error"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <div className="w-16 h-16 bg-red-500/20 border-2 border-red-500 rounded-full flex items-center justify-center mx-auto">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="mt-6 text-xl font-['Chivo'] font-bold text-white">
                Connexion échouée
              </h2>
              <p className="mt-2 text-red-400 font-['IBM_Plex_Sans'] text-sm">
                {error}
              </p>
              <p className="mt-4 text-[#A1A1AA] font-['IBM_Plex_Sans'] text-sm">
                Pas de panique, ça arrive. Tu peux retenter.
              </p>
              <button
                onClick={handleRetry}
                data-testid="auth-retry-btn"
                className="mt-6 inline-flex items-center gap-2 px-6 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all"
              >
                <RefreshCw className="w-4 h-4" />
                Réessayer
              </button>
            </motion.div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
