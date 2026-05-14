import React from 'react';
import { EyeOff, X } from 'lucide-react';
import useDeviceIdentity, { setStoredViewMode } from '../hooks/useDeviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Top thin banner that appears whenever the creator has toggled the view
 * mode to "guest preview". Lets them tap to exit the preview.
 */
export default function ViewModePreviewBanner() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  if (device.role !== 'creator' || device.viewMode !== 'guest') return null;

  return (
    <div
      data-testid="view-mode-preview-banner"
      className="fixed top-0 inset-x-0 z-[80] bg-amber-400/15 border-b border-amber-400/40 text-amber-200 backdrop-blur-md"
    >
      <div className="max-w-7xl mx-auto px-3 sm:px-4 py-1.5 flex items-center gap-2 text-[11px] sm:text-xs font-['IBM_Plex_Sans']">
        <EyeOff className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="flex-1 truncate">{t('vm_preview_banner')}</span>
        <button
          type="button"
          onClick={() => setStoredViewMode('creator')}
          data-testid="exit-guest-preview"
          className="inline-flex items-center gap-1 px-2 py-0.5 border border-amber-400/40 hover:bg-amber-400/20 rounded-sm transition"
        >
          {t('vm_back_to_creator')}
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
