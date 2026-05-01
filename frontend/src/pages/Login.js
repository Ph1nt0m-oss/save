import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import confetti from 'canvas-confetti';
import { motion } from 'framer-motion';
import { Mail, Lock, User, Phone, Loader2, ArrowRight, Copy, CheckCheck, Clock, RefreshCw, X } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';

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
  const { t } = useLanguage();

  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [demoLink, setDemoLink] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [idleNotice, setIdleNotice] = useState(false);

  // Verification polling state (active between /register and the user
  // clicking the magic link in their email / the demo link).
  const [waitingFor, setWaitingFor] = useState(null); // { token, email } | null
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [resending, setResending] = useState(false);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(0); // epoch ms
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  // Prefill email from localStorage (returning users)
  useEffect(() => {
    try {
      const last = localStorage.getItem(LAST_EMAIL_KEY);
      if (last) setEmail(last);
    } catch (_) {}
  }, []);

  // Surface ?verified=1 (post email confirm) or ?reason=idle (auto logout)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('verified') === '1') {
      setTimeout(() => toast.success('Email confirmé ! Connecte-toi maintenant.', { duration: 5000 }), 400);
      window.history.replaceState(null, '', window.location.pathname);
    } else if (params.get('reason') === 'idle') {
      setIdleNotice(true);
      window.history.replaceState(null, '', window.location.pathname);
    } else if (params.get('reason') === 'session_expired') {
      setTimeout(() => toast.info(
        'Ta session a expiré côté serveur. Reconnecte-toi.',
        { duration: 6000 }
      ), 400);
      window.history.replaceState(null, '', window.location.pathname);
    }
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
          toast.success("Lien de confirmation envoyé par email ! Vérifie ta boîte (et tes spams). Tu as 5 minutes.", { duration: 6000 });
        } else if (data.verification_link) {
          setDemoLink(data.verification_link);
          toast.info("Email indisponible — clique sur le lien ci-dessous pour confirmer.");
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

  const handleResend = async () => {
    if (resending || !waitingFor?.email) return;
    setResending(true);
    try {
      const { data } = await axios.post(`${API}/auth/resend-verification`, {
        email: waitingFor.email,
        frontend_url: window.location.origin,
      });
      if (data.verification_token) {
        // Restart waiting with the new token — stopWaiting clears old timers first
        stopWaiting();
        if (data.email_sent) {
          toast.success("Nouveau lien envoyé par email ! 5 minutes.");
          setDemoLink(null);
        } else if (data.verification_link) {
          setDemoLink(data.verification_link);
          toast.info("Nouveau lien généré (mode démo).");
        }
        startWaiting(data.verification_token, waitingFor.email, data.expires_in_seconds);
      } else {
        toast.info(data.message || "Demande de renvoi traitée.");
      }
    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        // Backend rate limit is 10 min; disable button until then
        setResendCooldownUntil(Date.now() + 10 * 60 * 1000);
      }
      toast.error(formatDetail(err.response?.data?.detail) || err.message);
    } finally {
      setResending(false);
    }
  };

  const handleForgotPassword = async () => {
    const target = (email || '').trim().toLowerCase();
    if (!target) {
      toast.error("Renseigne d'abord ton email pour recevoir le lien.");
      return;
    }
    try {
      const { data } = await axios.post(`${API}/auth/forgot-password`, {
        email: target,
        frontend_url: window.location.origin,
      });
      if (data.email_sent) {
        toast.success("Email de réinitialisation envoyé ! Vérifie ta boîte.");
      } else if (data.reset_link) {
        // Demo mode: open the link directly
        toast.info("Mode démo — lien de réinitialisation ouvert.");
        window.open(data.reset_link, '_blank', 'noopener,noreferrer');
      } else {
        toast.info(data.message || "Demande traitée.");
      }
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || err.message);
    }
  };

  const handleMagicLink = async () => {
    const target = (email || '').trim().toLowerCase();
    if (!target) {
      toast.error("Renseigne d'abord ton email.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/auth/magic-link`, {
        email: target,
        frontend_url: window.location.origin,
      });
      try { localStorage.setItem(LAST_EMAIL_KEY, target); } catch (_) {}
      if (data.email_sent) {
        toast.success("Lien de connexion envoyé par email !");
      } else if (data.verification_link) {
        setDemoLink(data.verification_link);
        toast.info("Mode démo — clique sur le lien ci-dessous.");
      } else {
        toast.info(data.message);
      }
      if (data.verification_token) {
        startWaiting(data.verification_token, target, data.expires_in_seconds);
      }
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || err.message);
    } finally {
      setSubmitting(false);
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
                  ? t('loginWaitingForConfirm')
                  : (mode === 'login' ? t('loginConnectToContinue') : t('loginCreateAccount'))}
              </p>
            </motion.div>

            {/* Idle auto-logout banner — dismissible */}
            {idleNotice && !waitingFor && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                data-testid="idle-logout-banner"
                className="flex items-start gap-3 p-3 bg-orange-400/10 border border-orange-400/30 rounded-sm text-left"
              >
                <Clock className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                <p className="flex-1 text-xs font-['IBM_Plex_Sans'] text-orange-200/90 leading-relaxed">
                  {t('loginIdleNotice')}
                </p>
                <button
                  type="button"
                  onClick={() => setIdleNotice(false)}
                  data-testid="idle-logout-banner-close"
                  aria-label="Fermer"
                  className="text-orange-300 hover:text-orange-200 transition-colors flex-shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              </motion.div>
            )}

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
                  <div className="flex gap-2 mt-3">
                    <button
                      type="button"
                      onClick={handleResend}
                      disabled={resending || Date.now() < resendCooldownUntil}
                      data-testid="resend-link-btn"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#E4FF00]/20 hover:bg-[#E4FF00]/30 text-[#E4FF00] text-xs font-['Chivo'] font-bold rounded-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {resending ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      {resending
                        ? 'Envoi…'
                        : (Date.now() < resendCooldownUntil ? 'Patiente 10 min' : 'Renvoyer le lien')}
                    </button>
                    <button
                      type="button"
                      onClick={() => { stopWaiting(); setDemoLink(null); }}
                      data-testid="verify-cancel-btn"
                      className="text-xs text-[#A1A1AA] hover:text-white underline"
                    >
                      Annuler
                    </button>
                  </div>
                </div>
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
                  {t('loginSignin')}
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
                  {t('loginSignup')}
                </button>
              </motion.div>
            )}

            {!waitingFor && (
              <motion.form variants={item} onSubmit={handleSubmit} className="space-y-3 text-left">
                {mode === 'signup' && (
                  <div>
                    <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">{t('loginName')}</label>
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
                    {t('loginEmail')}
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
                  <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">{t('loginPassword')}</label>
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
                    <p className="text-[10px] text-[#A1A1AA]/70 mt-1">{t('loginEmailMinChars')}</p>
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
                      {mode === 'signup' ? t('loginSubmitSignup') : t('loginSubmitSignin')}
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>

                {mode === 'login' && (
                  <>
                    <button
                      type="button"
                      onClick={handleMagicLink}
                      disabled={submitting}
                      data-testid="magic-link-btn"
                      className="w-full flex items-center justify-center gap-2 px-6 py-2.5 bg-white/[0.04] border border-white/10 text-white text-sm font-['Chivo'] font-bold rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-all mt-2 disabled:opacity-60"
                    >
                      <Mail className="w-4 h-4" />
                      {t('loginMagicLink')}
                    </button>
                    <button
                      type="button"
                      onClick={handleForgotPassword}
                      data-testid="forgot-password-btn"
                      className="w-full text-center text-xs text-[#A1A1AA] hover:text-[#E4FF00] font-['IBM_Plex_Sans'] underline transition-colors mt-1"
                    >
                      {t('loginForgot')}
                    </button>
                  </>
                )}
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
                  <span className="font-bold">Lien direct&nbsp;:</span> clique pour confirmer ton compte (s'ouvre dans un nouvel onglet) :
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
                    <span className="bg-[#0F0F13] px-3 text-xs text-[#A1A1AA]">{t('loginOrOffline')}</span>
                  </div>
                </motion.div>

                <motion.button
                  variants={item}
                  onClick={() => navigate('/sms-login')}
                  data-testid="sms-login-btn"
                  className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-white/[0.04] border border-white/10 text-white font-['Chivo'] font-bold rounded-sm hover:border-cyan-400 hover:text-cyan-400 hover:-translate-y-0.5 transition-all duration-200"
                >
                  <Phone className="w-4 h-4" />
                  {t('loginSmsDemo')}
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
            {t('loginBackHome')}
          </button>
          <div className="mt-3 flex items-center justify-center gap-3 text-[11px] text-[#A1A1AA]/60">
            <button
              type="button"
              onClick={() => navigate('/how-it-works')}
              data-testid="link-how-it-works"
              className="hover:text-[#E4FF00] transition-colors"
            >
              {t('loginHowItWorks')}
            </button>
            <span>·</span>
            <button
              type="button"
              onClick={() => navigate('/legal')}
              data-testid="link-legal"
              className="hover:text-[#E4FF00] transition-colors"
            >
              {t('loginLegal')}
            </button>
            <span>·</span>
            <LanguageToggle />
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
