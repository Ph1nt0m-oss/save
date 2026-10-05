import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { Send, Loader2, ArrowLeft, Sparkles, Pin, Download, Upload, X, BookOpen, RotateCcw, Lock, Brain, Cpu, Languages } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import VoiceRecorder from '../components/VoiceRecorder';
import AttachMenu from '../components/AttachMenu';
import MessageContent from '../components/MessageContent';
import ModelPicker from '../components/ModelPicker';
import OrchestrationLog from '../components/OrchestrationLog';
import AgentActivityLog from '../components/AgentActivityLog';
import OfflineAIInstaller from '../components/OfflineAIInstaller';
import LivePreviewPanel from '../components/LivePreviewPanel';
import CreatorChatPersonaBar, { useCreatorChatPersona } from '../components/CreatorChatPersonaBar';
import MessageTTSButton from '../components/MessageTTSButton';
import TypewriterEffect from '../components/TypewriterEffect';
import { useTranslatedMessages } from '../hooks/useTranslatedMessages';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import useOrchestrate from '../hooks/useOrchestrate';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { useCache } from '../contexts/CacheContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Chat() {
  const navigate = useNavigate();
  const location = useLocation();
  const { language, t } = useLanguage();
  const { user } = useAuth();
  const { cacheChatHistory, getCachedChatHistory } = useCache();
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
  // Chantier iter159 §2 — État IA réel (reflète le vrai pipeline backend) :
  //  - idle     : rien en cours ;
  //  - sending  : requête envoyée, pas encore de premier token ;
  //  - streaming: on reçoit des deltas (l'IA écrit) ;
  //  - error    : échec réseau/pipeline ;
  //  - cancelled: abandon utilisateur (futur).
  // Ces états sont STRICTEMENT dérivés d'événements réels (fetch, SSE deltas,
  // event `done`, exception). Aucun timer artificiel.
  const [aiRealState, setAiRealState] = useState('idle');
  // iter128.6 — Persona créa-only (3 personas + toggles IA répond / visible).
  // Par défaut : id='ai', aiReplies=true, visible=true → comportement inchangé
  // pour tous les rôles non-créa et même créa tant qu'elle ne touche pas la barre.
  const [creatorPersona, setCreatorPersona] = useCreatorChatPersona();
  const [historyLoading, setHistoryLoading] = useState(false);
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

  // iter96 — Mode Pro retiré sur demande utilisatrice. orchestrateur multi-agents reste disponible via /chat/orchestrate-stream pour les flows GuidedWizard.
  const [proMode] = useState(false);
  const orch = useOrchestrate();

  // iter94 — Traduction dynamique des contenus de messages selon langue UI.
  // Cache localStorage + cache MongoDB côté backend.
  const translatedMessages = useTranslatedMessages(messages, { enabled: true, defaultLang: 'fr' });

  // iter98 — Preview interactive (œil sous chaque création depuis Dashboard sidebar)
  const [showCreationPreview, setShowCreationPreview] = useState(() => {
    return Boolean(location.state?.openPreview);
  });

  // iter102 — Retrait des suggestions d'améliorations à la demande utilisatrice
  // ("c'est chiant de tjrs cliquer sur fermer"). Le widget et l'appel LLM
  // /chat/suggest-enhancements sont désactivés côté UI.
  // iter90 — Mode hors-ligne : auto-détecte Ollama + propose le tuto si absent.
  // Chantier iter160 §8 — DÉTECTION DÉPLACÉE CÔTÉ NAVIGATEUR.
  // Le backend tourne dans un pod isolé, son `localhost:11434` ne voit PAS
  // la machine de l'utilisateur. Le browser `fetch('http://localhost:11434')`
  // teste bien l'Ollama LOCAL de l'utilisateur (CORS activé par Ollama).
  // Chantier iter160 §11 — Exemption Créa / Créa propriétaire / Admin.
  const [showOfflineInstaller, setShowOfflineInstaller] = useState(false);
  // iter160 §11 — Un Créa/Admin n'est PAS verrouillé par l'absence d'Ollama.
  const isCreatorOrAdmin = (() => {
    const r = device?.role;
    const sk = device?.staff_kind;
    return r === 'creator' || sk === 'admin';
  })();
  const [ollamaAvailable, setOllamaAvailable] = useState(mode !== 'offline' || isCreatorOrAdmin);
  const [ollamaChecking, setOllamaChecking] = useState(mode === 'offline' && !isCreatorOrAdmin);
  const [ollamaDiag, setOllamaDiag] = useState(null); // {state, model, models}
  useEffect(() => {
    // Créa/Admin : jamais de verrou offline.
    if (mode !== 'offline' || isCreatorOrAdmin) {
      setOllamaAvailable(true); setOllamaChecking(false); return;
    }
    let cancelled = false;
    // Whitelist modèles chat compatibles (miroir côté backend).
    const RECOMMENDED = [
      'gemma3:4b', 'gemma3:2b', 'deepseek-r1:7b',
      'llama3.2', 'llama3.2:3b', 'llama3.2:8b',
      'gemma3:latest', 'gemma:latest', 'llama3:latest',
    ];
    const isRecommended = (name) => {
      if (!name) return false;
      if (RECOMMENDED.includes(name)) return true;
      // Match par préfixe de famille (gemma3:anything compte comme gemma3).
      return RECOMMENDED.some((x) => name.startsWith(x.split(':')[0] + ':'));
    };
    const check = async () => {
      // Chantier iter160 §8 — Détection RÉELLE côté user agent.
      // On tente directement http://localhost:11434/api/tags. CORS est
      // autorisé par Ollama (il envoie Access-Control-Allow-Origin: *).
      try {
        const r = await fetch('http://localhost:11434/api/tags', {
          method: 'GET',
          cache: 'no-store',
          signal: AbortSignal.timeout(3000),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        const installed = (data.models || []).map((m) => m.name).filter(Boolean);
        const recHit = installed.find(isRecommended) || null;
        if (cancelled) return;
        const ok = !!recHit;
        setOllamaDiag({ state: installed.length ? (ok ? 'ready' : 'no_compatible_model') : 'empty', model: recHit, models: installed });
        setOllamaAvailable((prev) => {
          if (!prev && ok) {
            try { toast.success('IA locale détectée — déverrouillage automatique.'); } catch (_) {}
          }
          return ok;
        });
        setOllamaChecking(false);
      } catch (err) {
        if (cancelled) return;
        setOllamaDiag({ state: 'unreachable', model: null, models: [] });
        setOllamaAvailable(false);
        setOllamaChecking(false);
      }
    };
    check();
    const iv = setInterval(check, 10000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [mode, isCreatorOrAdmin]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load chat history when a project is provided.
  // iter102 — Latence 0ms : hydrate INSTANTANÉMENT depuis le cache localStorage
  // (cacheChatHistory du CacheContext), puis fetch en arrière-plan et remplace
  // silencieusement. Plus jamais de flash blanc/spinner pour les chats déjà visités.
  useEffect(() => {
    if (!project?.project_id) {
      // Pas de projet → conversation neuve, on s'assure que le state est vierge.
      setMessages([]);
      setHistoryLoading(false);
      return;
    }
    let cancelled = false;
    const pid = project.project_id;

    // 1) Hydratation instantanée depuis le cache (0ms perçus)
    const cached = getCachedChatHistory(pid);
    if (Array.isArray(cached) && cached.length > 0) {
      setMessages(cached.map(m => ({
        ...m,
        timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
      })));
      setHistoryLoading(false);
    } else {
      // Pas de cache → spinner + reset visuel
      setMessages([]);
      setHistoryLoading(true);
    }

    // 2) Refresh silencieux en arrière-plan
    (async () => {
      try {
        const r = await axios.get(`${API}/chat/history?project_id=${pid}&limit=500`, { withCredentials: true });
        if (!cancelled && Array.isArray(r.data)) {
          const hydrated = r.data.map(m => ({
            ...m,
            download: m.download || null,
            ai_source: m.ai_source || null,
            model_id: m.model_id || null,
            timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
          }));
          setMessages(hydrated);
          // Persiste pour les prochains clics (timestamps ISO pour JSON-safe)
          try {
            cacheChatHistory(pid, hydrated.map(m => ({
              ...m,
              timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
            })));
          } catch { /* silent */ }
        }
      } catch (_) { /* silent */ }
      finally { if (!cancelled) setHistoryLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [project?.project_id, cacheChatHistory, getCachedChatHistory]);

  // iter102 — Cache live : persiste messages dès qu'ils changent (incluant l'IA qui répond)
  // pour que le prochain clic sidebar soit instantané, même après une nouvelle conversation.
  useEffect(() => {
    const pid = project?.project_id;
    if (!pid || messages.length === 0) return;
    try {
      cacheChatHistory(pid, messages.map(m => ({
        ...m,
        timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
        _just_arrived: undefined,  // ne pas cacher le flag d'animation typewriter
      })));
    } catch { /* silent */ }
  }, [messages, project?.project_id, cacheChatHistory]);

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

  // iter131 — Détecter si Forge a créé des fichiers workspace pour ce projet.
  const [workspaceCount, setWorkspaceCount] = useState(0);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  useEffect(() => {
    const pid = project?.project_id;
    if (!pid) { setWorkspaceCount(0); return; }
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/workspace/list/${pid}`, { withCredentials: true });
        if (!cancelled) setWorkspaceCount(r.data?.count || 0);
      } catch { if (!cancelled) setWorkspaceCount(0); }
    })();
    return () => { cancelled = true; };
  }, [project?.project_id, messages.length]);

  const downloadWorkspace = async () => {
    const pid = project?.project_id;
    if (!pid) return;
    setWorkspaceBusy(true);
    try {
      const r = await axios.get(`${API}/workspace/download/${pid}`, {
        withCredentials: true, responseType: 'blob',
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `forge-workspace-${pid.slice(0, 12)}.zip`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${workspaceCount} fichier(s) Forge téléchargé(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Téléchargement impossible.');
    } finally {
      setWorkspaceBusy(false);
    }
  };

  // iter132 — Import workspace : ré-upload d'un ZIP Forge modifié.
  const workspaceImportInputRef = useRef(null);
  const importWorkspace = async (file) => {
    const pid = project?.project_id;
    if (!pid || !file) return;
    if (!file.name.toLowerCase().endsWith('.zip')) {
      toast.error('Sélectionne un fichier .zip');
      return;
    }
    setWorkspaceBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await axios.post(`${API}/workspace/import/${pid}`, fd, {
        withCredentials: true, headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(`${r.data?.files || 0} fichier(s) importé(s) dans le workspace Forge.`);
      // Refresh count
      try {
        const rl = await axios.get(`${API}/workspace/list/${pid}`, { withCredentials: true });
        setWorkspaceCount(rl.data?.count || 0);
      } catch { /* ignore */ }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import impossible.');
    } finally {
      setWorkspaceBusy(false);
      if (workspaceImportInputRef.current) workspaceImportInputRef.current.value = '';
    }
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
    // Chantier iter160 §11 — Créa/Admin : jamais de verrou offline.
    if (mode === 'offline' && !ollamaAvailable && !isCreatorOrAdmin) {
      toast.error('IA locale non détectée — tout est bloqué.');
      return;
    }
    setIsLoading(true);
    setAiRealState('sending');  // Chantier §2 — vrai état backend
    // iter131 — Créa persona : attache l'identité choisie sur le message user
    // (avatar/pseudo custom + flag "fantôme" si visible=false).
    const isCreatorSelfPosing =
      device.role === 'creator' &&
      (!device.viewMode || device.viewMode === 'creator') &&
      creatorPersona && creatorPersona.id && creatorPersona.id !== 'ai';
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      isVoice: !!opts.isVoice,
      persona_id: isCreatorSelfPosing ? creatorPersona.id : null,
      persona_pseudo: isCreatorSelfPosing ? (creatorPersona.customPseudo || null) : null,
      persona_avatar: isCreatorSelfPosing ? (creatorPersona.customAvatar || null) : null,
      visible_to_target: creatorPersona ? creatorPersona.visible !== false : true,
      _just_sent_user: true,
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
      // iter111 — Streaming SSE token-par-token (effet ChatGPT).
      // On crée immédiatement le message assistant vide et on concatène les
      // deltas reçus du flux. Cela offre la latence perçue "0ms" attendue.
      const placeholderId = `streaming_${Date.now()}`;
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '',
        ai_source: null,
        model_id: selectedModel,
        _streaming: true,
        _streaming_id: placeholderId,
        timestamp: new Date()
      }]);

      const resp = await fetch(`${API}/chat/stream`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          mode,
          language,
          model: selectedModel,
          project_id: project?.project_id,
          attachments: opts.attachments || [],
          // iter128.6 — Persona override créa-only. Non-créa : champ ignoré
          // côté back. Si la créa ne touche RIEN, persona.id='ai' + aiReplies=true
          // → comportement IA standard, aucun impact.
          persona_override: creatorPersona,
        }),
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let autoPid = null;
      let downloadInfo = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE events séparés par \n\n.
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const line = part.split('\n').find(l => l.startsWith('data:'));
          if (!line) continue;
          let evt;
          try { evt = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (evt.delta) {
            // Chantier §2 — Premier delta reçu : on bascule officiellement en
            // mode « streaming / l'IA écrit ».
            setAiRealState('streaming');
            // Concatène le delta au message en cours.
            setMessages(prev => prev.map(m =>
              m._streaming_id === placeholderId
                ? { ...m, content: (m.content || '') + evt.delta }
                : m
            ));
          }
          // iter129 — Décision du Router : quel agent spécialisé répond.
          if (evt.agent) {
            setMessages(prev => prev.map(m =>
              m._streaming_id === placeholderId
                ? { ...m, agent_id: evt.agent.id, agent_name: evt.agent.name }
                : m
            ));
          }
          // iter129 — Événement du journal d'activité (moteur d'exécution visible).
          if (evt.event) {
            setMessages(prev => prev.map(m =>
              m._streaming_id === placeholderId
                ? { ...m, agent_events: [...(m.agent_events || []), evt.event] }
                : m
            ));
          }
          if (evt.done) {
            autoPid = evt.project_id || null;
            downloadInfo = evt.download || null;
            if (evt.skipped) {
              // iter131 — La créa a intercepté (aiReplies=false) : on retire
              // le placeholder assistant et on rend le message user avec les
              // métadonnées persona côté client (le backend a déjà persisté).
              setMessages(prev => prev.filter(m => m._streaming_id !== placeholderId).map(m => {
                if (m._just_sent_user) {
                  return {
                    ...m,
                    _just_sent_user: false,
                    persona_id: evt.persona?.id || m.persona_id,
                    persona_pseudo: evt.persona?.pseudo || m.persona_pseudo,
                    persona_avatar: evt.persona?.avatar || m.persona_avatar,
                    visible_to_target: evt.persona?.visible !== false,
                    message_id: evt.user_message_id || m.message_id,
                  };
                }
                return m;
              }));
              break;
            }
            setMessages(prev => prev.map(m =>
              m._streaming_id === placeholderId
                ? {
                    ...m,
                    content: evt.content || m.content,
                    download: downloadInfo,
                    message_id: evt.message_id || m.message_id,
                    agent_id: evt.agent?.id || m.agent_id,
                    agent_name: evt.agent?.name || m.agent_name,
                    agent_events: evt.agent_events?.length ? evt.agent_events : m.agent_events,
                    _streaming: false,
                    _just_arrived: false,  // SSE déjà animé naturellement
                  }
                : m
            ));
          }
        }
      }
      setPendingAtts([]);
      // If backend auto-created a project for this chat (first message case),
      // adopt it locally so the conversation is pinned from the first message.
      if (autoPid && !project?.project_id) {
        try {
          const pr = await axios.get(`${API}/projects/${autoPid}`, { withCredentials: true });
          if (pr?.data) {
            navigate('/chat', { state: { mode, project: pr.data }, replace: true });
          }
        } catch { /* silent */ }
      }
      // Chantier iter159 §3 — Déclenche le renommage automatique du projet
      // UNE FOIS la 1ère réponse IA terminée. Le backend respecte le verrou
      // title_manual et ne renomme JAMAIS si l'user a renommé à la main.
      // Chantier iter159.2 §4 — On transmet la langue UI active pour que le
      // titre soit généré DANS CETTE LANGUE (ex: UI en français → titre fr,
      // même si le 1er message était en anglais).
      const pidForTitle = autoPid || project?.project_id;
      if (pidForTitle) {
        // Fire-and-forget : ne bloque pas l'UI.
        axios.post(`${API}/projects/${pidForTitle}/auto-title`,
          { language: (language || 'fr') },
          { withCredentials: true })
          .then((r) => {
            if (r?.data?.applied && r?.data?.title) {
              try {
                window.dispatchEvent(new CustomEvent('codeforge:project-renamed', {
                  detail: { project_id: pidForTitle, name: r.data.title },
                }));
              } catch (_) {}
            }
          })
          .catch(() => { /* silent — titre tronqué déjà présent côté backend */ });
      }
    } catch (error) {
      setAiRealState('error');  // Chantier §2 — vrai état d'erreur
      // iter158.7 — Chantier 4 : mappage précis de la cause réelle (Cloudflare,
      // Ollama offline/erreur, timeout, JSON invalide, rate limit, provider…).
      // Les détails techniques restent dans console.warn pour le diagnostic ;
      // l'utilisateur voit un message adapté à la catégorie.
      const { classifyAiError } = await import('../lib/aiErrorMapper');
      const errInfo = classifyAiError(error, {
        provider: mode === 'offline' ? 'ollama' : undefined,
        context: 'chat_send_text',
      });
      // eslint-disable-next-line no-console
      console.warn('[AI error]', errInfo.code, {
        status: error?.response?.status,
        message: error?.message,
        raw: error?.response?.data,
      });
      const cleanMsg = t(errInfo.i18nKey) || errInfo.fallback;
      setMessages(prev => [...prev.filter(m => !m._streaming), {
        role: 'assistant',
        content: cleanMsg,
        timestamp: new Date(),
        _error: true,
        _error_code: errInfo.code,
      }]);
      toast.error(cleanMsg);
    } finally {
      setIsLoading(false);
      // Chantier §2 — Si on sortait d'une erreur, laisser 'error' visible 1
      // instant via le toast + banner d'erreur ; sinon on repasse 'idle'.
      setAiRealState((prev) => (prev === 'error' ? 'error' : 'idle'));
    }
  };
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
      <OfflineAIInstaller
        open={showOfflineInstaller}
        onClose={() => setShowOfflineInstaller(false)}
        onInstalled={() => setOllamaAvailable(true)}
      />
      {/* iter98 — Preview interactive de la création courante (déclenchée par œil sidebar) */}
      <LivePreviewPanel
        open={showCreationPreview}
        onClose={() => setShowCreationPreview(false)}
        defaultPath="/dashboard"
      />
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
            {/* iter131/132 — Téléchargement + Ré-import des fichiers créés par Forge */}
            {project?.project_id && workspaceCount > 0 && (
              <button
                onClick={downloadWorkspace}
                disabled={workspaceBusy}
                data-testid="chat-download-workspace-btn"
                title={`Télécharger ${workspaceCount} fichier(s) créé(s) par Forge`}
                className="inline-flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-sm border border-emerald-400/40 text-emerald-300 hover:bg-emerald-500/10 transition-colors"
              >
                {workspaceBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                <span className="hidden md:inline">Forge ({workspaceCount})</span>
              </button>
            )}
            {project?.project_id && (
              <>
                <input
                  ref={workspaceImportInputRef}
                  type="file"
                  accept=".zip,application/zip"
                  className="hidden"
                  data-testid="chat-import-workspace-input"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) importWorkspace(f); }}
                />
                <button
                  onClick={() => workspaceImportInputRef.current?.click()}
                  disabled={workspaceBusy}
                  data-testid="chat-import-workspace-btn"
                  title="Ré-importer un ZIP Forge modifié dans ce projet"
                  className="inline-flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-sm border border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/10 transition-colors"
                >
                  {workspaceBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                  <span className="hidden md:inline">Importer</span>
                </button>
              </>
            )}
            <ModelPicker mode={mode} value={selectedModel} onChange={setSelectedModel} />
            {mode === 'offline' && !ollamaAvailable && (
              <button
                onClick={() => setShowOfflineInstaller(true)}
                data-testid="chat-offline-installer-btn"
                title="Installer Ollama pour activer le mode hors-ligne"
                className="inline-flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-sm border border-amber-400/40 text-amber-300 hover:bg-amber-500/10 transition-colors"
              >
                <Cpu className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Installer IA locale</span>
              </button>
            )}
            {/* iter96 — Reset REPL, Mode Pro, et Export .docx retirés sur demande utilisatrice */}
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
          {historyLoading && (
            <div className="text-center py-20" data-testid="chat-history-loading">
              <Loader2 className="w-10 h-10 mx-auto mb-4 animate-spin" style={{ color: modeColor }} />
              <p className="text-[#A1A1AA] text-sm">{t('chatLoadingHistory') || 'Chargement de la conversation…'}</p>
            </div>
          )}
          {!historyLoading && messages.length === 0 && (
            <div className="text-center py-20" data-testid="chat-empty-state">
              <Sparkles className="w-20 h-20 mx-auto mb-6" style={{ color: modeColor }} />
              <h2 className="text-2xl font-['Chivo'] font-bold mb-3">
                {project?.project_id ? (t('chatResumedEmptyTitle') || 'Cette conversation est vide') : t('chatEmptyTitle')}
              </h2>
              <p className="text-[#A1A1AA] mb-4">
                {project?.project_id
                  ? (t('chatResumedEmptyBody') || 'Aucun message archivé. Reprends la discussion en envoyant un nouveau message.')
                  : (mode === 'online' ? t('chatEmptyOnline') : t('chatEmptyOffline'))}
              </p>
            </div>
          )}

          <div className="space-y-4">
            {translatedMessages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              const displayContent = msg.displayed_content || msg.content;
              return (
                <motion.div
                  key={msg.message_id || msg.id || msg._streaming_id || `msg-${idx}`}
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
                    {/* iter129 — Journal d'activité de l'agent (moteur d'exécution visible) */}
                    {!isUser && (msg.agent_events?.length > 0 || (msg._streaming && msg.agent_id && msg.agent_id !== 'chat')) && (
                      <AgentActivityLog
                        events={msg.agent_events || []}
                        running={!!msg._streaming}
                        agentName={msg.agent_name}
                      />
                    )}
                    {/* iter98 — TypewriterEffect pour les messages IA récents (skip pour Emergent qui rend code par code). */}
                    {!isUser && msg._just_arrived && !(msg.ai_source || '').includes('emergent') ? (
                      <div data-testid="chat-typewriter">
                        <TypewriterEffect text={displayContent} skip={false} speed={12} />
                      </div>
                    ) : (
                      <MessageContent content={displayContent} isUser={isUser} replSessionId={replSessionId} />
                    )}
                    {msg._is_translated && (
                      <div className="mt-1 text-[10px] text-[#71717A] italic flex items-center gap-1" data-testid="chat-translated-badge">
                        <Languages className="w-3 h-3" />
                        Traduit automatiquement
                      </div>
                    )}
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
                      {/* iter95 — Voice mode TTS sur chaque message IA */}
                      {!isUser && (
                        <MessageTTSButton text={displayContent} />
                      )}
                      {/* iter129 — Badge de l'agent spécialisé ayant répondu */}
                      {!isUser && msg.agent_name && (
                        <span
                          data-testid="msg-agent-badge"
                          title={`Agent spécialisé : ${msg.agent_name}`}
                          className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest text-[#E4FF00]/80 border border-[#E4FF00]/25 rounded-sm px-1.5 py-0.5"
                        >
                          {msg.agent_name}
                        </span>
                      )}
                      {!isUser && msg.ai_source && (() => {
                        const src = msg.ai_source || '';
                        // Pretty label from ai_source 'emergent:openai:gpt-5.2' or 'ollama:gemma3:12b'
                        let label = src;
                        if (src.startsWith('emergent:')) {
                          const parts = src.split(':');
                          const prov = parts[1] || '';
                          const mdl = parts.slice(2).join(':') || '';
                          if (prov === 'anthropic') label = mdl.includes('fable') ? 'Claude Fable 5' : mdl.includes('opus') ? 'Claude Opus 4.5' : mdl.includes('sonnet') ? 'Claude Sonnet 4.5' : 'Claude';
                          else if (prov === 'gemini') label = mdl.includes('flash') ? 'Gemini 3 Flash' : 'Gemini 3 Pro';
                          else if (prov === 'openai') label = 'Emergent (GPT-5.2)';
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
                  {isUser && msg.persona_id && msg.persona_id !== 'ai' && (
                    <span
                      data-testid="msg-persona-badge"
                      className="text-[10px] uppercase tracking-widest border rounded-sm px-1.5 py-0.5 self-center"
                      style={{
                        color: msg.persona_id === 'creator' ? '#E4FF00' : '#6EE7B7',
                        borderColor: msg.persona_id === 'creator' ? 'rgba(228,255,0,0.4)' : 'rgba(110,231,183,0.4)',
                        backgroundColor: msg.persona_id === 'creator' ? 'rgba(228,255,0,0.08)' : 'rgba(110,231,183,0.08)',
                      }}
                      title={msg.persona_pseudo ? `Persona créa : ${msg.persona_pseudo}` : `Persona créa : ${msg.persona_id}`}
                    >
                      {msg.persona_pseudo || (msg.persona_id === 'creator' ? 'Créa' : 'Compte')}
                      {msg.visible_to_target === false && ' · fantôme'}
                    </span>
                  )}
                  {isUser && (
                    (msg.persona_avatar) ? (
                      <img
                        src={msg.persona_avatar} alt="persona"
                        data-testid="chat-avatar-user-persona"
                        className="flex-shrink-0 w-9 h-9 rounded-full border border-white/15 object-cover"
                        onError={(e) => { e.currentTarget.style.display = 'none'; }}
                      />
                    ) : user?.picture ? (
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
                data-testid="chat-ai-status"
                data-ai-state={aiRealState}
              >
                <div className="flex-shrink-0 w-9 h-9 rounded-full bg-[#E4FF00] text-[#050505] flex items-center justify-center">
                  <Sparkles className="w-4 h-4 animate-pulse" />
                </div>
                {/* Chantier iter159.2 §3 — Indicateur DISCRET « L'IA écrit » avec
                    3 points animés qui pulsent pendant que les tokens arrivent
                    réellement. L'étiquette montre le modèle RÉEL sélectionné
                    (GPT-5.5, Claude Fable 5, Gemini 3 Pro, Ollama local, etc.)
                    — jamais « Caly » quand ce n'est pas Caly. Les points
                    animent indépendamment du streaming (pulse CSS), mais
                    l'état `aiRealState` reflète toujours le vrai pipeline. */}
                <div className="bg-[#0F0F13] border-l-2 py-2 px-3 rounded-lg flex items-center gap-2" style={{ borderLeftColor: modeColor }}>
                  <span className="text-xs text-[#A1A1AA] font-['IBM_Plex_Sans']" data-testid="chat-ai-status-label">
                    {(() => {
                      // Nom du modèle réel sélectionné (affiché près de l'indicateur).
                      const modelLabels = {
                        'gpt-5.2':        'GPT-5.2',
                        'gpt-5':          'GPT-5',
                        'gpt-5.5':        'GPT-5.5',
                        'claude-sonnet':  'Claude Sonnet 4.5',
                        'claude-opus':    'Claude Opus 4.5',
                        'claude-haiku':   'Claude Haiku 4.5',
                        'claude-fable':   'Claude Fable 5',
                        'claude-5-fable': 'Claude Fable 5',
                        'gemini-3-pro':   'Gemini 3 Pro',
                        'gemini-3-flash': 'Gemini 3 Flash',
                        'gemma':          'Ollama · Gemma',
                        'deepseek':       'Ollama · Deepseek',
                        'llama':          'Ollama · Llama 3.2',
                        'llama3':         'Ollama · Llama 3.2',
                      };
                      const modelName = modelLabels[selectedModel] || selectedModel;
                      return `${modelName} · ${t('ai_state_streaming')}`;
                    })()}
                  </span>
                  <span className="inline-flex items-center gap-0.5" aria-hidden="true" data-testid="chat-ai-dots">
                    <span className="w-1 h-1 rounded-full bg-[#A1A1AA] animate-[cfdot_1.2s_ease-in-out_infinite]" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-1 h-1 rounded-full bg-[#A1A1AA] animate-[cfdot_1.2s_ease-in-out_infinite]" style={{ animationDelay: '200ms' }}></span>
                    <span className="w-1 h-1 rounded-full bg-[#A1A1AA] animate-[cfdot_1.2s_ease-in-out_infinite]" style={{ animationDelay: '400ms' }}></span>
                  </span>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <form onSubmit={sendMessage}>
          {/* iter128.6 — Barre persona créa, visible uniquement pour la créa
              physique (le composant filtre lui-même). Aucun impact si non
              affichée. */}
          <CreatorChatPersonaBar value={creatorPersona} onChange={setCreatorPersona} className="mb-2" />
          {/* Chantier iter160 §12 — Message offline EXACT demandé par l'user :
              « IA locale non détectée. Tout a été bloqué et se déverouillera
              lorsque la détection est réussie. » */}
          {mode === 'offline' && !ollamaAvailable && !isCreatorOrAdmin && (
            <div
              data-testid="chat-offline-lock-banner"
              className="mb-2 px-3 py-2 bg-white/[0.04] border border-amber-400/40 rounded-sm text-xs text-amber-200 flex items-center gap-2"
            >
              <Lock className="w-3 h-3 flex-shrink-0" />
              <span className="flex-1">
                {ollamaChecking
                  ? 'Détection IA locale en cours…'
                  : 'IA locale non détectée. Tout a été bloqué et se déverouillera lorsque la détection est réussie.'}
              </span>
              <button
                type="button"
                onClick={() => setShowOfflineInstaller(true)}
                data-testid="chat-offline-install-link"
                className="text-amber-300 hover:text-amber-200 underline underline-offset-2"
              >
                Voir le tutoriel
              </button>
            </div>
          )}
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
            {/* Chantier iter159.3 §7 — Verrouillage réel écriture + voix :
                si mode=offline et IA locale non détectée, ces contrôles
                sont désactivés jusqu'à auto-unlock par polling.
                Chantier iter160 §11 — Exemption Créa/Admin : jamais verrouillés. */}
            {(() => {
              const offlineLocked = mode === 'offline' && !ollamaAvailable && !isCreatorOrAdmin;
              const writeDisabled = isLoading || !canWrite || offlineLocked;
              const voiceDisabled = isLoading || !canWrite || offlineLocked;
              return (
                <>
                  <AttachMenu onResult={handleAttachment} disabled={isLoading || analyzingAtt || !canWrite || offlineLocked} />
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={offlineLocked ? 'IA locale non détectée — écriture verrouillée' : (canWrite ? t('chatPlaceholder') : t('ro_chat_placeholder'))}
                    disabled={writeDisabled}
                    rows={1}
                    data-testid="chat-input"
                    data-offline-locked={offlineLocked ? '1' : '0'}
                    className="flex-1 min-w-0 px-3 sm:px-4 py-3 bg-[#0F0F13] border border-white/20 rounded-lg focus:outline-none disabled:opacity-50 resize-y min-h-[48px] max-h-[200px] font-['IBM_Plex_Sans']"
                    style={{ borderColor: input ? modeColor : undefined }}
                  />
                  <VoiceRecorder mode="dictate" onResult={handleVoiceResult} disabled={voiceDisabled} language={language} />
                  <VoiceRecorder mode="send"    onResult={handleVoiceResult} disabled={voiceDisabled} language={language} />
                  <Button
                    type="submit"
                    disabled={writeDisabled || !input.trim()}
                    size="lg"
                    data-testid="chat-send-btn"
                    className="px-4 sm:px-8 flex-shrink-0"
                    style={{ backgroundColor: modeColor, color: '#050505' }}
                  >
                    {isLoading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Send className="w-5 h-5" />
                    )}
                  </Button>
                </>
              );
            })()}
          </div>
        </form>
      </div>
    </div>
  );
}
