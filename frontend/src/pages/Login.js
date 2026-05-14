import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import confetti from 'canvas-confetti';
import { motion } from 'framer-motion';
import { Mail, Lock, User, Phone, Loader2, ArrowRight, Copy, CheckCheck, Clock, RefreshCw, X, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';
import CreatorToolbar from '../components/CreatorToolbar';
import TheftRecoveryDialog from '../components/TheftRecoveryDialog';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { rememberEmailForDevice, recallEmailForDevice } from '../lib/deviceIdentity';
import { detectDeviceLabel } from '../lib/deviceLabel';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LAST_EMAIL_KEY = 'codeforge_last_email';
const KNOWN_ACCOUNTS_KEY = 'codeforge_known_accounts';

function rememberAccount(user) {
  if (!user || !user.email) return;
  try {
    const raw = localStorage.getItem(KNOWN_ACCOUNTS_KEY);
    const list = raw ? JSON.parse(raw) : [];
    const filtered = Array.isArray(list)
      ? list.filter(a => a && a.email && a.email !== user.email)
      : [];
    const entry = {
      email: user.email,
      name: user.name || user.email.split('@')[0],
      picture: user.picture || null,
      last_used: new Date().toISOString(),
    };
    // newest first, cap at 6
    const updated = [entry, ...filtered].slice(0, 6);
    localStorage.setItem(KNOWN_ACCOUNTS_KEY, JSON.stringify(updated));
  } catch (_) {}
}

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

  const [mode, setMode] = useState('login'); // 'login' | 'signup' | 'forgot'
  const [confirmPassword, setConfirmPassword] = useState('');
  const [forgotSent, setForgotSent] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [demoLink, setDemoLink] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [idleNotice, setIdleNotice] = useState(false);
  const [authError, setAuthError] = useState(''); // inline red error (wrong password, etc.)
  const [pendingApproval, setPendingApproval] = useState(null); // {request_id, email} when 2nd-device flow active
  const [theftOpen, setTheftOpen] = useState(false);

  // Verification polling state (active between /register and the user
  // clicking the magic link in their email / the demo link).
  const [waitingFor, setWaitingFor] = useState(null); // { token, email } | null
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [resending, setResending] = useState(false);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(0); // epoch ms
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  // Sécurité : pas de prefill cross-device. Mais SUR CET APPAREIL, on
  // pré-remplit l'email du dernier compte utilisé (lié à la clé crypto de
  // l'appareil, jamais transmis au serveur). Le mot de passe n'est JAMAIS
  // mémorisé.
  const device = useDeviceIdentity();
  useEffect(() => {
    try { localStorage.removeItem(LAST_EMAIL_KEY); } catch (_) {}
    const remembered = recallEmailForDevice();
    if (remembered && !email) setEmail(remembered);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll the session-request status until approved/denied/expired by the
  // already-connected device.
  useEffect(() => {
    if (!pendingApproval?.request_id) return;
    let cancelled = false;
    let navigated = false;
    const tick = async () => {
      if (navigated) return;
      try {
        const r = await axios.post(`${API}/auth/session-request-status`, {
          request_id: pendingApproval.request_id,
        }, { withCredentials: true });
        if (cancelled || navigated) return;
        const status = r.data?.status;
        if (status === 'approved') {
          navigated = true;
          // Persist Bearer FIRST so any subsequent /api call has it.
          if (r.data?.session_token) {
            try { localStorage.setItem('session_token', r.data.session_token); } catch (_) {}
            axios.defaults.headers.common.Authorization = `Bearer ${r.data.session_token}`;
          }
          rememberEmailForDevice(r.data?.email || pendingApproval.email);
          rememberAccount(r.data);

          // Verify the new session is fully wired up BEFORE leaving the
          // login page — guards against any mobile race where the token is
          // accepted but a follow-up /api call returns 401.
          let okMe = false;
          try {
            await axios.get(`${API}/auth/me`, { withCredentials: true });
            okMe = true;
          } catch (_) { okMe = false; }

          setUser(r.data);
          toast.success(t('sess_approved'));
          setPendingApproval(null);

          if (okMe) {
            // Hard reload to /dashboard so AuthProvider re-bootstraps with
            // the fresh token in localStorage (avoids edge-cases on mobile
            // Safari where in-memory state isn't picked up by ProtectedRoute).
            window.location.replace('/dashboard');
          } else {
            // Token didn't validate — fall back to staying on /login with
            // a helpful error instead of bouncing to a 401-redirect loop.
            try { localStorage.removeItem('session_token'); } catch (_) {}
            delete axios.defaults.headers.common.Authorization;
            toast.error(t('sess_denied'));
          }
        } else if (status === 'denied' || status === 'expired') {
          navigated = true;
          toast.error(t('sess_denied'));
          setPendingApproval(null);
        } else if (status === 'pending') {
          // Update the waiting-banner details if the server included device
          // info (location, label) for the request. (Not yet returned by the
          // status endpoint — placeholder for future enrichment.)
        }
      } catch (_) { /* keep polling */ }
    };
    tick();
    const id = setInterval(tick, 2500);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingApproval?.request_id]);

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
          /* email non persisté (sécurité) */
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
        const pseudoTrimmed = name.trim();
        if (!pseudoTrimmed || pseudoTrimmed.length < 3) {
          toast.error('Le pseudo est requis (3 caractères minimum).');
          setSubmitting(false);
          return;
        }
        const { data } = await axios.post(`${API}/auth/register`, {
          email: email.trim(),
          password,
          name: pseudoTrimmed,
          pseudo: pseudoTrimmed,
          frontend_url: window.location.origin,
        });
        /* email non persisté (sécurité) */

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
        const cachedKeyId = (typeof localStorage !== 'undefined' ? localStorage.getItem('codeforge_device_key_id') : null) || null;
        const deviceLabel = detectDeviceLabel();
        let data;
        try {
          const res = await axios.post(`${API}/auth/login`, {
            email: email.trim(),
            password,
            device_key_id: cachedKeyId,
            device_label: deviceLabel,
          });
          data = res.data;
        } catch (err2) {
          // 202 → another device needs to approve this connection. Poll until decided.
          if (err2.response?.status === 202) {
            const detail = err2.response.data?.detail || {};
            const reqId = detail.request_id;
            if (reqId) {
              toast.info(t('sess_pending_title'));
              setPendingApproval({ request_id: reqId, email: email.trim() });
              return;
            }
          }
          throw err2;
        }
        if (data.session_token) {
          try { localStorage.setItem('session_token', data.session_token); } catch (_) {}
        }
        rememberEmailForDevice(data.email || email.trim());
        rememberAccount(data);
        setUser(data);
        toast.success(`Bienvenue, ${data.name || data.email} !`);
        navigate('/dashboard', { replace: true, state: { user: data } });
      }
    } catch (err) {
      const detail = formatDetail(err.response?.data?.detail) || err.message;
      const lower = String(detail).toLowerCase();
      // Map backend auth errors to inline red field error.
      // Backend returns generic "Email ou mot de passe incorrect" for sign-in failures.
      if (mode === 'login' && (
        lower.includes('mot de passe') || lower.includes('password') ||
        lower.includes('incorrect') || lower.includes('email ou mot')
      )) {
        setAuthError(t('login_password_wrong'));
      } else if (mode === 'login' && (lower.includes('aucun compte') || lower.includes('no account') || lower.includes('not found'))) {
        setAuthError(t('login_email_unknown'));
      } else {
        toast.error(detail);
      }
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
      toast.error("Renseigne ton email.");
      return;
    }
    if (!password || password.length < 6) {
      toast.error("Le nouveau mot de passe doit faire au moins 6 caractères.");
      return;
    }
    if (password !== confirmPassword) {
      toast.error("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/auth/forgot-password`, {
        email: target,
        password,
        frontend_url: window.location.origin,
      });
      setForgotSent(true);
      if (data.email_sent) {
        toast.success("Email de confirmation envoyé ! Vérifie ta boîte.");
      } else if (data.confirm_link) {
        toast.info("Mode démo — lien de confirmation ouvert.");
        window.open(data.confirm_link, '_blank', 'noopener,noreferrer');
      } else {
        toast.info(data.message || "Si le compte existe, un email a été envoyé.");
      }
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || err.message);
    } finally {
      setSubmitting(false);
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
      /* email non persisté (sécurité) */
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

            {pendingApproval && (
              <div
                data-testid="session-pending-banner"
                className="mb-3 p-4 bg-amber-400/10 border border-amber-400/40 rounded-sm space-y-3"
              >
                <div className="flex items-start gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-amber-300 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-['Chivo'] font-bold text-amber-200 mb-1">
                      {t('sess_pending_title')}
                    </div>
                    <p className="text-xs text-amber-100/80 leading-relaxed">
                      {t('sess_pending_body')}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPendingApproval(null)}
                    className="text-amber-200 hover:text-white flex-shrink-0"
                    data-testid="session-pending-cancel"
                    aria-label={t('dm_cancel')}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="bg-black/30 border border-amber-400/20 rounded-sm p-2.5 space-y-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-widest text-amber-100/60 w-24 flex-shrink-0">
                      {t('sess_device_label')}
                    </span>
                    <span className="text-amber-50 truncate">{detectDeviceLabel()}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-widest text-amber-100/60 w-24 flex-shrink-0">
                      Email
                    </span>
                    <span className="text-amber-50 truncate font-['IBM_Plex_Mono']">{pendingApproval.email}</span>
                  </div>
                </div>
                <p className="text-[11px] text-amber-100/60 italic leading-relaxed">
                  {t('sess_pending_hint')}
                </p>
              </div>
            )}

            {!waitingFor && (
              <motion.form variants={item} onSubmit={handleSubmit} autoComplete="off" data-form-type="other" className="space-y-3 text-left">
                {/* Honeypot fields to discourage browser autofill (hidden from users). */}
                <input type="text" name="username" tabIndex={-1} autoComplete="username" style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0 }} aria-hidden="true" />
                <input type="password" name="password" tabIndex={-1} autoComplete="current-password" style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0 }} aria-hidden="true" />
                {mode === 'signup' && (
                  <div>
                    <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">
                      {t('signup_pseudo_label')} <span className="text-red-400">*</span>
                    </label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        data-testid="signup-name-input"
                        required
                        minLength={3}
                        maxLength={30}
                        placeholder={t('signup_pseudo_placeholder')}
                        className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                      />
                    </div>
                    <p className="text-[10px] text-[#71717A] mt-1">{t('signup_pseudo_hint')}</p>
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
                      onChange={(e) => { setEmail(e.target.value); if (authError) setAuthError(''); }}
                      required
                      autoComplete="off"
                      autoCorrect="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      name={`email_${Math.random().toString(36).slice(2, 8)}`}
                      data-form-type="other"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-bwignore="true"
                      data-testid="auth-email-input"
                      placeholder="toi@gmail.com"
                      readOnly
                      onFocus={(e) => { e.target.removeAttribute('readonly'); }}
                      className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-1">{t('loginPassword')}</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                    <input
                      type="text"
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); if (authError) setAuthError(''); }}
                      required
                      minLength={6}
                      autoComplete="off"
                      autoCorrect="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      name={`x_pwd_${Math.random().toString(36).slice(2, 8)}`}
                      data-form-type="other"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-bwignore="true"
                      data-testid="auth-password-input"
                      placeholder="••••••••"
                      readOnly
                      onFocus={(e) => { e.target.removeAttribute('readonly'); }}
                      style={{
                        WebkitTextSecurity: 'disc',
                        MozTextSecurity: 'disc',
                        textSecurity: 'disc',
                        fontFamily: 'text-security-disc, "Chivo", monospace',
                      }}
                      className={`w-full bg-white/[0.04] border rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:outline-none transition-colors ${
                        authError ? 'border-red-500 focus:border-red-500' : 'border-white/10 focus:border-[#E4FF00]'
                      }`}
                    />
                  </div>
                  {authError && (
                    <p data-testid="auth-error" role="alert" className="text-xs text-red-400 mt-1.5 font-['IBM_Plex_Sans']">
                      {authError}
                    </p>
                  )}
                  {mode === 'signup' && (
                    <p className="text-[10px] text-[#A1A1AA]/70 mt-1">{t('loginEmailMinChars')}</p>
                  )}
                </div>

                {mode !== 'forgot' && (
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
                )}

                {mode === 'forgot' && (
                  <div data-testid="forgot-confirm-pwd-block">
                    <label className="text-xs font-['Chivo'] font-bold text-[#A1A1AA] mb-1.5 block">
                      Confirme le nouveau mot de passe
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                      <input
                        type="text"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                        minLength={6}
                        autoComplete="off"
                        data-lpignore="true"
                        data-1p-ignore="true"
                        data-bwignore="true"
                        data-testid="auth-confirm-password-input"
                        placeholder="••••••••"
                        readOnly
                        onFocus={(e) => { e.target.removeAttribute('readonly'); }}
                        style={{ WebkitTextSecurity: 'disc', MozTextSecurity: 'disc', textSecurity: 'disc' }}
                        className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none transition-colors"
                      />
                    </div>
                    {password && confirmPassword && password !== confirmPassword && (
                      <p className="text-xs text-red-400 mt-1.5">Les mots de passe ne correspondent pas.</p>
                    )}
                  </div>
                )}

                {mode === 'forgot' && (
                  <button
                    type="button"
                    onClick={handleForgotPassword}
                    disabled={submitting || forgotSent}
                    data-testid="forgot-submit-btn"
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(228,255,0,0.4)] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                    {forgotSent ? '✅ Email envoyé — vérifie ta boîte' : 'Envoyer le lien de confirmation'}
                  </button>
                )}

                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => { setMode('forgot'); setForgotSent(false); setConfirmPassword(''); setAuthError(''); }}
                    data-testid="forgot-password-btn"
                    className="w-full text-center text-xs text-[#A1A1AA] hover:text-[#E4FF00] font-['IBM_Plex_Sans'] underline transition-colors mt-1"
                  >
                    {t('loginForgot')}
                  </button>
                )}

                {mode === 'forgot' && (
                  <button
                    type="button"
                    onClick={() => { setMode('login'); setForgotSent(false); setConfirmPassword(''); }}
                    data-testid="forgot-back-btn"
                    className="w-full text-center text-xs text-[#A1A1AA] hover:text-[#E4FF00] font-['IBM_Plex_Sans'] underline transition-colors mt-1"
                  >
                    ← Retour à la connexion
                  </button>
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
              <motion.div variants={item} className="text-center text-[10px] text-[#A1A1AA]/50 mt-2">
                {/* SMS demo and magic-link removed at user request — single
                    sign-in path: email + password. */}
              </motion.div>
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
            <span>·</span>
            <CreatorToolbar />
          </div>
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setTheftOpen(true)}
              data-testid="declare-theft-link"
              className="inline-flex items-center gap-1.5 text-[11px] text-red-300/80 hover:text-red-300 font-['IBM_Plex_Sans'] transition-colors"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              {t('theft_link')}
            </button>
          </div>
        </motion.div>
      </motion.div>
      <TheftRecoveryDialog open={theftOpen} onClose={() => setTheftOpen(false)} />
    </div>
  );
}
