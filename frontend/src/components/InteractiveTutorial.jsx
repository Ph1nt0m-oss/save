/**
 * iter149 — Tutoriel interactif InteractiveTutorial.
 *
 * Contrairement au Tutorial en pleine page, ce composant est un
 * overlay léger qui affiche des « bulles » avec flèche pointant vers
 * un élément cible (selector CSS ou data-testid) sur la page courante.
 * Permet d'expliquer À QUOI SERT chaque bouton du menu.
 *
 * Fonctionnalités demandées (spec F) :
 *  - Piloté ENTIÈREMENT par étapes.
 *  - Peut être relancé à tout moment.
 *  - Mémorise la progression (localStorage).
 *  - Facile à modifier (config JSON en tête de fichier).
 *  - Utilisable sur Login / Inscription (steps: 'auth') ET sur le
 *    Dashboard pour montrer à quoi sert chaque bouton (steps: 'menu').
 *
 * Usage :
 *   <InteractiveTutorial scope="auth" onClose={() => ...} />
 *   <InteractiveTutorial scope="menu" onClose={() => ...} />
 *
 * Structure d'un step :
 *   { id, title, body, target, placement, ctaTarget? }
 *     - target : selector CSS ("[data-testid=xxx]") ou null pour centre
 *     - placement : 'top' | 'bottom' | 'left' | 'right' | 'center'
 *     - ctaTarget : selector optionnel du bouton à surligner à la fin
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { X, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';

// -----------------------------------------------------------
// Configuration des étapes — modifier ici pour ajouter/retirer.
// -----------------------------------------------------------
export const TUTORIAL_STEPS = {
  // Login / Inscription (page publique).
  auth: [
    {
      id: 'auth-tabs',
      title: 'Connexion ou Inscription',
      body: 'Bascule entre Connexion et Inscription en un clic. Ton appareil est identifié par une clé cryptographique locale (pas de mot de passe traditionnel).',
      target: '[data-testid=tab-login]',
      placement: 'bottom',
    },
    {
      id: 'auth-visit-account',
      title: 'Visite du compte',
      body: 'Prévisualise le site comme un utilisateur inscrit — sans créer de compte. Idéal pour tester avant de s\'engager.',
      target: '[data-testid=login-visit-account-btn]',
      placement: 'top',
    },
    {
      id: 'auth-view-picker',
      title: 'Choix de vue',
      body: 'Choisis la vue à prévisualiser : utilisateur inscrit ou invité (lecture seule, aucune donnée écrite).',
      target: '[data-testid=login-view-picker-btn]',
      placement: 'top',
    },
    {
      id: 'auth-language',
      title: 'Multi-langues',
      body: '16 langues disponibles. Ta préférence est persistée localement — même hors connexion.',
      target: '[data-testid=language-toggle]',
      placement: 'top',
    },
    {
      id: 'auth-legal',
      title: 'Comment ça marche · CGU',
      body: 'Découvre le fonctionnement du site et les conditions d\'utilisation avant de te connecter.',
      target: '[data-testid=link-how-it-works]',
      placement: 'top',
    },
    {
      id: 'auth-theft',
      title: 'Vol d\'appareil',
      body: 'Si tu as perdu ton appareil ou qu\'on t\'a volé ta clé, tu peux déclarer un vol et récupérer ton accès depuis un autre appareil.',
      target: '[data-testid=declare-theft-link]',
      placement: 'top',
    },
  ],
  // Menu du Dashboard (aperçu des boutons principaux).
  menu: [
    {
      id: 'menu-lang',
      title: 'Langue de l\'interface',
      body: 'Change la langue en un clic — persiste ton choix pour les prochaines visites.',
      target: '[data-testid=language-toggle]',
      placement: 'bottom',
    },
    {
      id: 'menu-tutorial',
      title: 'Ce tutoriel',
      body: 'À tout moment, tu peux relancer ce tour depuis ce bouton (icône diplôme).',
      target: '[data-testid=header-tutorial-btn]',
      placement: 'bottom',
    },
    {
      id: 'menu-accounts',
      title: 'Mes comptes / Comptes',
      body: 'Gère tes appareils enregistrés, tes sessions, ou (Créa/Staff) visite un compte.',
      target: '[data-testid=accounts-btn]',
      placement: 'bottom',
    },
    {
      id: 'menu-mentions',
      title: 'Mentions @',
      body: 'Reçois une notification lorsqu\'un membre te mentionne dans un tchat. En mode anonyme, l\'auteur reste anonyme mais tu es prévenu·e.',
      target: '[data-testid=mentions-bell-btn]',
      placement: 'top',
    },
    {
      id: 'menu-caly',
      title: 'Assistante Caly',
      body: 'Question sur l\'utilisation du site ? Caly te répond en temps réel.',
      target: '[data-testid=caly-floating-btn]',
      placement: 'top',
    },
    {
      id: 'menu-exports',
      title: 'Exports',
      body: 'Exporte tes projets en ZIP ou en application native (Créa/staff seulement).',
      target: '[data-testid=export-source-btn]',
      placement: 'bottom',
    },
  ],
};

const STORAGE_KEY_PREFIX = 'codeforge_tuto_progress_v2::';

function _storageKey(scope) { return STORAGE_KEY_PREFIX + scope; }

function readProgress(scope) {
  try {
    const raw = localStorage.getItem(_storageKey(scope));
    if (!raw) return 0;
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : 0;
  } catch (_e) { return 0; }
}
function writeProgress(scope, idx) {
  try { localStorage.setItem(_storageKey(scope), String(idx)); } catch (_e) { /* ignore */ }
}
function resetProgress(scope) {
  try { localStorage.removeItem(_storageKey(scope)); } catch (_e) { /* ignore */ }
}

