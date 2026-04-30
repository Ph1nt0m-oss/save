import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import confetti from 'canvas-confetti';
import { motion } from 'framer-motion';
import { Mail, Lock, User, Phone, Loader2, ArrowRight, Copy, CheckCheck, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LAST_EMAIL_KEY = 'codeforge_last_email';

function formatDetail(detail) {
  if (!detail) return 'Une erreur est survenue.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => (e?.msg ? e.msg : JSON.stringify(e))).join(' ');
  }
  return String(detail);
}

function fireConfetti() {
  const colors = ['#E4FF00', '#00FF66', '#ffffff'];
  const end = Date.now() + 900;
  (function frame() {
    confetti({ particleCount: 3, angle: 60, spread: 55, startVelocity: 45, origin: { x: 0, y: 0.7 }, colors });
    confetti({ particleCount: 3, angle: 120, spread: 55, startVelocity: 45, origin: { x: 1, y: 0.7 }, colors });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();
}

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();

  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [demoLink, setDemoLink] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);

  // Verification polling state (active between /register and the user
  // clicking the magic link in their email / the demo link).
  const [waitingFor, setWaitingFor] = useState(null); // { token, email } | null
  const [secondsLeft, setSecondsLeft] = useState(0);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  // Prefill email from localStorage (returning users)
  useEffect(() => {
    try {
      const last = localStorage.getItem(LAST_EMAIL_KEY);
      if (last) setEmail(last);
    } catch (_) {}
  }, []);

  // Stop all timers/pollers when unmounting
  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const stopWaiting = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setWaitingFor(null);
    setSecondsLeft(0);
  };

  const startWaiting = (token, userEmail, ttlSec) => {
    setWaitingFor({ token, email: userEmail });
    setSecondsLeft(ttlSec || 300);

    // Countdown timer (1s tick)
    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          // Expired locally — stop polling and surface a clear message
          stopWaiting();
          toast.error("La durée de validation de ce lien a expiré. Merci de réessayer à nouveau sur CodeForge AI.", { duration: 8000 });
          setDemoLink(null);
          return 0;
        }
        return s - 1;
      });
    }, 1000);

    // Poll every 2s
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/auth/verification-status`, { params: { token } });
        if (data.status === 'verified' && data.session_token) {
          stopWaiting();
          try { localStorage.setItem('session_token', data.session_token); } catch (_) {}
          try { localStorage.setItem(LAST_EMAIL_KEY, userEmail); } catch (_) {}
          setUser(data.user || { email: userEmail, session_token: data.session_token });
          setDemoLink(null);
          fireConfetti();
          toast.success(`Bienvenue, ${data.user?.name || data.user?.email || userEmail} !`);
          navigate('/dashboard', { replace: true, state: { user: data.user } });
        } else if (data.status === 'expired') {
          stopWaiting();
          setDemoLink(null);
          toast.error("La durée de validation de ce lien a expiré. Merci de réessayer à nouveau sur CodeForge AI.", { duration: 8000 });
        }
      } catch (_) {
        // transient errors: keep polling silently
      }
    }, 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setDemoLink(null);
    stopWaiting();
    setSubmitting(true);

    try {
      if (mode === 'signup') {
        const { data } = await axios.post(`${API}/auth/register`, {
          email: email.trim(),
          password,
          name: name.trim() || undefined,
          frontend_url: window.location.origin,
        });
        try { localStorage.setItem(LAST_EMAIL_KEY, email.trim().toLowerCase()); } catch (_) {}

        if (data.email_sent) {
          toast.success("Lien de confirmation envoyé par email ! Tu as 5 minutes.");
        } else if (data.verification_link) {
          setDemoLink(data.verification_link);
          toast.info("Mode démo — clique sur le lien ci-dessous pour confirmer.");
        }

        // Kick off polling so the original tab auto-unlocks the moment
        // the link is clicked (possibly in another tab from email client).
        if (data.verification_token) {
          startWaiting(data.verification_token, email.trim().toLowerCase(), data.expires_in_seconds);
        }
      } else {
        const { data } = await axios.post(`${API}/auth/login`, {
          email: email.trim(),
          password,
        });
        if (data.session_token) {
          try { localStorage.setItem('session_token', data.session_token); } catch (_) {}
        }
        try { localStorage.setItem(LAST_EMAIL_KEY, email.trim().toLowerCase()); } catch (_) {}
        setUser(data);
        toast.success(`Bienvenue, ${data.name || data.email} !`);
        navigate('/dashboard', { replace: true, state: { user: data } });
      }
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(demoLink);
      setLinkCopied(true);
      toast.success('Lien copié !');
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (_) {
      toast.error('Impossible de copier le lien');
    }
  };

  const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.08 } },
  };
  const item = {
    hidden: { opacity: 0, y: 14 },
    show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
  };

  const mm = Math.floor(secondsLeft / 60).toString().padStart(2, '0');
  const ss = (secondsLeft % 60).toString().padStart(2, '0');

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center relative overflow-hidden">
      <div className="fixed inset-0 noise-bg"></div>
      <div className="fixed inset-0 grid-bg opacity-20"></div>

      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="bg-white/[0.03] border border-white/10 rounded-sm p-10 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.4)]"
        >
          <div className="text-center space-y-5">
            <motion.div variants={item} className="inline-block">
              <div className="w-16 h-16 bg-[#E4FF00] rounded-sm flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(228,255,0,0.35)]">
                <span className="text-3xl font-['Chivo'] font-black text-[#050505]">CF</span>
              </div>
            </motion.div>

            <motion.div variants={item}>
              <h1 className="text-2xl font-['Chivo'] font-black text-white">CodeForge AI</h1>
              <p className="text-sm text-[#A1A1AA] font-['IBM_Plex_Sans'] mt-1">
                {waitingFor
                  ? 'En attente de la confirmation…'
                  : (mode === 'login' ? 'Connecte-toi pour continuer' : 'Crée ton compte gratuit')}
              </p>
            </motion.div>

            {/* Waiting banner — shown while polling */}
            {waitingFor && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                data-testid="verify-waiting-banner"
                className="flex items-start gap-3 p-4 bg-[#E4FF00]/10 border border-[#E4FF00]/30 rounded-sm text-left"
              >
                <Clock className="w-5 h-5 text-[#E4FF00] flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-['Chivo'] font-bold text-white">
                    Clique sur le lien envoyé à <span className="text-[#E4FF00]">{waitingFor.email}</span>
                  </p>
                  <p className="text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mt-1">
                    Dès que tu cliques, cette page se déverrouille automatiquement.
                  </p>
                  <p data-testid="verify-countdown" className="text-xs text-[#E4FF00] font-mono mt-2">
                    Expire dans {mm}:{ss}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => { stopWaiting(); setDemoLink(null); }}
                  data-testid="verify-cancel-btn"
                  className="text-xs text-[#A1A1AA] hover:text-white underline"
                >
                  Annuler
                </button>
              </motion.div>
            )}

            {/* Tabs — hidden while waiting to avoid confusion */}
            {!waitingFor && (
              <motion.div variants={item} className="flex gap-1 p-1 bg-white/[0.04] border border-white/10 rounded-sm">
                <button
                  type="button"
                  onClick={() => { setMode('login'); setDemoLink(null); }}
                  data-testid="tab-login"
                  className={`flex-1 py-2 text-sm font-['Chivo'] font-bold rounded-sm transition-all ${
                    mode === 'login'
                      ? 'bg-[#E4FF00] text-[#050505]'
                      : 'text-[#A1A1AA] hover:text-white'
                  }`}
                >
                  Connexion
                </button>
                <button
                  type="button"
                  onClick={() => { setMode('signup'); setDemoLink(null); }}
                  data-testid="tab-signup"
                  className={`flex-1 py-2 text-sm font-['Chivo'] font-bold rounded-sm transition-all ${
                    mode === 'signup'
                      ? 'bg-[#E4FF00] text-[#050505]'
                      : 'text-[#A1A1AA] hover:text-white'
                  }`}
                >
                  Inscription
                </button>
              </motion.div>
            )}

            {!waitingFor && (
              <motion.form variants={item} onSubmit={handleSubmit} className="space-y-3 text-left">
                {mode === 'signup' && (
                  <div>
                    <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">Nom (optionnel)</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        data-testid="signup-name-input"
                        placeholder="Ton nom"
                        className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">
                    Adresse email (Gmail de préférence)
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoComplete="email"
                      data-testid="auth-email-input"
                      placeholder="toi@gmail.com"
                      className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">Mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={6}
                      autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                      data-testid="auth-password-input"
                      placeholder="••••••••"
                      className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                    />
                  </div>
                  {mode === 'signup' && (
                    <p className="text-[10px] text-[#A1A1AA]/70 mt-1">6 caractères minimum</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  data-testid={mode === 'signup' ? 'signup-submit-btn' : 'login-submit-btn'}
                  className="w-full mt-2 flex items-center justify-center gap-2 px-6 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {mode === 'signup' ? 'Création…' : 'Connexion…'}
                    </>
                  ) : (
                    <>
                      {mode === 'signup' ? 'Créer mon compte' : 'Se connecter'}
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </motion.form>
            )}

            {/* Demo link (shown alongside the waiting banner) */}
            {demoLink && waitingFor && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                data-testid="demo-verification-link"
                className="p-3 bg-cyan-400/10 border border-cyan-400/30 rounded-sm text-left"
              >
                <p className="text-xs font-['IBM_Plex_Sans'] text-cyan-200 leading-relaxed mb-2">
                  <span className="font-bold">Mode démo actif.</span> Clique sur le lien (s'ouvre dans un nouvel onglet)&nbsp;:
                </p>
                <div className="flex gap-2">
                  <a
                    href={demoLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid="demo-verification-link-anchor"
                    className="flex-1 block bg-black/40 px-2 py-1.5 rounded-sm text-[10px] text-cyan-300 truncate hover:text-cyan-200 transition-colors"
                  >
                    {demoLink}
                  </a>
                  <button
                    onClick={copyLink}
                    type="button"
                    data-testid="demo-verification-link-copy"
                    className="px-2 py-1.5 bg-cyan-400/20 hover:bg-cyan-400/30 rounded-sm text-cyan-300 transition-colors"
                  >
                    {linkCopied ? <CheckCheck className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </motion.div>
            )}

            {!waitingFor && (
              <>
                <motion.div variants={item} className="relative py-2">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-white/10"></div>
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-[#0F0F13] px-3 text-xs text-[#A1A1AA]">ou mode hors-ligne</span>
                  </div>
                </motion.div>

                <motion.button
                  variants={item}
                  onClick={() => navigate('/sms-login')}
                  data-testid="sms-login-btn"
                  className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-white/[0.04] border border-white/10 text-white font-['Chivo'] font-bold rounded-sm hover:border-cyan-400 hover:text-cyan-400 hover:-translate-y-0.5 transition-all duration-200"
                >
                  <Phone className="w-4 h-4" />
                  Connexion SMS (démo)
                </motion.button>
              </>
            )}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-center mt-4"
        >
          <button
            onClick={() => navigate('/')}
            data-testid="back-to-home-btn"
            className="text-xs text-[#A1A1AA] hover:text-[#E4FF00] font-['IBM_Plex_Sans'] transition-colors"
          >
            ← Retour à l'accueil
          </button>
        </motion.div>
      </motion.div>
    </div>
  );
}
