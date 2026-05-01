import React from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { Globe } from 'lucide-react';

export default function LanguageToggle({ className = '' }) {
  const { language, toggleLanguage } = useLanguage();
  return (
    <button
      type="button"
      onClick={toggleLanguage}
      data-testid="language-toggle"
      aria-label="Changer de langue"
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm border border-white/10 bg-white/[0.04] text-xs font-['Chivo'] font-bold text-[#A1A1AA] hover:text-[#E4FF00] hover:border-[#E4FF00]/40 transition-colors ${className}`}
    >
      <Globe className="w-3 h-3" />
      {language === 'fr' ? 'FR' : 'EN'}
    </button>
  );
}
