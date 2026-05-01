import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Code, Smartphone, Monitor, Globe, Zap, Lock, Infinity } from 'lucide-react';
import LanguageToggle from '../components/LanguageToggle';
import { useLanguage } from '../contexts/LanguageContext';

export default function Landing() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const goLogin = () => navigate('/login');
  const goDiscover = () => navigate('/discover');

  // Highlight the keyword inside the H1 line if present, else show plain text.
  // Works for languages where the keyword exists; falls back gracefully otherwise.
  const renderH1Line1 = () => {
    const line = t('l_h1Line1');
    const word = t('l_h1Highlight');
    const idx = word ? line.indexOf(word) : -1;
    if (idx === -1) return <span className="text-white">{line}</span>;
    return (
      <>
        <span className="text-white">{line.slice(0, idx)}</span>
        <span className="text-[#E4FF00] cyber-glow">{word}</span>
        <span className="text-white">{line.slice(idx + word.length)}</span>
      </>
    );
  };

  const features = [
    { icon: <Code className="w-12 h-12" />,       k: 'feat1', color: '#E4FF00' },
    { icon: <Smartphone className="w-12 h-12" />, k: 'feat2', color: '#00FF66' },
    { icon: <Monitor className="w-12 h-12" />,    k: 'feat3', color: '#E4FF00' },
    { icon: <Globe className="w-12 h-12" />,      k: 'feat4', color: '#00FF66' },
    { icon: <Zap className="w-12 h-12" />,        k: 'feat5', color: '#E4FF00' },
    { icon: <Lock className="w-12 h-12" />,       k: 'feat6', color: '#00FF66' },
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-white overflow-x-hidden">
      {/* Noise texture */}
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      {/* Grid background */}
      <div className="fixed inset-0 grid-bg opacity-30 pointer-events-none"></div>

      {/* Navigation: [Language toggle] · [CodeForge AI logo] · [Discover button] */}
      <motion.nav
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="relative z-30 border-b border-white/10 backdrop-blur-md"
      >
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4 grid grid-cols-3 items-center gap-2">
          <div className="justify-self-start">
            <button
              onClick={goDiscover}
              data-testid="nav-discover-btn"
              className="px-3 sm:px-5 py-1.5 sm:py-2 bg-[#E4FF00] text-[#050505] text-xs sm:text-sm font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(228,255,0,0.4)] transition-all duration-200 whitespace-nowrap"
            >
              {t('l_navDiscover')}
            </button>
          </div>

          <div className="justify-self-center flex items-center gap-1.5 sm:gap-2 min-w-0">
            <Sparkles className="w-5 h-5 sm:w-7 sm:h-7 text-[#E4FF00] flex-shrink-0" />
            <span className="text-base sm:text-2xl font-['Chivo'] font-black tracking-tight truncate">CodeForge AI</span>
          </div>

          <div className="justify-self-end min-w-0">
            <LanguageToggle placement="bottom" />
          </div>
        </div>
      </motion.nav>

      {/* Hero */}
      <section className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 pt-10 sm:pt-20 pb-16 sm:pb-32">
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="text-center space-y-6 sm:space-y-8"
        >
          <h1 className="font-['Chivo'] font-black text-3xl sm:text-5xl md:text-6xl lg:text-7xl xl:text-8xl tracking-tighter leading-[1.05] break-words">
            {renderH1Line1()}
            <br />
            <span className="text-white">{t('l_h1Line2')}</span>
          </h1>

          <p className="text-base sm:text-lg lg:text-xl text-[#A1A1AA] max-w-3xl mx-auto font-['IBM_Plex_Sans'] leading-relaxed px-2">
            {t('l_subtitle')}
          </p>

          {/* Hero CTAs — Connexion (left, outline) · Inscription (right, outline) */}
          <div className="flex flex-wrap gap-3 sm:gap-4 justify-center items-center pt-2 sm:pt-4">
            <button
              onClick={goLogin}
              data-testid="hero-login-btn"
              className="px-6 sm:px-8 py-3 sm:py-4 border border-white/20 text-white text-base sm:text-lg font-['Chivo'] font-bold rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-all duration-200"
            >
              {t('l_loginBtn')}
            </button>
            <button
              onClick={goLogin}
              data-testid="hero-cta-btn"
              className="px-6 sm:px-8 py-3 sm:py-4 border border-white/20 text-white text-base sm:text-lg font-['Chivo'] font-bold rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-all duration-200"
            >
              {t('l_signupBtn')}
            </button>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap gap-6 sm:gap-12 justify-center pt-8 sm:pt-12 text-xs sm:text-sm font-['IBM_Plex_Mono']">
            <div>
              <div className="text-2xl sm:text-3xl font-bold text-[#E4FF00]"><Infinity className="inline w-6 h-6 sm:w-8 sm:h-8" /></div>
              <div className="text-[#A1A1AA] mt-1">{t('l_statUnlimited')}</div>
            </div>
            <div>
              <div className="text-2xl sm:text-3xl font-bold text-[#00FF66]">GPT-5.2</div>
              <div className="text-[#A1A1AA] mt-1">{t('l_statAI')}</div>
            </div>
            <div>
              <div className="text-2xl sm:text-3xl font-bold text-white">3</div>
              <div className="text-[#A1A1AA] mt-1">{t('l_statFormats')}</div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Features Bento Grid */}
      <section id="features" className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <motion.h2
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-3xl sm:text-4xl lg:text-5xl font-['Chivo'] font-black text-center mb-10 sm:mb-16 tracking-tight"
        >
          {(() => {
            const title = t('l_featTitle');
            const high = t('l_featTitleHighlight');
            const idx = high ? title.indexOf(high) : -1;
            if (idx === -1) return <span>{title}</span>;
            return (
              <>
                <span>{title.slice(0, idx)}</span>
                <span className="text-[#E4FF00]">{high}</span>
                <span>{title.slice(idx + high.length)}</span>
              </>
            );
          })()}
        </motion.h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-8">
          {features.map((feature, idx) => (
            <motion.div
              key={feature.k}
              initial={{ y: 20, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              className="relative p-5 sm:p-8 bg-[#0F0F13] border border-white/10 rounded-sm hover:border-white/30 transition-all duration-300 group"
            >
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-sm"
                   style={{ boxShadow: `0 0 30px ${feature.color}20` }}></div>

              <div className="relative z-10">
                <div className="mb-3 sm:mb-4" style={{ color: feature.color }}>
                  {feature.icon}
                </div>
                <h3 className="text-lg sm:text-xl font-['Chivo'] font-bold mb-2">{t(`l_${feature.k}T`)}</h3>
                <p className="text-sm sm:text-base text-[#A1A1AA] font-['IBM_Plex_Sans'] leading-relaxed">{t(`l_${feature.k}D`)}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 py-16 sm:py-32">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="relative p-6 sm:p-12 bg-[#0F0F13] border-2 border-[#E4FF00]/30 rounded-sm text-center"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-[#E4FF00]/10 to-transparent rounded-sm"></div>

          <div className="relative z-10 space-y-4 sm:space-y-6">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-['Chivo'] font-black tracking-tight">
              {t('l_ctaTitle')}
            </h2>
            <p className="text-base sm:text-lg text-[#A1A1AA] font-['IBM_Plex_Sans']">
              {t('l_ctaSub')}
            </p>
            <button
              onClick={goLogin}
              data-testid="footer-cta-btn"
              className="px-6 sm:px-10 py-3 sm:py-5 bg-[#E4FF00] text-[#050505] text-base sm:text-xl font-['Chivo'] font-black rounded-sm hover:-translate-y-1 hover:shadow-[0_8px_24px_rgba(228,255,0,0.6)] transition-all duration-200"
            >
              {t('l_ctaBtn')}
            </button>
          </div>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 backdrop-blur-md mt-10 sm:mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 text-center text-[#A1A1AA] font-['IBM_Plex_Sans'] text-xs sm:text-sm space-y-3">
          <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-5">
            <button
              type="button"
              onClick={() => navigate('/how-it-works')}
              data-testid="footer-how-it-works"
              className="hover:text-[#E4FF00] transition-colors underline-offset-2 hover:underline"
            >
              {t('loginHowItWorks')}
            </button>
            <span className="text-white/20">·</span>
            <button
              type="button"
              onClick={() => navigate('/legal')}
              data-testid="footer-legal"
              className="hover:text-[#E4FF00] transition-colors underline-offset-2 hover:underline"
            >
              {t('loginLegal')}
            </button>
          </div>
          <p>{t('l_footer')}</p>
        </div>
      </footer>
    </div>
  );
}
