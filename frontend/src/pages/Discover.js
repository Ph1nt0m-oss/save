import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, Code, Smartphone, Monitor, Wand2,
  ArrowRight, ArrowLeft, Lock, X, MessageCircle, Settings, Lightbulb
} from 'lucide-react';
import { toast } from 'sonner';

// Each step describes one element of the dashboard the user will discover.
const STEPS = [
  {
    title: 'Bienvenue dans CodeForge AI',
    body: "Voici un aperçu rapide de ton futur tableau de bord. Tout est désactivé pendant la visite — clique sur \"Suivant\" pour explorer chaque fonctionnalité.",
    highlight: null,
  },
  {
    title: '1️⃣ Assistant Guidé (Wizard)',
    body: "Décris ton idée en langage naturel, on te pose 3-4 questions ciblées, et l'IA génère une app complète. Idéal pour démarrer sans coder.",
    highlight: 'wizard',
  },
  {
    title: '2️⃣ Création libre',
    body: 'Tu sais déjà ce que tu veux ? Va droit au but : un prompt, une app. Web, mobile (PWA) ou desktop (.exe), au choix.',
    highlight: 'create',
  },
  {
    title: '3️⃣ Chat AI',
    body: "Discute avec l'IA pour raffiner ton app — \"ajoute un dark mode\", \"change la couleur principale\" — elle modifie le code en direct.",
    highlight: 'chat',
  },
  {
    title: '4️⃣ Mode Hors-Ligne',
    body: "Pas de connexion ? Pas grave. Avec Ollama installé sur ton PC, tu génères des apps sans envoyer aucune donnée à Internet.",
    highlight: 'offline',
  },
  {
    title: '🎁 Et c\'est gratuit, vraiment',
    body: "Aucun crédit, aucun quota mensuel, aucun upsell caché. La clé IA est incluse, le code est à toi, et tu peux supprimer ton compte d'un clic.",
    highlight: null,
  },
  {
    title: 'Prêt·e à essayer ?',
    body: "Crée ton compte en 30 secondes — il te suffit d'un email et d'un mot de passe. Pas de CB, pas de pub.",
    highlight: 'cta',
    final: true,
  },
];

// Mock cards mirroring the real Dashboard layout. They look identical to
// the real ones but have pointer-events:none and a Lock overlay that hints
// the user must sign in.
function MockCard({ icon, title, desc, color, accent, highlighted }) {
  return (
    <div
      className={`relative bg-white/[0.03] border rounded-sm p-6 transition-all overflow-hidden ${
        highlighted
          ? 'border-[#E4FF00] shadow-[0_0_40px_rgba(228,255,0,0.35)] scale-[1.02]'
          : 'border-white/10 opacity-60'
      }`}
      style={{ minHeight: 200 }}
    >
      <div className="flex items-center gap-3 mb-3" style={{ color }}>{icon}<h3 className="text-lg font-['Chivo'] font-black text-white">{title}</h3></div>
      <p className="text-sm text-[#A1A1AA] font-['IBM_Plex_Sans']">{desc}</p>
      <div className="absolute top-3 right-3 flex items-center gap-1 text-[10px] text-[#A1A1AA]/70">
        <Lock className="w-3 h-3" /> verrouillé
      </div>
      <div className="absolute bottom-4 left-6 right-6 h-px bg-white/10"></div>
      <p className="absolute bottom-3 left-6 text-[11px] font-bold" style={{ color: accent }}>{highlighted ? '← On parle de cette carte' : 'connexion requise'}</p>
    </div>
  );
}

