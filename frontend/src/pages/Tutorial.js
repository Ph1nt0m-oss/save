/**
 * iter148 — Tutoriel plateforme CodeForge AI.
 *
 * Parcours interactif étape par étape pour découvrir les principales
 * fonctionnalités : identité cryptographique, groupes de discussion,
 * modération intelligente, programmation des IA, exports, intégrations.
 *
 * Pas de dépendance backend — 100 % statique côté client. Persistance
 * de la progression via localStorage (`codeforge_tutorial_step`).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, Check, KeyRound, MessagesSquare, ShieldAlert,
  Bot, Package, Plug, Sparkles, Languages,
} from 'lucide-react';
import LanguageToggle from '../components/LanguageToggle';

const STORAGE_KEY = 'codeforge_tutorial_step_v1';

const STEPS = [
  {
    id: 'identity',
    Icon: KeyRound,
    title: 'Ton identité cryptographique',
    body: (
      <>
        <p>
          CodeForge AI n&apos;utilise <b>pas de mot de passe</b> traditionnel pour
          identifier ton appareil. Une paire de clés <span className="font-mono text-[#E4FF00]">ECDSA
          P-256</span> est générée localement (WebCrypto) et jamais transmise.
        </p>
        <p>
          Ton <b>identité publique unique</b> est ton <span className="font-mono">@handle</span> (3 à 24 caractères),
          choisie à l&apos;inscription. Elle est <em>unique</em> sur toute la plateforme.
        </p>
      </>
    ),
  },
  {
    id: 'groups',
    Icon: MessagesSquare,
    title: 'Groupes & anonymat',
    body: (
      <>
        <p>
          10 groupes de discussion existent selon ton rôle (public, private, users,
          staff, modo, admin…). Le tchat s&apos;ouvre depuis l&apos;icône bulle du Dashboard.
        </p>
        <p>
          Active le <b>Mode Anonyme</b> pour masquer ton pseudo. Les mentions
          <span className="font-mono"> @handle</span> continuent à fonctionner : le destinataire est
          notifié <em>sans jamais voir ton identité</em> si tu es en anonyme.
        </p>
      </>
    ),
  },
  {
    id: 'moderation',
    Icon: ShieldAlert,
    title: 'Modération intelligente en 2 couches',
    body: (
      <>
        <p>
          Chaque message est analysé en <b>2 couches indépendantes</b> :
        </p>
        <ul className="list-disc pl-5 space-y-1 text-white/80">
          <li><b>Règles déterministes</b> (spam, flood, mots-clés, mentions en rafale).</li>
          <li><b>LLM Emergent</b> — détecte l&apos;ironie, la moquerie et le harcèlement subtil.</li>
        </ul>
        <p>
          Les deux analyses sont journalisées séparément. Les modos reçoivent une
          alerte pop-up quand une suspicion est détectée. Ils peuvent sanctionner,
          classer « pas d&apos;infraction » ou déléguer à un autre staff.
        </p>
      </>
    ),
  },
  {
    id: 'ai-programming',
    Icon: Bot,
    title: 'Programmation des IA (Créa)',
    body: (
      <>
        <p>
          La Créa peut ajuster le <b>profil comportemental</b> de chaque agent
          (Caly, Forge, Archi, bots analystes…) : style d&apos;écriture, limites,
          domaines, prompt système, mode de raisonnement.
        </p>
        <p>
          Chaque sauvegarde crée une <b>nouvelle version</b> archivée — tu peux
          restaurer une version antérieure en un clic (via l&apos;historique).
        </p>
        <p className="text-white/60">
          Règle absolue : <em>interdiction de fusion des personnalités</em>. Chaque IA
          garde son rôle propre.
        </p>
      </>
    ),
  },
  {
    id: 'exports',
    Icon: Package,
    title: 'Exports & validation Créa',
    body: (
      <>
        <p>
          Tu peux exporter tes projets en <b>ZIP</b> (avec ou sans push GitHub silencieux).
          Chaque demande passe par des <b>bots validateurs</b> qui analysent le
          projet (compte, cohérence, discussions liées) avant d&apos;être validée par
          la Créa.
        </p>
      </>
    ),
  },
  {
    id: 'integrations',
    Icon: Plug,
    title: 'Intégrations tierces',
    body: (
      <>
        <p>
          Connecte tes comptes <b>Stripe</b>, <b>Google</b> et <b>ChatGPT</b> depuis
          la page <Link to="/private/integrations" className="text-[#E4FF00] underline underline-offset-2">Intégrations</Link>.
          Les clés sont chiffrées AES-GCM au repos, jamais renvoyées en clair.
        </p>
      </>
    ),
  },
  {
    id: 'languages',
    Icon: Languages,
    title: 'Multi-langues',
    body: (
      <>
        <p>
          L&apos;interface est disponible en <b>16 langues</b> (dont l&apos;arabe RTL).
          Change la langue via le sélecteur ci-dessous — tu peux essayer tout de suite :
        </p>
        <div className="mt-2"><LanguageToggle placement="bottom" /></div>
      </>
    ),
  },
];


export default function Tutorial() {
  const navigate = useNavigate();
  const [step, setStep] = useState(() => {
    try {
      const s = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
      return Math.max(0, Math.min(s, STEPS.length - 1));
    } catch (_e) { return 0; }
  });

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, String(step)); } catch (_e) { /* ignore */ }
  }, [step]);

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const percent = useMemo(() => Math.round(((step + 1) / STEPS.length) * 100), [step]);

  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col" data-testid="tutorial-page">
      <header className="border-b border-white/10 px-4 py-3 flex items-center gap-3">
        <button
          onClick={() => navigate('/dashboard')}
          data-testid="tutorial-back"
          className="text-[#A1A1AA] hover:text-white"
          aria-label="Retour au dashboard"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <Sparkles className="w-4 h-4 text-[#E4FF00]" />
        <h1 className="text-sm font-['Chivo'] font-bold">Tutoriel CodeForge AI</h1>
        <div className="ml-auto text-[11px] text-[#A1A1AA]" data-testid="tutorial-progress">
          Étape {step + 1} / {STEPS.length} · {percent}%
        </div>
      </header>

      {/* Barre de progression */}
      <div className="h-1 bg-white/5 relative overflow-hidden">
        <div
          className="h-full bg-[#E4FF00] transition-all duration-300"
          style={{ width: `${percent}%` }}
          data-testid="tutorial-progress-bar"
        />
      </div>

      {/* Rail de navigation */}
      <div className="border-b border-white/5 px-3 py-2 flex items-center gap-1.5 overflow-x-auto">
        {STEPS.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setStep(i)}
            data-testid={`tutorial-jump-${s.id}`}
            className={`inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-sm border whitespace-nowrap ${
              i === step
                ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00] font-bold'
                : i < step
                ? 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10'
                : 'text-white/60 border-white/15'
            }`}
          >
            {i < step && <Check className="w-3 h-3" />}
            {s.id}
          </button>
        ))}
      </div>

      <main className="flex-1 overflow-y-auto p-4 sm:p-8 flex items-start justify-center">
        <div className="w-full max-w-2xl space-y-5">
          <div className="flex items-center gap-3">
            <current.Icon className="w-6 h-6 text-[#E4FF00]" />
            <h2 className="text-lg sm:text-xl font-['Chivo'] font-bold">{current.title}</h2>
          </div>
          <div
            className="space-y-3 text-sm text-white/85 leading-relaxed"
            data-testid={`tutorial-step-${current.id}`}
          >
            {current.body}
          </div>
        </div>
      </main>

      <footer className="border-t border-white/10 px-4 py-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          data-testid="tutorial-prev"
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 border border-white/15 rounded-sm text-white/80 hover:border-white/40 disabled:opacity-30"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Précédent
        </button>
        <div className="flex-1" />
        {isLast ? (
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            data-testid="tutorial-finish"
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90"
          >
            Terminer <Check className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            data-testid="tutorial-next"
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90"
          >
            Suivant <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </footer>
    </div>
  );
}
