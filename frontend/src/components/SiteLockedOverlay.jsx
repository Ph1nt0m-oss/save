import React from 'react';
import { Crown, KeyRound, RefreshCw } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Full-screen overlay shown when the site is locked to creator-only mode
 * and the current device is NOT a creator. Read-only — no way around it
 * except getting promoted (which requires possession of the creator's key).
 */
export default function SiteLockedOverlay({ siteMode, role, onRetry }) {
  const { t } = useLanguage();
  // Only show when access is strictly denied (creator-only mode + non-creator)
  if (siteMode !== 'creator' || role === 'creator') return null;

  return (
    <div
      className="fixed inset-0 z-[9999] bg-black/95 backdrop-blur-md flex items-center justify-center p-6"
      data-testid="site-locked-overlay"
    >
      <div className="max-w-md text-center space-y-5">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#E4FF00]/10 border border-[#E4FF00]/40">
          <Crown className="w-8 h-8 text-[#E4FF00]" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-['Chivo'] font-bold text-white">{t('sl_title')}</h1>
          <p className="text-sm text-[#A1A1AA]">
            {t('sl_body')}
          </p>
        </div>
        <div className="flex items-center justify-center gap-2 text-xs text-[#71717A] bg-white/[0.03] border border-white/10 rounded-sm p-3">
          <KeyRound className="w-3.5 h-3.5 text-[#E4FF00]" />
          <span>{t('sl_hint')}</span>
        </div>
        <button
          type="button"
          onClick={onRetry}
          data-testid="site-locked-retry"
          className="inline-flex items-center gap-2 px-4 py-2 border border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t('sl_retry')}
        </button>
      </div>
    </div>
  );
}
