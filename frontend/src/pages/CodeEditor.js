import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import axios from 'axios';
import { 
  Send, Save, Folder, FileCode, 
  Plus, X, Loader2, Sparkles, ArrowLeft,
  Download, Smartphone, Monitor
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function CodeEditor() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const project = location.state?.project;

  const [files, setFiles] = useState([
    { name: 'index.html', language: 'html', content: '<!DOCTYPE html>\\n<html>\\n<head>\\n  <title>Mon App</title>\\n</head>\\n<body>\\n  <h1>Hello World!</h1>\\n</body>\\n</html>' }
  ]);
  const [activeFile, setActiveFile] = useState(0);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const editorRef = useRef(null);

  useEffect(() => {
    if (project?.generated_code?.files) {
      const projectFiles = project.generated_code.files.map(f => ({
        name: f.path,
        language: getLanguageFromFilename(f.path),
        content: f.content
      }));
      setFiles(projectFiles);
    }
  }, [project]);

  const getLanguageFromFilename = (filename) => {
    const ext = filename.split('.').pop();
    const langMap = {
      'js': 'javascript',
      'jsx': 'javascript',
      'ts': 'typescript',
      'tsx': 'typescript',
      'html': 'html',
      'css': 'css',
      'py': 'python',
      'json': 'json',
      'md': 'markdown'
    };
    return langMap[ext] || 'plaintext';
  };

  const handleEditorMount = (editor, monaco) => {
    editorRef.current = editor;
    monaco.editor.defineTheme('cyberTheme', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#0F0F13',
        'editor.foreground': '#FFFFFF',
        'editorCursor.foreground': '#E4FF00',
        'editor.lineHighlightBackground': '#1A1A1F',
        'editorLineNumber.foreground': '#A1A1AA',
        'editor.selectionBackground': '#E4FF0033',
        'editor.inactiveSelectionBackground': '#E4FF0020'
      }
    });
    monaco.editor.setTheme('cyberTheme');
  };

  const handleEditorChange = (value) => {
    const newFiles = [...files];
    newFiles[activeFile].content = value;
    setFiles(newFiles);
  };

  const addFile = () => {
    const filename = prompt('Nom du fichier (ex: app.js):');
    if (!filename) return;

    setFiles([...files, {
      name: filename,
      language: getLanguageFromFilename(filename),
      content: ''
    }]);
    setActiveFile(files.length);
  };

  const deleteFile = (index) => {
    if (files.length === 1) {
      toast.error('Impossible de supprimer le dernier fichier');
      return;
    }
    const newFiles = files.filter((_, i) => i !== index);
    setFiles(newFiles);
    setActiveFile(Math.max(0, activeFile - 1));
  };

  const generateCode = async () => {
    if (!chatInput.trim()) return;

    setIsGenerating(true);
    const userMsg = { role: 'user', content: chatInput };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');

    try {
      const response = await axios.post(
        `${API}/ai/generate-code`,
        { 
          prompt: chatInput,
          existing_files: files.map(f => ({ path: f.name, content: f.content }))
        },
        { withCredentials: true }
      );

      const aiMsg = { role: 'assistant', content: response.data.explanation };
      setChatMessages(prev => [...prev, aiMsg]);

      if (response.data.files && response.data.files.length > 0) {
        const newFiles = response.data.files.map(f => ({
          name: f.path,
          language: getLanguageFromFilename(f.path),
          content: f.content
        }));
        setFiles(newFiles);
        setActiveFile(0);
        toast.success('Code généré avec succès !');
      }
    } catch (error) {
      console.error('Error generating code:', error);
      const errorMsg = { 
        role: 'assistant', 
        content: 'Erreur: Installez Ollama pour une IA gratuite illimitée. Voir OLLAMA_SETUP.md' 
      };
      setChatMessages(prev => [...prev, errorMsg]);
      toast.error('Erreur de génération');
    } finally {
      setIsGenerating(false);
    }
  };

  const saveProject = async () => {
    if (!project) {
      toast.error('Aucun projet sélectionné');
      return;
    }

    try {
      await axios.put(
        `${API}/projects/${project.project_id}`,
        {
          generated_code: {
            files: files.map(f => ({ path: f.name, content: f.content }))
          },
          status: 'completed'
        },
        { withCredentials: true }
      );
      toast.success('Projet sauvegardé !');
    } catch (error) {
      console.error('Error saving:', error);
      toast.error('Erreur de sauvegarde');
    }
  };

  const exportProject = async (type) => {
    await saveProject();
    
    if (type === 'apk') {
      window.open(`${BACKEND_URL}/api/export/mobile/${project.project_id}`, '_blank');
    } else if (type === 'exe') {
      window.open(`${BACKEND_URL}/api/export/desktop/${project.project_id}`, '_blank');
    } else if (type === 'zip') {
      try {
        const response = await axios.post(
          `${API}/export/download`,
          { project_id: project.project_id, export_type: 'source' },
          { withCredentials: true, responseType: 'blob' }
        );
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${project.name}.zip`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        toast.success('Code téléchargé !');
      } catch (error) {
        toast.error('Erreur de téléchargement');
      }
    }
  };

  return (
    <div className=\"h-screen bg-[#050505] text-white flex flex-col\">
      <header className=\"bg-[#0F0F13] border-b border-white/10 px-6 py-4 flex items-center justify-between\">
        <div className=\"flex items-center gap-4\">
          <Button onClick={() => navigate('/dashboard')} variant=\"ghost\" size=\"sm\">
            <ArrowLeft className=\"w-4 h-4 mr-2\" />
            Retour
          </Button>
          <div>
            <h1 className=\"font-['Chivo'] font-bold text-xl\">
              {project?.name || 'Éditeur de Code'}
            </h1>
            <p className=\"text-xs text-[#A1A1AA]\">IA Locale Gratuite - Sans Limites</p>
          </div>
        </div>

        <div className=\"flex items-center gap-2\">
          <Button onClick={saveProject} size=\"sm\" variant=\"outline\">
            <Save className=\"w-4 h-4 mr-2\" />
            Sauv.
          </Button>
          <Button onClick={() => exportProject('zip')} size=\"sm\" variant=\"outline\" className=\"border-[#E4FF00] text-[#E4FF00]\">
            <Download className=\"w-4 h-4\" />
          </Button>
          <Button onClick={() => exportProject('apk')} size=\"sm\" variant=\"outline\" className=\"border-[#E4FF00] text-[#E4FF00]\">
            <Smartphone className=\"w-4 h-4\" />
          </Button>
          <Button onClick={() => exportProject('exe')} size=\"sm\" variant=\"outline\" className=\"border-[#E4FF00] text-[#E4FF00]\">
            <Monitor className=\"w-4 h-4\" />
          </Button>
        </div>
      </header>

      <div className=\"flex-1 flex overflow-hidden\">
        <div className=\"w-64 bg-[#0F0F13] border-r border-white/10 flex flex-col\">
          <div className=\"p-4 border-b border-white/10 flex items-center justify-between\">
            <span className=\"font-['Chivo'] font-bold text-sm\">FICHIERS</span>
            <Button onClick={addFile} size=\"sm\" variant=\"ghost\" className=\"h-8 w-8 p-0\">
              <Plus className=\"w-4 h-4\" />
            </Button>
          </div>

          <ScrollArea className=\"flex-1\">
            <div className=\"p-2 space-y-1\">
              {files.map((file, index) => (
                <div
                  key={index}
                  onClick={() => setActiveFile(index)}
                  className={`group flex items-center justify-between p-2 rounded cursor-pointer ${
                    activeFile === index ? 'bg-[#E4FF00]/10 border border-[#E4FF00]' : 'hover:bg-white/5'
                  }`}
                >
                  <div className=\"flex items-center gap-2 flex-1 min-w-0\">
                    <FileCode className=\"w-4 h-4 text-[#E4FF00]\" />
                    <span className=\"text-sm truncate font-['IBM_Plex_Mono']\">{file.name}</span>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); deleteFile(index); }} className=\"opacity-0 group-hover:opacity-100\">
                    <X className=\"w-3 h-3 text-red-500\" />
                  </button>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        <div className=\"flex-1\">
          <Editor
            height=\"100%\"
            language={files[activeFile]?.language}
            value={files[activeFile]?.content}
            onChange={handleEditorChange}
            onMount={handleEditorMount}
            theme=\"cyberTheme\"
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: \"'IBM Plex Mono', monospace\",
              lineNumbers: 'on',
              automaticLayout: true
            }}
          />
        </div>

        <div className=\"w-96 bg-[#0F0F13] border-l border-white/10 flex flex-col\">
          <div className=\"p-4 border-b border-white/10 flex items-center gap-2\">
            <Sparkles className=\"w-5 h-5 text-[#E4FF00]\" />
            <span className=\"font-['Chivo'] font-bold\">IA Gratuite</span>
          </div>

          <ScrollArea className=\"flex-1 p-4\">
            <div className=\"space-y-4\">
              {chatMessages.length === 0 && (
                <div className=\"text-center py-8 text-[#A1A1AA] text-sm\">
                  <Sparkles className=\"w-12 h-12 mx-auto mb-4 text-[#E4FF00]\" />
                  <p>Décrivez ce que vous voulez créer</p>
                </div>
              )}

              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`p-3 rounded-sm ${msg.role === 'user' ? 'bg-[#050505] ml-8' : 'bg-[#050505] border-l-2 border-[#E4FF00] mr-8'}`}>
                  <p className=\"text-sm whitespace-pre-wrap\">{msg.content}</p>
                </div>
              ))}

              {isGenerating && (
                <div className=\"flex items-center gap-2 text-[#E4FF00]\">
                  <Loader2 className=\"w-4 h-4 animate-spin\" />
                  <span className=\"text-sm\">Génération...</span>
                </div>
              )}
            </div>
          </ScrollArea>

          <div className=\"p-4 border-t border-white/10\">
            <div className=\"flex gap-2\">
              <input
                type=\"text\"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && generateCode()}
                placeholder=\"Créez un formulaire...\"
                disabled={isGenerating}
                className=\"flex-1 px-3 py-2 bg-[#050505] border border-white/20 rounded-sm text-sm focus:outline-none focus:border-[#E4FF00]\"
              />
              <Button onClick={generateCode} disabled={isGenerating || !chatInput.trim()} size=\"sm\" className=\"bg-[#E4FF00] text-[#050505]\">
                <Send className=\"w-4 h-4\" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
