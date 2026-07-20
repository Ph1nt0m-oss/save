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
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
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
      // iter152 — Sur Landing, `language-toggle` est dans le nav top-right :
      // on préfère centrer la bulle pour éviter le chevauchement CreatorToolbar.
      target: '[data-testid=language-toggle]',
      placement: 'auto-top',
    },
    {
      id: 'auth-legal',
      title: 'Comment ça marche · CGU',
      body: 'Découvre le fonctionnement du site et les conditions d\'utilisation avant de te connecter.',
      // iter152 — Fallback multi-selectors : Login → link-how-it-works ;
      // Landing → footer-how-it-works.
      target: '[data-testid=link-how-it-works], [data-testid=footer-how-it-works]',
      placement: 'auto-top',
    },
    {
      id: 'auth-theft',
      title: 'Vol d\'appareil',
      body: 'Si tu as perdu ton appareil ou qu\'on t\'a volé ta clé, tu peux déclarer un vol et récupérer ton accès depuis un autre appareil.',
      // iter152 — Fallback Landing : theft-labelled-btn (TheftButton).
      target: '[data-testid=declare-theft-link], [data-testid=theft-labelled-btn]',
      placement: 'auto-top',
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
// `bubbleW` / `bubbleH` = dimensions RÉELLES mesurées post-render.
// Chaque placement candidat est testé « rentre entièrement dans le
// viewport ? » avant d'être choisi (iter154).
function computeBubblePos(target, placement, bubbleW, bubbleH) {
  const off = 14;
  const margin = 12;
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  // Sans cible → centre du viewport (dernier recours).
  if (!target) {
    return {
      top: `${Math.max(margin, (vh - bubbleH) / 2)}px`,
      left: `${Math.max(margin, (vw - bubbleW) / 2)}px`,
      transform: '',
    };
  }

  const rect = target.getBoundingClientRect();
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  // Calcule un point d'ancrage pour un placement donné + vérifie qu'il
  // rentre. Retourne { fits: bool, top, left, overflow }.
  const tryPlacement = (p) => {
    let top, left;
    switch (p) {
      case 'top':
        top = rect.top - bubbleH - off;
        left = rect.left + rect.width / 2 - bubbleW / 2;
        break;
      case 'bottom':
        top = rect.bottom + off;
        left = rect.left + rect.width / 2 - bubbleW / 2;
        break;
      case 'left':
        top = rect.top + rect.height / 2 - bubbleH / 2;
        left = rect.left - bubbleW - off;
        break;
      case 'right':
        top = rect.top + rect.height / 2 - bubbleH / 2;
        left = rect.right + off;
        break;
      case 'center':
      default:
        top = (vh - bubbleH) / 2;
        left = (vw - bubbleW) / 2;
    }
    // Overflow = somme des débordements sur les 4 côtés.
    const overflow =
      Math.max(0, margin - top) +
      Math.max(0, top + bubbleH - (vh - margin)) +
      Math.max(0, margin - left) +
      Math.max(0, left + bubbleW - (vw - margin));
    const fits = overflow === 0;
    // Clamp final aux limites du viewport (pour ne jamais dépasser).
    const clTop = clamp(top, margin, Math.max(margin, vh - bubbleH - margin));
    const clLeft = clamp(left, margin, Math.max(margin, vw - bubbleW - margin));
    return { fits, top: clTop, left: clLeft, overflow };
  };

  // Ordre de candidats selon le placement demandé — auto-top / auto
  // essaie plusieurs candidats successivement.
  let candidates;
  if (placement === 'auto-top' || placement === 'auto') {
    // iter155 — Priorité TOP (retour au comportement d'origine — bulle
    // près de la cible). Fallback bottom si top ne rentre pas dans la
    // fenêtre. La mesure RÉELLE de bubbleH (via ResizeObserver) permet
    // ce choix précis désormais.
    candidates = ['top', 'bottom', 'right', 'left', 'center'];
  } else if (placement === 'top') {
    candidates = ['top', 'bottom', 'right', 'left', 'center'];
  } else if (placement === 'bottom') {
    candidates = ['bottom', 'top', 'right', 'left', 'center'];
  } else if (placement === 'left') {
    candidates = ['left', 'right', 'top', 'bottom', 'center'];
  } else if (placement === 'right') {
    candidates = ['right', 'left', 'top', 'bottom', 'center'];
  } else {
    candidates = ['center', 'bottom', 'top', 'right', 'left'];
  }

  // Prend le premier qui RENTRE entièrement. Sinon celui qui déborde le
  // moins (mesure d'overflow), et on l'aura clampé pour rester visible.
  let best = null;
  for (const p of candidates) {
    const r = tryPlacement(p);
    if (r.fits) { best = r; break; }
    if (!best || r.overflow < best.overflow) best = r;
  }
  return { top: `${best.top}px`, left: `${best.left}px`, transform: '' };
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

  // iter154 — Mesure la hauteur/largeur RÉELLES de la bulle après rendu
  // pour que le moteur de placement puisse tester chaque emplacement en
  // fonction des dimensions vraies (et pas d'un H estimé à 240px).
  const bubbleRef = useRef(null);
  // Estimations initiales — remplacées par la vraie mesure au 1er layout.
  const [bubbleDims, setBubbleDims] = useState({ w: 340, h: 240 });
  useLayoutEffect(() => {
    if (!open || !bubbleRef.current) return;
    const el = bubbleRef.current;
    const measure = () => {
      const r = el.getBoundingClientRect();
      // Ignore les mesures nulles (avant peinture).
      if (r.width > 0 && r.height > 0) {
        setBubbleDims((prev) => {
          if (Math.abs(prev.w - r.width) < 1 && Math.abs(prev.h - r.height) < 1) return prev;
          return { w: r.width, h: r.height };
        });
      }
    };
    measure();
    // ResizeObserver garantit un recalcul si le contenu texte change de
    // hauteur (retour ligne, wrapping, i18n…) ou si la fenêtre change.
    let ro = null;
    try {
      ro = new window.ResizeObserver(() => measure());
      ro.observe(el);
    } catch (_) { /* ResizeObserver indispo → recalcul via resize event uniquement */ }
    window.addEventListener('resize', measure);
    return () => {
      if (ro) { try { ro.disconnect(); } catch (_) { /* ignore */ } }
      window.removeEventListener('resize', measure);
    };
  }, [open, stepIdx]);

  const bubblePos = useMemo(
    () => computeBubblePos(target, current?.placement || 'center', bubbleDims.w, bubbleDims.h),
    [target, current, tick, bubbleDims.w, bubbleDims.h],
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

  // iter153 — Portal vers document.body pour ÉCHAPPER à tout stacking context
  // parent (navbar sticky, motion.div, CreatorToolbar…) qui empêchait la
  // bulle de passer par-dessus les chips. Combiné à z-[9999], le tuto passe
  // désormais au-dessus de TOUT.
  const tree = (
    <div data-testid={`tuto-overlay-${scope}`} className="fixed inset-0 z-[9999] pointer-events-none">
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
          className="absolute border-2 border-[#E4FF00] rounded-sm shadow-[0_0_0_9999px_rgba(0,0,0,0.55)] transition-all duration-200 pointer-events-none"
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
        ref={bubbleRef}
        data-testid={`tuto-bubble-${scope}`}
        className="absolute w-[340px] max-w-[calc(100vw-24px)] bg-[#050505] border border-[#E4FF00]/60 rounded-sm shadow-[0_20px_60px_rgba(0,0,0,0.8)] pointer-events-auto text-white p-4 space-y-3"
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
  // iter153 — Attache au body via Portal (skip stacking contexts parents).
  if (typeof document === 'undefined') return null;
  return createPortal(tree, document.body);
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
