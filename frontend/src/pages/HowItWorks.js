import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Cpu, Cloud, WifiOff, Zap, Infinity, Lock, FileCode, Smartphone } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';
import { HOW_I18N } from './HowItWorksContent';

const ICONS = [Infinity, Cloud, WifiOff, Zap, FileCode, Lock, Cpu];
const COLORS = ['#00FF66', '#00D4FF', '#E4FF00', '#E4FF00', '#00FF66', '#00D4FF', '#A1A1AA'];

export default function HowItWorks() {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const L = HOW_I18N[language] || HOW_I18N.en || HOW_I18N.fr;

  return (
    <div className="min-h-screen bg-[#050505] relative overflow-hidden">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="fixed inset-0 grid-bg opacity-10 pointer-events-none"></div>

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-10">
        <div className="flex items-center justify-between mb-8 gap-3">
          <button
            onClick={() => navigate(-1)}
            data-testid="how-back-btn"
            className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> {L.back}
          </button>
          <LanguageToggle placement="bottom" />
        </div>

        <motion.header
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-['Chivo'] font-black text-white leading-tight">
            {L.h1a} <span className="text-[#E4FF00]">{L.h1b}</span>
          </h1>
          <p className="mt-3 text-base text-[#A1A1AA] font-['IBM_Plex_Sans'] max-w-2xl">
            {L.intro}
          </p>
        </motion.header>

        <div className="mt-10 space-y-6">
          {L.sections.map((s, i) => {
            const Icon = ICONS[i] || Cpu;
            const color = COLORS[i] || '#A1A1AA';
            return (
              <motion.section
                key={i}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.05 + i * 0.06, ease: 'easeOut' }}
                className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl"
              >
                <div className="flex items-start gap-4">
                  <div
                    className="w-11 h-11 rounded-sm flex items-center justify-center flex-shrink-0"
                    style={{ background: `${color}20`, border: `1px solid ${color}40` }}
                  >
                    <Icon className="w-5 h-5" style={{ color }} />
                  </div>
                  <div className="flex-1">
                    <h2 className="text-lg sm:text-xl font-['Chivo'] font-bold text-white">{s.title}</h2>
                    <ul className="mt-3 space-y-2 text-sm text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed">
                      {s.points.map((p, idx) => (
                        <li key={idx} className="flex gap-2">
                          <span style={{ color }} className="flex-shrink-0">▸</span>
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </motion.section>
            );
          })}
        </div>

        <div className="mt-10 p-6 bg-[#E4FF00]/10 border border-[#E4FF00]/30 rounded-sm flex items-start gap-4">
          <Smartphone className="w-6 h-6 text-[#E4FF00] flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-white font-['Chivo'] font-bold">{L.ctaTitle}</p>
            <p className="text-sm text-[#A1A1AA] mt-1">{L.ctaText}</p>
            <button
              onClick={() => navigate('/login')}
              data-testid="how-cta-btn"
              className="mt-3 inline-flex items-center gap-2 px-5 py-2.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all"
            >
              {L.ctaBtn}
            </button>
          </div>
        </div>

        <p className="mt-12 text-center text-xs text-[#A1A1AA]/60">
          {L.footer}
        </p>
      </div>
    </div>
  );
}
