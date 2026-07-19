import React, { useEffect, useState } from 'react';
import { Eye, X, Lock } from 'lucide-react';
import { setStoredViewMode, readVisitTarget } from '../hooks/useDeviceIdentity';

const LABELS = {
  user: 'utilisateur',
  modo: 'modérateur',
  admin: 'administrateur',
  guest: 'visiteur',
  creator: 'créateur',
};

/**
 * iter86 — Bandeau persistant en haut quand la créatrice simule une vue.
 * iter128.5 — Si la simulation a été déclenchée via "Visiter le compte"
 *   (visitTargetPseudo en localStorage), on affiche le pseudo cible.
 * iter149 — Le badge "Lecture seule" est TOUJOURS visible pour TOUT type
 *   de vue (spec D) — y compris quand la Créa consulte sa PROPRE vue Créa
 *   (rappelle que c'est une prévisualisation, pas une session réelle).
 */
export default function ViewSimulationBanner({ role, viewMode }) {
  const [visitTarget, setVisitTarget] = useState(readVisitTarget());

  useEffect(() => {
    const sync = () => setVisitTarget(readVisitTarget());
    window.addEventListener('codeforge:view-mode-changed', sync);
    return () => window.removeEventListener('codeforge:view-mode-changed', sync);
  }, []);

  // Uniquement pour la Créa (seule à pouvoir simuler des vues).
  if (role !== 'creator') return null;
  // iter149 : afficher aussi quand viewMode==='creator' — permet à la
  // Créa de savoir qu'elle est dans une prévisualisation même de sa
  // propre vue Créa.
  const activeMode = viewMode || 'creator';
  const isCreatorSelfView = activeMode === 'creator';

  return (
    <div
      data-testid="view-simulation-banner"
      className={`px-4 py-1.5 flex items-center gap-2 text-xs border-b ${
        isCreatorSelfView
          ? 'bg-cyan-500/10 border-cyan-400/30'
          : 'bg-amber-500/15 border-amber-400/40'
      }`}
    >
      <Eye className={`w-3.5 h-3.5 flex-shrink-0 ${isCreatorSelfView ? 'text-cyan-300' : 'text-amber-300'}`} />
      <span className={`font-bold uppercase tracking-widest ${isCreatorSelfView ? 'text-cyan-200' : 'text-amber-200'}`}>
        {isCreatorSelfView ? 'Prévisualisation' : 'Simulation'}
      </span>
      <span className={`${isCreatorSelfView ? 'text-cyan-100' : 'text-amber-100'} flex items-center gap-1.5`}>
        {visitTarget ? (
          <>Tu vois actuellement le compte de <strong>{visitTarget}</strong>.</>
        ) : (
          <>Tu vois actuellement l&apos;app comme un <strong>{LABELS[activeMode] || activeMode}</strong>.</>
        )}
      </span>
      {/* iter149 — Badge « Lecture seule » TOUJOURS visible pour toute vue,
          y compris la vue Créa (rappel qu'il s'agit d'une prévisualisation). */}
      <span
        data-testid="read-only-badge"
        title="Toute vue simulée est en lecture seule — aucune écriture ne sera envoyée au serveur."
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border font-bold uppercase tracking-widest ${
          isCreatorSelfView
            ? 'border-cyan-400/50 bg-cyan-500/20 text-cyan-100'
            : 'border-white/30 bg-black/40 text-white'
        }`}
      >
        <Lock className="w-3 h-3" />
        Lecture seule
      </span>
      {!isCreatorSelfView && (
        <button
          type="button"
          onClick={() => setStoredViewMode('creator')}
          data-testid="view-simulation-revert"
          className="ml-auto inline-flex items-center gap-1 text-amber-200 hover:text-white border border-amber-400/40 hover:bg-amber-500/20 px-2 py-0.5 rounded-sm"
        >
          <X className="w-3 h-3" />
          <span>Quitter la simulation</span>
        </button>
      )}
    </div>
  );
}
