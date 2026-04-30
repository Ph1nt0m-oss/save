import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Cpu, Cloud, WifiOff, Zap, Infinity, Lock, FileCode, Smartphone } from 'lucide-react';

const sections = [
  {
    icon: Infinity,
    title: '100% gratuit, vraiment illimité',
    color: '#00FF66',
    points: [
      'Pas de crédits à acheter, pas de quota mensuel.',
      "L'IA s'exécute soit en local sur ton appareil (gratuit par essence), soit côté serveur via la clé Emergent (clé universelle déjà incluse — aucune action de ta part).",
      "Aucune limite arbitraire codée dans CodeForge AI : tu peux générer 1 ou 10 000 apps, peu importe.",
    ],
  },
  {
    icon: Cloud,
    title: 'Mode EN LIGNE — IA puissante (GPT-4o via Emergent)',
    color: '#00D4FF',
    points: [
      'Quand tu as une connexion internet, CodeForge utilise GPT-4o via la clé universelle Emergent intégrée.',
      "Avantages : qualité de génération maximale, code idiomatique, réponses rapides (2-10 sec).",
      'Coût pour toi : 0€. La clé est gérée par Emergent. Si le crédit Emergent baisse, le système bascule automatiquement vers Ollama hors-ligne.',
    ],
  },
  {
    icon: WifiOff,
    title: 'Mode HORS LIGNE — IA locale (Ollama + Deepseek)',
    color: '#E4FF00',
    points: [
      "Si tu n'as pas internet ou que tu veux 100% confidentialité, installe Ollama (gratuit, open-source) sur ton PC.",
      "Modèle recommandé : deepseek-coder:6.7b (4 Go RAM minimum). Tu peux aussi utiliser des modèles plus légers (phi, gemma) si ton PC est limité.",
      "L'IA tourne entièrement sur ta machine. Ton code, tes prompts, tes idées : rien ne sort de ton ordinateur. Vraiment 100% privé.",
      "Plus lent que l'online (10-60 sec selon le modèle et le CPU/GPU), mais aucune limite et aucune fuite de données.",
    ],
  },
  {
    icon: Zap,
    title: 'L\'Assistant Guidé (Wizard)',
    color: '#E4FF00',
    points: [
      'Tu décris ton idée en langage naturel : "Je veux une app de listes de courses avec partage entre amis"',
      'Le Wizard pose 3-4 questions guidées pour préciser : type d\'app (web/mobile/desktop), thème visuel, fonctionnalités principales.',
      "L'IA génère ensuite l'arborescence complète : code source, dépendances, instructions d'installation.",
      "Tu peux toujours raffiner via le Chat AI intégré : 'ajoute une fonction d'export PDF', 'change la couleur principale en bleu', etc.",
    ],
  },
  {
    icon: FileCode,
    title: 'Exports natifs Desktop (.exe) & Mobile (PWA)',
    color: '#00FF66',
    points: [
      'Desktop : un clic → fichier .exe Windows installable (via electron-builder + wine côté serveur).',
      "Mobile : un clic → PWA installable sur Android/iOS depuis le navigateur (manifest, service worker, offline cache).",
      'Pas de compte Google Play ou App Store nécessaire. Pas de frais de distribution. Tu télécharges, tu installes, ça marche.',
      "Code source toujours accessible : tu peux pousser sur GitHub d'un clic et reprendre la main quand tu veux.",
    ],
  },
  {
    icon: Lock,
    title: 'Confidentialité & Sécurité',
    color: '#00D4FF',
    points: [
      'Auth par email + mot de passe (bcrypt) ou lien magique. Pas de tracking publicitaire.',
      "Tes projets sont stockés en MongoDB chiffré côté serveur. Tu peux les exporter (RGPD) ou les supprimer définitivement à tout moment depuis ton profil.",
      "Toutes tes sessions s'invalident automatiquement après 1h d'inactivité.",
      "En mode hors-ligne (Ollama), absolument rien ne quitte ton PC.",
    ],
  },
  {
    icon: Cpu,
    title: 'Sous le capot (pour les curieux)',
    color: '#A1A1AA',
    points: [
      'Backend : FastAPI + MongoDB + AsyncIO. Hébergé sur Emergent (Kubernetes).',
      'Frontend : React 18 + Tailwind + Framer Motion. Build en mode PWA.',
      "IA online : emergentintegrations + LiteLLM → routes vers GPT-4o, Claude, Gemini selon le besoin.",
      'IA offline : appel HTTP direct vers ton instance Ollama locale (port 11434).',
      "Auto-deploy : push GitHub → webhook → redéploiement automatique sur Emergent.",
    ],
  },
];

export default function HowItWorks() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-[#050505] relative overflow-hidden">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="fixed inset-0 grid-bg opacity-10 pointer-events-none"></div>

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-10">
        <button
          onClick={() => navigate(-1)}
          data-testid="how-back-btn"
          className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" /> Retour
        </button>

        <motion.header
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-['Chivo'] font-black text-white leading-tight">
            Comment ça <span className="text-[#E4FF00]">marche</span>
          </h1>
          <p className="mt-3 text-base text-[#A1A1AA] font-['IBM_Plex_Sans'] max-w-2xl">
            Le moteur de création de CodeForge AI, expliqué sans bullshit.
            Promesse&nbsp;: <span className="text-white">100% gratuit, vraiment illimité, vraiment privé en mode hors-ligne</span>.
          </p>
        </motion.header>

        <div className="mt-10 space-y-6">
          {sections.map((s, i) => (
            <motion.section
              key={s.title}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.05 + i * 0.06, ease: 'easeOut' }}
              className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl"
            >
              <div className="flex items-start gap-4">
                <div
                  className="w-11 h-11 rounded-sm flex items-center justify-center flex-shrink-0"
                  style={{ background: `${s.color}20`, border: `1px solid ${s.color}40` }}
                >
                  <s.icon className="w-5 h-5" style={{ color: s.color }} />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg sm:text-xl font-['Chivo'] font-bold text-white">{s.title}</h2>
                  <ul className="mt-3 space-y-2 text-sm text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed">
                    {s.points.map((p, idx) => (
                      <li key={idx} className="flex gap-2">
                        <span style={{ color: s.color }} className="flex-shrink-0">▸</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </motion.section>
          ))}
        </div>

        <div className="mt-10 p-6 bg-[#E4FF00]/10 border border-[#E4FF00]/30 rounded-sm flex items-start gap-4">
          <Smartphone className="w-6 h-6 text-[#E4FF00] flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-white font-['Chivo'] font-bold">Prêt·e à essayer ?</p>
            <p className="text-sm text-[#A1A1AA] mt-1">Crée ton compte en 30 secondes, sans CB, sans quota.</p>
            <button
              onClick={() => navigate('/login')}
              data-testid="how-cta-btn"
              className="mt-3 inline-flex items-center gap-2 px-5 py-2.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all"
            >
              Commencer maintenant
            </button>
          </div>
        </div>

        <p className="mt-12 text-center text-xs text-[#A1A1AA]/60">
          Une question, un bug, une suggestion ? Utilise le bouton feedback en bas à droite de l'écran.
        </p>
      </div>
    </div>
  );
}
