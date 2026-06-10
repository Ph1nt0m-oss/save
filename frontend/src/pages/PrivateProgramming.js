import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Lock } from 'lucide-react';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

/**
 * iter79 — Pages privées créa : Programmation du site / Programmation des IA.
 *
 * Visibles depuis le Dashboard, mais bloquées par un message « Accès refusé
 * pour des raisons de sécurité » pour tout device qui n'est pas la créatrice
 * (incluant les visiteurs en vue créateur).
 */
export default function PrivateProgramming() {
  const device = useDeviceIdentity();
  const navigate = useNavigate();
  const location = useLocation();
  const isAI = location.pathname.includes('ai-programming');
  const title = isAI ? 'Programmation des IA' : 'Programmation du site';
  const allowed = device.role === 'creator' && device.viewMode !== 'guest';

  return (
    <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center p-6">
      <div className="max-w-2xl w-full bg-[#0A0A0A] border border-white/10 rounded-md p-8" data-testid="private-programming-page">
        <button onClick={() => navigate('/dashboard')} className="text-[#A1A1AA] hover:text-white text-sm inline-flex items-center gap-1 mb-4">
          <ArrowLeft className="w-4 h-4" /> Retour
        </button>
        <h1 className="text-3xl font-['Chivo'] font-black mb-4">{title}</h1>
        {!allowed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-sm p-6 text-center" data-testid="private-access-denied">
            <Lock className="w-12 h-12 mx-auto text-red-300 mb-3" />
            <p className="text-base text-red-200 leading-relaxed">
              Accès refusé pour des raisons de sécurité.
            </p>
          </div>
        ) : (
          <div className="text-sm text-[#A1A1AA] leading-relaxed space-y-3">
            <p>Cet espace est privé et exclusivement réservé à la créatrice.</p>
            <p>{isAI
              ? 'Ici tu pourras orchestrer les modèles IA, les prompts système, les boucles de vérification et la mémoire de validation.'
              : 'Ici tu pourras éditer le code source de la plateforme, déployer, et superviser les services.'}</p>
            <p className="text-[#71717A] italic">Implémentation détaillée à venir — l&apos;écran de garde sécuritaire est en place.</p>
          </div>
        )}
      </div>
    </div>
  );
}
