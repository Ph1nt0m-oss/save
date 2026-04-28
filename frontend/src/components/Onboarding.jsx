import React, { useState, useEffect } from 'react';
import { Joyride, EVENTS } from 'react-joyride';

/**
 * First-time user onboarding tour.
 * Runs once per user (flag stored in localStorage).
 * Reset by clearing `codeforge_onboarded_v1` in localStorage.
 *
 * react-joyride v3 NOTES:
 *  - The `callback` prop was removed; use `onEvent` instead.
 *  - `hideOverlay` is a per-Step option (not a top-level Props field).
 *  - Top-level `spotlightClicks` is supported.
 */
const STORAGE_KEY = 'codeforge_onboarded_v1';

const STEPS = [
  {
    target: 'body',
    placement: 'center',
    title: 'Bienvenue sur CodeForge AI',
    content:
      "Crée des applications complètes en quelques mots, sans une ligne de code. Voici un tour rapide (15 secondes).",
    disableBeacon: true,
    hideOverlay: true,
  },
  {
    target: '[data-tour="wizard"]',
    title: 'Assistant Guidé',
    content:
      "Pas d'idée ? Choisis parmi 35+ templates (CRM, e-commerce, jeu, IA…). Tu n'as qu'à personnaliser et générer.",
    disableBeacon: true,
    hideOverlay: true,
  },
  {
    target: '[data-tour="create"]',
    title: 'Création libre',
    content:
      "Décris ton appli en langage naturel. L'IA construit le code, l'interface, et même les explications.",
    disableBeacon: true,
    hideOverlay: true,
  },
  {
    target: '[data-testid="create-project-btn"]',
    title: 'Tes projets',
    content:
      "Tous tes projets s'affichent ici. Clic-droit sur un projet pour le renommer ou le supprimer.",
    disableBeacon: true,
    hideOverlay: true,
  },
];

const markCompleted = () => {
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch (_) {}
};

export default function Onboarding() {
  const [run, setRun] = useState(false);

  useEffect(() => {
    const seen = localStorage.getItem(STORAGE_KEY);
    if (!seen) {
      const t = setTimeout(() => setRun(true), 600);
      return () => clearTimeout(t);
    }
  }, []);

  // react-joyride v3: use onEvent (not callback). TOUR_END fires when the
  // user clicks Terminer (last step) or Passer (skip), or when the tour
  // closes for any other reason.
  const handleEvent = (data) => {
    if (!data) return;
    if (data.type === EVENTS.TOUR_END) {
      markCompleted();
      setRun(false);
    }
  };

  if (!run) return null;

  return (
    <div data-testid="onboarding-tour">
      <Joyride
        steps={STEPS}
        run={run}
        continuous
        showProgress
        showSkipButton
        spotlightClicks
        spotlightPadding={6}
        onEvent={handleEvent}
        locale={{
          back: 'Retour',
          close: 'Fermer',
          last: 'Terminer',
          next: 'Suivant',
          skip: 'Passer',
        }}
        styles={{
          options: {
            primaryColor: '#E4FF00',
            backgroundColor: '#0F0F13',
            textColor: '#ffffff',
            arrowColor: '#0F0F13',
            overlayColor: 'rgba(5, 5, 5, 0.78)',
            zIndex: 10000,
          },
          buttonNext: {
            backgroundColor: '#E4FF00',
            color: '#050505',
            fontWeight: 600,
            borderRadius: 8,
          },
          buttonBack: { color: '#E4FF00' },
          buttonSkip: { color: 'rgba(255,255,255,0.6)' },
          tooltipTitle: { color: '#E4FF00', fontFamily: 'IBM Plex Sans, sans-serif' },
          tooltipContent: { fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 14 },
        }}
      />
    </div>
  );
}
