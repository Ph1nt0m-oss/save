import React from 'react';
import { Crown, KeyRound, RefreshCw, Lock, Eye } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';
import { setStoredViewMode } from '../hooks/useDeviceIdentity';

/**
 * Full-screen overlay shown when the site is locked AND the current device
 * cannot access it. Adapts the message based on `kickReason` returned by
 * /devices/verify or computed from site_mode.
 *
 *  - 'kick_creator_only' (site_mode = creator, device != creator):
 *      "La personne gérant ce site souhaite être en privé"
 *  - 'kick_private' (site_mode = private, device not approved):
 *      "Modifications en cours… repasser prochainement"
 *      + an explicit "Voir en mode invité" button that lets the user
 *      browse the site read-only (drops them into guest view).
 *  - 'kick_blocked' (creator marked this device as blocked):
 *      "Votre demande a été formulée…"
 */
export default function SiteLockedOverlay({ siteMode, role, kickReason, onRetry, hasAccount }) {
  const { t } = useLanguage();

  // Decide if we should render and which reason.
  let reason = kickReason;
  if (!reason) {
    if (role === 'blocked') reason = 'kick_blocked';
    else if (role === 'banned') reason = 'kick_banned';
    else if (siteMode === 'none' && role !== 'creator') reason = 'kick_closed';
    else if (siteMode === 'creator' && role !== 'creator') reason = 'kick_creator_only';
    else if (siteMode === 'private' && !['creator', 'approved'].includes(role)) reason = 'kick_private';
  }
  if (!reason) return null;

  const titleKey = `kick_${reason.replace('kick_', '')}_title`;
  const bodyKey  = `kick_${reason.replace('kick_', '')}_body`;
  const isPrivate = reason === 'kick_private';

  const enterGuestView = () => {
    setStoredViewMode('guest');
    // Re-render the host page so the overlay disappears and the user
    // sees the site as a read-only guest.
    onRetry?.();
  };

  return (
    <div
      className="fixed inset-0 z-[9999] bg-black/95 backdrop-blur-md flex items-center justify-center p-6"
      data-testid="site-locked-overlay"
    >
      <div className="max-w-md text-center space-y-5">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#E4FF00]/10 border border-[#E4FF00]/40">
          {reason === 'kick_blocked' ? <Lock className="w-8 h-8 text-red-400" /> : <Crown className="w-8 h-8 text-[#E4FF00]" />}
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-['Chivo'] font-bold text-white">{t(titleKey)}</h1>
          <p className="text-sm text-[#A1A1AA]">
            {t(bodyKey)}
          </p>
          {isPrivate && (
            <p className="text-sm text-[#E4FF00] mt-2">
              {t('kick_private_guest_offer')}
            </p>
          )}
        </div>
        {!isPrivate && (
          <div className="flex items-center justify-center gap-2 text-xs text-[#71717A] bg-white/[0.03] border border-white/10 rounded-sm p-3">
            <KeyRound className="w-3.5 h-3.5 text-[#E4FF00]" />
            <span>{t('sl_hint')}</span>
          </div>
        )}
        <div className="flex flex-wrap gap-2 justify-center">
          {isPrivate && (
            <button
              type="button"
              onClick={enterGuestView}
              data-testid="site-locked-enter-guest"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#E4FF00]/15 hover:bg-[#E4FF00]/25 border border-[#E4FF00]/40 text-[#E4FF00] rounded-sm font-['Chivo'] font-bold text-sm transition"
            >
              <Eye className="w-3.5 h-3.5" />
              {hasAccount ? t('kick_view_guest_with_history') : t('kick_view_guest_only')}
            </button>
          )}
          <button
            type="button"
            onClick={onRetry}
            data-testid="site-locked-retry"
            className="inline-flex items-center gap-2 px-4 py-2 border border-white/30 text-white hover:bg-white/10 rounded-sm font-['Chivo'] font-bold text-sm transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            {t('sl_retry')}
          </button>
        </div>
      </div>
    </div>
  );
}
