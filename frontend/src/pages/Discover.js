import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, Code, Smartphone, Monitor, Wand2,
  ArrowRight, ArrowLeft, Lock, MessageCircle, Lightbulb,
  Send, Wifi, Globe as GlobeIcon, Download, Plus, Loader2
} from 'lucide-react';
import { toast } from 'sonner';

// 7 tutorial steps. Each step renders a different mock screen so visitors
// can see EXAMPLES of every page (Dashboard, Wizard, Create, Chat, generated
// app preview, Offline, final CTA). Everything is locked: only the tutorial
// arrows and the top-right "Connexion" button are clickable.
const TOTAL_STEPS = 7;

const STEP_META = [
  {
    title: 'Bienvenue dans CodeForge AI',
    body: "Voici ton futur tableau de bord. Avance avec les flèches pour découvrir chaque écran. Tu pourras tout utiliser après inscription.",
  },
  {
    title: '1️⃣ Assistant Guidé (Wizard)',
    body: "L'IA te pose 4 à 5 questions simples (type d'app, nom, couleurs, plateforme) et génère le projet complet. Idéal si tu n'as pas d'idée précise.",
  },
  {
    title: '2️⃣ Création libre',
    body: "Décris ton app en une phrase comme « un site de recettes avec note 5 étoiles ». L'IA génère le code complet en moins d'une minute.",
  },
  {
    title: '3️⃣ Chat avec l\'IA',
    body: "Une fois ton app générée, demande des modifications en langage naturel : « ajoute un dark mode », « change le bouton en vert ». L'IA met à jour le code.",
  },
  {
    title: '4️⃣ Aperçu instantané',
    body: "Vois ton app tourner immédiatement, comme si elle était déjà déployée. Web, mobile (PWA) ou desktop — au choix.",
  },
  {
    title: '5️⃣ Mode Hors-Ligne',
    body: "Pas de connexion ? Avec Ollama installé sur ton PC, tu génères des apps sans envoyer aucune donnée à Internet. 100% privé, 100% gratuit.",
  },
  {
    title: 'Prêt·e à essayer ?',
    body: "Crée ton compte en 30 secondes — il te suffit d'un email et d'un mot de passe. Pas de CB, pas de pub, pas de quotas.",
    final: true,
  },
];

// ─── Mock screens ────────────────────────────────────────────────────────────

