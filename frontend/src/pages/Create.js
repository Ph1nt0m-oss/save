import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import ModelPicker from '../components/ModelPicker';
import axios from 'axios';
import { 
  Send, Sparkles, Loader2, ArrowLeft, Download, 
  Smartphone, Monitor, Globe, Play, Code, Eye,
  FileText, FileType, Image, ExternalLink
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import VoiceRecorder from '../components/VoiceRecorder';
import AttachMenu from '../components/AttachMenu';
import OfflineAIInstaller from '../components/OfflineAIInstaller';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Create() {
  const { user } = useAuth();
  const { language, t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const device = useDeviceIdentity();
  const canWrite = device.canWrite;
  const mode = location.state?.mode || 'online';
  // Chantier iter161 §P0.2 — Lorsque le Chat détecte une demande de création
  // d'application, il redirige ici avec prefillPrompt (et éventuellement
  // prefillModel). On lance alors la génération automatiquement.
  const prefillPrompt = location.state?.prefillPrompt || '';
  const prefillModel = location.state?.prefillModel || null;
  
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(prefillPrompt);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStartedAt, setGenerationStartedAt] = useState(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [currentProject, setCurrentProject] = useState(null);
  const [generatedCode, setGeneratedCode] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  // Modèle IA sélectionné pour la création — Claude Sonnet par défaut car
  // excellent en code, GPT-5.2 et Claude Opus en alternative.
  const [selectedModel, setSelectedModel] = useState(prefillModel || (mode === 'offline' ? 'gemma' : 'claude-sonnet'));
  const messagesEndRef = useRef(null);

  // Chantier iter159.2 §6 — Mode création hors-ligne : vérifie Ollama + modèle
  // recommandé à CHAQUE entrée (useEffect sur `mode`). Si pas prêt, refus
  // d'accès et affichage du tutoriel natif OfflineAIInstaller.
  // Chantier iter160 §8 — Détection RÉELLE côté navigateur.
  // Chantier iter160 §11 — Exemption Créa/Admin.
  const isCreatorOrAdmin = (device?.role === 'creator') || (device?.staff_kind === 'admin');
  const [showOfflineInstaller, setShowOfflineInstaller] = useState(false);
  const [ollamaAvailable, setOllamaAvailable] = useState(true);
  useEffect(() => {
    if (mode !== 'offline' || isCreatorOrAdmin) { setOllamaAvailable(true); return; }
    let cancelled = false;
    const RECOMMENDED = ['gemma3:4b','gemma3:2b','deepseek-r1:7b','llama3.2','llama3.2:3b','llama3.2:8b','gemma3:latest','gemma:latest','llama3:latest'];
    const check = async () => {
      try {
        const r = await fetch('http://localhost:11434/api/tags', { cache: 'no-store', signal: AbortSignal.timeout(3000) });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        const installed = (data.models || []).map((m) => m.name).filter(Boolean);
        const hit = installed.find((n) => RECOMMENDED.includes(n) || RECOMMENDED.some((x) => n.startsWith(x.split(':')[0] + ':')));
        if (cancelled) return;
        setOllamaAvailable(!!hit);
      } catch {
        if (!cancelled) setOllamaAvailable(false);
      }
    };
    check();
    const iv = setInterval(check, 10000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [mode, isCreatorOrAdmin]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Chantier iter161 §P0.3 — Compteur de temps réel de génération.
  // Affiche "⏳ Génération... 0:12" pour que l'user voie que ça avance.
  useEffect(() => {
    if (!isGenerating || !generationStartedAt) {
      setElapsedSec(0);
      return undefined;
    }
    const tick = () => setElapsedSec(Math.floor((Date.now() - generationStartedAt) / 1000));
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [isGenerating, generationStartedAt]);

  // Chantier iter161 §P0.2 — Autostart si on arrive avec un prefillPrompt
  // depuis le Chat ("tu peux me faire une app de X" détecté).
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (!prefillPrompt || autoStartedRef.current) return;
    if (!user) return;
    autoStartedRef.current = true;
    // Petit délai pour laisser le DOM se stabiliser.
    const timeoutId = setTimeout(() => generateApp(prefillPrompt), 300);
    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillPrompt, user]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const generateApp = async (overrideText) => {
    const userMessage = (overrideText ?? input).trim();
    if (!userMessage || isGenerating) return;
    if (!canWrite) {
      toast.error(t('ro_toast_generate'), { id: 'read-only' });
      return;
    }
    // Chantier iter159.2 §6 — Refus d'accès au workflow si Ollama/modèle
    // recommandé absent en mode hors-ligne.
    // Chantier iter160 §11 — Créa/Admin exempt du verrou.
    if (mode === 'offline' && !ollamaAvailable && !isCreatorOrAdmin) {
      setShowOfflineInstaller(true);
      toast.error('IA locale non détectée — tout est bloqué.');
      return;
    }

    if (!overrideText) setInput('');
    setIsGenerating(true);
    setGenerationStartedAt(Date.now());

    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      isVoice: !!overrideText,
      timestamp: new Date()
    }]);

    try {
      // Chantier iter159.2 §5 — Timeout explicite + feedback actionnable.
      // L'ancienne version attendait indéfiniment : si le pipeline backend
      // dépasse le proxy edge (≈ 100s) l'UI restait bloquée sur « Génération
      // en cours… ». Désormais : 180s max côté client avec `AbortController`,
      // et message clair si c'est dépassé. Le backend persiste quand même via
      // `_run_in_background`, l'utilisateur retrouve son projet dans la
      // sidebar après rechargement.
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort('client_timeout'), 180000);
      let response;
      try {
        response = await axios.post(
          `${API}/ai/generate-complete-app`,
          { description: userMessage, mode, language, model: selectedModel },
          { withCredentials: true, signal: controller.signal, timeout: 180000 }
        );
      } finally {
        clearTimeout(timeoutId);
      }

      setGeneratedCode(response.data.code);
      setCurrentProject(response.data.project);
      
      // Set preview URL
      if (response.data.preview_url) {
        setPreviewUrl(response.data.preview_url);
      } else if (response.data.project?.id) {
        setPreviewUrl(`${API}/preview/project/${response.data.project.id}`);
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.explanation,
        timestamp: new Date(),
        hasCode: true,
        ai_source: response.data.ai_source || `emergent:${selectedModel}`,
        previewUrl: response.data.preview_url || `${API}/preview/project/${response.data.project?.id}`
      }]);

      // Build & Test pattern (Emergent-like) — kick off automatic preview + lightweight test.
      try {
        const pid = response.data.project?.id || response.data.project?.project_id;
        if (pid) {
          // 1) Smoke test: GET the preview HTML. If 200 + body length OK, the build is up.
          const previewUrlEff = response.data.preview_url || `${API}/preview/project/${pid}`;
          const r = await axios.get(previewUrlEff, { withCredentials: true, validateStatus: () => true });
          const ok = r.status === 200 && typeof r.data === 'string' && r.data.length > 200;
          const fileCount = response.data.code?.files ? Object.keys(response.data.code.files).length : 0;
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: ok
              ? `✅ **Build & Test réussi** — ${fileCount} fichier${fileCount > 1 ? 's' : ''} générés, page de preview chargée correctement (${r.data.length} octets). Tu peux la voir live à droite ou cliquer sur **Aperçu Live** dans le menu projet.`
              : `⚠️ **Build OK mais test preview KO** (status ${r.status}). Le code est généré, mais la page d'aperçu n'a pas répondu comme prévu. Va dans **Aperçu Live** pour voir manuellement.`,
            timestamp: new Date(),
            isStatusLine: true,
          }]);
        }
      } catch (testErr) {
        // Non-blocking
        console.warn('Build&Test smoke failed:', testErr?.message);
      }

      toast.success('Application générée !');
    } catch (error) {
      // Chantier iter159.2 §5 — Détection explicite d'un timeout / abort client.
      const isTimeout = error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED' || error?.message?.includes('timeout') || String(error?.code) === 'ECONNABORTED';
      if (isTimeout) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: '⏱️ **La génération prend plus longtemps que prévu** (> 3 min). Elle continue en arrière-plan côté serveur — recharge le dashboard dans 1-2 minutes, ton projet apparaîtra dans la sidebar. Tu peux aussi réessayer avec un modèle plus rapide (Gemini Flash, Claude Haiku).',
          timestamp: new Date(),
          _error: true,
          _error_code: 'ai_timeout_client',
        }]);
        toast.error('Génération longue — elle continue en arrière-plan.');
        return; // sort du catch sans classifier
      }

      // Chantier iter161 §P0.1 — Erreur explicite du backend sur modèle non
      // branché (501 ai_integration_not_configured, ai_grok_key_missing,
      // ai_model_unknown). On n'affiche PAS « erreur réseau » : on dit
      // précisément quel modèle n'est pas disponible.
      const backendDetail = error?.response?.data?.detail;
      if (error?.response?.status === 501 && backendDetail && typeof backendDetail === 'object') {
        const errMsgMap = {
          ai_integration_not_configured: `Le modèle « ${backendDetail.requested_model || selectedModel} » n'est pas branché côté serveur (${backendDetail.provider || '?'}). Choisis un autre modèle (OpenAI, Anthropic ou Gemini).`,
          ai_grok_key_missing: `Grok a été sélectionné mais la clé XAI_API_KEY est absente côté backend. Demande à l'admin d'ajouter la clé xAI.`,
          ai_model_unknown: `Modèle « ${backendDetail.requested_model || selectedModel} » inconnu. Choisis un modèle supporté.`,
        };
        const prettyMsg = errMsgMap[backendDetail.code] || backendDetail.message || 'Modèle sélectionné non disponible.';
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `⚠️ ${prettyMsg}`,
          timestamp: new Date(),
          _error: true,
          _error_code: backendDetail.code,
        }]);
        toast.error(prettyMsg);
        return;
      }

      // iter158.12 — P1.1 : mappage précis via classifyAiError partagé.
      const { classifyAiError } = await import('../lib/aiErrorMapper');
      const errInfo = classifyAiError(error, {
        provider: mode === 'offline' ? 'ollama' : undefined,
        context: 'create.generate',
      });
      // eslint-disable-next-line no-console
      console.warn('[AI error]', errInfo.code, {
        status: error?.response?.status,
        message: error?.message,
        raw: error?.response?.data,
      });
      const cleanMsg = t(errInfo.i18nKey) || errInfo.fallback;
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: cleanMsg,
        timestamp: new Date(),
        _error: true,
        _error_code: errInfo.code,
      }]);
      toast.error(cleanMsg);
    } finally {
      setIsGenerating(false);
    }
  };

  // Ouvrir la prévisualisation dans un nouvel onglet
  const openPreview = (type) => {
    const previewTypes = {
      web: `${API}/preview/demo/web`,
      pdf: `${API}/preview/demo/pdf`,
      docx: `${API}/preview/demo/docx`,
      app: `${API}/preview/demo/app`,
      image: `${API}/preview/demo/image`
    };
    
    const url = previewUrl || previewTypes[type] || previewTypes.web;
    window.open(url, '_blank');
    toast.success(`Prévisualisation ${type.toUpperCase()} ouverte`);
  };

  const exportApp = async (type) => {
    if (!currentProject) {
      toast.error('Générez d\'abord une application');
      return;
    }

    if (type === 'apk') {
      window.open(`${BACKEND_URL}/api/export/mobile/${currentProject.id}`, '_blank');
      toast.success('Page d\'installation mobile ouverte');
    } else if (type === 'exe') {
      window.open(`${BACKEND_URL}/api/export/desktop/${currentProject.id}`, '_blank');
      toast.success('Page de téléchargement desktop ouverte');
    } else if (type === 'web') {
      toast.info('Génération du déploiement web...');
      // Instructions de déploiement
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      {/* Header */}
      <header className="bg-[#0F0F13] border-b border-white/10 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button onClick={() => navigate('/dashboard')} variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Retour
            </Button>
            <div className="flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-[#E4FF00]" />
              <h1 className="font-['Chivo'] font-bold text-2xl">Création IA Sans Limites</h1>
              <span className={`ml-2 px-2 py-1 text-xs rounded-full font-bold ${mode === 'online' ? 'bg-[#00FF66] text-[#050505]' : 'bg-purple-400 text-[#050505]'}`}>
                {mode === 'online' ? 'EN LIGNE' : 'HORS LIGNE'}
              </span>
            </div>
          </div>

          {/* Boutons de Prévisualisation - TOUJOURS VISIBLES */}
          <div className="flex items-center gap-2">
            <ModelPicker mode={mode} context="create" value={selectedModel} onChange={setSelectedModel} />
            <span className="text-xs text-[#A1A1AA] font-['IBM_Plex_Mono'] mr-2">PRÉVISUALISATION:</span>
            
            <Button
              onClick={() => openPreview('web')}
              size="sm"
              variant="outline"
              data-testid="preview-web-btn"
              className="border-[#00FF66] text-[#00FF66] hover:bg-[#00FF66] hover:text-[#050505]"
              title="Prévisualiser Web"
            >
              <Globe className="w-4 h-4 mr-1" />
              Web
            </Button>
            
            <Button
              onClick={() => openPreview('app')}
              size="sm"
              variant="outline"
              data-testid="preview-app-btn"
              className="border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505]"
              title="Prévisualiser App"
            >
              <Smartphone className="w-4 h-4 mr-1" />
              App
            </Button>
            
            <Button
              onClick={() => openPreview('pdf')}
              size="sm"
              variant="outline"
              data-testid="preview-pdf-btn"
              className="border-red-400 text-red-400 hover:bg-red-400 hover:text-[#050505]"
              title="Prévisualiser PDF"
            >
              <FileText className="w-4 h-4 mr-1" />
              PDF
            </Button>
            
            <Button
              onClick={() => openPreview('docx')}
              size="sm"
              variant="outline"
              data-testid="preview-docx-btn"
              className="border-blue-400 text-blue-400 hover:bg-blue-400 hover:text-[#050505]"
              title="Prévisualiser DOCX"
            >
              <FileType className="w-4 h-4 mr-1" />
              DOCX
            </Button>

            {currentProject && (
              <>
                <div className="w-px h-6 bg-white/10 mx-2" />
                <Button onClick={() => exportApp('apk')} size="sm" className="bg-[#E4FF00] text-[#050505]">
                  <Smartphone className="w-4 h-4 mr-1" />
                  APK
                </Button>
                <Button onClick={() => exportApp('exe')} size="sm" className="bg-[#E4FF00] text-[#050505]">
                  <Monitor className="w-4 h-4 mr-1" />
                  EXE
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chat Interface */}
          <div className="bg-[#0F0F13] border border-white/10 rounded-lg flex flex-col" style={{height: 'calc(100vh - 200px)'}}>
            <div className="p-4 border-b border-white/10">
              <h2 className="font-['Chivo'] font-bold">Décrivez votre application</h2>
              <p className="text-sm text-[#A1A1AA] mt-1">L'IA génère tout automatiquement</p>
            </div>

            <ScrollArea className="flex-1 p-6">
              {messages.length === 0 && (
                <div className="text-center py-20">
                  <Sparkles className="w-20 h-20 mx-auto mb-6 text-[#E4FF00]" />
                  <h3 className="text-xl font-['Chivo'] font-bold mb-2">Création Illimitée</h3>
                  <p className="text-[#A1A1AA] mb-4">Décrivez ce que vous voulez créer</p>
                  <div className="text-left max-w-md mx-auto space-y-2 text-sm text-[#A1A1AA]">
                    <p>💡 "Créé-moi une app de todo avec authentification"</p>
                    <p>💡 "Fait un site e-commerce avec panier"</p>
                    <p>💡 "Génère un blog avec CMS"</p>
                  </div>
                </div>
              )}

              <div className="space-y-4">
                {messages.map((msg, idx) => (
                  <motion.div
                    key={msg.message_id || msg.id || `msg-${msg.timestamp || idx}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[80%] p-4 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-[#E4FF00]/10 border border-[#E4FF00]'
                        : 'bg-[#050505] border border-white/10'
                    }`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      {msg.hasCode && (
                        <div className="mt-3 pt-3 border-t border-white/10 space-y-2">
                          <p className="text-xs text-[#00FF66] flex items-center gap-2">
                            <Code className="w-4 h-4" />
                            Code généré et prêt à exporter
                          </p>
                          {/* Bouton Prévisualisation inline */}
                          <Button
                            onClick={() => window.open(msg.previewUrl || `${API}/preview/demo/web`, '_blank')}
                            size="sm"
                            data-testid={`preview-inline-btn-${idx}`}
                            className="bg-[#00FF66] text-[#050505] hover:bg-[#00FF66]/80"
                          >
                            <ExternalLink className="w-3 h-3 mr-1" />
                            Prévisualiser
                          </Button>
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}

                {isGenerating && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex justify-start"
                    data-testid="create-generation-progress"
                  >
                    <div className="bg-[#050505] border border-white/10 p-4 rounded-lg flex items-center gap-3">
                      <Loader2 className="w-5 h-5 animate-spin text-[#E4FF00]" />
                      {/* Chantier iter161 §P0.3 — Compteur de temps réel + info
                          utile sur le modèle en cours pour éviter la sensation
                          de blocage. 1-2 min est NORMAL pour Claude 5 Fable
                          sur une app complète ; on le dit explicitement. */}
                      <div className="flex flex-col">
                        <span className="font-semibold" data-testid="create-generation-timer">
                          Génération en cours · {Math.floor(elapsedSec / 60)}:{String(elapsedSec % 60).padStart(2, '0')}
                        </span>
                        <span className="text-xs text-[#A1A1AA]">
                          Modèle : {selectedModel} — compte 1 à 2 min selon la complexité.
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>

              <div ref={messagesEndRef} />
            </ScrollArea>

            <div className="p-4 border-t border-white/10">
              <div className="flex gap-2 sm:gap-3 items-end">
                <AttachMenu
                  disabled={isGenerating}
                  onResult={(att) => {
                    if (att.kind === 'text') setInput(prev => (prev ? `${prev} ${att.text}` : att.text));
                    else if (att.kind === 'url') setInput(prev => (prev ? `${prev} ${att.url}` : att.url));
                    else if (att.kind === 'file') setInput(prev => (prev ? `${prev} [📎 ${att.name}]` : `[📎 ${att.name}]`));
                  }}
                />
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  rows={1}
                  placeholder="Créé-moi une application de... (Entrée = saut de ligne, clique sur Générer pour envoyer)"
                  disabled={isGenerating}
                  className="flex-1 min-w-0 px-3 sm:px-4 py-3 bg-[#050505] border border-white/20 rounded-lg focus:outline-none focus:border-[#E4FF00] disabled:opacity-50 resize-y min-h-[48px] max-h-[200px] font-['IBM_Plex_Sans']"
                />
                <VoiceRecorder
                  mode="dictate"
                  disabled={isGenerating}
                  language={language}
                  onResult={(text) => setInput(prev => (prev ? `${prev} ${text}` : text))}
                />
                <VoiceRecorder
                  mode="send"
                  disabled={isGenerating}
                  language={language}
                  onResult={(text, autoSend) => {
                    if (autoSend) generateApp(text);
                  }}
                />
                <Button
                  onClick={() => generateApp()}
                  disabled={isGenerating || !input.trim()}
                  size="lg"
                  className="bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90 px-4 sm:px-8 flex-shrink-0"
                >
                  {isGenerating ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <><Sparkles className="w-5 h-5 mr-2" /><span className="hidden sm:inline">Générer</span></>
                  )}
                </Button>
              </div>
            </div>
          </div>

          {/* Preview/Instructions */}
          <div className="bg-[#0F0F13] border border-white/10 rounded-lg p-6" style={{height: 'calc(100vh - 200px)'}}>
            {!currentProject ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Code className="w-16 h-16 text-[#A1A1AA] mb-4" />
                <h3 className="font-['Chivo'] font-bold text-xl mb-2">Aucune génération</h3>
                <p className="text-[#A1A1AA] max-w-sm">
                  Décrivez votre application dans le chat et l'IA générera tout automatiquement.
                </p>
              </div>
            ) : (
              <div className="h-full flex flex-col">
                <div className="mb-4">
                  <h3 className="font-['Chivo'] font-bold text-xl mb-2">Application Générée</h3>
                  <p className="text-sm text-[#A1A1AA]">Prête à être exportée</p>
                </div>

                <ScrollArea className="flex-1">
                  {showPreview && generatedCode && (
                    <div className="space-y-4">
                      {generatedCode.files?.map((file, idx) => (
                        <div key={file.path || `file-${idx}`} className="bg-[#050505] border border-white/10 rounded p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Code className="w-4 h-4 text-[#E4FF00]" />
                            <span className="font-['IBM_Plex_Mono'] text-sm">{file.path}</span>
                          </div>
                          <pre className="text-xs overflow-x-auto text-[#A1A1AA]">
                            {file.content.substring(0, 200)}...
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}

                  {!showPreview && (
                    <div className="space-y-4">
                      <div className="bg-[#050505] border border-[#E4FF00] rounded p-4">
                        <h4 className="font-bold mb-2 flex items-center gap-2">
                          <Smartphone className="w-5 h-5 text-[#E4FF00]" />
                          Export Mobile (APK)
                        </h4>
                        <p className="text-sm text-[#A1A1AA] mb-3">
                          Installez l'application sur Android directement
                        </p>
                        <Button onClick={() => exportApp('apk')} className="w-full bg-[#E4FF00] text-[#050505]">
                          Ouvrir page d'installation
                        </Button>
                      </div>

                      <div className="bg-[#050505] border border-[#E4FF00] rounded p-4">
                        <h4 className="font-bold mb-2 flex items-center gap-2">
                          <Monitor className="w-5 h-5 text-[#E4FF00]" />
                          Export Desktop (EXE)
                        </h4>
                        <p className="text-sm text-[#A1A1AA] mb-3">
                          Téléchargez l'installateur Windows
                        </p>
                        <Button onClick={() => exportApp('exe')} className="w-full bg-[#E4FF00] text-[#050505]">
                          Télécharger installateur
                        </Button>
                      </div>

                      <div className="bg-[#050505] border border-[#00FF66] rounded p-4">
                        <h4 className="font-bold mb-2 flex items-center gap-2">
                          <Globe className="w-5 h-5 text-[#00FF66]" />
                          Déploiement Web
                        </h4>
                        <p className="text-sm text-[#A1A1AA] mb-3">
                          Déployez sur Vercel, Netlify ou votre hébergeur
                        </p>
                        <Button onClick={() => exportApp('web')} className="w-full bg-[#00FF66] text-[#050505]">
                          Instructions de déploiement
                        </Button>
                      </div>
                    </div>
                  )}
                </ScrollArea>
              </div>
            )}
          </div>
        </div>
      </div>
      {/* Chantier iter159.2 §6 — Tutoriel natif OfflineAIInstaller monté
          uniquement en mode offline, forcé si Ollama ou modèle recommandé
          manquants. */}
      {mode === 'offline' && (
        <OfflineAIInstaller
          open={showOfflineInstaller}
          onClose={() => setShowOfflineInstaller(false)}
          onInstalled={() => { setOllamaAvailable(true); setShowOfflineInstaller(false); }}
        />
      )}
    </div>
  );
}
