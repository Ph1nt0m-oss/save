import React, { useState, useEffect } from 'react';
import { Joyride, STATUS } from 'react-joyride';

/**
 * First-time user onboarding tour.
 * Runs once per user (flag stored in localStorage).
 * Reset by clearing `codeforge_onboarded` in localStorage.
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
  },
  {
    target: '[data-testid="wizard-btn"]',
    title: 'Assistant Guidé',
    content:
      "Pas d'idée ? Choisis parmi 35+ templates (CRM, e-commerce, jeu, IA…). Tu n'as qu'à personnaliser et générer.",
    disableBeacon: true,
  },
  {
    target: '[data-testid="online-create-btn"]',
    title: 'Création libre',
    content:
      "Décris ton appli en langage naturel. L'IA construit le code, l'interface, et même les explications.",
    disableBeacon: true,
  },
  {
    target: '[data-testid="create-project-btn"]',
    title: 'Tes projets',
    content:
      "Tous tes projets s'affichent ici. Clic-droit sur un projet pour le renommer ou le supprimer.",
    disableBeacon: true,
  },
];

export default function Onboarding() {
  const [run, setRun] = useState(false);

  useEffect(() => {
    const seen = localStorage.getItem(STORAGE_KEY);
    if (!seen) {
      // Small delay so target elements are mounted
      const t = setTimeout(() => setRun(true), 600);
      return () => clearTimeout(t);
    }
  }, []);

  const handleCallback = (data) => {
    const { status } = data;
    if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      localStorage.setItem(STORAGE_KEY, '1');
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
        hideOverlay
        spotlightClicks
        spotlightPadding={6}
        callback={handleCallback}
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