function MockTopBar({ title, subtitle }) {
  return (
    <div className="bg-[#0F0F13] border-b border-white/10 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="font-['Chivo'] font-bold text-xl">{title}</h1>
        {subtitle && <p className="text-xs text-[#A1A1AA] mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2 text-[10px] text-[#A1A1AA]/70 px-2 py-1 border border-white/10 rounded-sm">
        <Lock className="w-3 h-3" /> aperçu
      </div>
    </div>
  );
}

function MockDashboardScreen() {
  const tiles = [
    { icon: Wand2, color: '#E4FF00', title: 'Assistant Guidé', desc: "L'IA te guide pas à pas pour créer ton app." },
    { icon: Code, color: '#00FF66', title: 'Création libre', desc: 'Décris ton idée, génère une app complète.' },
    { icon: MessageCircle, color: '#00D4FF', title: 'Chat AI', desc: 'Modifie ton app en discutant.' },
    { icon: Smartphone, color: '#A78BFA', title: 'Hors-Ligne', desc: 'Génère sans internet via Ollama.' },
  ];
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="CodeForge AI" subtitle="Création Sans Limites" />
      <div className="p-8">
        <h2 className="text-2xl font-['Chivo'] font-black text-white text-center mb-6">Que souhaites-tu faire ?</h2>
        <div className="grid grid-cols-2 gap-4 max-w-3xl mx-auto">
          {tiles.map((t, i) => (
            <div key={i} className="bg-white/[0.03] border rounded-lg p-5 flex items-start gap-3"
              style={{ borderColor: `${t.color}33` }}>
              <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ background: t.color }}>
                <t.icon className="w-5 h-5 text-[#050505]" />
              </div>
              <div>
                <p className="text-sm font-['Chivo'] font-bold text-white">{t.title}</p>
                <p className="text-xs text-[#A1A1AA] mt-0.5">{t.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MockWizardScreen() {
  const opts = ['🛒 E-Commerce', '📝 Blog/CMS', '💬 Messagerie', '🎮 Jeu', '📊 Dashboard', '🎨 Portfolio'];
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="Assistant Guidé" subtitle="Étape 1/5 — Type d'application" />
      <div className="p-8">
        <h2 className="text-xl font-['Chivo'] font-black text-white mb-2">Quel type d'application ?</h2>
        <p className="text-sm text-[#A1A1AA] mb-6">Choisis le modèle qui correspond le mieux.</p>
        <div className="grid grid-cols-3 gap-3 max-w-3xl">
          {opts.map((o, i) => (
            <div key={i} className={`p-4 border rounded-sm text-center text-sm font-['IBM_Plex_Sans'] ${
              i === 0 ? 'border-[#E4FF00] bg-[#E4FF00]/10 text-[#E4FF00]' : 'border-white/10 text-[#A1A1AA]'
            }`}>
              {o}
            </div>
          ))}
        </div>
        <div className="mt-6 flex items-center justify-end gap-2">
          <span className="text-xs text-[#A1A1AA]">Suivant →</span>
          <span className="px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm">Étape 2</span>
        </div>
      </div>
    </div>
  );
}

function MockCreateScreen() {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="Création libre" subtitle="Décris ton app, l'IA fait le reste" />
      <div className="p-8 grid grid-cols-2 gap-6">
        {/* Left: chat-style description */}
        <div>
          <p className="text-xs text-[#A1A1AA] mb-2">EXEMPLE DE PROMPT</p>
          <div className="bg-white/[0.04] border border-[#E4FF00]/30 rounded-sm p-4 text-sm text-white font-['IBM_Plex_Sans']">
            « Crée un site de recettes de cuisine avec une page d'accueil,
            une recherche par ingrédient, des notes 5 étoiles et un mode sombre. »
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs text-[#00FF66]">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Génération en cours…</span>
          </div>
        </div>
        {/* Right: simulated generated app preview */}
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm overflow-hidden">
          <div className="bg-[#1a1a1f] px-3 py-1.5 flex items-center gap-1 text-[10px] text-[#A1A1AA]">
            <span className="w-2 h-2 rounded-full bg-red-400" />
            <span className="w-2 h-2 rounded-full bg-yellow-400" />
            <span className="w-2 h-2 rounded-full bg-green-400" />
            <span className="ml-2 truncate">recettes-app.preview</span>
          </div>
          <div className="p-4">
            <p className="text-base font-['Chivo'] font-bold text-[#E4FF00]">🍳 Délices de Léa</p>
            <p className="text-[10px] text-[#A1A1AA]">Recettes faciles & savoureuses</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {['Tarte aux pommes', 'Curry de poulet', 'Pasta carbonara', 'Smoothie vert'].map((r, i) => (
                <div key={i} className="bg-white/[0.04] border border-white/10 rounded-sm p-2">
                  <p className="text-[11px] text-white truncate">{r}</p>
                  <p className="text-[9px] text-[#E4FF00]">★★★★★</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MockChatScreen() {
  const msgs = [
    { who: 'user', text: "Ajoute un bouton « partager » sur chaque recette." },
    { who: 'ai', text: "✅ Bouton ajouté avec un menu (Twitter, Email, copier le lien). Le code a été mis à jour." },
    { who: 'user', text: "Change la couleur principale en vert sapin." },
    { who: 'ai', text: "✅ Couleur principale mise à jour (#0F4C3A). Le mode sombre conserve un bon contraste (WCAG AA)." },
  ];
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="Chat IA" subtitle="Modifie ton app en langage naturel" />
      <div className="p-6 space-y-3 max-w-2xl mx-auto">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.who === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[75%] p-3 rounded-sm text-sm font-['IBM_Plex_Sans'] ${
              m.who === 'user'
                ? 'bg-[#E4FF00] text-[#050505]'
                : 'bg-white/[0.05] border border-white/10 text-white'
            }`}>
              {m.text}
            </div>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-2 border-t border-white/10 mt-4">
          <div className="flex-1 bg-white/[0.04] border border-white/10 rounded-sm px-3 py-2 text-xs text-[#A1A1AA]/60">
            Décris la modification…
          </div>
          <Send className="w-4 h-4 text-[#E4FF00]" />
        </div>
      </div>
    </div>
  );
}

function MockPreviewScreen() {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="Aperçu instantané" subtitle="Web · Mobile (PWA) · Desktop (.exe)" />
      <div className="p-6 grid grid-cols-3 gap-4">
        {/* Web */}
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
          <div className="aspect-video bg-gradient-to-br from-[#E4FF00]/20 to-[#00FF66]/10 rounded-sm flex items-center justify-center">
            <GlobeIcon className="w-10 h-10 text-[#E4FF00]" />
          </div>
          <p className="mt-2 text-xs font-['Chivo'] font-bold text-white">Web</p>
          <p className="text-[10px] text-[#A1A1AA]">Déploiement Vercel/Netlify</p>
        </div>
        {/* Mobile */}
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
          <div className="aspect-video bg-gradient-to-br from-[#00D4FF]/20 to-[#00FF66]/10 rounded-sm flex items-center justify-center">
            <Smartphone className="w-10 h-10 text-[#00D4FF]" />
          </div>
          <p className="mt-2 text-xs font-['Chivo'] font-bold text-white">PWA Mobile</p>
          <p className="text-[10px] text-[#A1A1AA]">Installable iOS/Android</p>
        </div>
        {/* Desktop */}
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
          <div className="aspect-video bg-gradient-to-br from-[#A78BFA]/20 to-[#E4FF00]/10 rounded-sm flex items-center justify-center">
            <Monitor className="w-10 h-10 text-[#A78BFA]" />
          </div>
          <p className="mt-2 text-xs font-['Chivo'] font-bold text-white">Desktop .exe</p>
          <p className="text-[10px] text-[#A1A1AA]">Windows / macOS / Linux</p>
        </div>
      </div>
      <div className="px-6 pb-6 flex items-center justify-center gap-3">
        <span className="px-3 py-1.5 text-[10px] font-bold bg-[#E4FF00]/10 text-[#E4FF00] border border-[#E4FF00]/30 rounded-sm inline-flex items-center gap-1">
          <Download className="w-3 h-3" /> Code source ZIP
        </span>
        <span className="px-3 py-1.5 text-[10px] font-bold bg-white/[0.04] text-white border border-white/10 rounded-sm">
          Push GitHub d'un clic
        </span>
      </div>
    </div>
  );
}

function MockOfflineScreen() {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="Mode Hors-Ligne" subtitle="100% local, 100% privé" />
      <div className="p-8 grid grid-cols-2 gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs bg-orange-400/20 text-orange-400">
            <Wifi className="w-3 h-3" /> Sans connexion
          </div>
          <h2 className="mt-3 text-xl font-['Chivo'] font-black text-white">Ollama en local</h2>
          <p className="mt-2 text-sm text-[#A1A1AA] leading-relaxed">
            Installe Ollama sur ton PC, télécharge un modèle (Deepseek-Coder, Llama),
            et CodeForge l'utilisera comme moteur d'IA. Aucune donnée ne quitte ta machine.
          </p>
          <div className="mt-4 bg-black/40 border border-white/10 rounded-sm p-3 font-['IBM_Plex_Mono'] text-xs text-[#00FF66]">
            $ ollama pull deepseek-coder:6.7b<br/>
            $ ollama serve
          </div>
        </div>
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-5 space-y-3">
          <p className="text-xs text-[#A1A1AA]">AVANTAGES</p>
          <ul className="text-sm text-white space-y-2">
            <li>✅ 100% gratuit, à vie</li>
            <li>✅ Aucune donnée envoyée</li>
            <li>✅ Fonctionne en avion</li>
            <li>✅ Aucun quota mensuel</li>
            <li>✅ Code source ZIP à toi</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function MockFinalScreen() {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title="🎁 Rejoins CodeForge AI" subtitle="Création illimitée, gratuite, sans pub" />
      <div className="p-12 text-center max-w-2xl mx-auto">
        <Sparkles className="w-12 h-12 text-[#E4FF00] mx-auto" />
        <h2 className="mt-4 text-3xl font-['Chivo'] font-black text-white">30 secondes pour commencer</h2>
        <p className="mt-3 text-sm text-[#A1A1AA]">
          Email + mot de passe. Pas de CB, pas de pub, pas de quotas. Code source 100% à toi.
        </p>
        <div className="mt-6 inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
          <Plus className="w-4 h-4 text-[#E4FF00]" />
          Clique sur « Connexion » en haut à droite pour t'inscrire.
        </div>
      </div>
    </div>
  );
}

const SCREENS = [
  MockDashboardScreen,
  MockWizardScreen,
  MockCreateScreen,
  MockChatScreen,
  MockPreviewScreen,
  MockOfflineScreen,
  MockFinalScreen,
];

// ─── Main component ──────────────────────────────────────────────────────────

export default function Discover() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const wrapperRef = useRef(null);

  const meta = STEP_META[step];
  const ScreenComponent = SCREENS[step];

  useEffect(() => {
    // Block any click that doesn't carry the explicit allow flag.
    const node = wrapperRef.current;
    if (!node) return;
    const blocker = (e) => {
      if (!e.target.closest('[data-discover-allow]')) {
        e.preventDefault();
        e.stopPropagation();
        toast.info('🔒 Connecte-toi pour utiliser cette fonctionnalité.', { duration: 1800 });
      }
    };
    node.addEventListener('click', blocker, true);
    return () => node.removeEventListener('click', blocker, true);
  }, []);

  // Keyboard arrows for navigation (great UX touch).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight') setStep(s => Math.min(TOTAL_STEPS - 1, s + 1));
      else if (e.key === 'ArrowLeft') setStep(s => Math.max(0, s - 1));
      else if (e.key === 'Escape') navigate('/');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const next = () => setStep(s => Math.min(TOTAL_STEPS - 1, s + 1));
  const prev = () => setStep(s => Math.max(0, s - 1));

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
          <span data-testid="discover-step-counter">Étape {step + 1} / {TOTAL_STEPS}</span>
        </div>
        <button
          onClick={() => navigate('/login')}
          data-testid="discover-login-btn"
          className="px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
        >
          Connexion
        </button>
      </header>

      {/* Mock screen for the current step */}
      <main className="relative z-10 max-w-6xl mx-auto px-4 py-8 pb-44">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.25 }}
            data-testid={`discover-screen-${step}`}
          >
            <ScreenComponent />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Floating tutorial card with arrows */}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-30 w-[94%] max-w-2xl" data-discover-allow>
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -10, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="bg-[#0A0A0A] border border-[#E4FF00]/30 rounded-sm p-5 backdrop-blur-2xl shadow-[0_8px_30px_rgba(228,255,0,0.15)]"
            data-testid="discover-tutorial-card"
          >
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-[#E4FF00] flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h2 className="text-base font-['Chivo'] font-bold text-white" data-testid="discover-step-title">{meta.title}</h2>
                <p className="mt-1.5 text-sm text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed">{meta.body}</p>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-2">
              <button
                type="button" onClick={prev} disabled={step === 0}
                data-testid="discover-prev-btn"
                aria-label="Étape précédente"
                className="inline-flex items-center gap-1 px-3 py-2 text-xs text-[#A1A1AA] border border-white/10 rounded-sm hover:text-white hover:border-white/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Précédent
              </button>

              <div className="flex items-center gap-1.5">
                {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
                  <span
                    key={i}
                    className={`h-1.5 rounded-full transition-all ${
                      i === step ? 'w-6 bg-[#E4FF00]' : 'w-1.5 bg-white/15'
                    }`}
                  />
                ))}
              </div>

              {step < TOTAL_STEPS - 1 ? (
                <button
                  type="button" onClick={next}
                  data-testid="discover-next-btn"
                  aria-label="Étape suivante"
                  className="inline-flex items-center gap-1 px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
                >
                  Suivant
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button
                  type="button" onClick={() => navigate('/login')}
                  data-testid="discover-final-cta"
                  className="inline-flex items-center gap-1 px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
                >
                  S'inscrire
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {meta.final && (
              <p className="mt-3 text-[10px] text-[#A1A1AA]/70 text-center">
                Astuce : utilise les flèches ← → du clavier pour naviguer.
              </p>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
