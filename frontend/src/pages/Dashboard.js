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
  Wand2, Wifi, WifiOff, Users, BookOpen, UserCog
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
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

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
      <Onboarding />
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
              <button
                key={project.project_id}
                onClick={() => setSelectedProject(project)}
                data-testid={`project-${project.project_id}`}
                className={`w-full text-left p-3 rounded-sm border transition-all ${
                  selectedProject?.project_id === project.project_id
                    ? 'bg-[#E4FF00]/10 border-[#E4FF00]'
                    : 'bg-[#050505] border-white/10 hover:border-white/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="font-['IBM_Plex_Sans'] font-medium truncate">
                      {project.name}
                    </div>
                    <div className="text-xs text-[#A1A1AA] mt-1 flex items-center gap-2">
                      {project.project_type === 'web' && <Globe className="w-3 h-3" />}
                      {project.project_type === 'mobile' && <Smartphone className="w-3 h-3" />}
                      {project.project_type === 'desktop' && <Monitor className="w-3 h-3" />}
                      <span>{project.project_type}</span>
                    </div>
                  </div>
                  {selectedProject?.project_id === project.project_id && (
                    <ChevronRight className="w-4 h-4 text-[#E4FF00]" />
                  )}
                </div>
              </button>
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
              <button
                onClick={() => navigate('/discover')}
                data-testid="dashboard-tutorial-btn"
                title={t('dashTutorial')}
                aria-label={t('dashTutorial')}
                className="inline-flex items-center gap-1.5 text-xs text-[#A1A1AA] hover:text-[#E4FF00] border border-white/10 hover:border-[#E4FF00]/40 rounded-sm px-2 sm:px-2.5 py-1.5 transition-colors font-['Chivo'] font-bold"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span className="hidden md:inline">{t('dashTutorial')}</span>
              </button>

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
              <p className="text-[#A1A1AA] text-lg flex items-center justify-center gap-2">
                {t('dashChooseMode')}
                <FeatureHint id="modes" side="bottom">
                  {t('dashInfoOnline')} — {t('dashInfoOffline')}
                </FeatureHint>
              </p>
              {projects.length === 0 && (
                <p data-testid="empty-projects-hint" className="text-xs text-[#E4FF00]/80 mt-3 font-['IBM_Plex_Sans']">
                  {t('dashEmptyHint')}
                </p>
              )}
            </div>

            {/* Assistant Guidé - Nouveau bouton principal */}
            <div className="relative">
              <div className="absolute top-3 right-3 z-10">
                <FeatureHint id="wizard">
                  35+ templates prêts à personnaliser : CRM, e-commerce, blog, jeu, IA. Idéal si tu n'as pas d'idée précise — réponds à 4-5 questions, l'IA fait le reste.
                </FeatureHint>
              </div>
              <motion.button
              whileHover={{ y: -2, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate('/wizard')}
              data-testid="wizard-btn"
              data-tour="wizard"
              className="w-full mb-6 bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-[#050505] rounded-lg p-6 hover:opacity-95 hover:shadow-[0_8px_30px_rgba(228,255,0,0.35)] transition-all"
            >
              <div className="flex items-center justify-center gap-4">
                <Wand2 className="w-8 h-8" />
                <div className="text-left">
                  <h3 className="text-2xl font-['Chivo'] font-bold">{t('dashWizard')}</h3>
                  <p className="text-[#050505]/70">{t('dashWizardDesc')}</p>
                </div>
              </div>
            </motion.button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Bouton 1: Interaction en ligne */}
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
                    <div className="inline-block px-3 py-1 bg-[#00FF66] text-[#050505] rounded-full text-xs font-bold mb-3">
                      {t('dashChatBadgeOn')}
                    </div>
                    <p className="text-[#A1A1AA]">{t('dashChatDescOn')}</p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton 2: Création en ligne */}
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
                    <div className="inline-block px-3 py-1 bg-[#00FF66] text-[#050505] rounded-full text-xs font-bold mb-3">
                      {t('dashCreateBadgeOn')}
                    </div>
                    <p className="text-[#A1A1AA]">{t('dashCreateDescOn')}</p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton 3: Interaction hors ligne */}
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
                    <div className="inline-block px-3 py-1 bg-cyan-400 text-[#050505] rounded-full text-xs font-bold mb-3">
                      {t('dashChatBadgeOff')}
                    </div>
                    <p className="text-[#A1A1AA]">{t('dashChatDescOff')}</p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton 4: Création hors ligne */}
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
                    <div className="inline-block px-3 py-1 bg-purple-400 text-[#050505] rounded-full text-xs font-bold mb-3">
                      {t('dashCreateBadgeOff')}
                    </div>
                    <p className="text-[#A1A1AA]">{t('dashCreateDescOff')}</p>
                  </div>
                </div>
              </motion.button>
            </div>

            {/* Info section */}
            <div className="mt-12 text-center">
              <p className="text-sm text-[#A1A1AA] mb-2">{t('dashInfoOnline')}</p>
              <p className="text-sm text-[#A1A1AA]">{t('dashInfoOffline')}</p>
            </div>
          </div>
        </div>
      </div>

      <SwitchAccountModal
        open={switchAccountOpen}
        onClose={() => setSwitchAccountOpen(false)}
      />
    </div>
  );
}
