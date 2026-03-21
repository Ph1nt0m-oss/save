import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Chrome, Phone } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center relative overflow-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 noise-bg"></div>
      <div className="fixed inset-0 grid-bg opacity-20"></div>

      {/* Login card */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-12 backdrop-blur-md">
          <div className="text-center space-y-6">
            <motion.div
              initial={{ y: -10 }}
              animate={{ y: 0 }}
              transition={{ repeat: Infinity, duration: 2, repeatType: 'reverse' }}
              className="inline-block"
            >
              <div className="w-20 h-20 bg-[#E4FF00] rounded-sm flex items-center justify-center mx-auto">
                <span className="text-4xl font-['Chivo'] font-black text-[#050505]">CF</span>
              </div>
            </motion.div>

            <div>
              <h1 className="text-3xl font-['Chivo'] font-black text-white mb-2">CodeForge AI</h1>
              <p className="text-[#A1A1AA] font-['IBM_Plex_Sans']">Connectez-vous pour commencer</p>
            </div>

            <button
              onClick={handleGoogleLogin}
              data-testid="google-login-btn"
              className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-1 hover:shadow-[0_6px_20px_rgba(255,255,255,0.3)] transition-all duration-200"
            >
              <Chrome className="w-5 h-5" />
              Continuer avec Google
            </button>

            <div className="relative py-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/10"></div>
              </div>
              <div className="relative flex justify-center">
                <span className="bg-[#0F0F13] px-4 text-sm text-[#A1A1AA]">ou</span>
              </div>
            </div>

            <button
              onClick={() => navigate('/sms-login')}
              data-testid="sms-login-btn"
              className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-cyan-400 text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-1 hover:shadow-[0_6px_20px_rgba(0,255,255,0.3)] transition-all duration-200"
            >
              <Phone className="w-5 h-5" />
              Connexion SMS (Hors Ligne)
            </button>

            <div className="pt-4">
              <p className="text-xs text-[#A1A1AA] font-['IBM_Plex_Sans']">
                💡 La connexion SMS permet d'utiliser l'app même sans internet
              </p>
            </div>
          </div>
        </div>

        <div className="text-center mt-6">
          <button
            onClick={() => navigate('/')}
            className="text-[#E4FF00] hover:text-[#00FF66] font-['IBM_Plex_Sans'] transition-colors"
          >
            ← Retour à l'accueil
          </button>
        </div>
      </motion.div>
    </div>
  );
}