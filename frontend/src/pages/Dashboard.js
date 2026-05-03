import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { useCache } from '../contexts/CacheContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { 
  Send, Plus, LogOut, Sparkles, 
  Code2, Smartphone, Monitor, Globe, 
  Download, Loader2, PanelLeftClose, PanelLeftOpen, ChevronRight,
  Wand2, Wifi, WifiOff, Users, BookOpen, UserCog, Pencil, Trash2, MessageSquare, Eye, Brain, Link2
} from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import Onboarding from '../components/Onboarding';
import UserMenu from '../components/UserMenu';
import FeatureHint from '../components/FeatureHint';
import SwitchAccountModal from '../components/SwitchAccountModal';
import LanguageToggle from '../components/LanguageToggle';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const { isOnline, cacheProjects, getCachedProjects } = useCache();
  const navigate = useNavigate();
  
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [aiStatus, setAiStatus] = useState('online');
  const [switchAccountOpen, setSwitchAccountOpen] = useState(false);
  // Right-click context menu state for projects in the sidebar.
  const [ctxMenu, setCtxMenu] = useState(null); // { x, y, project } | null
  const [renameTarget, setRenameTarget] = useState(null); // project being renamed
  const [renameValue, setRenameValue] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null); // project pending delete confirm

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Close the context menu on any outside click / escape.
  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    const onKey = (e) => { if (e.key === 'Escape') setCtxMenu(null); };
    document.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('click', close);
      document.removeEventListener('keydown', onKey);
    };
  }, [ctxMenu]);

  const onProjectContextMenu = (e, project) => {
    e.preventDefault();
    setCtxMenu({ x: e.clientX, y: e.clientY, project });
  };

  const startRename = (project) => {
    setRenameTarget(project);
    setRenameValue(project.name || '');
    setCtxMenu(null);
  };

  const submitRename = async () => {
    if (!renameTarget) return;
    const name = renameValue.trim();
    if (!name || name === renameTarget.name) {
      setRenameTarget(null);
      return;
    }
    try {
      await axios.put(`${API}/projects/${renameTarget.project_id}`,
        { name }, { withCredentials: true });
      setProjects(p => p.map(pr => pr.project_id === renameTarget.project_id ? { ...pr, name } : pr));
      if (selectedProject?.project_id === renameTarget.project_id) {
        setSelectedProject(s => ({ ...s, name }));
      }
      toast.success('Projet renommé');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Renommage impossible');
    } finally {
      setRenameTarget(null);
    }
  };

  const askDelete = (project) => { setDeleteTarget(project); setCtxMenu(null); };

  const exportProjectZip = async (project) => {
    setCtxMenu(null);
    if (!project?.project_id) return;
    try {
      const r = await axios.post(
        `${API}/export/download`,
        { project_id: project.project_id, export_type: 'source' },
        { withCredentials: true, responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/zip' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `${project.name || project.project_id}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('ZIP téléchargé');
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Export impossible';
      toast.error(detail);
    }
  };

  const exportProjectGithub = async (project) => {
    setCtxMenu(null);
    if (!project?.project_id) return;
    const t1 = toast.loading('Push GitHub en cours…');
    try {
      const r = await axios.post(
        `${API}/export/github/${project.project_id}`,
        {},
        { withCredentials: true }
      );
      toast.dismiss(t1);
      if (r.data?.url) {
        toast.success('Poussé sur GitHub', {
          action: {
            label: 'Ouvrir',
            onClick: () => window.open(r.data.url, '_blank'),
          },
          duration: 8000,
        });
      } else {
        toast.success('Push terminé');
      }
    } catch (err) {
      toast.dismiss(t1);
      toast.error(err.response?.data?.detail || 'Push GitHub impossible');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/projects/${deleteTarget.project_id}`, { withCredentials: true });
      setProjects(p => p.filter(pr => pr.project_id !== deleteTarget.project_id));
      if (selectedProject?.project_id === deleteTarget.project_id) setSelectedProject(null);
      toast.success('Projet supprimé');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Suppression impossible');
    } finally {
      setDeleteTarget(null);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadProjects = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/projects`, {
        withCredentials: true
      });
      setProjects(response.data);
      // Cache pour mode hors ligne
      cacheProjects(response.data);
    } catch (error) {
      // Utiliser le cache en mode hors ligne
      if (!isOnline) {
        const cached = getCachedProjects();
        if (cached.length > 0) {
          setProjects(cached);
          toast.info('Projets chargés depuis le cache');
          return;
        }
      }
      toast.error('Erreur lors du chargement des projets');
    }
  }, [cacheProjects, getCachedProjects, isOnline]);

  const loadChatHistory = useCallback(async (projectId) => {
    try {
      const response = await axios.get(`${API}/chat/history?project_id=${projectId}`, {
        withCredentials: true
      });
      setMessages(response.data);
    } catch (error) {
      // Silent fail — chat history is non-critical
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProject) {
      loadChatHistory(selectedProject.project_id);
    }
  }, [selectedProject, loadChatHistory]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const createNewProject = async () => {
    const projectName = prompt('Nom du projet:');
    if (!projectName) return;

    const projectType = prompt('Type (web/mobile/desktop):') || 'web';

    try {
      const response = await axios.post(
        `${API}/projects`,
        {
          name: projectName,
          description: `Nouveau projet ${projectType}`,
          project_type: projectType
        },
        { withCredentials: true }
      );

      setProjects([response.data, ...projects]);
      setSelectedProject(response.data);
      toast.success('Projet créé !');
    } catch (error) {
      console.error('Error creating project:', error);
      toast.error('Erreur lors de la création');
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    // Add user message to UI immediately
    const tempUserMsg = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      const response = await axios.post(
        `${API}/chat/message`,
        {
          message: userMessage,
          project_id: selectedProject?.project_id
        },
        { withCredentials: true }
      );

      // Add AI response
      setMessages(prev => [...prev.slice(0, -1), response.data.user_message, response.data.ai_response]);
    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Erreur lors de l\'envoi du message');
      
      // Remove temp message on error
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  };

  const generateCode = async () => {
    if (!selectedProject) {
      toast.error('Créez d\'abord un projet');
      return;
    }

    const description = prompt('Décrivez l\'application à générer:');
    if (!description) return;

    setIsLoading(true);
    toast.info('Génération du code en cours...');

    try {
      const response = await axios.post(
        `${API}/generate/code`,
        {
          project_id: selectedProject.project_id,
          description,
          project_type: selectedProject.project_type
        },
        { withCredentials: true }
      );

      toast.success('Code généré avec succès !');
      
      // Add generation result to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `✅ Code généré pour "${selectedProject.name}"!\n\nType: ${selectedProject.project_type}\n\nVous pouvez maintenant exporter ce projet.`,
        timestamp: new Date().toISOString()
      }]);

      loadProjects();
    } catch (error) {
      console.error('Error generating code:', error);
      toast.error('Erreur lors de la génération');
    } finally {
      setIsLoading(false);
    }
  };

  const exportProject = async (exportType) => {
    if (!selectedProject) {
      toast.error('Créez et sélectionnez un projet d\'abord');
      return;
    }

    if (!selectedProject.generated_code) {
      toast.error('Générez d\'abord le code du projet');
      return;
    }

    try {
      if (exportType === 'source') {
        // Download ZIP directly
        const response = await axios.post(
          `${API}/export/download`,
          { project_id: selectedProject.project_id, export_type: 'source' },
          { 
            withCredentials: true,
            responseType: 'blob'
          }
        );

        // Create download link
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${selectedProject.name}.zip`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        
        toast.success('Code source téléchargé !');
      } else if (exportType === 'apk') {
        // Open mobile export page
        const exportUrl = `${BACKEND_URL}/api/export/mobile/${selectedProject.project_id}`;
        window.open(exportUrl, '_blank');
        toast.success('Page d\'installation mobile ouverte !');
      } else if (exportType === 'exe') {
        // Open desktop export page
        const exportUrl = `${BACKEND_URL}/api/export/desktop/${selectedProject.project_id}`;
        window.open(exportUrl, '_blank');
        toast.success('Page de téléchargement desktop ouverte !');
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Erreur lors de l\'export');
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="h-screen bg-[#050505] text-white flex overflow-hidden">
      {/* Onboarding retiré du dashboard — l'utilisateur découvre l'interface par lui-même */}
      {/* Sidebar - Projects */}
      <motion.aside
        initial={false}
        animate={{ width: isSidebarOpen ? 280 : 0 }}
        className="bg-[#0F0F13] border-r border-white/10 flex flex-col overflow-hidden"
      >
        <div className="p-4 border-b border-white/10 flex items-center">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-[#E4FF00]" />
            <span className="font-['Chivo'] font-bold">{t('dashProjects')}</span>
          </div>
        </div>

        <div className="p-4">
          <Button
            onClick={createNewProject}
            data-testid="create-project-btn"
            className="w-full bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90 font-['Chivo'] font-bold"
          >
            <Plus className="w-4 h-4 mr-2" />
            {t('dashNewProject')}
          </Button>
        </div>

        <ScrollArea className="flex-1 px-4">
          <div className="space-y-2">
            {projects.map(project => (
              renameTarget?.project_id === project.project_id ? (
                <div
                  key={project.project_id}
                  data-testid={`project-rename-${project.project_id}`}
                  className="bg-white/[0.04] border border-[#E4FF00] rounded-sm p-2 flex items-center gap-2"
                >
                  {/* Dot visible mais non modifiable pendant le rename */}
                  {(() => {
                    const t2 = project.project_type || 'web';
                    const m = project.ai_mode || 'online';
                    let bg = 'bg-[#A1A1AA]';
                    if (t2 === 'chat' && m === 'online') bg = 'bg-yellow-400';
                    else if (t2 === 'chat' && m === 'offline') bg = 'bg-sky-400';
                    else if (t2 !== 'chat' && m === 'online') bg = 'bg-emerald-400';
                    else if (t2 !== 'chat' && m === 'offline') bg = 'bg-violet-400';
                    return <span className={`flex-shrink-0 w-2.5 h-2.5 rounded-full ${bg} opacity-70`} />;
                  })()}
                  <input
                    autoFocus
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') submitRename();
                      else if (e.key === 'Escape') setRenameTarget(null);
                    }}
                    onBlur={submitRename}
                    className="flex-1 bg-transparent text-sm text-white font-['IBM_Plex_Sans'] focus:outline-none px-1"
                  />
                </div>
              ) : (
                <button
                  key={project.project_id}
                  onClick={() => {
                    setSelectedProject(project);
                    const mode = project.ai_mode || 'online';
                    if (project.project_type === 'chat') {
                      navigate('/chat', { state: { mode, project } });
                    } else {
                      navigate('/chat', { state: { mode, project } });
                    }
                  }}
                  onContextMenu={(e) => onProjectContextMenu(e, project)}
                  data-testid={`project-${project.project_id}`}
                  className={`w-full text-left p-3 rounded-sm border transition-all ${
                    selectedProject?.project_id === project.project_id
                      ? 'bg-[#E4FF00]/10 border-[#E4FF00]'
                      : 'bg-[#050505] border-white/10 hover:border-white/30'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {/* Type dot — couleur selon (project_type, ai_mode) */}
                    {(() => {
                      const t2 = project.project_type || 'web';
                      const m = project.ai_mode || 'online';
                      let bg = 'bg-[#A1A1AA]'; let title = 'Projet';
                      if (t2 === 'chat' && m === 'online')  { bg = 'bg-yellow-400';  title = 'Discussion avec l’IA en ligne (GPT-5.2)'; }
                      else if (t2 === 'chat' && m === 'offline') { bg = 'bg-sky-400';    title = 'Discussion avec Ollama (hors-ligne)'; }
                      else if (t2 !== 'chat' && m === 'online')  { bg = 'bg-emerald-400';title = 'Création avec Emergent (en ligne)'; }
                      else if (t2 !== 'chat' && m === 'offline') { bg = 'bg-violet-400'; title = 'Création avec Ollama (hors-ligne)'; }
                      return (
                        <span
                          data-testid={`project-dot-${project.project_id}`}
                          title={title}
                          className={`flex-shrink-0 w-2.5 h-2.5 rounded-full ${bg} shadow-[0_0_6px_rgba(255,255,255,0.15)]`}
                        />
                      );
                    })()}
                    {project.project_type === 'web' && <Globe className="w-4 h-4 text-[#A1A1AA] flex-shrink-0" />}
                    {project.project_type === 'mobile' && <Smartphone className="w-4 h-4 text-[#A1A1AA] flex-shrink-0" />}
                    {project.project_type === 'desktop' && <Monitor className="w-4 h-4 text-[#A1A1AA] flex-shrink-0" />}
                    {project.project_type === 'chat' && <MessageSquare className="w-4 h-4 text-[#A1A1AA] flex-shrink-0" />}
                    <span className="font-['IBM_Plex_Sans'] font-medium truncate flex-1 min-w-0">
                      {project.name}
                    </span>
                    {selectedProject?.project_id === project.project_id && (
                      <ChevronRight className="w-4 h-4 text-[#E4FF00] flex-shrink-0" />
                    )}
                  </div>
                </button>
              )
            ))}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-white/10 space-y-2">
          <button
            onClick={() => navigate('/profile')}
            data-testid="sidebar-profile-btn"
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-white/[0.04] border border-white/15 rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-all text-sm font-['IBM_Plex_Sans']"
          >
            <UserCog className="w-4 h-4" />
            <span>{t('sidebar_my_profile')}</span>
          </button>

          <button
            onClick={() => setSwitchAccountOpen(true)}
            data-testid="sidebar-switch-account-btn"
            className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-white/20 rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-all text-sm font-['IBM_Plex_Sans']"
          >
            <Users className="w-4 h-4" />
            <span>{t('dashSwitchAccount')}</span>
          </button>

          <button
            onClick={handleLogout}
            data-testid="sidebar-logout-btn"
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/40 text-red-400 rounded-sm hover:bg-red-500/20 hover:border-red-500 hover:text-red-300 transition-all text-sm font-['IBM_Plex_Sans']"
          >
            <LogOut className="w-4 h-4" />
            <span>{t('dashLogout')}</span>
          </button>
        </div>
      </motion.aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col">
        {/* Header — [Sidebar toggle + Lang] · [CodeForge AI] · [Tutorial + Exports + UserMenu] */}
        <header className="bg-[#0F0F13] border-b border-white/10 px-3 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between gap-2 sm:gap-4">
            {/* LEFT */}
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <button
                onClick={() => setIsSidebarOpen(o => !o)}
                data-testid="sidebar-toggle-btn"
                aria-label={isSidebarOpen ? t('dashCollapseSidebar') : t('dashExpandSidebar')}
                title={isSidebarOpen ? t('dashCollapseSidebar') : t('dashExpandSidebar')}
                className="text-[#A1A1AA] hover:text-[#E4FF00] transition-colors p-1.5 rounded-sm hover:bg-white/[0.04] flex-shrink-0"
              >
                {isSidebarOpen
                  ? <PanelLeftClose className="w-5 h-5" />
                  : <PanelLeftOpen className="w-5 h-5" />}
              </button>
              <LanguageToggle placement="bottom" />
            </div>

            {/* CENTER */}
            <div className="flex flex-col items-center text-center min-w-0">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-[#E4FF00] flex-shrink-0" />
                <h1 className="font-['Chivo'] font-bold text-sm sm:text-xl truncate">{t('dashTitle')}</h1>
              </div>
              <p className="text-[10px] sm:text-xs text-[#A1A1AA] hidden sm:block truncate">{t('dashSubtitle')}</p>
            </div>

            {/* RIGHT */}
            <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
              <Button
                onClick={() => exportProject('apk')}
                size="sm"
                variant="outline"
                data-testid="export-apk-btn"
                className="hidden sm:inline-flex border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] px-2 lg:px-3"
                title="Export Mobile (APK)"
              >
                <Smartphone className="w-4 h-4 lg:mr-1" />
                <span className="hidden lg:inline">APK</span>
              </Button>

              <Button
                onClick={() => exportProject('exe')}
                size="sm"
                variant="outline"
                data-testid="export-exe-btn"
                className="hidden sm:inline-flex border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] px-2 lg:px-3"
                title="Export Desktop (EXE)"
              >
                <Monitor className="w-4 h-4 lg:mr-1" />
                <span className="hidden lg:inline">EXE</span>
              </Button>

              <Button
                onClick={() => exportProject('source')}
                size="sm"
                variant="outline"
                data-testid="export-source-btn"
                className="hidden sm:inline-flex border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] px-2 lg:px-3"
                title="Source code (ZIP)"
              >
                <Download className="w-4 h-4 lg:mr-1" />
                <span className="hidden lg:inline">ZIP</span>
              </Button>

              <div className="ml-1 sm:ml-2 flex items-center gap-2 border-l border-white/10 pl-1 sm:pl-2">
                <UserMenu user={user} onLogout={handleLogout} />
              </div>
            </div>
          </div>
        </header>

        {/* 4 Main Buttons Center */}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-5xl w-full">
            <div className="text-center mb-8">
              <h2 className="text-4xl font-['Chivo'] font-black mb-4">
                {t('dashWhatToDo')}
              </h2>
              {projects.length === 0 && (
                <p data-testid="empty-projects-hint" className="text-xs text-[#E4FF00]/80 mt-3 font-['IBM_Plex_Sans']">
                  {t('dashEmptyHint')}
                </p>
              )}
            </div>

            {/* (Assistant Guidé retiré du dashboard sur demande utilisateur — la route /wizard reste accessible) */}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Bouton Chat (en ligne uniquement) */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/chat', { state: { mode: 'online' } })}
                data-testid="online-chat-btn"
                className="group bg-white/[0.03] border border-[#E4FF00]/30 rounded-lg p-8 backdrop-blur-xl hover:border-[#E4FF00] hover:bg-[#E4FF00]/[0.06] hover:shadow-[0_8px_30px_rgba(228,255,0,0.2)] transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-[#E4FF00] rounded-full flex items-center justify-center">
                    <Send className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">{t('dashChat')}</h3>
                    <p className="text-[#A1A1AA]">{t('dashChatDescOn')}</p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton Création (en ligne uniquement) */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/create', { state: { mode: 'online' } })}
                data-testid="online-create-btn"
                data-tour="create"
                className="group bg-white/[0.03] border border-[#00FF66]/30 rounded-lg p-8 backdrop-blur-xl hover:border-[#00FF66] hover:bg-[#00FF66]/[0.06] hover:shadow-[0_8px_30px_rgba(0,255,102,0.2)] transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-[#00FF66] rounded-full flex items-center justify-center">
                    <Code2 className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">{t('dashCreate')}</h3>
                    <p className="text-[#A1A1AA]">{t('dashCreateDescOn')}</p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton Chat hors ligne (Ollama) */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/chat', { state: { mode: 'offline' } })}
                data-testid="offline-chat-btn"
                className="group bg-white/[0.03] border border-cyan-400/30 rounded-lg p-8 backdrop-blur-xl hover:border-cyan-400 hover:bg-cyan-400/[0.06] hover:shadow-[0_8px_30px_rgba(34,211,238,0.2)] transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-cyan-400 rounded-full flex items-center justify-center">
                    <Send className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">{t('dashChat')}</h3>
                    <p className="text-[#A1A1AA]">{t('dashChatDescOff')}</p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton Création hors ligne (Ollama) */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/create', { state: { mode: 'offline' } })}
                data-testid="offline-create-btn"
                className="group bg-white/[0.03] border border-purple-400/30 rounded-lg p-8 backdrop-blur-xl hover:border-purple-400 hover:bg-purple-400/[0.06] hover:shadow-[0_8px_30px_rgba(192,132,252,0.2)] transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-purple-400 rounded-full flex items-center justify-center">
                    <Code2 className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">{t('dashCreate')}</h3>
                    <p className="text-[#A1A1AA]">{t('dashCreateDescOff')}</p>
                  </div>
                </div>
              </motion.button>
            </div>
          </div>
        </div>
      </div>

      <SwitchAccountModal
        open={switchAccountOpen}
        onClose={() => setSwitchAccountOpen(false)}
      />

      {/* Right-click context menu on a project */}
      {ctxMenu && (
        <div
          data-testid="project-ctx-menu"
          onClick={(e) => e.stopPropagation()}
          style={{ top: Math.min(ctxMenu.y, window.innerHeight - 200), left: Math.min(ctxMenu.x, window.innerWidth - 200) }}
          className="fixed z-50 w-48 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_8px_30px_rgba(0,0,0,0.6)] backdrop-blur-xl py-1"
        >
          <button
            type="button"
            onClick={() => startRename(ctxMenu.project)}
            data-testid="project-ctx-rename"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <Pencil className="w-4 h-4 text-[#E4FF00]" />
            <span>Renommer</span>
          </button>
          <button
            type="button"
            onClick={async () => {
              const pid = ctxMenu.project.project_id;
              const url = `${window.location.origin}/chat?project=${encodeURIComponent(pid)}`;
              try {
                await navigator.clipboard.writeText(url);
                toast.success('Lien copié ! Colle-le dans un nouveau chat pour y faire référence.');
              } catch {
                toast.error('Impossible de copier le lien');
              }
              setCtxMenu(null);
            }}
            data-testid="project-ctx-copy-link"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <Link2 className="w-4 h-4 text-cyan-400" />
            <span>Copier le lien</span>
          </button>
          {(ctxMenu.project?.project_type !== 'chat') && (
            <button
              type="button"
              onClick={() => { const pid = ctxMenu.project.project_id; setCtxMenu(null); navigate(`/preview/${pid}`); }}
              data-testid="project-ctx-preview"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
            >
              <Eye className="w-4 h-4 text-emerald-400" />
              <span>Aperçu Live</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => exportProjectZip(ctxMenu.project)}
            data-testid="project-ctx-export-zip"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <Download className="w-4 h-4 text-cyan-400" />
            <span>Télécharger ZIP</span>
          </button>
          <button
            type="button"
            onClick={() => exportProjectGithub(ctxMenu.project)}
            data-testid="project-ctx-export-github"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <BookOpen className="w-4 h-4 text-purple-400" />
            <span>Pousser vers GitHub</span>
          </button>
          <button
            type="button"
            onClick={() => askDelete(ctxMenu.project)}
            data-testid="project-ctx-delete"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            <span>Supprimer</span>
          </button>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div
          data-testid="project-delete-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => setDeleteTarget(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-sm w-full bg-[#0F0F13] border border-red-500/40 rounded-sm p-6 space-y-4"
          >
            <div className="flex items-start gap-3">
              <Trash2 className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
              <div>
                <h3 className="font-['Chivo'] font-bold text-white">Supprimer ce projet ?</h3>
                <p className="text-sm text-[#A1A1AA] mt-1">
                  « {deleteTarget.name} » sera définitivement supprimé. Cette action est irréversible.
                </p>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                data-testid="project-delete-cancel"
                className="px-4 py-2 text-sm border border-white/15 rounded-sm text-white hover:border-white/30 transition-colors"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                data-testid="project-delete-confirm"
                className="px-4 py-2 text-sm bg-red-500/20 border border-red-500 text-red-300 rounded-sm hover:bg-red-500/30 transition-colors font-['Chivo'] font-bold"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
