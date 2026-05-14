import React, { useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import TheftRecoveryDialog from './TheftRecoveryDialog';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Top-bar icon button that opens the "Declare theft" biometric recovery
 * dialog. Used in every header.
 */
export default function TheftButton() {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
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
