import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Lock, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPassword() {
  const navigate = useNavigate();
  const location = useLocation();
  const tokenRef = useRef('');
  const [phase, setPhase] = useState('form'); // 'form' | 'success' | 'error'
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    if (!token) {
      setPhase('error');
      setError("Lien invalide — aucun token dans l'URL.");
      return;
    }
    tokenRef.current = token;
  }, [location.search]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    if (password.length < 6) {
      toast.error('Le mot de passe doit faire au moins 6 caractères');
      return;
    }
    if (password !== confirm) {
      toast.error('Les deux mots de passe ne correspondent pas');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/reset-password`, {
        token: tokenRef.current,
        password,
      });
      setPhase('success');
      toast.success('Mot de passe mis à jour !');
      setTimeout(() => navigate('/login', { replace: true }), 1500);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : 'Erreur lors de la réinitialisation';
      setError(msg);
      if (typeof msg === 'string' && msg.toLowerCase().includes('expir')) {
        setPhase('error');
      } else {
        toast.error(msg);
      }
    } finally {
      setSubmitting(false);
    }
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
        <div className="bg-white/[0.03] border border-white/10 rounded-sm p-10 backdrop-blur-xl text-center">
          {phase === 'form' && (
            <div data-testid="reset-form">
              <div className="w-16 h-16 bg-[#E4FF00] rounded-sm flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(228,255,0,0.35)]">
                <Lock className="w-8 h-8 text-[#050505]" />
              </div>
              <h1 className="mt-5 text-2xl font-['Chivo'] font-black text-white">Nouveau mot de passe</h1>
              <p className="mt-2 text-sm text-[#A1A1AA] font-['IBM_Plex_Sans']">
                Choisis un nouveau mot de passe pour ton compte.
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-3 text-left">
                <div>
                  <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">Nouveau mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={6}
                      data-testid="reset-password-input"
                      placeholder="••••••••"
                      className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                    />
                  </div>
                  <p className="text-[10px] text-[#A1A1AA]/70 mt-1">6 caractères minimum</p>
                </div>

                <div>
                  <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">Confirme le mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                    <input
                      type="password"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      required
                      minLength={6}
                      data-testid="reset-confirm-input"
                      placeholder="••••••••"
                      className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  data-testid="reset-submit-btn"
                  className="w-full mt-4 flex items-center justify-center gap-2 px-6 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all duration-200 disabled:opacity-60"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Mise à jour…
                    </>
                  ) : (
                    'Mettre à jour mon mot de passe'
                  )}
                </button>
              </form>
            </div>
          )}

          {phase === 'success' && (
            <motion.div
              data-testid="reset-success"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 220, damping: 18 }}
            >
              <div className="w-20 h-20 bg-[#00FF66] rounded-full flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(0,255,102,0.5)]">
                <CheckCircle2 className="w-12 h-12 text-[#050505]" strokeWidth={2.5} />
              </div>
              <h2 className="mt-6 text-xl font-['Chivo'] font-black text-white">Mot de passe mis à jour</h2>
              <p className="mt-3 text-[#A1A1AA] font-['IBM_Plex_Sans'] text-sm">
                Redirection vers la page de connexion…
              </p>
            </motion.div>
          )}

          {phase === 'error' && (
            <motion.div
              data-testid="reset-error"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <div className="w-16 h-16 bg-orange-500/20 border-2 border-orange-500 rounded-full flex items-center justify-center mx-auto">
                <AlertTriangle className="w-8 h-8 text-orange-400" />
              </div>
              <h2 className="mt-6 text-lg font-['Chivo'] font-bold text-white">Lien invalide ou expiré</h2>
              <p className="mt-3 text-orange-200/80 font-['IBM_Plex_Sans'] text-sm">{error}</p>
              <button
                onClick={() => navigate('/login', { replace: true })}
                data-testid="reset-error-back-btn"
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
