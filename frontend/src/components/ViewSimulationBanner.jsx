import React from 'react';
import { Eye, X } from 'lucide-react';
import { setStoredViewMode } from '../hooks/useDeviceIdentity';

const LABELS = {
  user: 'utilisateur',
  modo: 'modérateur',
  admin: 'administrateur',
  guest: 'visiteur',
};

/**
 * iter86 — Bandeau persistant en haut quand la créatrice simule une vue.
 * Évite d'oublier qu'on est en simulation. Click sur la croix = revert.
 */
export default function ViewSimulationBanner({ role, viewMode }) {
  if (role !== 'creator') return null;
  if (!viewMode || viewMode === 'creator') return null;

  return (
    <div
      data-testid="view-simulation-banner"
      className="bg-amber-500/15 border-b border-amber-400/40 px-4 py-1.5 flex items-center gap-2 text-xs"
    >
      <Eye className="w-3.5 h-3.5 text-amber-300 flex-shrink-0" />
      <span className="text-amber-200 font-bold uppercase tracking-widest">Simulation</span>
      <span className="text-amber-100">
        Tu vois actuellement l&apos;app comme un <strong>{LABELS[viewMode] || viewMode}</strong>.
      </span>
      <button
        type="button"
        onClick={() => setStoredViewMode('creator')}
        data-testid="view-simulation-revert"
        className="ml-auto inline-flex items-center gap-1 text-amber-200 hover:text-white border border-amber-400/40 hover:bg-amber-500/20 px-2 py-0.5 rounded-sm"
      >
        <X className="w-3 h-3" />
        <span>Quitter la simulation</span>
      </button>
    </div>
  );
}
