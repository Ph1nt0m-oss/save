import React, { useEffect, useRef, useState } from 'react';
import { Check } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';
import { SUPPORTED_LANGS } from '../contexts/LanguageContext';

export default function LanguageToggle({ className = '', placement = 'top' }) {
  const { language, setLanguage } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const current = SUPPORTED_LANGS.find(l => l.code === language) || SUPPORTED_LANGS[1];
  const dropdownPos = placement === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2';

  return (
    <div ref={ref} className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        data-testid="language-toggle"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Changer de langue"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm border border-white/10 bg-white/[0.04] text-xs font-['Chivo'] font-bold text-[#A1A1AA] hover:text-[#E4FF00] hover:border-[#E4FF00]/40 transition-colors"
      >
        <span className="text-base leading-none">{current.flag}</span>
        <span className="hidden sm:inline">{current.label}</span>
        <span className="sm:hidden">{current.native}</span>
      </button>

      {open && (
        <div
          role="listbox"
          data-testid="language-dropdown"
          className={`absolute right-0 ${dropdownPos} w-56 max-h-72 overflow-auto bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_8px_30px_rgba(0,0,0,0.6)] backdrop-blur-xl py-1 z-50`}
        >
          {SUPPORTED_LANGS.map((lang) => (
            <button
              key={lang.code}
              type="button"
              role="option"
              aria-selected={language === lang.code}
              onClick={() => { setLanguage(lang.code); setOpen(false); }}
              data-testid={`language-option-${lang.code}`}
              className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-xs font-['IBM_Plex_Sans'] transition-colors ${
                language === lang.code
                  ? 'text-[#E4FF00] bg-[#E4FF00]/5'
                  : 'text-[#E4E4E7] hover:bg-white/5'
              }`}
            >
              <span className="flex items-center gap-2">
                <span className="text-base leading-none">{lang.flag}</span>
                <span>{lang.label}</span>
              </span>
              {language === lang.code && <Check className="w-3 h-3" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