export default function Discover() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const wrapperRef = useRef(null);

  const current = STEPS[step];

  useEffect(() => {
    // Block all click events inside the mock dashboard
    const node = wrapperRef.current;
    if (!node) return;
    const blocker = (e) => {
      if (!e.target.closest('[data-discover-allow]')) {
        e.preventDefault();
        e.stopPropagation();
        toast.info('🔒 Connecte-toi pour utiliser cette fonctionnalité.', { duration: 2000 });
      }
    };
    node.addEventListener('click', blocker, true);
    return () => node.removeEventListener('click', blocker, true);
  }, []);

  const next = () => {
    if (step < STEPS.length - 1) setStep(step + 1);
    else navigate('/dashboard');
  };
  const prev = () => setStep(Math.max(0, step - 1));

  return (
    <div ref={wrapperRef} className="min-h-screen bg-[#050505] relative overflow-hidden">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="fixed inset-0 grid-bg opacity-10 pointer-events-none"></div>

      {/* Top bar */}
      <header className="relative z-20 flex items-center justify-between px-6 py-4 border-b border-white/10 bg-black/60 backdrop-blur-md" data-discover-allow>
        <button
          onClick={() => navigate('/')}
          data-testid="discover-exit-btn"
          className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Quitter la visite
        </button>
        <div className="flex items-center gap-2 text-xs text-[#A1A1AA]">
          <Lightbulb className="w-4 h-4 text-[#E4FF00]" />
          <span data-testid="discover-step-counter">Étape {step + 1} / {STEPS.length}</span>
        </div>
        <button
          onClick={() => navigate('/login')}
          data-testid="discover-login-btn"
          className="px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
        >
          Se connecter
        </button>
      </header>

      {/* Mock Dashboard preview */}
      <main className="relative z-10 max-w-6xl mx-auto px-4 py-10">
        <div className="text-center mb-8 select-none">
          <h1 className="text-3xl sm:text-4xl font-['Chivo'] font-black text-white">Tableau de bord</h1>
          <p className="text-sm text-[#A1A1AA] mt-1">(aperçu — connecte-toi pour utiliser)</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <MockCard
            icon={<Wand2 className="w-7 h-7" />}
            title="Assistant Guidé"
            desc="L'IA te guide pas à pas pour créer ton app sans aucune connaissance technique."
            color="#E4FF00" accent="#E4FF00"
            highlighted={current.highlight === 'wizard'}
          />
          <MockCard
            icon={<Code className="w-7 h-7" />}
            title="Création libre"
            desc="Décris ton idée en une phrase, génère une app complète web/mobile/desktop."
            color="#00D4FF" accent="#00D4FF"
            highlighted={current.highlight === 'create'}
          />
          <MockCard
            icon={<MessageCircle className="w-7 h-7" />}
            title="Chat AI"
            desc="Modifie ton app en discutant : changement de couleurs, ajout de features, debug."
            color="#00FF66" accent="#00FF66"
            highlighted={current.highlight === 'chat'}
          />
          <MockCard
            icon={<Smartphone className="w-7 h-7" />}
            title="Mode Hors-Ligne"
            desc="Génère sans internet via Ollama (installé sur ton PC). 100% privé, illimité."
            color="#A78BFA" accent="#A78BFA"
            highlighted={current.highlight === 'offline'}
          />
        </div>

        <div className="mt-12 text-center text-xs text-[#A1A1AA]/60 select-none">
          <p>3 formats d'export — Web, PWA mobile, .exe Windows. Push GitHub d'un clic.</p>
        </div>
      </main>

      {/* Floating tutorial card */}
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -10, opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-30 w-[92%] max-w-md bg-[#0A0A0A] border border-[#E4FF00]/30 rounded-sm p-5 backdrop-blur-2xl shadow-[0_8px_30px_rgba(228,255,0,0.15)]"
          data-discover-allow
          data-testid="discover-tutorial-card"
        >
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-[#E4FF00] flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h2 className="text-base font-['Chivo'] font-bold text-white" data-testid="discover-step-title">{current.title}</h2>
              <p className="mt-1.5 text-sm text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed">{current.body}</p>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between gap-2">
            <button
              type="button" onClick={prev} disabled={step === 0}
              data-testid="discover-prev-btn"
              className="text-xs text-[#A1A1AA] hover:text-white transition-colors disabled:opacity-30"
            >
              ← Précédent
            </button>

            <div className="flex items-center gap-1.5">
              {STEPS.map((_, i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === step ? 'w-6 bg-[#E4FF00]' : 'w-1.5 bg-white/15'
                  }`}
                />
              ))}
            </div>

            <button
              type="button" onClick={next}
              data-testid="discover-next-btn"
              className="inline-flex items-center gap-1 px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
            >
              {step === STEPS.length - 1 ? 'Terminer' : 'Suivant'}
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {current.final && (
            <button
              type="button"
              onClick={() => navigate('/login')}
              data-testid="discover-final-cta"
              className="w-full mt-3 px-5 py-3 bg-white/[0.06] border border-[#E4FF00]/40 text-[#E4FF00] text-sm font-['Chivo'] font-bold rounded-sm hover:bg-[#E4FF00]/10 transition-all"
            >
              Créer mon compte gratuit
            </button>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
