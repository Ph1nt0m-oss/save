import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { Send, Loader2, ArrowLeft, Sparkles, Pin, Download, X, BookOpen, RotateCcw, Lock, Brain, Cpu } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import VoiceRecorder from '../components/VoiceRecorder';
import AttachMenu from '../components/AttachMenu';
import MessageContent from '../components/MessageContent';
import ModelPicker from '../components/ModelPicker';
import OrchestrationLog from '../components/OrchestrationLog';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import useOrchestrate from '../hooks/useOrchestrate';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Chat() {
  const navigate = useNavigate();
  const location = useLocation();
  const { language, t } = useLanguage();
  const { user } = useAuth();
  const device = useDeviceIdentity();
  const canWrite = device.canWrite;
  const mode = location.state?.mode || 'online';
  const projectFromState = location.state?.project || null;

  // Support linking directly to a chat via ?project=<id>
  const [urlProject, setUrlProject] = useState(null);
  useEffect(() => {
    if (projectFromState?.project_id) return;
    const qp = new URLSearchParams(location.search);
    const pid = qp.get('project');
    if (!pid) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/projects/${pid}`, { withCredentials: true });
        if (!cancelled && r?.data) setUrlProject(r.data);
      } catch {
        if (!cancelled) toast.error('Lien invalide ou discussion supprimée');
      }
    })();
    return () => { cancelled = true; };
  }, [location.search, projectFromState?.project_id]);

  const project = projectFromState || urlProject;
  
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pinning, setPinning] = useState(false);
  // Pending attachments for the NEXT message (analyzed by the backend).
  const [pendingAtts, setPendingAtts] = useState([]); // [{kind, filename, mime_type, content, data_base64}]
  const [analyzingAtt, setAnalyzingAtt] = useState(false);
  // Persistent REPL session — shared across all code blocks in this chat.
  // Same projectId => same Python namespace across messages (Jupyter-style).
  const replSessionId = `repl_${user?.id || user?.email || 'anon'}_${project?.project_id || 'noproj'}`;
  // Selected AI model — defaults differ for online vs offline.
  const [selectedModel, setSelectedModel] = useState(mode === 'offline' ? 'gemma' : 'gpt-5.2');
  const messagesEndRef = useRef(null);

  // iter84 — Mode "Pro" : route les messages via l'orchestrateur multi-agents
  // au lieu du chat classique. L'utilisateur voit les actions en temps réel.
  const [proMode, setProMode] = useState(false);
  const orch = useOrchestrate();

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
          setMessages(r.data.map(m => ({
            ...m,
            download: m.download || null,
            ai_source: m.ai_source || null,
            model_id: m.model_id || null,
            timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
          })));
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
    if (!canWrite) {
      toast.error(t('ro_toast_write'), { id: 'read-only' });
      return;
    }
    const text = input.trim();
    if ((!text && pendingAtts.length === 0) || isLoading) return;
    setInput('');
    await sendText(text || '(pièce jointe)', { attachments: pendingAtts });
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

    // iter84 — Mode Pro : route vers l'orchestrateur multi-agents.
    if (proMode) {
      try {
        await orch.run(userMessage, { projectId: project?.project_id, language });
        // L'orchestrateur affiche les events. On ajoute le final dans la liste
        // des messages aussi pour l'historique chat.
        if (orch.finalAnswer) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: orch.finalAnswer,
            ai_source: 'orchestrator',
            confidence: orch.confidence,
            timestamp: new Date(),
          }]);
        }
      } catch (err) {
        toast.error(err.message || t('error'));
      } finally {
        setIsLoading(false);
      }
      return;
    }

    try {
      const response = await axios.post(
        `${API}/chat/message`,
        {
          message: userMessage,
          mode,
          language,
          model: selectedModel,
          project_id: project?.project_id,
          attachments: opts.attachments || [],
        },
        { withCredentials: true }
      );

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.ai_response.content,
        download: response.data.ai_response.download || null,
        ai_source: response.data.ai_response.ai_source || null,
        model_id: selectedModel,
        timestamp: new Date()
      }]);
      setPendingAtts([]);
      // If backend auto-created a project for this chat (first message case),
      // adopt it locally so the conversation is pinned from the first message.
      const autoPid = response.data.project_id;
      if (autoPid && !project?.project_id) {
        try {
          const pr = await axios.get(`${API}/projects/${autoPid}`, { withCredentials: true });
          if (pr?.data) {
            // Replace the project reference so pinChatToSidebar button hides.
            navigate('/chat', { state: { mode, project: pr.data }, replace: true });
          }
        } catch { /* silent */ }
      }
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
  const handleAttachment = async (att) => {
    if (att.kind === 'text') {
      setInput(prev => (prev ? `${prev} ${att.text}` : att.text));
    } else if (att.kind === 'url') {
      setInput(prev => (prev ? `${prev} ${att.url}` : att.url));
      toast.success('🔗 ' + att.url);
    } else if (att.kind === 'file' && att.file) {
      setAnalyzingAtt(true);
      const t1 = toast.loading(`Analyse de ${att.name}…`);
      try {
        const fd = new FormData();
        fd.append('file', att.file, att.name || att.file.name);
        const r = await axios.post(`${API}/chat/analyze-attachment`, fd, {
          withCredentials: true,
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        setPendingAtts(prev => [...prev, r.data]);
        toast.dismiss(t1);
        toast.success(`📎 ${r.data.filename} — analysé`);
      } catch (err) {
        toast.dismiss(t1);
        toast.error(err.response?.data?.detail || "Analyse impossible");
      } finally {
        setAnalyzingAtt(false);
      }
    }
  };

  const removePendingAtt = (idx) => setPendingAtts(a => a.filter((_, i) => i !== idx));

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
          <div className="flex items-center gap-1.5 flex-shrink-0 ml-auto">
            {/* iter84 — Toggle Mode Pro : route via orchestrateur multi-agents */}
            <button
              onClick={() => setProMode((p) => !p)}
              data-testid="chat-pro-mode-toggle"
              title={proMode ? 'Désactiver le mode Pro (orchestrateur multi-agents)' : 'Activer le mode Pro : l\'IA travaille via 4 agents (Planner → Executor → Critic → Arbiter)'}
              className={`px-2 py-1.5 rounded-sm border text-xs inline-flex items-center gap-1.5 transition-colors ${
                proMode
                  ? 'bg-[#E4FF00]/15 border-[#E4FF00]/60 text-[#E4FF00]'
                  : 'border-white/20 text-[#A1A1AA] hover:text-white hover:border-white/30'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Mode Pro</span>
            </button>
            <ModelPicker mode={mode} value={selectedModel} onChange={setSelectedModel} />
            {/* iter79 — Reset REPL retiré pour le mode Ollama (hors-ligne) sur demande. Conservé pour 'online'. */}
            {mode !== 'offline' && (
              <Button
                onClick={async () => {
                  try {
                    await axios.post(`${API}/sandbox/reset`, { session_id: replSessionId }, { withCredentials: true });
                    toast.success('État REPL réinitialisé');
                  } catch (e) { toast.error('Échec reset REPL'); }
                }}
                variant="ghost" size="sm"
                title="Effacer les variables persistantes du sandbox Python"
                data-testid="chat-repl-reset-btn"
                className="px-2 text-[#A1A1AA] hover:text-white"
              >
                <RotateCcw className="w-4 h-4 sm:mr-1.5" />
                <span className="hidden md:inline text-xs">Reset REPL</span>
              </Button>
            )}
            {project?.project_id && messages.length > 0 && (
              <a
                href={`${API}/chat/export-docx/${project.project_id}`}
                download
                data-testid="chat-export-docx-btn"
                title="Exporter la conversation en .docx (Word)"
                className="inline-flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-sm border border-purple-400/30 text-purple-300 hover:bg-purple-500/10 transition-colors"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Export .docx</span>
              </a>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 max-w-5xl w-full mx-auto flex flex-col p-6">
        {/* iter84 — Journal d'actions de l'orchestrateur (Mode Pro) */}
        {proMode && (orch.events.length > 0 || orch.running) && (
          <div className="mb-4 p-3 bg-[#0A0A0A] border border-[#E4FF00]/30 rounded-sm">
            <div className="flex items-center gap-2 mb-2">
              <Brain className="w-4 h-4 text-[#E4FF00]" />
              <span className="text-xs font-['Chivo'] font-bold text-[#E4FF00]">Journal d&apos;orchestration</span>
              {orch.confidence !== null && (
                <span className="ml-auto text-[10px] text-[#A1A1AA]">Confiance : {orch.confidence}/100</span>
              )}
            </div>
            <OrchestrationLog events={orch.events} running={orch.running} finalAnswer={orch.finalAnswer} />
          </div>
        )}
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
                    <MessageContent content={msg.content} isUser={isUser} replSessionId={replSessionId} />
                    {msg.download && (
                      <a
                        href={`${API}${msg.download.url}`}
                        target="_blank" rel="noopener noreferrer"
                        data-testid="chat-download-link"
                        download={msg.download.filename}
                        className="inline-flex items-center gap-2 mt-3 px-3 py-2 bg-[#E4FF00] hover:bg-[#C8E000] text-[#050505] text-sm font-['Chivo'] font-bold rounded-sm transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        {msg.download.filename}
                      </a>
                    )}
                    {msg.download && (msg.download.mime_type || '').startsWith('image/') && (
                      <img
                        src={`${API}${msg.download.url}`}
                        alt={msg.download.filename}
                        data-testid="chat-download-preview"
                        className="mt-3 max-w-full rounded-sm border border-white/10"
                      />
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      <p className="text-xs text-[#A1A1AA]">
                        {msg.timestamp.toLocaleTimeString('fr-FR')}
                      </p>
                      {!isUser && msg.ai_source && (() => {
                        const src = msg.ai_source || '';
                        // Pretty label from ai_source 'emergent:openai:gpt-5.2' or 'ollama:gemma3:12b'
                        let label = src;
                        if (src.startsWith('emergent:')) {
                          const parts = src.split(':');
                          const prov = parts[1] || '';
                          const mdl = parts.slice(2).join(':') || '';
                          if (prov === 'anthropic') label = mdl.includes('opus') ? 'Claude Opus 4.5' : mdl.includes('sonnet') ? 'Claude Sonnet 4.5' : 'Claude';
                          else if (prov === 'gemini') label = mdl.includes('flash') ? 'Gemini 3 Flash' : 'Gemini 3 Pro';
                          else if (prov === 'openai') label = 'Caly (GPT-5.2)';
                          else label = `${prov} / ${mdl}`;
                        } else if (src.startsWith('ollama:')) {
                          label = `Ollama · ${src.split(':').slice(1).join(':')}`;
                        }
                        return (
                          <span
                            data-testid="msg-ai-badge"
                            title={`Modèle ayant répondu : ${src}`}
                            className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest text-[#71717A] border border-white/10 rounded-sm px-1.5 py-0.5"
                          >
                            {label}
                          </span>
                        );
                      })()}
                    </div>
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
          {!canWrite && (
            <div
              data-testid="chat-readonly-banner"
              className="mb-2 px-3 py-2 bg-white/[0.04] border border-amber-400/30 rounded-sm text-xs text-amber-200 flex items-center gap-2"
            >
              <Lock className="w-3 h-3 flex-shrink-0" />
              <span>{t('ro_chat_banner')}</span>
            </div>
          )}
          {pendingAtts.length > 0 && (
            <div data-testid="chat-pending-atts" className="flex flex-wrap gap-2 mb-2">
              {pendingAtts.map((a, i) => {
                const isImg = a.kind === 'image' && a.data_base64;
                return (
                  <div key={i} className="relative inline-flex items-center gap-2 p-1.5 bg-[#0F0F13] border border-white/10 rounded-sm">
                    {isImg ? (
                      <img
                        src={`data:${a.mime_type || 'image/png'};base64,${a.data_base64}`}
                        alt={a.filename}
                        data-testid={`chat-pending-preview-${i}`}
                        className="w-12 h-12 object-cover rounded-sm border border-white/10"
                      />
                    ) : (
                      <span className="w-12 h-12 flex items-center justify-center text-2xl bg-white/[0.03] border border-white/10 rounded-sm">📄</span>
                    )}
                    <span className="max-w-[140px] truncate text-xs text-[#D4D4D8] px-1">{a.filename}</span>
                    <button type="button" onClick={() => removePendingAtt(i)} className="text-[#A1A1AA] hover:text-red-400 pr-1" title="Retirer">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
              {analyzingAtt && <Loader2 className="w-3.5 h-3.5 animate-spin text-[#E4FF00]" />}
            </div>
          )}
          <div className="flex gap-2 sm:gap-3 items-end">
            <AttachMenu onResult={handleAttachment} disabled={isLoading || analyzingAtt || !canWrite} />
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={canWrite ? t('chatPlaceholder') : t('ro_chat_placeholder')}
              disabled={isLoading || !canWrite}
              rows={1}
              data-testid="chat-input"
              className="flex-1 min-w-0 px-3 sm:px-4 py-3 bg-[#0F0F13] border border-white/20 rounded-lg focus:outline-none disabled:opacity-50 resize-y min-h-[48px] max-h-[200px] font-['IBM_Plex_Sans']"
              style={{ borderColor: input ? modeColor : undefined }}
            />
            <VoiceRecorder mode="dictate" onResult={handleVoiceResult} disabled={isLoading || !canWrite} language={language} />
            <VoiceRecorder mode="send"    onResult={handleVoiceResult} disabled={isLoading || !canWrite} language={language} />
            <Button
              type="submit"
              disabled={isLoading || !input.trim() || !canWrite}
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
