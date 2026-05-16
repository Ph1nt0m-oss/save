import React from 'react';
import { ShieldCheck, X, Loader2 } from 'lucide-react';

/**
 * iter78 — Plein écran centré quand un user non-créa demande un export
 * (apk/exe/zip+github). Aucune confirmation n'est nécessaire côté user :
 * le bouton X ferme le modal mais le polling continue en arrière-plan.
 */
export default function ExportInReviewModal({ open, status, kind, onClose }) {
  if (!open) return null;
  const isApproved = status === 'approved';
  const isRejected = status === 'rejected';
  const isPending = status === 'pending' || !status;
  return (
    <div className="fixed inset-0 z-[125] flex items-center justify-center bg-black/92 backdrop-blur-md p-3 sm:p-6" data-testid="export-review-modal">
      <div className="w-full max-w-2xl bg-[#0A0A0A] border-2 border-[#E4FF00]/60 rounded-md p-6 sm:p-10 shadow-[0_20px_80px_rgba(228,255,0,0.3)] relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[#A1A1AA] hover:text-white p-2" aria-label="Close" data-testid="export-review-close">
          <X className="w-6 h-6" />
        </button>
        <div className="flex flex-col items-center text-center gap-4">
          {isPending && <Loader2 className="w-14 h-14 text-[#E4FF00] animate-spin" />}
          {isApproved && <ShieldCheck className="w-14 h-14 text-emerald-400" />}
          {isRejected && <X className="w-14 h-14 text-red-400" />}
          <h2 className="text-2xl sm:text-4xl font-['Chivo'] font-black text-white leading-tight">
            {isApproved && 'Export approuvé !'}
            {isRejected && 'Export refusé'}
            {isPending && 'Votre projet est en cours d\'examination par la communauté administrative'}
          </h2>
          <p className="text-base sm:text-lg text-[#E4E4E7] leading-relaxed whitespace-pre-line">
            {isApproved && `Le créateur a validé ton export ${kind?.toUpperCase() || ''}.\nLe téléchargement va démarrer.`}
            {isRejected && `Le créateur a refusé ton export ${kind?.toUpperCase() || ''}.\nTu peux retenter plus tard ou modifier ton projet.`}
            {isPending && `Tu as demandé un export ${kind?.toUpperCase() || ''}.\nUn admin, un modo ou la créatrice doit valider ta demande\navant que le téléchargement ne démarre.\n\nTu peux fermer ce message — l'export se lancera automatiquement\nquand il sera approuvé.`}
          </p>
          {isPending && <div className="text-xs text-[#71717A] uppercase tracking-widest mt-2">vérification toutes les 4 secondes…</div>}
        </div>
      </div>
    </div>
  );
}
