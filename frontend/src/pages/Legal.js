import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, FileText, Shield, Cookie } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';
import { LEGAL_I18N } from './LegalContent';

export default function Legal() {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get('tab') || 'cgu');

  const L = LEGAL_I18N[language] || LEGAL_I18N.en || LEGAL_I18N.fr;

  const TABS = [
    { key: 'cgu', label: L.tab_cgu, icon: FileText },
    { key: 'privacy', label: L.tab_privacy, icon: Shield },
    { key: 'cookies', label: L.tab_cookies, icon: Cookie },
  ];

  return (
    <div className="min-h-screen bg-[#050505] relative">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="relative z-10 max-w-3xl mx-auto px-4 py-10">
        <div className="flex items-center justify-between mb-6 gap-3">
          <button
            onClick={() => navigate(-1)}
            data-testid="legal-back-btn"
            className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> {L.back}
          </button>
          <LanguageToggle placement="bottom" />
        </div>

        <motion.h1
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="text-3xl sm:text-4xl font-['Chivo'] font-black text-white"
        >
          {L.title}
        </motion.h1>
        <p className="text-sm text-[#A1A1AA] mt-1">{L.updated}</p>

        <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              data-testid={`legal-tab-${key}`}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-['Chivo'] font-bold border-b-2 -mb-px transition-colors ${
                tab === key ? 'text-[#E4FF00] border-[#E4FF00]' : 'text-[#A1A1AA] border-transparent hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        <div className="mt-6 bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed text-sm space-y-4">
          {tab === 'cgu' && <Section data-testid="legal-cgu" sections={L.cgu} />}
          {tab === 'privacy' && <Section data-testid="legal-privacy" sections={L.privacy} />}
          {tab === 'cookies' && <Section data-testid="legal-cookies" sections={L.cookies} />}
        </div>
      </div>
    </div>
  );
}

const Section = ({ sections, ...rest }) => (
  <div className="space-y-3" {...rest}>
    {sections.map((s, i) => (
      <div key={i}>
        {s.h && <h2 className="text-base font-['Chivo'] font-bold text-white mt-5">{s.h}</h2>}
        {s.p && <p className="mt-1">{s.p}</p>}
        {s.ul && (
          <ul className="list-disc pl-5 space-y-1 mt-1">
            {s.ul.map((li, k) => <li key={k} dangerouslySetInnerHTML={{ __html: li }} />)}
          </ul>
        )}
      </div>
    ))}
  </div>
);
