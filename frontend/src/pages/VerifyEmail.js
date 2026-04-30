import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { CheckCircle2, AlertTriangle, Loader2, Clock } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Phase: 'processing' | 'verified' | 'expired' | 'invalid'
export default function VerifyEmail() {
  const navigate = useNavigate();
  const location = useLocation();
  const processed = useRef(false);
  const [phase, setPhase] = useState('processing');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    if (!token) {
      setPhase('invalid');
      setMessage("Lien invalide — aucun token présent dans l'URL.");
      return;
    }

    (async () => {
      try {
        const { data } = await axios.get(`${API}/auth/verify-email`, { params: { token } });
        setMessage(data?.message || 'Compte certifié.');
        setPhase('verified');
      } catch (err) {
        const detail = err.response?.data?.detail || '';
        // Backend sends the exact expired message text; detect it.
        if (typeof detail === 'string' && detail.toLowerCase().includes('expir')) {
          setPhase('expired');
          setMessage(detail);
        } else {
          setPhase('invalid');
          setMessage(typeof detail === 'string' ? detail : 'Lien invalide ou déjà utilisé.');
        }
      }
    })();
  }, [location.search]);

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

          {phase === 'verified' && (
            <motion.div
              data-testid="verify-success"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 220, damping: 18 }}
            >
              <div className="w-20 h-20 bg-[#00FF66] rounded-full flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(0,255,102,0.5)]">
                <CheckCircle2 className="w-12 h-12 text-[#050505]" strokeWidth={2.5} />
              </div>
              <h2 className="mt-6 text-xl font-['Chivo'] font-black text-white leading-snug">
                Compte certifié ✔
              </h2>
              <p className="mt-3 text-[#A1A1AA] font-['IBM_Plex_Sans'] text-sm leading-relaxed">
                {message || 'Votre compte est désormais certifié. Vous pouvez fermer cette page et retourner sur l\'application.'}
              </p>
              <div className="mt-6 p-3 bg-[#00FF66]/10 border border-[#00FF66]/30 rounded-sm">
                <p className="text-xs text-[#00FF66] font-['IBM_Plex_Sans']">
                  L'onglet CodeForge AI d'origine se déverrouille automatiquement — pas besoin d'y retourner manuellement.
                </p>
              </div>
            </motion.div>
          )}

          {phase === 'expired' && (
            <motion.div
              data-testid="verify-expired"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <div className="w-16 h-16 bg-orange-500/20 border-2 border-orange-500 rounded-full flex items-center justify-center mx-auto">
                <Clock className="w-8 h-8 text-orange-400" />
              </div>
              <h2 className="mt-6 text-lg font-['Chivo'] font-bold text-white leading-snug">
                Lien expiré
              </h2>
              <p className="mt-3 text-orange-200/80 font-['IBM_Plex_Sans'] text-sm leading-relaxed">
                {message}
              </p>
              <button
                onClick={() => navigate('/login', { replace: true })}
                data-testid="verify-expired-retry-btn"
                className="mt-6 inline-flex items-center gap-2 px-6 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
              >
                Recommencer sur CodeForge AI
              </button>
            </motion.div>
          )}

          {phase === 'invalid' && (
            <motion.div
              data-testid="verify-invalid"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <div className="w-16 h-16 bg-red-500/20 border-2 border-red-500 rounded-full flex items-center justify-center mx-auto">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="mt-6 text-lg font-['Chivo'] font-bold text-white">Lien invalide</h2>
              <p className="mt-3 text-red-400 font-['IBM_Plex_Sans'] text-sm">{message}</p>
              <button
                onClick={() => navigate('/login', { replace: true })}
                data-testid="verify-invalid-back-btn"
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
