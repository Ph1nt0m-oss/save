import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import confetti from 'canvas-confetti';
import { motion } from 'framer-motion';
import { CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function VerifyEmail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const processed = useRef(false);
  const [phase, setPhase] = useState('processing');
  const [error, setError] = useState(null);
  const [userName, setUserName] = useState(null);

  const fireConfetti = () => {
    const colors = ['#E4FF00', '#00FF66', '#ffffff'];
    const end = Date.now() + 900;
    (function frame() {
      confetti({ particleCount: 3, angle: 60, spread: 55, startVelocity: 45, origin: { x: 0, y: 0.7 }, colors });
      confetti({ particleCount: 3, angle: 120, spread: 55, startVelocity: 45, origin: { x: 1, y: 0.7 }, colors });
      if (Date.now() < end) requestAnimationFrame(frame);
    })();
  };

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    if (!token) {
      setError("Lien invalide — aucun token présent.");
      setPhase('error');
      return;
    }

    (async () => {
      try {
        const { data } = await axios.get(`${API}/auth/verify-email`, { params: { token } });
        if (data?.session_token) {
          try { localStorage.setItem('session_token', data.session_token); } catch (_) {}
        }
        if (data?.email) {
          try { localStorage.setItem('codeforge_last_email', data.email); } catch (_) {}
        }
        setUser(data);
        setUserName(data?.name || data?.email || 'utilisateur');
        setPhase('success');
        fireConfetti();
        toast.success('Email confirmé !');
        setTimeout(() => navigate('/dashboard', { replace: true, state: { user: data } }), 1200);
      } catch (err) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : "Lien invalide ou expiré.");
        setPhase('error');
      }
    })();
  }, [location.search, navigate, setUser]);

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
            <div data-testid="verify-processing">
              <Loader2 className="w-12 h-12 text-[#E4FF00] mx-auto animate-spin" />
              <p className="mt-6 text-white font-['IBM_Plex_Sans'] text-lg">Vérification en cours…</p>
            </div>
          )}

          {phase === 'success' && (
            <motion.div
              data-testid="verify-success"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 220, damping: 18 }}
            >
              <div className="w-20 h-20 bg-[#00FF66] rounded-full flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(0,255,102,0.5)]">
                <CheckCircle2 className="w-12 h-12 text-[#050505]" strokeWidth={2.5} />
              </div>
              <h2 className="mt-6 text-2xl font-['Chivo'] font-black text-white">
                {userName ? `Bienvenue, ${userName} !` : 'Compte confirmé !'}
              </h2>
              <p className="mt-2 text-[#A1A1AA] font-['IBM_Plex_Sans']">Redirection vers ton dashboard…</p>
            </motion.div>
          )}

          {phase === 'error' && (
            <motion.div
              data-testid="verify-error"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <div className="w-16 h-16 bg-red-500/20 border-2 border-red-500 rounded-full flex items-center justify-center mx-auto">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="mt-6 text-xl font-['Chivo'] font-bold text-white">Lien invalide</h2>
              <p className="mt-2 text-red-400 font-['IBM_Plex_Sans'] text-sm">{error}</p>
              <button
                onClick={() => navigate('/login', { replace: true })}
                data-testid="verify-error-back-btn"
                className="mt-6 inline-flex items-center gap-2 px-6 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
              >
                Retour à la connexion
              </button>
            </motion.div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
