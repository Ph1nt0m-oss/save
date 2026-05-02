import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { Send, Loader2, ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import VoiceRecorder from '../components/VoiceRecorder';
import AttachMenu from '../components/AttachMenu';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Chat() {
  const navigate = useNavigate();
  const location = useLocation();
  const { language, t } = useLanguage();
  const { user } = useAuth();
  const mode = location.state?.mode || 'online';
  const project = location.state?.project || null;
  
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pinning, setPinning] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load chat history when a project is provided.
  useEffect(() => {
    if (!project?.project_id) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/chat/history?project_id=${project.project_id}`, { withCredentials: true });
        if (!cancelled && Array.isArray(r.data)) {
          setMessages(r.data.map(m => ({ ...m, timestamp: m.timestamp ? new Date(m.timestamp) : new Date() })));
        }
      } catch (_) { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, [project?.project_id]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    await sendText(text);
  };

  // Pin the current chat to the sidebar by creating a "chat" project linked to this user.
  // The history is automatically tied via project_id on subsequent messages.
  const pinChatToSidebar = async () => {
    if (project?.project_id) { toast.info(t('chatAlreadyPinned')); return; }
    if (messages.length === 0) { toast.error(t('chatPinEmpty')); return; }
    setPinning(true);
    try {
      const firstUserMsg = messages.find(m => m.role === 'user')?.content || 'Discussion';
      const name = firstUserMsg.slice(0, 60).trim();
      const r = await axios.post(`${API}/projects`, {
        name,
        description: t('chatPinDescription'),
        project_type: 'chat',
      }, { withCredentials: true });
      const newProj = r.data;
      // Re-attach existing local messages to the new project_id (best-effort).
      try {
        await Promise.all(messages.map(m => axios.post(`${API}/chat/attach`, {
          message_id: m.message_id || m.id,
          project_id: newProj.project_id,
        }, { withCredentials: true }).catch(() => null)));
      } catch (_) { /* silent */ }
      toast.success(t('chatPinned'));
      navigate('/chat', { state: { mode, project: newProj } });
    } catch (err) {
      toast.error(err.response?.data?.detail || t('error'));
    } finally { setPinning(false); }
  };

  // Shared sender — used by the form, Enter key, and the voice "send" mic.
  const sendText = async (userMessage, opts = {}) => {
    if (!userMessage || isLoading) return;
    setIsLoading(true);
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      isVoice: !!opts.isVoice,
      timestamp: new Date()
    }]);

    try {
      const response = await axios.post(
        `${API}/chat/message`,
        { message: userMessage, mode, language, project_id: project?.project_id },
        { withCredentials: true }
      );

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.ai_response.content,
        timestamp: new Date()
      }]);
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Erreur: Vérifiez qu\'Ollama est installé et en cours d\'exécution.',
        timestamp: new Date()
      }]);
      toast.error('Erreur de chat');
    } finally {
      setIsLoading(false);
    }
  };

  // Bridge between VoiceRecorder and the chat input/sender.
  const handleVoiceResult = (text, autoSend) => {
    if (autoSend) {
      sendText(text, { isVoice: true });
    } else {
      // dictate mode — fill the input for review.
      setInput(prev => (prev ? `${prev} ${text}` : text));
    }
  };

  // Bridge between AttachMenu and the chat input.
  const handleAttachment = (att) => {
    if (att.kind === 'text') {
      setInput(prev => (prev ? `${prev} ${att.text}` : att.text));
    } else if (att.kind === 'url') {
      setInput(prev => (prev ? `${prev} ${att.url}` : att.url));
      toast.success('🔗 ' + att.url);
    } else if (att.kind === 'file') {
      // For now we just append the filename as a tag — full upload pipeline is a P2.
      setInput(prev => (prev ? `${prev} [📎 ${att.name}]` : `[📎 ${att.name}]`));
      toast.success('📎 ' + att.name);
    }
  };

  const modeColor = mode === 'online' ? '#00FF66' : 'cyan';
  const modeLabel = mode === 'online' ? 'EN LIGNE' : 'HORS LIGNE';

  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col">
      <header className="bg-[#0F0F13] border-b border-white/10 px-3 sm:px-6 py-3 sm:py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-2">
          <Button onClick={() => navigate('/dashboard')} variant="ghost" size="sm" className="px-2 sm:px-3 flex-shrink-0" data-testid="chat-back-btn">
            <ArrowLeft className="w-4 h-4 sm:mr-2" />
            <span className="hidden sm:inline">{t('back')}</span>
          </Button>
          {!project?.project_id && messages.length > 0 && (
            <Button
              onClick={pinChatToSidebar}
              disabled={pinning}
              variant="outline" size="sm"
              data-testid="chat-pin-btn"
              className="border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/10 flex-shrink-0"
            >
              {pinning ? <Loader2 className="w-4 h-4 sm:mr-2 animate-spin" /> : <Pin className="w-4 h-4 sm:mr-2" />}
              <span className="hidden sm:inline">{t('chatPinBtn')}</span>
            </Button>
          )}
        </div>
      </header>

      <div className="flex-1 max-w-5xl w-full mx-auto flex flex-col p-6">
        <ScrollArea className="flex-1 mb-6">
          {messages.length === 0 && (
            <div className="text-center py-20">
              <Sparkles className="w-20 h-20 mx-auto mb-6" style={{ color: modeColor }} />
              <h2 className="text-2xl font-['Chivo'] font-bold mb-3">
                {t('chatEmptyTitle')}
              </h2>
              <p className="text-[#A1A1AA] mb-4">
                {mode === 'online' ? t('chatEmptyOnline') : t('chatEmptyOffline')}
              </p>
            </div>
          )}

          <div className="space-y-4">
            {messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <motion.div
                  key={msg.message_id || msg.id || `msg-${msg.timestamp || idx}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex items-start gap-2 sm:gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  {!isUser && (
                    <div className="flex-shrink-0 w-9 h-9 rounded-full bg-[#E4FF00] text-[#050505] flex items-center justify-center font-['Chivo'] font-black text-sm shadow-[0_0_12px_rgba(228,255,0,0.4)]" data-testid="chat-avatar-ai" title="CodeForge AI">
                      <Sparkles className="w-4 h-4" />
                    </div>
                  )}
                  <div
                    className={`max-w-[78%] p-4 rounded-lg ${
                      isUser
                        ? 'bg-[#0F0F13] border border-white/10'
                        : 'bg-[#0F0F13] border-l-2'
                    }`}
                    style={!isUser ? { borderLeftColor: modeColor } : {}}
                  >
                    {/* Visually hidden role prefix — inline in flow so it's INCLUDED when the user copies the conversation. */}
                    <span style={{ fontSize: 0, lineHeight: 0, opacity: 0 }} aria-hidden="true" data-copy-prefix>
                      {isUser ? `${user?.name || user?.email?.split('@')[0] || 'Toi'} : ` : 'CodeForge : '}
                    </span>
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    <p className="text-xs text-[#A1A1AA] mt-2">
                      {msg.timestamp.toLocaleTimeString('fr-FR')}
                    </p>
                  </div>
                  {isUser && (
                    user?.picture ? (
                      <img
                        src={user.picture} alt={user.name || user.email || 'Toi'}
                        data-testid="chat-avatar-user"
                        title={user.name || user.email}
                        className="flex-shrink-0 w-9 h-9 rounded-full border border-white/15 object-cover"
                      />
                    ) : (
                      <div data-testid="chat-avatar-user" title={user?.name || user?.email || 'Toi'}
                        className="flex-shrink-0 w-9 h-9 rounded-full bg-white/10 border border-white/15 flex items-center justify-center text-white font-['Chivo'] font-bold text-sm">
                        {(user?.name || user?.email || '?')[0]?.toUpperCase()}
                      </div>
                    )
                  )}
                </motion.div>
              );
            })}

            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-start gap-2 sm:gap-3 justify-start"
              >
                <div className="flex-shrink-0 w-9 h-9 rounded-full bg-[#E4FF00] text-[#050505] flex items-center justify-center">
                  <Sparkles className="w-4 h-4 animate-pulse" />
                </div>
                <div className="bg-[#0F0F13] border-l-2 p-4 rounded-lg" style={{ borderLeftColor: modeColor }}>
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: modeColor }} />
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <form onSubmit={sendMessage}>
          <div className="flex gap-2 sm:gap-3 items-end">
            <AttachMenu onResult={handleAttachment} disabled={isLoading} />
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('chatPlaceholder')}
              disabled={isLoading}
              rows={1}
              data-testid="chat-input"
              className="flex-1 min-w-0 px-3 sm:px-4 py-3 bg-[#0F0F13] border border-white/20 rounded-lg focus:outline-none disabled:opacity-50 resize-y min-h-[48px] max-h-[200px] font-['IBM_Plex_Sans']"
              style={{ borderColor: input ? modeColor : undefined }}
            />
            <VoiceRecorder mode="dictate" onResult={handleVoiceResult} disabled={isLoading} language={language} />
            <VoiceRecorder mode="send"    onResult={handleVoiceResult} disabled={isLoading} language={language} />
            <Button
              type="submit"
              disabled={isLoading || !input.trim()}
              size="lg"
              className="px-4 sm:px-8 flex-shrink-0"
              style={{ backgroundColor: modeColor, color: '#050505' }}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
