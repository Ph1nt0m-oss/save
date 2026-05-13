import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { Cpu, ChevronDown, Loader2, Sparkles, Brain, Code, Zap, Globe } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BADGE_ICONS = {
  'Défaut': Sparkles,
  'Thinking': Brain,
  'Code': Code,
  'Multimodal': Globe,
  'Ultra-rapide': Zap,
  'Équilibré': Cpu,
  'Puissant': Brain,
  'Léger': Zap,
  'Généraliste': Sparkles,
  'Multilingue': Globe,
  'Européen': Sparkles,
  'Compact': Cpu,
};

const COLOR_RING = {
  yellow: 'border-yellow-400/40 text-yellow-300',
  amber: 'border-amber-400/40 text-amber-300',
  orange: 'border-orange-400/40 text-orange-300',
  blue: 'border-blue-400/40 text-blue-300',
  cyan: 'border-cyan-400/40 text-cyan-300',
  sky: 'border-sky-400/40 text-sky-300',
  indigo: 'border-indigo-400/40 text-indigo-300',
  purple: 'border-purple-400/40 text-purple-300',
  violet: 'border-violet-400/40 text-violet-300',
  emerald: 'border-emerald-400/40 text-emerald-300',
  teal: 'border-teal-400/40 text-teal-300',
  rose: 'border-rose-400/40 text-rose-300',
  fuchsia: 'border-fuchsia-400/40 text-fuchsia-300',
};

/**
 * Sélecteur de modèle d'IA — sidebar/dropdown.
 * Props :
 *   - mode: 'online' | 'offline'  → choisit la liste à afficher
 *   - context: 'chat' | 'create' → adapte les descriptions au contexte
 *   - value: id du modèle actuellement sélectionné
 *   - onChange: (modelId) => void
 */
export default function ModelPicker({ mode = 'online', context = 'chat', value, onChange }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState({ online: [], offline: [] });
  const boxRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/chat/models?context=${context}`, { withCredentials: true })
      .then((r) => { if (!cancelled) setModels(r.data || { online: [], offline: [] }); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [context]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const list = mode === 'offline' ? (models.offline || []) : (models.online || []);
  const current = list.find((m) => m.id === value) || list[0];

  if (loading) {
    return (
      <div className="inline-flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-sm bg-white/[0.04] border border-white/10">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span className="text-[#A1A1AA]">Modèles…</span>
      </div>
    );
  }
  if (!current) return null;

  const Icon = BADGE_ICONS[current.badge] || Cpu;
  const ringCls = COLOR_RING[current.color] || 'border-white/10 text-[#D4D4D8]';

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid="model-picker-trigger"
        className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-sm bg-white/[0.04] border hover:bg-white/[0.08] transition-colors ${ringCls}`}
        title={`Modèle actuel : ${current.name}`}
      >
        <Icon className="w-3.5 h-3.5" />
        <span className="max-w-[140px] truncate font-['Chivo'] font-bold">{current.name}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1.5 w-[340px] max-h-[60vh] overflow-y-auto bg-[#0A0A0A] border border-white/10 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50"
          data-testid="model-picker-menu"
        >
          <div className="px-3 py-2 border-b border-white/10 text-[10px] uppercase tracking-widest text-[#71717A]">
            {mode === 'offline' ? 'Modèles hors-ligne (Ollama)' : 'Modèles en ligne (Emergent)'}
          </div>
          {list.map((m) => {
            const Mi = BADGE_ICONS[m.badge] || Cpu;
            const ring = COLOR_RING[m.color] || 'text-white';
            const isActive = m.id === value;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => { onChange?.(m.id); setOpen(false); }}
                data-testid={`model-option-${m.id}`}
                className={`w-full text-left px-3 py-2.5 hover:bg-white/[0.04] border-l-2 transition-colors ${
                  isActive ? 'bg-white/[0.03] border-l-[#E4FF00]' : 'border-l-transparent'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Mi className={`w-3.5 h-3.5 ${ring.split(' ')[1] || ''}`} />
                  <span className="text-sm font-['Chivo'] font-bold text-white">{m.name}</span>
                  <span className={`ml-auto text-[10px] uppercase tracking-widest px-1.5 py-0.5 rounded-sm border ${ring}`}>
                    {m.badge}
                  </span>
                </div>
                <div className="text-[11px] text-[#A1A1AA] mt-0.5 pl-5">
                  {m.provider} · {m.description}
                </div>
                {Array.isArray(m.good_for) && m.good_for.length > 0 && (
                  <div className="mt-1 pl-5 flex flex-wrap gap-1">
                    {m.good_for.slice(0, 4).map((g, i) => (
                      <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded-sm bg-white/[0.04] border ${ring}`}>
                        {g}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
          {list.length === 0 && (
            <div className="px-3 py-4 text-xs text-[#71717A]">Aucun modèle disponible.</div>
          )}
        </div>
      )}
    </div>
  );
}