// Positionne la bulle par rapport à l'élément cible.
function computeBubblePos(target, placement) {
  if (!target) return { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' };
  const rect = target.getBoundingClientRect();
  const off = 14;
  const bubbleW = 340;
  const bubbleH = 240;
  const margin = 12;
  let top, left, transform = '';
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  // Sélectionne la meilleure orientation si celle demandée manque de place.
  const spaceTop = rect.top;
  const spaceBottom = vh - rect.bottom;
  const spaceLeft = rect.left;
  const spaceRight = vw - rect.right;
  let p = placement;
  if (p === 'top' && spaceTop < bubbleH + off && spaceBottom > bubbleH + off) p = 'bottom';
  if (p === 'bottom' && spaceBottom < bubbleH + off && spaceTop > bubbleH + off) p = 'top';
  if (p === 'left' && spaceLeft < bubbleW + off && spaceRight > bubbleW + off) p = 'right';
  if (p === 'right' && spaceRight < bubbleW + off && spaceLeft > bubbleW + off) p = 'left';

  switch (p) {
    case 'top':
      top = clamp(rect.top - bubbleH - off, margin, vh - bubbleH - margin);
      left = clamp(rect.left + rect.width / 2 - bubbleW / 2, margin, vw - bubbleW - margin);
      break;
    case 'left':
      top = clamp(rect.top + rect.height / 2 - bubbleH / 2, margin, vh - bubbleH - margin);
      left = clamp(rect.left - bubbleW - off, margin, vw - bubbleW - margin);
      break;
    case 'right':
      top = clamp(rect.top + rect.height / 2 - bubbleH / 2, margin, vh - bubbleH - margin);
      left = clamp(rect.right + off, margin, vw - bubbleW - margin);
      break;
    case 'center':
      top = vh / 2 - bubbleH / 2;
      left = vw / 2 - bubbleW / 2;
      break;
    default: // bottom
      top = clamp(rect.bottom + off, margin, vh - bubbleH - margin);
      left = clamp(rect.left + rect.width / 2 - bubbleW / 2, margin, vw - bubbleW - margin);
  }
  return { top: `${top}px`, left: `${left}px`, transform };
}

function highlightRect(target) {
  if (!target) return null;
  return target.getBoundingClientRect();
}

function scrollTargetIntoView(target) {
  if (!target || typeof target.scrollIntoView !== 'function') return;
  try {
    target.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
  } catch (_) {
    try { target.scrollIntoView(); } catch (__) { /* ignore */ }
  }
}

export default function InteractiveTutorial({ scope = 'auth', onClose, autoOpen = false }) {
  const steps = TUTORIAL_STEPS[scope] || [];
  const [open, setOpen] = useState(autoOpen);
  const [stepIdx, setStepIdx] = useState(() => Math.min(readProgress(scope), Math.max(steps.length - 1, 0)));
  const [tick, setTick] = useState(0); // re-render on resize

  useEffect(() => {
    if (!open) return undefined;
    const onResize = () => setTick((v) => v + 1);
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', onResize, true);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onResize, true);
    };
  }, [open]);

  useEffect(() => { writeProgress(scope, stepIdx); }, [scope, stepIdx]);

  const current = steps[stepIdx];

  // iter150 — Résolution de la cible avec RETRY (si l'élément n'est pas
  // encore monté au premier tick), scroll-into-view, et RAF forcé sur
  // changement d'étape/ouverture pour recomputer précisément.
  const [target, setTarget] = useState(null);
  useEffect(() => {
    if (!open || !current) { setTarget(null); return undefined; }
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 20; // 20 × 100ms = 2s
    const tryResolve = () => {
      if (cancelled) return;
      const el = current.target ? document.querySelector(current.target) : null;
      if (el) {
        scrollTargetIntoView(el);
        // Attends 60ms que le scroll se stabilise puis lit la position.
        setTimeout(() => {
          if (!cancelled) {
            setTarget(el);
            setTick((v) => v + 1);
          }
        }, 60);
      } else if (attempts < maxAttempts) {
        attempts += 1;
        setTimeout(tryResolve, 100);
      } else {
        setTarget(null);
      }
    };
    tryResolve();
    return () => { cancelled = true; };
  }, [open, current]);

  const bubblePos = useMemo(
    () => computeBubblePos(target, current?.placement || 'center'),
    [target, current, tick],
  );
  const hRect = highlightRect(target);

  const doClose = useCallback((finished = false) => {
    setOpen(false);
    if (finished) resetProgress(scope);
    if (typeof onClose === 'function') onClose(finished);
  }, [onClose, scope]);

  const goNext = useCallback(() => {
    if (stepIdx + 1 >= steps.length) return doClose(true);
    setStepIdx((i) => i + 1);
  }, [stepIdx, steps.length, doClose]);
  const goPrev = useCallback(() => setStepIdx((i) => Math.max(0, i - 1)), []);

  // Handle explicitly used by parent triggers to (re)start.
  useEffect(() => { if (autoOpen) setOpen(true); }, [autoOpen]);

  if (!open || !current) return null;
  const percent = Math.round(((stepIdx + 1) / steps.length) * 100);

  return (
    <div data-testid={`tuto-overlay-${scope}`} className="fixed inset-0 z-[95] pointer-events-none">
      {/* Voile assombri PARTIEL + trou sur l'élément cible (via clip-path). */}
      <div
        className="absolute inset-0 bg-black/60 pointer-events-auto"
        onClick={() => doClose(false)}
        aria-hidden
      />
      {/* Halo autour de la cible */}
      {hRect && (
        <div
          data-testid={`tuto-highlight-${scope}`}
          className="absolute border-2 border-[#E4FF00] rounded-sm shadow-[0_0_0_9999px_rgba(0,0,0,0.55)] transition-all duration-200"
          style={{
            top: hRect.top - 6,
            left: hRect.left - 6,
            width: hRect.width + 12,
            height: hRect.height + 12,
          }}
        />
      )}
      {/* Bulle */}
      <div
        data-testid={`tuto-bubble-${scope}`}
        className="absolute w-[340px] bg-[#050505] border border-[#E4FF00]/50 rounded-sm shadow-2xl pointer-events-auto text-white p-4 space-y-3"
        style={bubblePos}
      >
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[#E4FF00]" />
          <h4 className="text-sm font-['Chivo'] font-bold flex-1">{current.title}</h4>
          <button
            type="button"
            onClick={() => doClose(false)}
            data-testid={`tuto-close-${scope}`}
            aria-label="Fermer le tutoriel"
            className="text-[#A1A1AA] hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-white/85 leading-relaxed">{current.body}</p>
        <div className="h-1 bg-white/10 rounded-sm overflow-hidden">
          <div className="h-full bg-[#E4FF00] transition-all" style={{ width: `${percent}%` }} data-testid={`tuto-progress-${scope}`} />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goPrev}
            disabled={stepIdx === 0}
            data-testid={`tuto-prev-${scope}`}
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1 border border-white/15 rounded-sm text-white/70 hover:border-white/40 disabled:opacity-30"
          >
            <ChevronLeft className="w-3 h-3" /> Précédent
          </button>
          <span className="text-[10px] text-white/50 flex-1 text-center">{stepIdx + 1} / {steps.length}</span>
          <button
            type="button"
            onClick={goNext}
            data-testid={`tuto-next-${scope}`}
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90"
          >
            {stepIdx + 1 >= steps.length ? 'Terminer' : 'Suivant'} <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
}

/** Bouton public pour (re)lancer le tutoriel — à utiliser depuis toute page. */
export function LaunchTutorialButton({ scope = 'auth', label = 'Tutoriel', className = '', onLaunched }) {
  const [nonce, setNonce] = useState(0);
  const [open, setOpen] = useState(false);
  const launch = () => {
    resetProgress(scope);
    setNonce((n) => n + 1);
    setOpen(true);
    onLaunched?.();
  };
  return (
    <>
      <button
        type="button"
        onClick={launch}
        data-testid={`tuto-launch-${scope}`}
        className={className || 'inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/10 rounded-sm transition-colors'}
      >
        <Sparkles className="w-3 h-3" /> {label}
      </button>
      {open && (
        <InteractiveTutorial
          key={`${scope}-${nonce}`}
          scope={scope}
          autoOpen
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
