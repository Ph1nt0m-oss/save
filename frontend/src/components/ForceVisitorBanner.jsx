/**
 * iter158.3 — Bannière affichée en haut de l'app quand un compte est
 * en `force_visitor=true` (spec CDC : le message exact doit être visible
 * à l'utilisateur concerné). Utilise les clés i18n `kick_force_visitor_*`.
 *
 * Ne s'affiche pas pour la Créa réelle (elle peut simuler ce mode sans
 * en subir les effets).
 */
import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

export default function ForceVisitorBanner() {
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  if (!device.forceVisitor) return null;
  if (device.role === 'creator') return null;
  return (
    <div
      data-testid="force-visitor-banner"
      className="fixed top-0 left-0 right-0 z-[80] bg-orange-500/95 text-black px-4 py-2 shadow-md flex items-start gap-2 backdrop-blur-md"
    >
      <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="font-['Chivo'] font-bold text-xs uppercase tracking-widest">
          {t('kick_force_visitor_title')}
        </div>
        <div className="text-xs leading-snug mt-0.5">
          {t('kick_force_visitor_body')}
        </div>
      </div>
    </div>
  );
}
