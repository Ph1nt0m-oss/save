import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Code, Smartphone, Monitor, Globe, Zap, Lock, Infinity } from 'lucide-react';

export default function Landing() {
  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white overflow-hidden">
      {/* Noise texture */}
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      
      {/* Grid background */}
      <div className="fixed inset-0 grid-bg opacity-30 pointer-events-none"></div>

      {/* Navigation */}
      <motion.nav 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="relative z-10 border-b border-white/10 backdrop-blur-md"
      >
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-8 h-8 text-[#E4FF00]" />
            <span className="text-2xl font-['Chivo'] font-black tracking-tight">CodeForge AI</span>
          </div>
          <button
            onClick={handleLogin}
            data-testid="nav-login-btn"
            className="px-6 py-2 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(228,255,0,0.4)] transition-all duration-200"
          >
            Connexion
          </button>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-32">
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="text-center space-y-8"
        >
          <h1 className="font-['Chivo'] font-black text-5xl sm:text-6xl lg:text-8xl tracking-tighter leading-none">
            Créez des <span className="text-[#E4FF00] cyber-glow">Applications</span>
            <br />
            Sans Écrire de Code
          </h1>
          
          <p className="text-lg sm:text-xl text-[#A1A1AA] max-w-3xl mx-auto font-['IBM_Plex_Sans'] leading-relaxed">
            Décrivez votre projet en français, notre IA génère instantanément le code complet.
            Applications web, mobile, et desktop. Sans limites. 100% gratuit.
          </p>

          <div className="flex flex-wrap gap-4 justify-center items-center pt-4">
            <button
              onClick={handleLogin}
              data-testid="hero-cta-btn"
              className="px-8 py-4 bg-[#E4FF00] text-[#050505] text-lg font-['Chivo'] font-black rounded-sm hover:-translate-y-1 hover:shadow-[0_6px_20px_rgba(228,255,0,0.5)] transition-all duration-200"
            >
              Commencer Gratuitement
            </button>
            <Link
              to="#features"
              className="px-8 py-4 border border-white/20 text-white text-lg font-['Chivo'] font-bold rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-all duration-200"
            >
              Découvrir
            </Link>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap gap-12 justify-center pt-12 text-sm font-['IBM_Plex_Mono']">
            <div>
              <div className="text-3xl font-bold text-[#E4FF00]"><Infinity className="inline w-8 h-8" /></div>
              <div className="text-[#A1A1AA] mt-1">Génération Illimitée</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-[#00FF66]">GPT-5.2</div>
              <div className="text-[#A1A1AA] mt-1">IA de Pointe</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-white">3 Formats</div>
              <div className="text-[#A1A1AA] mt-1">Web, Mobile, Desktop</div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Features Bento Grid */}
      <section id="features" className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        <motion.h2
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-4xl sm:text-5xl font-['Chivo'] font-black text-center mb-16 tracking-tight"
        >
          Une Plateforme <span className="text-[#E4FF00]">Révolutionnaire</span>
        </motion.h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {[
            {
              icon: <Code className="w-12 h-12" />,
              title: "Génération Intelligente",
              desc: "GPT-5.2 analyse votre description et génère du code professionnel instantanément.",
              color: "#E4FF00"
            },
            {
              icon: <Smartphone className="w-12 h-12" />,
              title: "Apps Mobile (.apk)",
              desc: "Exportez directement vers Android. Installation en un clic sur votre téléphone.",
              color: "#00FF66"
            },
            {
              icon: <Monitor className="w-12 h-12" />,
              title: "Logiciels Desktop (.exe)",
              desc: "Créez des applications Windows professionnelles prêtes à distribuer.",
              color: "#E4FF00"
            },
            {
              icon: <Globe className="w-12 h-12" />,
              title: "Sites Web",
              desc: "Déployez instantanément sur le web avec un hébergement intégré.",
              color: "#00FF66"
            },
            {
              icon: <Zap className="w-12 h-12" />,
              title: "Mode Hors Ligne",
              desc: "Continuez à créer même sans connexion. Basculement automatique.",
              color: "#E4FF00"
            },
            {
              icon: <Lock className="w-12 h-12" />,
              title: "Sans Restrictions",
              desc: "Aucune limite d'utilisation. Aucun crédit. Créativité totale.",
              color: "#00FF66"
            }
          ].map((feature, idx) => (
            <motion.div
              key={idx}
              initial={{ y: 20, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              className="relative p-8 bg-[#0F0F13] border border-white/10 rounded-sm hover:border-white/30 transition-all duration-300 group"
            >
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-sm"
                   style={{ boxShadow: `0 0 30px ${feature.color}20` }}></div>
              
              <div className="relative z-10">
                <div className="mb-4" style={{ color: feature.color }}>
                  {feature.icon}
                </div>
                <h3 className="text-xl font-['Chivo'] font-bold mb-2">{feature.title}</h3>
                <p className="text-[#A1A1AA] font-['IBM_Plex_Sans'] leading-relaxed">{feature.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 py-32">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="relative p-12 bg-[#0F0F13] border-2 border-[#E4FF00]/30 rounded-sm text-center"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-[#E4FF00]/10 to-transparent rounded-sm"></div>
          
          <div className="relative z-10 space-y-6">
            <h2 className="text-4xl sm:text-5xl font-['Chivo'] font-black tracking-tight">
              Prêt à Créer Sans Limites ?
            </h2>
            <p className="text-lg text-[#A1A1AA] font-['IBM_Plex_Sans']">
              Rejoignez la révolution du développement assisté par IA.
            </p>
            <button
              onClick={handleLogin}
              data-testid="footer-cta-btn"
              className="px-10 py-5 bg-[#E4FF00] text-[#050505] text-xl font-['Chivo'] font-black rounded-sm hover:-translate-y-1 hover:shadow-[0_8px_24px_rgba(228,255,0,0.6)] transition-all duration-200"
            >
              Démarrer Maintenant
            </button>
          </div>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 backdrop-blur-md mt-20">
        <div className="max-w-7xl mx-auto px-6 py-8 text-center text-[#A1A1AA] font-['IBM_Plex_Sans'] text-sm">
          <p>© 2026 CodeForge AI. Propulsé par Emergent AI. Sans restrictions, sans limites.</p>
        </div>
      </footer>
    </div>
  );
}