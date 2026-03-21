import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { 
  Send, Plus, LogOut, User, Sparkles, 
  Code2, Smartphone, Monitor, Globe, 
  Download, Loader2, Menu, X, ChevronRight
} from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const { user, logout } = useAuth();
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
    } catch (error) {
      console.error('Error loading projects:', error);
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
      toast.error('Sélectionnez un projet');
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
      toast.error('Sélectionnez un projet');
      return;
    }

    try {
      const response = await axios.post(
        `${API}/export/prepare?project_id=${selectedProject.project_id}&export_type=${exportType}`,
        {},
        { withCredentials: true }
      );

      toast.success(response.data.message);
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
            <div className={`w-2 h-2 rounded-full animate-pulse-slow ${
              aiStatus === 'online' ? 'bg-[#00FF66]' : 'bg-cyan-400'
            }`}></div>
            <span className="text-[#A1A1AA]">
              {aiStatus === 'online' ? 'IA en ligne' : 'Mode hors ligne'}
            </span>
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

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-[#0F0F13] border-b border-white/10 px-6 py-4 flex items-center justify-between">
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
              <h1 className="font-['Chivo'] font-bold text-xl">
                {selectedProject ? selectedProject.name : 'CodeForge AI'}
              </h1>
              {selectedProject && (
                <p className="text-sm text-[#A1A1AA] font-['IBM_Plex_Sans']">
                  {selectedProject.description}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {selectedProject && (
              <>
                <Button
                  onClick={generateCode}
                  disabled={isLoading}
                  data-testid="generate-code-btn"
                  className="bg-[#00FF66] text-[#050505] hover:bg-[#00FF66]/90 font-['Chivo'] font-bold"
                >
                  <Code2 className="w-4 h-4 mr-2" />
                  Générer Code
                </Button>

                <div className="flex items-center gap-1 border-l border-white/10 pl-3">
                  <Button
                    onClick={() => exportProject('apk')}
                    size="sm"
                    variant="outline"
                    data-testid="export-apk-btn"
                    className="border-white/20 hover:border-[#E4FF00] hover:text-[#E4FF00]"
                  >
                    <Smartphone className="w-4 h-4" />
                  </Button>
                  <Button
                    onClick={() => exportProject('exe')}
                    size="sm"
                    variant="outline"
                    data-testid="export-exe-btn"
                    className="border-white/20 hover:border-[#E4FF00] hover:text-[#E4FF00]"
                  >
                    <Monitor className="w-4 h-4" />
                  </Button>
                  <Button
                    onClick={() => exportProject('web')}
                    size="sm"
                    variant="outline"
                    data-testid="export-web-btn"
                    className="border-white/20 hover:border-[#E4FF00] hover:text-[#E4FF00]"
                  >
                    <Globe className="w-4 h-4" />
                  </Button>
                </div>
              </>
            )}

            <div className="flex items-center gap-2 border-l border-white/10 pl-3">
              <User className="w-5 h-5 text-[#A1A1AA]" />
              <span className="text-sm font-['IBM_Plex_Sans']">{user?.name}</span>
            </div>
          </div>
        </header>

        {/* Messages */}
        <ScrollArea className="flex-1 px-6 py-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {messages.length === 0 && !selectedProject && (
              <div className="text-center py-20">
                <Sparkles className="w-16 h-16 text-[#E4FF00] mx-auto mb-6" />
                <h2 className="text-2xl font-['Chivo'] font-bold mb-3">
                  Bienvenue sur CodeForge AI
                </h2>
                <p className="text-[#A1A1AA] font-['IBM_Plex_Sans'] mb-6">
                  Créez un nouveau projet pour commencer à générer des applications
                </p>
                <Button
                  onClick={createNewProject}
                  className="bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90 font-['Chivo'] font-bold"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Créer un Projet
                </Button>
              </div>
            )}

            <AnimatePresence>
              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] p-4 rounded-sm ${
                      msg.role === 'user'
                        ? 'bg-[#0F0F13] border border-white/10 text-right'
                        : 'bg-[#0F0F13] border-l-2 border-[#E4FF00]'
                    }`}
                    data-testid={`message-${msg.role}-${idx}`}
                  >
                    <div className="font-['IBM_Plex_Sans'] whitespace-pre-wrap">
                      {msg.content}
                    </div>
                    <div className="text-xs text-[#A1A1AA] mt-2 font-['IBM_Plex_Mono']">
                      {new Date(msg.timestamp).toLocaleTimeString('fr-FR')}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex justify-start"
              >
                <div className="bg-[#0F0F13] border-l-2 border-[#E4FF00] p-4 rounded-sm">
                  <Loader2 className="w-5 h-5 animate-spin text-[#E4FF00]" />
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="border-t border-white/10 bg-[#0F0F13] px-6 py-4">
          <form onSubmit={sendMessage} className="max-w-4xl mx-auto">
            <div className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Décrivez votre application ou posez une question..."
                disabled={isLoading}
                data-testid="chat-input"
                className="flex-1 px-4 py-3 bg-[#050505] border border-white/20 rounded-sm text-white placeholder:text-[#A1A1AA] focus:outline-none focus:border-[#E4FF00] font-['IBM_Plex_Sans'] disabled:opacity-50"
              />
              <Button
                type="submit"
                disabled={isLoading || !inputMessage.trim()}
                data-testid="send-message-btn"
                className="px-6 bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90 disabled:opacity-50 font-['Chivo'] font-bold"
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
    </div>
  );
}
