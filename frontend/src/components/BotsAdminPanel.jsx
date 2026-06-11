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
import { Bot, Plus, X, Edit3, Trash2, Star, Save, Loader2, Eye, EyeOff, Play, BookOpen, Send } from 'lucide-react';
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

  // iter102 — Playground test bot
  const [testing, setTesting] = useState(null);  // {bot_id, name}
  const [testInput, setTestInput] = useState('');
  const [testReply, setTestReply] = useState('');
  const [testBusy, setTestBusy] = useState(false);

  // iter102 — Knowledge base par bot
  const [kbOpen, setKbOpen] = useState(null);  // {bot_id, name}
  const [kbEntries, setKbEntries] = useState([]);
  const [kbForm, setKbForm] = useState({ question: '', answer: '', entry_id: null });
  const [kbLoading, setKbLoading] = useState(false);

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

  // iter102 — Test bot
  const startTest = (b) => { setTesting({ bot_id: b.bot_id, name: b.name }); setTestInput(''); setTestReply(''); };
  const runTest = async () => {
    if (!testInput.trim() || !testing) return;
    setTestBusy(true); setTestReply('');
    try {
      const body = await withCreatorProof(API, axios, { bot_id: testing.bot_id, user_message: testInput.trim() });
      const r = await axios.post(`${API}/community-bots/test`, body);
      setTestReply(r.data?.reply || '(vide)');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec test bot');
    } finally { setTestBusy(false); }
  };

  // iter102 — Knowledge base
  const openKb = async (b) => {
    setKbOpen({ bot_id: b.bot_id, name: b.name });
    setKbForm({ question: '', answer: '', entry_id: null });
    setKbLoading(true);
    try {
      const r = await axios.get(`${API}/community-bots/knowledge/list?bot_id=${encodeURIComponent(b.bot_id)}`);
      setKbEntries(r.data?.entries || []);
    } catch (e) {
      toast.error('Impossible de charger la KB');
    } finally { setKbLoading(false); }
  };
  const saveKbEntry = async () => {
    if (!kbForm.question.trim() || !kbForm.answer.trim() || !kbOpen) return;
    try {
      const body = await withCreatorProof(API, axios, {
        bot_id: kbOpen.bot_id,
        question: kbForm.question.trim(),
        answer: kbForm.answer.trim(),
        entry_id: kbForm.entry_id || undefined,
      });
      await axios.post(`${API}/community-bots/knowledge/upsert`, body);
      toast.success(kbForm.entry_id ? 'Entrée mise à jour' : 'Entrée ajoutée');
      setKbForm({ question: '', answer: '', entry_id: null });
      openKb(kbOpen);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec sauvegarde KB');
    }
  };
  const deleteKbEntry = async (entry_id) => {
    if (!window.confirm('Supprimer cette entrée ?') || !kbOpen) return;
    try {
      const body = await withCreatorProof(API, axios, { bot_id: kbOpen.bot_id, entry_id });
      await axios.post(`${API}/community-bots/knowledge/delete`, body);
      toast.success('Entrée supprimée');
      openKb(kbOpen);
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
          className="w-full max-w-4xl h-[85vh] bg-[#0A0A0A] border border-white/10 rounded-lg shadow-[0_20px_60px_rgba(0,0,0,0.7)] flex flex-col overflow-hidden relative"
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
                        <button onClick={() => startTest(b)} data-testid={`bot-test-${b.bot_id}`}
                          title="Tester le bot"
                          className="text-[11px] bg-emerald-500/10 border border-emerald-400/30 text-emerald-200 hover:bg-emerald-500/20 px-2 py-1 rounded-sm">
                          <Play className="w-3 h-3" />
                        </button>
                        <button onClick={() => openKb(b)} data-testid={`bot-kb-${b.bot_id}`}
                          title="Base de connaissances (FAQ)"
                          className="text-[11px] bg-cyan-500/10 border border-cyan-400/30 text-cyan-200 hover:bg-cyan-500/20 px-2 py-1 rounded-sm">
                          <BookOpen className="w-3 h-3" />
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

          {/* iter102 — Test bot playground overlay */}
          {testing && (
            <div className="absolute inset-0 bg-black/90 backdrop-blur-sm flex flex-col" data-testid="bot-test-overlay">
              <header className="px-4 py-3 border-b border-white/10 flex items-center justify-between bg-emerald-500/10">
                <div className="flex items-center gap-2">
                  <Play className="w-4 h-4 text-emerald-300" />
                  <h3 className="font-['Chivo'] font-bold text-sm text-white">Tester : {testing.name}</h3>
                </div>
                <button onClick={() => setTesting(null)} data-testid="bot-test-close" className="text-[#A1A1AA] hover:text-white p-1"><X className="w-5 h-5" /></button>
              </header>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <textarea
                  value={testInput}
                  onChange={(e) => setTestInput(e.target.value)}
                  placeholder="Tape un message pour tester le bot…"
                  rows={3}
                  data-testid="bot-test-input"
                  className="w-full bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-400"
                />
                <button onClick={runTest} disabled={testBusy || !testInput.trim()} data-testid="bot-test-run"
                  className="inline-flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-[#050505] font-['Chivo'] font-bold text-xs px-4 py-2 rounded-sm">
                  {testBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Envoyer
                </button>
                {testReply && (
                  <div className="bg-[#0F0F13] border border-emerald-400/30 rounded-sm p-3" data-testid="bot-test-reply">
                    <div className="text-[10px] text-emerald-300 mb-1.5 uppercase tracking-wider">Réponse du bot</div>
                    <p className="text-xs text-white whitespace-pre-wrap">{testReply}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* iter102 — Knowledge Base (FAQ) overlay */}
          {kbOpen && (
            <div className="absolute inset-0 bg-black/90 backdrop-blur-sm flex flex-col" data-testid="bot-kb-overlay">
              <header className="px-4 py-3 border-b border-white/10 flex items-center justify-between bg-cyan-500/10">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-cyan-300" />
                  <h3 className="font-['Chivo'] font-bold text-sm text-white">FAQ : {kbOpen.name}</h3>
                  <span className="text-[10px] text-[#71717A]">({kbEntries.length})</span>
                </div>
                <button onClick={() => setKbOpen(null)} data-testid="bot-kb-close" className="text-[#A1A1AA] hover:text-white p-1"><X className="w-5 h-5" /></button>
              </header>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3 space-y-2">
                  <input
                    value={kbForm.question}
                    onChange={(e) => setKbForm({ ...kbForm, question: e.target.value })}
                    placeholder="Question (≤300 chars)"
                    data-testid="bot-kb-question-input"
                    className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-400"
                  />
                  <textarea
                    value={kbForm.answer}
                    onChange={(e) => setKbForm({ ...kbForm, answer: e.target.value })}
                    placeholder="Réponse (≤2000 chars)"
                    rows={3}
                    data-testid="bot-kb-answer-input"
                    className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-400"
                  />
                  <div className="flex gap-2">
                    <button onClick={saveKbEntry} disabled={!kbForm.question.trim() || !kbForm.answer.trim()} data-testid="bot-kb-save"
                      className="inline-flex items-center gap-1.5 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-[#050505] font-['Chivo'] font-bold text-xs px-4 py-2 rounded-sm">
                      <Save className="w-3.5 h-3.5" /> {kbForm.entry_id ? 'Mettre à jour' : 'Ajouter'}
                    </button>
                    {kbForm.entry_id && (
                      <button onClick={() => setKbForm({ question: '', answer: '', entry_id: null })}
                        className="text-[#A1A1AA] hover:text-white text-xs px-3 py-2">Annuler</button>
                    )}
                  </div>
                </div>
                {kbLoading ? (
                  <div className="text-center py-8"><Loader2 className="w-5 h-5 mx-auto animate-spin text-cyan-300" /></div>
                ) : kbEntries.length === 0 ? (
                  <div className="text-center py-8 text-[#71717A] text-xs">Aucune entrée pour ce bot.</div>
                ) : (
                  <div className="space-y-2" data-testid="bot-kb-list">
                    {kbEntries.map((e) => (
                      <div key={e.entry_id} data-testid={`bot-kb-entry-${e.entry_id}`}
                        className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
                        <div className="text-xs font-bold text-cyan-200 mb-1">Q : {e.question}</div>
                        <div className="text-[11px] text-[#A1A1AA] whitespace-pre-wrap">R : {e.answer}</div>
                        <div className="flex gap-2 mt-2">
                          <button onClick={() => setKbForm({ question: e.question, answer: e.answer, entry_id: e.entry_id })}
                            data-testid={`bot-kb-edit-${e.entry_id}`}
                            className="text-[10px] bg-cyan-500/10 border border-cyan-400/30 text-cyan-200 hover:bg-cyan-500/20 px-2 py-0.5 rounded-sm">
                            Éditer
                          </button>
                          <button onClick={() => deleteKbEntry(e.entry_id)}
                            data-testid={`bot-kb-delete-${e.entry_id}`}
                            className="text-[10px] bg-rose-500/10 border border-rose-400/30 text-rose-200 hover:bg-rose-500/20 px-2 py-0.5 rounded-sm">
                            <Trash2 className="w-2.5 h-2.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
