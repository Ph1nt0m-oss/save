import React, { useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircle, Bug, Lightbulb, MoreHorizontal, X, Loader2, Send } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TYPES = [
  { key: 'bug', label: 'Bug / Problème', icon: Bug, color: '#FF6B6B' },
  { key: 'suggestion', label: 'Suggestion', icon: Lightbulb, color: '#E4FF00' },
  { key: 'other', label: 'Autre', icon: MoreHorizontal, color: '#00D4FF' },
];

export default function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState('suggestion');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (message.trim().length < 5) return toast.error('Décris au moins 5 caractères');
    setSubmitting(true);
    try {
      await axios.post(`${API}/feedback`, {
        type,
        message: message.trim(),
        page: window.location.pathname,
      });
      toast.success('Merci ! Ton retour a bien été envoyé.');
      setMessage('');
      setOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur — réessaie.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Floating trigger */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="feedback-open-btn"
        aria-label="Donner un avis"
        className="fixed bottom-20 right-5 z-40 w-12 h-12 rounded-full bg-[#E4FF00] text-[#050505] shadow-[0_8px_30px_rgba(228,255,0,0.4)] hover:scale-105 active:scale-95 transition-transform flex items-center justify-center"
      >
        <MessageCircle className="w-5 h-5" />
      </button>

      {/* Dialog */}
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
                maxLength={5000}
                required
                data-testid="feedback-message-input"
                placeholder="Décris ton retour… Plus tu donnes de détails, mieux on peut t'aider."
                className="w-full bg-white/[0.04] border border-white/10 rounded-sm px-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none resize-none"
              />
              <p className="text-[10px] text-[#A1A1AA]/70 mt-1 text-right">{message.length}/5000</p>

              <button
                type="submit" disabled={submitting}
                data-testid="feedback-submit-btn"
                className="w-full mt-3 inline-flex items-center justify-center gap-2 px-5 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all disabled:opacity-60"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {submitting ? 'Envoi…' : 'Envoyer'}
              </button>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
