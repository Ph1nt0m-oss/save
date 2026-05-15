import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Bug, Lightbulb, MoreHorizontal, X, Loader2, Send, Inbox, MailCheck } from 'lucide-react';
import { toast } from 'sonner';
import AttachMenu from './AttachMenu';
import { useLanguage } from '../contexts/LanguageContext';
import { withCreatorProof } from '../lib/deviceIdentity';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve(null);
    if (file.size > 4 * 1024 * 1024) {
      toast.error('Fichier > 4 Mo : non envoyé en pièce jointe.');
      return resolve(null);
    }
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Floating yellow round button — present on EVERY page (Login, Landing,
 * Dashboard). Sends feedback (bug / idea / other) into the same /api/ideas
 * collection so creators get notified inside their Ideas inbox.
 *
 * No content limit and an empty submission is accepted (kept as "ping").
 * Once signed (device.keyId available), the user can also browse their
 * own history via the "Mes envois" tab.
 */
export default function FeedbackButton() {
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('send'); // 'send' | 'mine'
  const [type, setType] = useState('suggestion');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [mine, setMine] = useState([]);
  const isCreator = device.role === 'creator';

  // iter77 — Sur demande utilisatrice, le bouton flottant doit rester visible
  // partout, y compris pour la créatrice sur /dashboard (« je peux moi-même
  // noter des trucs pour que le staff les fasse »).
  const hideForCreator = false;

  const TYPES = [
    { key: 'bug', kind: 'bug', label: t('fbBug'), icon: Bug, color: '#FF6B6B' },
    { key: 'suggestion', kind: 'idea', label: t('fbSuggestion'), icon: Lightbulb, color: '#E4FF00' },
    { key: 'other', kind: 'other', label: t('fbOther'), icon: MoreHorizontal, color: '#00D4FF' },
  ];

  const loadMine = useCallback(async () => {
    if (!device.keyId) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/ideas/mine`, body);
      setMine(r.data?.ideas || []);
    } catch (_) { /* silent */ }
  }, [device.keyId]);

  useEffect(() => { if (open && tab === 'mine') loadMine(); }, [open, tab, loadMine]);

  const onAttach = async (att) => {
    if (att.kind === 'file' && att.file) {
      const data_url = await fileToDataUrl(att.file);
      setAttachments(a => [...a, { kind: 'file', name: att.name || att.file.name, data_url }]);
      toast.success('📎 ' + (att.name || att.file.name));
    } else if (att.kind === 'url') {
      setAttachments(a => [...a, { kind: 'url', url: att.url }]);
    } else if (att.kind === 'text') {
      setAttachments(a => [...a, { kind: 'text', text: att.text }]);
    }
  };
  const removeAttachment = (i) => setAttachments(a => a.filter((_, k) => k !== i));

  const submit = async (e) => {
    e?.preventDefault?.();
    setSubmitting(true);
    try {
      const selected = TYPES.find((tt) => tt.key === type) || TYPES[1];
      const contentBody = (message || '').trim();
      // Build a self-contained payload: empty body is accepted per spec.
      // Attachments are folded into the content as a tail block so the
      // creator sees them inline in the Ideas inbox.
      const tail = attachments.length
        ? '\n\n— Pièces jointes —\n' + attachments.map((a) => a.kind === 'url' ? `🔗 ${a.url}` : a.kind === 'text' ? `📋 ${a.text?.slice(0, 500)}` : `📎 ${a.name}`).join('\n')
        : '';
      const fullContent = (contentBody + tail).slice(0, 50000);

      // Sign when possible; fall back to anonymous send for fresh visitors.
      let payload = { content: fullContent, kind: selected.kind, page: window.location.pathname };
      if (device.keyId) {
        try { payload = await withCreatorProof(API, axios, payload); } catch (_) {}
      }
      await axios.post(`${API}/ideas/send`, payload);
      toast.success(t('ideas_sent'));
      setMessage(''); setAttachments([]); setOpen(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('ideas_send_failed'));
    } finally { setSubmitting(false); }
  };

  if (hideForCreator) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="feedback-open-btn"
        aria-label={t('ideas_title')}
        title={t('ideas_title')}
        className="fixed bottom-5 right-5 z-40 w-14 h-14 rounded-full bg-[#E4FF00] text-[#050505] shadow-[0_8px_30px_rgba(228,255,0,0.45)] hover:scale-105 active:scale-95 transition-transform flex items-center justify-center"
      >
        <Lightbulb className="w-6 h-6" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setOpen(false)}
          >
            <motion.div
              initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 20, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 280, damping: 25 }}
              onClick={(e) => e.stopPropagation()}
              data-testid="feedback-modal"
              className="w-full max-w-md max-h-[85vh] bg-[#0A0A0A] border border-white/15 rounded-sm flex flex-col overflow-hidden"
            >
              <header className="px-4 py-3 border-b border-white/10 flex items-center gap-2 flex-shrink-0">
                <Lightbulb className="w-4 h-4 text-[#E4FF00]" />
                <h2 className="text-sm font-['Chivo'] font-bold text-white">{t('ideas_title')}</h2>
                <div className="ml-auto flex items-center gap-1">
                  {device.keyId && (
                    <button
                      type="button" onClick={() => setTab(tab === 'send' ? 'mine' : 'send')}
                      data-testid="feedback-tab-toggle"
                      className={`inline-flex items-center gap-1 px-2 py-1 text-[11px] rounded-sm border transition ${
                        tab === 'mine' ? 'border-[#E4FF00]/40 text-[#E4FF00] bg-[#E4FF00]/10' : 'border-white/15 text-[#A1A1AA]'
                      }`}
                    >
                      <Inbox className="w-3 h-3" />{tab === 'mine' ? 'Envoyer' : 'Mes envois'}
                    </button>
                  )}
                  <button type="button" onClick={() => setOpen(false)} className="text-[#A1A1AA] hover:text-white p-1" data-testid="feedback-close-btn">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </header>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {tab === 'send' && (
                  <form onSubmit={submit} className="space-y-3" data-testid="feedback-form">
                    <div className="grid grid-cols-3 gap-2">
                      {TYPES.map(({ key, label, icon: Icon, color }) => (
                        <button
                          key={key} type="button" onClick={() => setType(key)}
                          data-testid={`feedback-type-${key}`}
                          className={`flex flex-col items-center gap-1 px-2 py-3 border rounded-sm text-xs font-['Chivo'] font-bold transition-all ${
                            type === key ? 'bg-white/[0.06] border-white/30 text-white' : 'bg-transparent border-white/10 text-[#A1A1AA] hover:border-white/20'
                          }`}
                          style={{ color: type === key ? color : undefined }}
                        >
                          <Icon className="w-4 h-4" /> {label.split(' ')[0]}
                        </button>
                      ))}
                    </div>
                    <textarea
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      rows={6}
                      data-testid="feedback-message-input"
                      placeholder={t('ideas_send_placeholder')}
                      className="w-full bg-white/[0.04] border border-white/10 rounded-sm px-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none resize-y"
                    />
                    <div className="flex items-center justify-between">
                      <AttachMenu onResult={onAttach} />
                      <p className="text-[10px] text-[#A1A1AA]/70">{message.length}</p>
                    </div>
                    {attachments.length > 0 && (
                      <div data-testid="feedback-attachments" className="flex flex-wrap gap-1.5">
                        {attachments.map((a, i) => (
                          <span key={i} className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-white/5 border border-white/10 rounded-sm">
                            {a.kind === 'file' ? '📎' : a.kind === 'url' ? '🔗' : '📋'}
                            <span className="max-w-[160px] truncate">{a.name || a.url || 'extrait'}</span>
                            <button type="button" onClick={() => removeAttachment(i)} className="text-[#A1A1AA] hover:text-red-400">×</button>
                          </span>
                        ))}
                      </div>
                    )}
                    <button
                      type="submit" disabled={submitting}
                      data-testid="feedback-submit-btn"
                      className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all disabled:opacity-60"
                    >
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      {t('ideas_send_btn')}
                    </button>
                  </form>
                )}

                {tab === 'mine' && (
                  <>
                    {mine.length === 0 && (
                      <div className="text-xs text-[#A1A1AA] py-6 text-center">Aucun envoi pour l'instant.</div>
                    )}
                    {mine.map((idea) => (
                      <div key={idea.idea_id} data-testid={`mine-${idea.idea_id}`} className="bg-black/30 border border-white/10 rounded-sm p-2.5 space-y-1">
                        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-[#71717A]">
                          <span className="px-1.5 py-0.5 border border-white/15 rounded-sm text-white">{idea.kind || 'idea'}</span>
                          <span>{new Date(idea.ts).toLocaleString()}</span>
                          {idea.read && <span className="inline-flex items-center gap-1 text-emerald-300 ml-auto"><MailCheck className="w-3 h-3" />Lu</span>}
                        </div>
                        <div className="text-xs text-white whitespace-pre-wrap break-words">{idea.content || <em className="text-[#71717A]">(message vide)</em>}</div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
