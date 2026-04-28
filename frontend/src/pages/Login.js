import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Chrome, Phone, Loader2, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

const ERROR_MESSAGES = {
  access_denied: "Connexion refusée. Réessaie quand tu veux.",
  invalid_request: "Requête invalide. Reviens à la page d'accueil et réessaie.",
  server_error: "Erreur serveur. Réessaie dans quelques instants.",
  default: "Une erreur est survenue. Réessaie.",
};

export default function Login() {
  const navigate = useNavigate();
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const toastedRef = useRef(false);

  // Toast on ?error=... query param (instead of silent redirect).
  // Fires once per mount. Reads window.location.search directly so this
  // does not depend on react-router's hook timing.
  // The <Toaster /> in App.js mounts as a sibling and only subscribes to
  // Sonner's toast store *after* its useEffect runs. Toasts dispatched
  // before subscription are lost. We defer dispatch with a setTimeout.
  // We deliberately DO NOT clear the timer in cleanup — in React 18
  // StrictMode the dev double-invocation would kill the timer permanently
  // (effect setup → cleanup → setup, state+refs preserved → guard hits → no retry).
  useEffect(() => {
    if (toastedRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const err = params.get('error');
    if (!err) return;
    toastedRef.current = true;
    const msg = ERROR_MESSAGES[err] || ERROR_MESSAGES.default;
    setTimeout(() => {
      toast.error(msg, { duration: 6000 });
    }, 600);
  }, []);

  const handleGoogleLogin = () => {
    setIsGoogleLoading(true);
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  // Stagger config for child elements
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.08, delayChildren: 0.1 },
    },
  };
  const item = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center relative overflow-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 noise-bg"></div>
      <div className="fixed inset-0 grid-bg opacity-20"></div>

      {/* Login card */}
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
          className="bg-white/[0.03] border border-white/10 rounded-sm p-12 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.4)]"
        >
          <div className="text-center space-y-6">
            <motion.div
              variants={item}
              initial={{ y: -10 }}
              animate={{ y: 0 }}
              transition={{ repeat: Infinity, duration: 2, repeatType: 'reverse' }}
              className="inline-block"
            >
              <div className="w-20 h-20 bg-[#E4FF00] rounded-sm flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(228,255,0,0.35)]">
                <span className="text-4xl font-['Chivo'] font-black text-[#050505]">CF</span>
              </div>
            </motion.div>

            <motion.div variants={item}>
              <h1 className="text-3xl font-['Chivo'] font-black text-white mb-2">CodeForge AI</h1>
              <p className="text-[#A1A1AA] font-['IBM_Plex_Sans']">Connectez-vous pour commencer</p>
            </motion.div>

            {/* Heads-up: Emergent Auth platform issue (issue raised with support).
                Surfacing it transparently so the user picks SMS without confusion. */}
            <motion.div
              variants={item}
              data-testid="google-auth-notice"
              className="flex items-start gap-3 p-3 bg-orange-400/10 border border-orange-400/30 rounded-sm text-left"
            >
              <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
              <div className="text-xs font-['IBM_Plex_Sans'] text-orange-200/90 leading-relaxed">
                <span className="font-bold text-orange-300">Connexion Google temporairement indisponible</span> côté plateforme Emergent. Utilise la connexion SMS ci-dessous (instantanée, fonctionne hors-ligne).
              </div>
            </motion.div>

            <motion.button
              variants={item}
              onClick={() => navigate('/sms-login')}
              data-testid="sms-login-btn"
              className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-cyan-400 text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(34,211,238,0.3)] transition-all duration-200"
            >
              <Phone className="w-5 h-5" />
              Connexion SMS (recommandée)
            </motion.button>

            <motion.div variants={item} className="relative py-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/10"></div>
              </div>
              <div className="relative flex justify-center">
                <span className="bg-[#0F0F13] px-4 text-sm text-[#A1A1AA]">ou (en attendant le fix)</span>
              </div>
            </motion.div>

            <motion.button
              variants={item}
              onClick={handleGoogleLogin}
              disabled={isGoogleLoading}
              data-testid="google-login-btn"
              className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white/80 text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(255,255,255,0.25)] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isGoogleLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" data-testid="google-login-spinner" />
                  Redirection vers Google...
                </>
              ) : (
                <>
                  <Chrome className="w-5 h-5" />
                  Continuer avec Google
                </>
              )}
            </motion.button>

            <motion.div variants={item} className="pt-4">
              <p className="text-xs text-[#A1A1AA] font-['IBM_Plex_Sans']">
                💡 La connexion SMS permet d'utiliser l'app même sans internet
              </p>
            </motion.div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-center mt-6"
        >
          <button
            onClick={() => navigate('/')}
            data-testid="back-to-home-btn"
            className="text-[#E4FF00] hover:text-[#00FF66] font-['IBM_Plex_Sans'] transition-colors"
          >
            ← Retour à l'accueil
          </button>
        </motion.div>
      </motion.div>
    </div>
  );
}
