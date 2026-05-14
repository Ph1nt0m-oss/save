import React, { useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import TheftRecoveryDialog from './TheftRecoveryDialog';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Top-bar icon button that opens the "Declare theft" biometric recovery
 * dialog. Used in every header.
 *
 * Variants:
 *  - 'icon' (default): just the ShieldAlert glyph in a 36×36 square.
 *  - 'labelled': icon + "Déclarer un vol" label, used on the LEFT side of
 *    every header so the recovery flow is impossible to miss.
 */
export default function TheftButton({ variant = 'icon' }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  if (variant === 'labelled') {
    return (
      <>
        <button
          type="button"
          onClick={() => setOpen(true)}
          data-testid="theft-labelled-btn"
          title={t('theft_link')}
          className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-red-300 hover:border-red-400/40 transition-colors"
        >
          <ShieldAlert className="w-4 h-4 flex-shrink-0" />
          <span className="text-xs font-['Chivo'] font-bold whitespace-nowrap">{t('theft_short')}</span>
        </button>
        <TheftRecoveryDialog open={open} onClose={() => setOpen(false)} />
      </>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="theft-icon-btn"
        title={t('theft_link')}
        className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-red-400 hover:border-red-400/40 transition-colors"
      >
        <ShieldAlert className="w-4 h-4" />
      </button>
      <TheftRecoveryDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
