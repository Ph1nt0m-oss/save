import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { useCache } from '../contexts/CacheContext';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { 
  Send, Plus, LogOut, User, Sparkles, 
  Code2, Smartphone, Monitor, Globe, 
  Download, Loader2, Menu, X, ChevronRight, Zap,
  Wand2, Languages, Wifi, WifiOff
} from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import Onboarding from '../components/Onboarding';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const { user, logout } = useAuth();
  const { language, toggleLanguage, t } = useLanguage();
  const { isOnline, cacheProjects, getCachedProjects } = useCache();
  const navigate = useNavigate();
  
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [aiStatus, setAiStatus] = useState('online');
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadChatHistory(selectedProject.project_id);
    }
  }, [selectedProject]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`, {
        withCredentials: true
      });
      setProjects(response.data);
      // Cache pour mode hors ligne
      cacheProjects(response.data);
    } catch (error) {
      console.error('Error loading projects:', error);
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
  };

  const loadChatHistory = async (projectId) => {
    try {
      const response = await axios.get(`${API}/chat/history?project_id=${projectId}`, {
        withCredentials: true
      });
      setMessages(response.data);
    } catch (error) {
      console.error('Error loading chat history:', error);
    }
  };

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
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-[#E4FF00]" />
            <span className="font-['Chivo'] font-bold">Projets</span>
          </div>
          <button
            onClick={() => setIsSidebarOpen(false)}
            className="lg:hidden text-[#A1A1AA] hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          <Button
            onClick={createNewProject}
            data-testid="create-project-btn"
            className="w-full bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90 font-['Chivo'] font-bold"
          >
            <Plus className="w-4 h-4 mr-2" />
            Nouveau Projet
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
          <div className="flex items-center gap-2 text-sm font-['IBM_Plex_Mono']">
            <div className="w-2 h-2 rounded-full bg-[#00FF66] animate-pulse-slow"></div>
            <span className="text-[#A1A1AA]">IA Disponible</span>
          </div>
          
          <button
            onClick={handleLogout}
            data-testid="logout-btn"
            className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-white/20 rounded-sm hover:border-red-500 hover:text-red-500 transition-all"
          >
            <LogOut className="w-4 h-4" />
            <span className="font-['IBM_Plex_Sans']">Déconnexion</span>
          </button>
        </div>
      </motion.aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col">
        {/* Header with exports */}
        <header className="bg-[#0F0F13] border-b border-white/10 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {!isSidebarOpen && (
                <button
                  onClick={() => setIsSidebarOpen(true)}
                  className="text-[#A1A1AA] hover:text-white"
                >
                  <Menu className="w-6 h-6" />
                </button>
              )}
              <div>
                <h1 className="font-['Chivo'] font-bold text-xl">CodeForge AI</h1>
                <p className="text-sm text-[#A1A1AA]">Création Sans Limites</p>
              </div>
            </div>

            {/* EXPORTS - TOUJOURS VISIBLES */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#A1A1AA] font-['IBM_Plex_Mono'] mr-2">EXPORTS:</span>
              
              <Button
                onClick={() => exportProject('apk')}
                size="sm"
                variant="outline"
                data-testid="export-apk-btn"
                className="border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505]"
                title="Export Mobile (APK)"
              >
                <Smartphone className="w-4 h-4 mr-1" />
                APK
              </Button>
              
              <Button
                onClick={() => exportProject('exe')}
                size="sm"
                variant="outline"
                data-testid="export-exe-btn"
                className="border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505]"
                title="Export Desktop (EXE)"
              >
                <Monitor className="w-4 h-4 mr-1" />
                EXE
              </Button>
              
              <Button
                onClick={() => exportProject('source')}
                size="sm"
                variant="outline"
                data-testid="export-source-btn"
                className="border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505]"
                title="Télécharger Code Source (ZIP)"
              >
                <Download className="w-4 h-4 mr-1" />
                ZIP
              </Button>

              <div className="ml-3 flex items-center gap-2 border-l border-white/10 pl-3">
                <User className="w-5 h-5 text-[#A1A1AA]" />
                <span className="text-sm">{user?.name}</span>
              </div>
            </div>
          </div>
        </header>

        {/* 4 Main Buttons Center */}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-5xl w-full">
            <div className="text-center mb-8">
              <div className="flex items-center justify-center gap-4 mb-4">
                {/* Indicateur de connexion */}
                <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs ${isOnline ? 'bg-[#00FF66]/20 text-[#00FF66]' : 'bg-orange-400/20 text-orange-400'}`}>
                  {isOnline ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                  {isOnline ? 'En ligne' : 'Hors ligne'}
                </div>
                
                {/* Sélecteur de langue */}
                <button
                  onClick={toggleLanguage}
                  className="flex items-center gap-2 px-3 py-1 rounded-full text-xs bg-white/10 hover:bg-white/20 transition-colors"
                >
                  <Languages className="w-3 h-3" />
                  {language === 'fr' ? 'FR' : 'EN'}
                </button>
              </div>
              
              <h2 className="text-4xl font-['Chivo'] font-black mb-4">
                {language === 'fr' ? 'Que souhaitez-vous faire ?' : 'What would you like to do?'}
              </h2>
              <p className="text-[#A1A1AA] text-lg">
                {language === 'fr' ? 'Choisissez votre mode de travail' : 'Choose your work mode'}
              </p>
            </div>

            {/* Assistant Guidé - Nouveau bouton principal */}
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate('/wizard')}
              data-testid="wizard-btn"
              className="w-full mb-6 bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-[#050505] rounded-lg p-6 hover:opacity-90 transition-all"
            >
              <div className="flex items-center justify-center gap-4">
                <Wand2 className="w-8 h-8" />
                <div className="text-left">
                  <h3 className="text-2xl font-['Chivo'] font-bold">
                    {language === 'fr' ? 'Assistant Guidé' : 'Guided Wizard'}
                  </h3>
                  <p className="text-[#050505]/70">
                    {language === 'fr' ? 'Créez votre app étape par étape avec des questions simples' : 'Create your app step by step with simple questions'}
                  </p>
                </div>
              </div>
            </motion.button>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Bouton 1: Interaction en ligne */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/chat', { state: { mode: 'online' } })}
                data-testid="online-chat-btn"
                className="group bg-[#0F0F13] border-2 border-[#E4FF00] rounded-lg p-8 hover:bg-[#E4FF00]/5 transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-[#E4FF00] rounded-full flex items-center justify-center">
                    <Send className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">
                      {language === 'fr' ? 'Interaction' : 'Chat'}
                    </h3>
                    <div className="inline-block px-3 py-1 bg-[#00FF66] text-[#050505] rounded-full text-xs font-bold mb-3">
                      {language === 'fr' ? 'IA EN LIGNE' : 'ONLINE AI'}
                    </div>
                    <p className="text-[#A1A1AA]">
                      {language === 'fr' ? 'Discutez avec une IA puissante' : 'Chat with a powerful AI'}
                    </p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton 2: Création en ligne */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/create', { state: { mode: 'online' } })}
                data-testid="online-create-btn"
                className="group bg-[#0F0F13] border-2 border-[#00FF66] rounded-lg p-8 hover:bg-[#00FF66]/5 transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-[#00FF66] rounded-full flex items-center justify-center">
                    <Code2 className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">
                      {language === 'fr' ? 'Création' : 'Create'}
                    </h3>
                    <div className="inline-block px-3 py-1 bg-[#00FF66] text-[#050505] rounded-full text-xs font-bold mb-3">
                      {language === 'fr' ? 'EN LIGNE' : 'ONLINE'}
                    </div>
                    <p className="text-[#A1A1AA]">
                      {language === 'fr' ? 'Générez apps mobile, web, desktop' : 'Generate mobile, web, desktop apps'}
                    </p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton 3: Interaction hors ligne */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/chat', { state: { mode: 'offline' } })}
                data-testid="offline-chat-btn"
                className="group bg-[#0F0F13] border-2 border-cyan-400 rounded-lg p-8 hover:bg-cyan-400/5 transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-cyan-400 rounded-full flex items-center justify-center">
                    <Send className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">
                      {language === 'fr' ? 'Interaction' : 'Chat'}
                    </h3>
                    <div className="inline-block px-3 py-1 bg-cyan-400 text-[#050505] rounded-full text-xs font-bold mb-3">
                      {language === 'fr' ? 'IA HORS LIGNE' : 'OFFLINE AI'}
                    </div>
                    <p className="text-[#A1A1AA]">
                      {language === 'fr' ? 'IA locale (Ollama) sans connexion' : 'Local AI (Ollama) without internet'}
                    </p>
                  </div>
                </div>
              </motion.button>

              {/* Bouton 4: Création hors ligne */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/create', { state: { mode: 'offline' } })}
                data-testid="offline-create-btn"
                className="group bg-[#0F0F13] border-2 border-purple-400 rounded-lg p-8 hover:bg-purple-400/5 transition-all"
              >
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 bg-purple-400 rounded-full flex items-center justify-center">
                    <Code2 className="w-8 h-8 text-[#050505]" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-['Chivo'] font-bold mb-2">
                      {language === 'fr' ? 'Création' : 'Create'}
                    </h3>
                    <div className="inline-block px-3 py-1 bg-purple-400 text-[#050505] rounded-full text-xs font-bold mb-3">
                      {language === 'fr' ? 'HORS LIGNE' : 'OFFLINE'}
                    </div>
                    <p className="text-[#A1A1AA]">
                      {language === 'fr' ? 'Générez apps avec IA locale (Ollama)' : 'Generate apps with local AI (Ollama)'}
                    </p>
                  </div>
                </div>
              </motion.button>
            </div>

            {/* Info section */}
            <div className="mt-12 text-center">
              <p className="text-sm text-[#A1A1AA] mb-2">
                {language === 'fr' 
                  ? '💡 Mode en ligne : IA puissante avec Ollama distant'
                  : '💡 Online mode: Powerful AI with remote Ollama'}
              </p>
              <p className="text-sm text-[#A1A1AA]">
                {language === 'fr'
                  ? '🔌 Mode hors ligne : Nécessite Ollama installé localement'
                  : '🔌 Offline mode: Requires Ollama installed locally'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
