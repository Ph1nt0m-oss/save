import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { Send, Loader2, ArrowLeft, Sparkles, Globe, FileText, FileType, Smartphone, ExternalLink } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Chat() {
  const navigate = useNavigate();
  const location = useLocation();
  const mode = location.state?.mode || 'online';
  
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Ouvrir la prévisualisation dans un nouvel onglet
  const openPreview = (type) => {
    const previewTypes = {
      web: `${API}/preview/demo/web`,
      pdf: `${API}/preview/demo/pdf`,
      docx: `${API}/preview/demo/docx`,
      app: `${API}/preview/demo/app`
    };
    
    window.open(previewTypes[type], '_blank');
    toast.success(`Prévisualisation ${type.toUpperCase()} ouverte`);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input;
    setInput('');
    setIsLoading(true);

    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    }]);

    try {
      const response = await axios.post(
        `${API}/chat/message`,
        { message: userMessage, mode },
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

  const modeColor = mode === 'online' ? '#00FF66' : 'cyan';
  const modeLabel = mode === 'online' ? 'EN LIGNE' : 'HORS LIGNE';

  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col">
      <header className="bg-[#0F0F13] border-b border-white/10 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button onClick={() => navigate('/dashboard')} variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Retour
            </Button>
            <div>
              <h1 className="font-['Chivo'] font-bold text-2xl">Interaction IA</h1>
              <div className="flex items-center gap-2 mt-1">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: modeColor }}></div>
                <span className="text-xs font-['IBM_Plex_Mono']" style={{ color: modeColor }}>
                  {modeLabel}
                </span>
              </div>
            </div>
          </div>
          
          {/* Boutons de Prévisualisation */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#A1A1AA] font-['IBM_Plex_Mono'] mr-2">PRÉVISUALISATION:</span>
            
            <Button
              onClick={() => openPreview('web')}
              size="sm"
              variant="outline"
              data-testid="chat-preview-web-btn"
              className="border-[#00FF66] text-[#00FF66] hover:bg-[#00FF66] hover:text-[#050505]"
            >
              <Globe className="w-4 h-4 mr-1" />
              Web
            </Button>
            
            <Button
              onClick={() => openPreview('app')}
              size="sm"
              variant="outline"
              data-testid="chat-preview-app-btn"
              className="border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505]"
            >
              <Smartphone className="w-4 h-4 mr-1" />
              App
            </Button>
            
            <Button
              onClick={() => openPreview('pdf')}
              size="sm"
              variant="outline"
              data-testid="chat-preview-pdf-btn"
              className="border-red-400 text-red-400 hover:bg-red-400 hover:text-[#050505]"
            >
              <FileText className="w-4 h-4 mr-1" />
              PDF
            </Button>
            
            <Button
              onClick={() => openPreview('docx')}
              size="sm"
              variant="outline"
              data-testid="chat-preview-docx-btn"
              className="border-blue-400 text-blue-400 hover:bg-blue-400 hover:text-[#050505]"
            >
              <FileType className="w-4 h-4 mr-1" />
              DOCX
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 max-w-5xl w-full mx-auto flex flex-col p-6">
        <ScrollArea className="flex-1 mb-6">
          {messages.length === 0 && (
            <div className="text-center py-20">
              <Sparkles className="w-20 h-20 mx-auto mb-6" style={{ color: modeColor }} />
              <h2 className="text-2xl font-['Chivo'] font-bold mb-3">
                Interaction IA {modeLabel}
              </h2>
              <p className="text-[#A1A1AA] mb-4">
                {mode === 'online' 
                  ? 'Discutez avec une IA puissante en ligne'
                  : 'Discutez avec une IA locale (nécessite Ollama)'}
              </p>
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
                <div
                  className={`max-w-[80%] p-4 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-[#0F0F13] border border-white/10'
                      : 'bg-[#0F0F13] border-l-2'
                  }`}
                  style={msg.role === 'assistant' ? { borderLeftColor: modeColor } : {}}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <p className="text-xs text-[#A1A1AA] mt-2">
                    {msg.timestamp.toLocaleTimeString('fr-FR')}
                  </p>
                </div>
              </motion.div>
            ))}

            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex justify-start"
              >
                <div className="bg-[#0F0F13] border-l-2 p-4 rounded-lg" style={{ borderLeftColor: modeColor }}>
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: modeColor }} />
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <form onSubmit={sendMessage}>
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Posez une question..."
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-[#0F0F13] border border-white/20 rounded-lg focus:outline-none disabled:opacity-50"
              style={{ borderColor: input ? modeColor : undefined }}
            />
            <Button
              type="submit"
              disabled={isLoading || !input.trim()}
              size="lg"
              className="px-8"
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
