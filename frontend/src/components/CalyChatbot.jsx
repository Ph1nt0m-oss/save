/**
 * iter97 — Caly Chatbot : icône bouton dans le header qui ouvre un panel
 * avec un guide d'utilisation du site, FAQ interactive style assistant IA.
 *
 * Logique : Caly est un chatbot dédié à l'aide à l'usage du site (pas un agent
 * de génération de code). Il pose des questions ciblées pour identifier où
 * l'utilisateur bloque puis guide étape par étape.
 */
import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircleQuestion, X, Send, Loader2, Sparkles } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CALY_SYSTEM_PROMPT = `Tu es Caly, l'assistante d'aide à l'utilisation de CodeForge AI — une plateforme zero-code de génération d'applis IA-assistée.

Ton rôle UNIQUE : aider les utilisateurs qui bloquent sur le site.
- Tu poses des questions courtes et précises ("Tu vois tel bouton ?", "Tu es sur mobile ou PC ?")
- Tu guides étape par étape sans jamais coder à la place de l'utilisateur
- Tu ne crées PAS de projet ou de fichier
- Tu reformules les concepts compliqués (vues, modes, signatures, créations) en langage simple
- Tu ne mentionnes JAMAIS d'aspects techniques internes (MongoDB, API endpoints, code...)

Au premier message, propose 3-5 choix : "Je veux créer X", "Je veux modifier Y", "Je ne trouve pas Z", "Aide d'urgence (mon compte)", "Autre question".

Réponds toujours en français, ton chaleureux et concret, max 4 phrases courtes.`;

const QUICK_CHOICES = [
  { id: 'create', label: '🎨 Je veux créer une appli/site' },
  { id: 'modify', label: '✏️ Je veux modifier ma création' },
  { id: 'find', label: '🔍 Je ne trouve pas une fonctionnalité' },
  { id: 'account', label: '🔐 Aide pour mon compte/clé' },
  { id: 'other', label: '💬 Autre question' },
];

export default function CalyChatbot() {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `caly_${Math.random().toString(36).slice(2, 10)}`);
  const endRef = useRef(null);

  useEffect(() => {
    if (open && messages.length === 0) {
      // Premier message de Caly
      setMessages([{
        role: 'caly',
        content: 'Salut ! Je suis Caly, ton assistante CodeForge. Sur quoi tu bloques aujourd\'hui ?',
        choices: QUICK_CHOICES,
      }]);
    }
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [open, messages.length]);

  const send = async (text) => {
    const userMsg = (text || input).trim();
    if (!userMsg || loading) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: userMsg }]);
    setLoading(true);
    try {
      const r = await axios.post(`${API}/chat/message`, {
        message: userMsg,
        session_id: sessionId,
        mode: 'online',
        model: 'gpt-5.2',
        system_prompt: CALY_SYSTEM_PROMPT,
      }, { withCredentials: true });
      const aiText = r?.data?.ai_response?.content || 'Désolée, je n\'ai pas compris. Tu peux reformuler ?';
      setMessages((m) => [...m, { role: 'caly', content: aiText }]);
    } catch {
      setMessages((m) => [...m, { role: 'caly', content: 'Connexion impossible. Réessaie dans un moment.' }]);
    } finally {
      setLoading(false);
    }
  };

  const onChoice = (choice) => {
    const map = {
      create: 'Je veux créer une appli ou un site',
      modify: 'Je veux modifier ma création existante',
      find: 'Je ne trouve pas une fonctionnalité du site',
      account: 'J\'ai besoin d\'aide pour mon compte / ma clé',
      other: 'J\'ai une autre question',
    };
    send(map[choice.id] || choice.label);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid="header-caly-btn"
        title="Caly — Assistante d'aide à l'utilisation"
        className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-pink-500/10 border border-pink-400/40 text-pink-400 hover:bg-pink-500/20 hover:text-pink-300 transition-colors"
      >
        <MessageCircleQuestion className="w-4 h-4" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-2 sm:p-4"
            onClick={() => setOpen(false)}
            data-testid="caly-modal"
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.96, opacity: 0, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg h-[80vh] sm:h-[600px] bg-[#0A0A0A] border border-violet-400/30 rounded-lg shadow-[0_20px_60px_rgba(167,139,250,0.2)] flex flex-col overflow-hidden"
            >
              <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-[#A78BFA] flex items-center justify-center">
                    <Sparkles className="w-4 h-4 text-[#050505]" />
                  </div>
                  <div>
                    <p className="font-['Chivo'] font-bold text-sm text-white">Caly</p>
                    <p className="text-[10px] text-[#A1A1AA]">{t('caly_title') || 'Assistante d\'utilisation'}</p>
                  </div>
                </div>
                <button
                  onClick={() => setOpen(false)}
                  data-testid="caly-close"
                  className="text-[#A1A1AA] hover:text-white p-1"
                >
                  <X className="w-4 h-4" />
                </button>
              </header>

              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {messages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-3 rounded-lg ${
                      m.role === 'user'
                        ? 'bg-[#E4FF00]/10 border border-[#E4FF00]/30 text-white'
                        : 'bg-[#0F0F13] border border-violet-400/20 text-[#E4E4E7]'
                    }`}>
                      <p className="text-xs whitespace-pre-wrap leading-relaxed">{m.content}</p>
                      {m.choices && (
                        <div className="flex flex-col gap-1.5 mt-2.5">
                          {m.choices.map((c) => (
                            <button
                              key={c.id}
                              onClick={() => onChoice(c)}
                              data-testid={`caly-choice-${c.id}`}
                              className="text-left text-[11px] px-2.5 py-1.5 rounded-sm bg-violet-500/10 border border-violet-400/30 text-violet-200 hover:bg-violet-500/20 transition-colors"
                            >
                              {c.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-[#0F0F13] border border-violet-400/20 p-3 rounded-lg flex items-center gap-2">
                      <Loader2 className="w-3 h-3 animate-spin text-violet-300" />
                      <span className="text-[11px] text-[#A1A1AA]">Caly réfléchit…</span>
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>

              <form onSubmit={(e) => { e.preventDefault(); send(); }}
                className="flex items-center gap-2 p-3 border-t border-white/10 bg-white/[0.02]">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Pose ta question…"
                  disabled={loading}
                  data-testid="caly-input"
                  className="flex-1 bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 text-xs text-white placeholder-[#71717A] focus:outline-none focus:border-violet-400"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  data-testid="caly-send"
                  className="bg-violet-500 hover:bg-violet-400 disabled:opacity-40 text-white p-2 rounded-sm transition-colors"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
