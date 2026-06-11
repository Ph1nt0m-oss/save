/**
 * iter94 — Widget "Agent suggesting enhancements" à la Emergent.
 *
 * Affiche une liste de suggestions d'améliorations proposées par l'orchestrateur,
 * sous forme de cartes interactives avec thumbnail/icône. L'utilisateur peut :
 *   - Retirer une suggestion via le X
 *   - Cliquer sur une suggestion pour la sélectionner
 *   - Valider sa sélection avec "Add to proceed" → callback onProceed(selectedIds)
 *
 * Props :
 *   - suggestions: [{ id, title, description, kind, thumbnail_url? }]
 *     kind ∈ {'feature', 'fix', 'design', 'integration', 'performance'}
 *   - onProceed(selectedIds[]): callback quand l'utilisateur valide
 *   - onSkipAll(): callback quand l'utilisateur ignore tout
 *   - className: optionnel pour le wrapper
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, X, Sparkles, Wand2, Palette, Plug, Zap, ChevronRight, Check } from 'lucide-react';

const KIND_META = {
  feature: {
    icon: Sparkles, label: 'Fonctionnalité',
    bgClass: 'bg-violet-500/10', borderClass: 'border-violet-400/30',
    textClass: 'text-violet-300', selectedBorderClass: 'border-violet-400/60',
    badgeBg: 'bg-violet-500', shadowClass: 'shadow-[0_0_0_1px_rgba(168,85,247,0.2)]',
  },
  fix: {
    icon: Wand2, label: 'Correction',
    bgClass: 'bg-amber-500/10', borderClass: 'border-amber-400/30',
    textClass: 'text-amber-300', selectedBorderClass: 'border-amber-400/60',
    badgeBg: 'bg-amber-500', shadowClass: 'shadow-[0_0_0_1px_rgba(245,158,11,0.2)]',
  },
  design: {
    icon: Palette, label: 'Design',
    bgClass: 'bg-rose-500/10', borderClass: 'border-rose-400/30',
    textClass: 'text-rose-300', selectedBorderClass: 'border-rose-400/60',
    badgeBg: 'bg-rose-500', shadowClass: 'shadow-[0_0_0_1px_rgba(244,63,94,0.2)]',
  },
  integration: {
    icon: Plug, label: 'Intégration',
    bgClass: 'bg-cyan-500/10', borderClass: 'border-cyan-400/30',
    textClass: 'text-cyan-300', selectedBorderClass: 'border-cyan-400/60',
    badgeBg: 'bg-cyan-500', shadowClass: 'shadow-[0_0_0_1px_rgba(34,211,238,0.2)]',
  },
  performance: {
    icon: Zap, label: 'Performance',
    bgClass: 'bg-emerald-500/10', borderClass: 'border-emerald-400/30',
    textClass: 'text-emerald-300', selectedBorderClass: 'border-emerald-400/60',
    badgeBg: 'bg-emerald-500', shadowClass: 'shadow-[0_0_0_1px_rgba(16,185,129,0.2)]',
  },
};

export default function EnhancementSuggestionsWidget({
  suggestions = [],
  onProceed,
  onSkipAll,
  className = '',
}) {
  const [removedIds, setRemovedIds] = useState(new Set());
  const [selectedIds, setSelectedIds] = useState(new Set());

  const visible = suggestions.filter((s) => !removedIds.has(s.id));

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const removeSuggestion = (id, e) => {
    e?.stopPropagation();
    setRemovedIds((prev) => new Set(prev).add(id));
    setSelectedIds((prev) => {
      const n = new Set(prev); n.delete(id); return n;
    });
  };

  const handleProceed = () => {
    if (selectedIds.size === 0 && visible.length > 0) {
      // Auto-sélectionne toutes les visibles si rien n'a été cliqué
      onProceed?.(visible.map((s) => s.id));
    } else {
      onProceed?.(Array.from(selectedIds));
    }
  };

  if (visible.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-gradient-to-br from-violet-500/5 via-[#0F0F13] to-emerald-500/5 border border-white/10 rounded-lg overflow-hidden ${className}`}
      data-testid="enhancement-suggestions-widget"
    >
      <header className="px-4 py-3 border-b border-white/10 bg-white/[0.02] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-300" />
          <span className="text-xs font-['Chivo'] font-bold text-white">
            L&apos;agent suggère des améliorations
          </span>
          <span className="text-[10px] text-[#71717A]">
            ({visible.length} {visible.length > 1 ? 'suggestions' : 'suggestion'})
          </span>
        </div>
        <button
          onClick={() => onSkipAll?.()}
          data-testid="enhancement-skip-all"
          className="text-[10px] text-[#71717A] hover:text-white px-2 py-0.5 transition-colors"
        >
          Tout ignorer
        </button>
      </header>

      <div className="p-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        <AnimatePresence>
          {visible.map((s) => {
            const meta = KIND_META[s.kind] || KIND_META.feature;
            const Icon = meta.icon;
            const isSelected = selectedIds.has(s.id);
            return (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, scale: 0.92 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.92, transition: { duration: 0.15 } }}
                layout
                onClick={() => toggleSelect(s.id)}
                data-testid={`enhancement-card-${s.id}`}
                className={`relative bg-[#0A0A0A] border rounded-sm p-3 cursor-pointer transition-all ${
                  isSelected ? `${meta.selectedBorderClass} ${meta.shadowClass}` : 'border-white/10 hover:border-white/20'
                }`}
              >
                {/* Thumbnail or icon */}
                <div className="flex items-start gap-2.5 mb-2">
                  {s.thumbnail_url ? (
                    <img
                      src={s.thumbnail_url}
                      alt={s.title}
                      className="w-10 h-10 rounded-sm object-cover flex-shrink-0 border border-white/10"
                    />
                  ) : (
                    <div className={`w-10 h-10 rounded-sm flex items-center justify-center flex-shrink-0 ${meta.bgClass} border ${meta.borderClass}`}>
                      <Icon className={`w-4 h-4 ${meta.textClass}`} />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <span className={`text-[9px] uppercase tracking-widest ${meta.textClass} font-['Chivo'] font-bold`}>
                      {meta.label}
                    </span>
                    <h3 className="text-xs font-['Chivo'] font-bold text-white leading-tight mt-0.5 line-clamp-2">
                      {s.title}
                    </h3>
                  </div>
                  <button
                    onClick={(e) => removeSuggestion(s.id, e)}
                    data-testid={`enhancement-remove-${s.id}`}
                    title="Retirer cette suggestion"
                    className="text-[#71717A] hover:text-rose-400 p-0.5 flex-shrink-0"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                {s.description && (
                  <p className="text-[11px] text-[#A1A1AA] leading-snug line-clamp-3">{s.description}</p>
                )}
                {isSelected && (
                  <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className={`absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full ${meta.badgeBg} border-2 border-[#0A0A0A] flex items-center justify-center`}
                  >
                    <Check className="w-3 h-3 text-[#050505]" />
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      <footer className="px-4 py-2.5 border-t border-white/10 bg-white/[0.02] flex items-center justify-between">
        <span className="text-[10px] text-[#71717A]">
          {selectedIds.size > 0
            ? `${selectedIds.size} sélectionnée${selectedIds.size > 1 ? 's' : ''}`
            : 'Clique sur une carte pour la sélectionner'}
        </span>
        <button
          onClick={handleProceed}
          data-testid="enhancement-proceed-btn"
          className="inline-flex items-center gap-1.5 bg-[#E4FF00] hover:bg-[#C8E000] text-[#050505] font-['Chivo'] font-bold text-xs px-3 py-1.5 rounded-sm transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Ajouter pour continuer
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </footer>
    </motion.div>
  );
}
