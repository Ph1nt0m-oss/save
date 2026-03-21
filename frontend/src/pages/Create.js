import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { 
  Send, Sparkles, Loader2, ArrowLeft, Download, 
  Smartphone, Monitor, Globe, Play, Code, Eye
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Create() {
  const { user } = useAuth();
  const navigate = useNavigate();
  
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentProject, setCurrentProject] = useState(null);
  const [generatedCode, setGeneratedCode] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const generateApp = async () => {
    if (!input.trim() || isGenerating) return;

    const userMessage = input;
    setInput('');
    setIsGenerating(true);

    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    }]);

    try {
      const response = await axios.post(
        `${API}/ai/generate-complete-app`,
        { description: userMessage },
        { withCredentials: true }
      );

      setGeneratedCode(response.data.code);
      setCurrentProject(response.data.project);

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.explanation,
        timestamp: new Date(),
        hasCode: true
      }]);

      toast.success('Application générée !');
    } catch (error) {
      console.error('Generation error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Erreur: Installez Ollama pour une génération illimitée. Voir OLLAMA_SETUP.md',
        timestamp: new Date()
      }]);
      toast.error('Erreur de génération');
    } finally {
      setIsGenerating(false);
    }
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
            </div>
          </div>

          {currentProject && (
            <div className="flex items-center gap-2">
              <Button onClick={() => setShowPreview(!showPreview)} size="sm" variant="outline">
                <Eye className="w-4 h-4 mr-2" />
                {showPreview ? 'Cacher' : 'Aperçu'}
              </Button>
              <Button onClick={() => exportApp('apk')} size="sm" className="bg-[#E4FF00] text-[#050505]">
                <Smartphone className="w-4 h-4 mr-2" />
                APK
              </Button>
              <Button onClick={() => exportApp('exe')} size="sm" className="bg-[#E4FF00] text-[#050505]">
                <Monitor className="w-4 h-4 mr-2" />
                EXE
              </Button>
              <Button onClick={() => exportApp('web')} size="sm" className="bg-[#00FF66] text-[#050505]">
                <Globe className="w-4 h-4 mr-2" />
                Web
              </Button>
            </div>
          )}
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
                    key={idx}
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
                        <div className="mt-3 pt-3 border-t border-white/10">
                          <p className="text-xs text-[#00FF66] flex items-center gap-2">
                            <Code className="w-4 h-4" />
                            Code généré et prêt à exporter
                          </p>
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
                  >
                    <div className="bg-[#050505] border border-white/10 p-4 rounded-lg flex items-center gap-3">
                      <Loader2 className="w-5 h-5 animate-spin text-[#E4FF00]" />
                      <span>Génération en cours...</span>
                    </div>
                  </motion.div>
                )}
              </div>

              <div ref={messagesEndRef} />
            </ScrollArea>

            <div className="p-4 border-t border-white/10">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && generateApp()}
                  placeholder="Créé-moi une application de..."
                  disabled={isGenerating}
                  className="flex-1 px-4 py-3 bg-[#050505] border border-white/20 rounded-lg focus:outline-none focus:border-[#E4FF00] disabled:opacity-50"
                />
                <Button
                  onClick={generateApp}
                  disabled={isGenerating || !input.trim()}
                  size="lg"
                  className="bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90 px-8"
                >
                  {isGenerating ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <><Sparkles className="w-5 h-5 mr-2" /> Générer</>
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
                        <div key={idx} className="bg-[#050505] border border-white/10 rounded p-4">
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
    </div>
  );
}
