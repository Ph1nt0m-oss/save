import React from 'react';
import { motion } from 'framer-motion';
import { Wand2, Sparkles, Plus } from 'lucide-react';

/**
 * Designed empty state shown on the Dashboard when the user has zero projects.
 * Two CTAs: open the Wizard (recommended) or start free creation.
 */
export default function EmptyProjectsState({ onWizard, onCreate }) {
  return (
    <motion.div
      data-testid="empty-projects-state"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="relative max-w-3xl w-full mx-auto"
    >
      {/* Glow background */}
      <div className="absolute -inset-32 bg-gradient-to-br from-[#E4FF00]/10 via-transparent to-[#00FF66]/10 blur-3xl pointer-events-none"></div>

      <div className="relative bg-white/[0.03] border border-white/10 rounded-lg backdrop-blur-xl p-10 sm:p-14 text-center shadow-[0_8px_30px_rgba(0,0,0,0.4)]">
        {/* SVG illustration: stylized blueprint/forge */}
        <div className="relative mx-auto w-40 h-40 mb-6">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 28, repeat: Infinity, ease: 'linear' }}
            className="absolute inset-0"
          >
            <svg viewBox="0 0 100 100" className="w-full h-full" fill="none">
              <circle cx="50" cy="50" r="42" stroke="#E4FF00" strokeWidth="0.5" strokeDasharray="2 4" opacity="0.5" />
              <circle cx="50" cy="50" r="34" stroke="#00FF66" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.4" />
            </svg>
          </motion.div>
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              className="w-24 h-24 bg-[#E4FF00] rounded-sm flex items-center justify-center shadow-[0_0_60px_rgba(228,255,0,0.4)]"
            >
              <Sparkles className="w-12 h-12 text-[#050505]" strokeWidth={2.5} />
            </motion.div>
          </div>
        </div>

        <h3 className="text-3xl sm:text-4xl font-['Chivo'] font-black text-white mb-3">
          Ton premier chef-d'œuvre t'attend
        </h3>
        <p className="text-[#A1A1AA] font-['IBM_Plex_Sans'] max-w-lg mx-auto mb-8">
          Aucun projet pour l'instant. Décris ton idée en quelques mots, ou laisse-toi guider par l'assistant.
          Mobile, web, desktop — CodeForge s'occupe du code.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={onWizard}
            data-testid="empty-state-wizard-cta"
            data-tour="wizard"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all"
          >
            <Wand2 className="w-5 h-5" />
            Lancer l'assistant guidé
          </button>
          <button
            onClick={onCreate}
            data-testid="empty-state-create-cta"
            data-tour="create"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-transparent border border-white/20 text-white font-['Chivo'] font-bold rounded-sm hover:border-[#00FF66] hover:text-[#00FF66] hover:-translate-y-0.5 transition-all"
          >
            <Plus className="w-5 h-5" />
            Créer librement
          </button>
        </div>
      </div>
    </motion.div>
  );
}
