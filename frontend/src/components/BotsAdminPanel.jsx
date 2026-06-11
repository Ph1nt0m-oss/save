/**
 * iter99 — Panel admin pour gérer les Community Bots façon Top.gg.
 *
 * Admins peuvent : créer, éditer, publier, supprimer leurs bots.
 * Créatrice peut : voir tous les bots, en supprimer n'importe lequel.
 * Tout le monde peut : voir la liste publique + noter (1-5 étoiles).
 *
 * Usage :
 *   <BotsAdminPanel open={open} onClose={...} />
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Plus, X, Edit3, Trash2, Star, Save, Loader2, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KIND_LABELS = {
  assistance: { label: '🤝 Assistance', color: 'cyan' },
  animation: { label: '🎉 Animation', color: 'violet' },
  jeu: { label: '🎮 Jeu', color: 'amber' },
  information: { label: '📰 Information', color: 'emerald' },
  modération: { label: '🛡️ Modération', color: 'rose' },
};

export default function BotsAdminPanel({ open, onClose }) {
  const { t } = useLanguage();
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);  // null = liste, {} = nouveau, {bot} = edit
  const [form, setForm] = useState({ name: '', description: '', kind: 'assistance', prompt: '', triggers: '', is_published: false });

  const loadBots = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/community-bots/list?only_published=false`);
      setBots(r.data?.bots || []);
    } catch (e) {
      toast.error('Impossible de charger les bots');
    } finally { setLoading(false); }
  };

  useEffect(() => { if (open) loadBots(); }, [open]);

  const startNew = () => {
    setForm({ name: '', description: '', kind: 'assistance', prompt: '', triggers: '', is_published: false });
    setEditing({});
  };

  const startEdit = (b) => {
    setForm({
      name: b.name || '', description: b.description || '', kind: b.kind || 'assistance',
      prompt: b.prompt || '', triggers: (b.triggers || []).join(', '), is_published: !!b.is_published,
    });
    setEditing(b);
  };

  const saveForm = async () => {
    if (!form.name.trim() || !form.prompt.trim()) {
      toast.error('Nom + prompt requis');
      return;
    }
    try {
      const body = await withCreatorProof(API, axios, {
        bot_id: editing?.bot_id || undefined,
        name: form.name.trim(),
        description: form.description.trim(),
        kind: form.kind,
        prompt: form.prompt.trim(),
        triggers: form.triggers.split(',').map(t => t.trim()).filter(Boolean),
        is_published: form.is_published,
      });
      await axios.post(`${API}/community-bots/create`, body);
      toast.success(editing?.bot_id ? 'Bot mis à jour' : 'Bot créé');
      setEditing(null);
      loadBots();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec sauvegarde');
    }
  };

  const deleteBot = async (bot_id) => {
    if (!window.confirm('Supprimer ce bot définitivement ?')) return;
    try {
      const body = await withCreatorProof(API, axios, { bot_id });
      await axios.post(`${API}/community-bots/delete`, body);
      toast.success('Bot supprimé');
      loadBots();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec suppression');
    }
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-3"
        onClick={onClose}
        data-testid="bots-admin-panel"
      >
        <motion.div
          initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-4xl h-[85vh] bg-[#0A0A0A] border border-white/10 rounded-lg shadow-[0_20px_60px_rgba(0,0,0,0.7)] flex flex-col overflow-hidden"
        >
          <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-gradient-to-r from-violet-500/10 to-cyan-500/10">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-violet-300" />
              <h2 className="font-['Chivo'] font-bold text-white text-sm">{t('bots_community_title') || 'Communauté de bots'}</h2>
              <span className="text-[10px] text-[#71717A]">({bots.length})</span>
            </div>
            <div className="flex items-center gap-2">
              {editing === null && (
                <button onClick={startNew} data-testid="bots-new-btn"
                  className="inline-flex items-center gap-1.5 bg-violet-500 hover:bg-violet-400 text-white text-xs font-['Chivo'] font-bold px-3 py-1.5 rounded-sm">
                  <Plus className="w-3.5 h-3.5" /> Nouveau bot
                </button>
              )}
              <button onClick={onClose} data-testid="bots-admin-close" className="text-[#A1A1AA] hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto p-3">
            {editing !== null ? (
              <div className="space-y-3" data-testid="bots-edit-form">
                <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                  placeholder="Nom du bot (ex: AnimateurDeQuiz)" data-testid="bot-name-input"
                  className="w-full bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-400" />
                <textarea value={form.description} onChange={(e) => setForm({...form, description: e.target.value})}
                  placeholder="Description courte (≤500 chars)" rows={2} data-testid="bot-description-input"
                  className="w-full bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-xs text-white focus:outline-none focus:border-violet-400" />
                <select value={form.kind} onChange={(e) => setForm({...form, kind: e.target.value})} data-testid="bot-kind-select"
                  className="w-full bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-xs text-white">
                  {Object.entries(KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                <textarea value={form.prompt} onChange={(e) => setForm({...form, prompt: e.target.value})}
                  placeholder="System prompt : définit la personnalité et le comportement du bot…" rows={6} data-testid="bot-prompt-input"
                  className="w-full bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-violet-400" />
                <input value={form.triggers} onChange={(e) => setForm({...form, triggers: e.target.value})}
                  placeholder="Mots-clés déclencheurs (séparés par virgule)" data-testid="bot-triggers-input"
                  className="w-full bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-xs text-white focus:outline-none focus:border-violet-400" />
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" checked={form.is_published} onChange={(e) => setForm({...form, is_published: e.target.checked})}
                    data-testid="bot-published-toggle" className="accent-violet-500" />
                  <span className="text-[#A1A1AA]">Publier (visible par la communauté)</span>
                </label>
                <div className="flex gap-2 pt-2">
                  <button onClick={saveForm} data-testid="bot-save-btn"
                    className="inline-flex items-center gap-1.5 bg-[#E4FF00] hover:bg-[#C8E000] text-[#050505] font-['Chivo'] font-bold text-xs px-4 py-2 rounded-sm">
                    <Save className="w-3.5 h-3.5" /> Sauvegarder
                  </button>
                  <button onClick={() => setEditing(null)} className="text-[#A1A1AA] hover:text-white text-xs px-3 py-2">
                    Annuler
                  </button>
                </div>
              </div>
            ) : loading ? (
              <div className="text-center py-12">
                <Loader2 className="w-6 h-6 mx-auto animate-spin text-violet-300" />
              </div>
            ) : bots.length === 0 ? (
              <div className="text-center py-12 text-[#71717A] text-sm">
                Aucun bot pour l&apos;instant. Crée le premier !
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2" data-testid="bots-list">
                {bots.map((b) => {
                  const kind = KIND_LABELS[b.kind] || KIND_LABELS.assistance;
                  return (
                    <div key={b.bot_id} data-testid={`bot-card-${b.bot_id}`}
                      className="bg-[#0F0F13] border border-white/10 rounded-sm p-3 flex flex-col gap-2 hover:border-violet-400/40 transition-colors">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-['Chivo'] font-bold text-sm text-white flex-1 truncate">{b.name}</h3>
                        <span className="text-[10px] text-[#71717A] flex-shrink-0">{kind.label}</span>
                      </div>
                      <p className="text-[11px] text-[#A1A1AA] line-clamp-3 min-h-[3em]">{b.description || '(pas de description)'}</p>
                      <div className="flex items-center justify-between text-[10px] text-[#71717A]">
                        <span className="flex items-center gap-1">
                          {b.is_published ? <Eye className="w-3 h-3 text-emerald-400" /> : <EyeOff className="w-3 h-3" />}
                          {b.is_published ? 'Publié' : 'Brouillon'}
                        </span>
                        {b.avg_rating !== null && (
                          <span className="flex items-center gap-0.5">
                            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                            {b.avg_rating} ({b.rating_count})
                          </span>
                        )}
                      </div>
                      <div className="flex gap-1.5 mt-1">
                        <button onClick={() => startEdit(b)} data-testid={`bot-edit-${b.bot_id}`}
                          className="flex-1 text-[11px] bg-violet-500/10 border border-violet-400/30 text-violet-200 hover:bg-violet-500/20 px-2 py-1 rounded-sm inline-flex items-center justify-center gap-1">
                          <Edit3 className="w-3 h-3" /> Modifier
                        </button>
                        <button onClick={() => deleteBot(b.bot_id)} data-testid={`bot-delete-${b.bot_id}`}
                          className="text-[11px] bg-rose-500/10 border border-rose-400/30 text-rose-200 hover:bg-rose-500/20 px-2 py-1 rounded-sm">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
