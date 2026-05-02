import React, { useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircle, Bug, Lightbulb, MoreHorizontal, X, Loader2, Send } from 'lucide-react';
import { toast } from 'sonner';
import AttachMenu from './AttachMenu';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Convert a File into a small data URL (capped at ~4 MB to keep payload sane).
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve(null);
    if (file.size > 4 * 1024 * 1024) {
      toast.error('Fichier > 4 Mo : non envoyé en pièce jointe (le nom est conservé).');
      return resolve(null);
    }
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function FeedbackButton() {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState('suggestion');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [attachments, setAttachments] = useState([]);

  const TYPES_T = [
    { key: 'bug', label: t('fbBug'), icon: Bug, color: '#FF6B6B' },
    { key: 'suggestion', label: t('fbSuggestion'), icon: Lightbulb, color: '#E4FF00' },
    { key: 'other', label: t('fbOther'), icon: MoreHorizontal, color: '#00D4FF' },
  ];

  const onAttach = async (att) => {
    if (att.kind === 'file' && att.file) {
      const dataUrl = await fileToDataUrl(att.file);
      setAttachments(a => [...a, { kind: 'file', name: att.name || att.file.name, data_url: dataUrl }]);
      toast.success('📎 ' + (att.name || att.file.name));
    } else if (att.kind === 'url') {
      setAttachments(a => [...a, { kind: 'url', url: att.url }]);
      toast.success('🔗 ' + att.url);
    } else if (att.kind === 'text') {
      setAttachments(a => [...a, { kind: 'text', text: att.text }]);
      toast.success('📋 Presse-papier ajouté');
    }
  };

  const removeAttachment = (i) => setAttachments(a => a.filter((_, k) => k !== i));

  const submit = async (e) => {
    e.preventDefault();
    if (message.trim().length < 5) return toast.error('Décris au moins 5 caractères');
    setSubmitting(true);
    try {
      await axios.post(`${API}/feedback`, {
        type,
        message: message.trim(),
        page: window.location.pathname,
        attachments,
      });
      toast.success('Merci ! Ton retour a bien été envoyé.');
      setMessage('');
      setAttachments([]);
      setOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur — réessaie.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="feedback-open-btn"
        aria-label="Donner un avis"
        className="fixed bottom-5 right-5 z-40 w-12 h-12 rounded-full bg-[#E4FF00] text-[#050505] shadow-[0_8px_30px_rgba(228,255,0,0.4)] hover:scale-105 active:scale-95 transition-transform flex items-center justify-center"
      >
        <MessageCircle className="w-5 h-5" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setOpen(false)}
          >
            <motion.form
              initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 20, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 280, damping: 25 }}
              onClick={(e) => e.stopPropagation()}
              onSubmit={submit}
              data-testid="feedback-form"
              className="w-full max-w-md bg-[#0A0A0A] border border-white/15 rounded-sm p-6 backdrop-blur-2xl"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-lg font-['Chivo'] font-black text-white">Ton avis nous intéresse</h2>
                  <p className="text-xs text-[#A1A1AA] mt-1">
                    Bug, idée, ou autre — on lit tout. Une réponse n'est pas garantie mais ça nous aide vraiment.
                  </p>
                </div>
                <button type="button" onClick={() => setOpen(false)} data-testid="feedback-close-btn" className="text-[#A1A1AA] hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-4">
                {TYPES.map(({ key, label, icon: Icon, color }) => (
                  <button
                    key={key} type="button" onClick={() => setType(key)}
                    data-testid={`feedback-type-${key}`}
                    className={`flex flex-col items-center gap-1 px-2 py-3 border rounded-sm text-xs font-['Chivo'] font-bold transition-all ${
                      type === key
                        ? 'bg-white/[0.06] border-white/30 text-white'
                        : 'bg-transparent border-white/10 text-[#A1A1AA] hover:border-white/20'
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
                rows={5}
                required
                data-testid="feedback-message-input"
                placeholder="Décris ton retour… Plus tu donnes de détails, mieux on peut t'aider."
                className="w-full bg-white/[0.04] border border-white/10 rounded-sm px-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none resize-y"
              />

              <div className="flex items-center justify-between mt-2">
                <AttachMenu onResult={onAttach} />
                <p className="text-[10px] text-[#A1A1AA]/70">{message.length} caractères</p>
              </div>

              {attachments.length > 0 && (
                <div data-testid="feedback-attachments" className="flex flex-wrap gap-1.5 mt-3">
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
                className="w-full mt-3 inline-flex items-center justify-center gap-2 px-5 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all disabled:opacity-60"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {submitting ? t('fbSending') : t('fbSend')}
              </button>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
