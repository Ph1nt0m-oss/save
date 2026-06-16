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
  Wand2, Wifi, WifiOff, Users, BookOpen, UserCog, Pencil, Trash2, MessageSquare, Eye, Brain, Link2, Copy, Share2, MessageCircleQuestion, Bot
} from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';
import { Button } from '../components/ui/button';
import ExportInReviewModal from '../components/ExportInReviewModal';
import { toast } from 'sonner';
import Onboarding from '../components/Onboarding';
import UserMenu from '../components/UserMenu';
import FeatureHint from '../components/FeatureHint';
import SwitchAccountModal from '../components/SwitchAccountModal';
import LanguageToggle from '../components/LanguageToggle';
import CreatorToolbar from '../components/CreatorToolbar';
import NotificationBell from '../components/NotificationBell';
import SiteLockedOverlay from '../components/SiteLockedOverlay';
import MessageButton from '../components/MessageButton';
import TheftButton from '../components/TheftButton';
import IdeasButton from '../components/IdeasButton';
import AnnounceButton from '../components/AnnounceButton';
import AccountsButton from '../components/AccountsButton';
import AccountVisitView from '../components/AccountVisitView';
import ExportApprovalNotifier from '../components/ExportApprovalNotifier';
import GroupChatsPanel from '../components/GroupChatsPanel';
import FriendsPanel from '../components/FriendsPanel';
import ViewSimulationBanner from '../components/ViewSimulationBanner';
import TranslatedProjectName from '../components/TranslatedProjectName';
import BotsAdminPanel from '../components/BotsAdminPanel';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import useViewSpec from '../hooks/useViewSpec';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const { isOnline, cacheProjects, getCachedProjects } = useCache();
  const navigate = useNavigate();
  const device = useDeviceIdentity();
  const canWrite = device.canWrite;
  const requireWrite = (action) => {
    if (canWrite) return true;
    toast.error(t('ro_toast_write'), { id: 'read-only' });
    return false;
  };
  
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    // iter67: open by default on desktop, closed on mobile so the main
    // content takes the full viewport instead of being squashed behind a
    // 280px-wide drawer that never appeared visually.
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches) {
      return false;
    }
    return true;
  });
  const [aiStatus, setAiStatus] = useState('online');
  const [switchAccountOpen, setSwitchAccountOpen] = useState(false);
  // Right-click context menu state for projects in the sidebar.
  const [ctxMenu, setCtxMenu] = useState(null); // { x, y, project } | null
  const [renameTarget, setRenameTarget] = useState(null); // project being renamed
  const [renameValue, setRenameValue] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null); // project pending delete confirm
  // Filtre de la sidebar — 'all' | 'chat-online' | 'chat-offline' | 'web-online' | 'web-offline'
  const [sidebarFilter, setSidebarFilter] = useState('all');
  const [visiting, setVisiting] = useState(null);
  // iter78 — fullscreen modal pour export pending/approved/rejected
  const [exportReview, setExportReview] = useState(null);  // {kind, status, request_id}
  // iter112 — Picker d'export multi-projets : si un chat parent a plusieurs
  // enfants (parent_chat_id===chat.project_id), l'utilisatrice doit choisir
  // lequel exporter (APK/EXE/ZIP). Le state stocke {kind, candidates, resolve}.
  const [exportPicker, setExportPicker] = useState(null);
  // iter82 — Group chats + Friend system
  const [groupsOpen, setGroupsOpen] = useState(false);
  const [friendsOpen, setFriendsOpen] = useState(false);
  // iter99 — Panel admin community bots
  const [showBotsAdmin, setShowBotsAdmin] = useState(false);
  // iter101 — Câblage useViewSpec : la vue simulée gouverne l'affichage UI
  const viewSpec = useViewSpec();

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

  // iter80 — C17: dialog "Inclure dans le ZIP" (code source + conversations)
  const [zipOptions, setZipOptions] = useState(null);  // { project, includeCode, includeChat }

  const askExportProjectZip = (project) => {
    setCtxMenu(null);
    if (!project?.project_id) return;
    setZipOptions({ project, includeCode: true, includeChat: false });
  };

  const exportProjectZip = async (project, opts) => {
    if (!project?.project_id) return;
    const o = opts || { includeCode: true, includeChat: false };
    try {
      const r = await axios.post(
        `${API}/export/download`,
        { project_id: project.project_id, export_type: 'source', include_code: !!o.includeCode, include_chat: !!o.includeChat },
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
    if (!requireWrite()) { setDeleteTarget(null); return; }
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

  const duplicateProject = async (project) => {
    setCtxMenu(null);
    if (!project?.project_id) return;
    if (!requireWrite()) return;
    try {
      const r = await axios.post(
        `${API}/projects/${project.project_id}/duplicate`,
        {},
        { withCredentials: true }
      );
      if (r.data?.project) {
        setProjects(p => [r.data.project, ...p]);
        toast.success(`Projet dupliqué : ${r.data.project.name}`);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Duplication impossible');
    }
  };

  const togglePublicShare = async (project) => {
    setCtxMenu(null);
    if (!project?.project_id) return;
    const turningOn = !project.is_public;
    try {
      const r = await axios.post(
        `${API}/projects/${project.project_id}/share`,
        { enable: turningOn },
        { withCredentials: true }
      );
      const updated = {
        ...project,
        is_public: r.data?.is_public ?? turningOn,
        share_slug: r.data?.slug || null,
      };
      setProjects(p => p.map(pr => pr.project_id === project.project_id ? updated : pr));
      if (selectedProject?.project_id === project.project_id) setSelectedProject(updated);
      if (r.data?.is_public && r.data?.url) {
        try {
          const fullUrl = r.data.url.startsWith('http')
            ? r.data.url
            : `${window.location.origin}${r.data.url}`;
          await navigator.clipboard.writeText(fullUrl);
          toast.success('Lien public copié dans le presse-papier', {
            description: fullUrl,
            action: { label: 'Ouvrir', onClick: () => window.open(fullUrl, '_blank') },
            duration: 9000,
          });
        } catch {
          toast.success('Partage public activé', { description: r.data.url });
        }
      } else {
        toast.success('Partage public désactivé');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Partage impossible');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadProjects = useCallback(async () => {
    // iter96 — Latence : on hydrate IMMÉDIATEMENT depuis le cache localStorage
    // pour un rendu instantané (0ms perçus), puis on rafraîchit en arrière-plan.
    try {
      const cached = getCachedProjects();
      if (Array.isArray(cached) && cached.length > 0) {
        setProjects(cached);  // affichage instantané
      }
    } catch { /* silent */ }
    try {
      const response = await axios.get(`${API}/projects`, {
        withCredentials: true
      });
      setProjects(response.data);
      cacheProjects(response.data);
    } catch (error) {
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
    if (!requireWrite()) return;
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

    // iter112 — Si le projet sélectionné est un chat parent ayant >=2 enfants,
    // on affiche un picker pour choisir lequel exporter (chat lui-même OU un
    // enfant spécifique). Si une seule enfant, on prend le plus récent.
    if (selectedProject.project_type === 'chat') {
      const children = projects.filter(p => p.parent_chat_id === selectedProject.project_id);
      if (children.length >= 2) {
        // Ouvre le picker et attend le choix.
        const chosen = await new Promise((resolve) => {
          setExportPicker({
            kind: exportType,
            candidates: [selectedProject, ...children],
            resolve,
          });
        });
        setExportPicker(null);
        if (!chosen) return;  // annulation
        // On exporte le projet choisi en mettant à jour selectedProject temporairement.
        return exportProjectFor(chosen, exportType);
      }
      if (children.length === 1) {
        // Une seule enfant → exporte directement l'enfant (qui contient le code).
        return exportProjectFor(children[0], exportType);
      }
    }

    return exportProjectFor(selectedProject, exportType);
  };

  // iter112 — Variante utilisée à la fois par exportProject (no-picker) et le picker.
  const exportProjectFor = async (project, exportType) => {
    if (!project.generated_code) {
      toast.error('Générez d\'abord le code du projet');
      return;
    }
    // Délègue à l'ancien chemin en remplaçant temporairement selectedProject.
    const previous = selectedProject;
    setSelectedProject(project);
    try {
      await _doExport(project, exportType);
    } finally {
      setSelectedProject(previous);
    }
  };

  const _doExport = async (project, exportType) => {
    if (!project) return;

    // Export approval gate — iter54. Non-creator devices must obtain an
    // explicit approval from the creator before exporting any APK / ZIP+GitHub
    // / EXE. Creators bypass this entirely.
    //
    // iter125 changes:
    //  - 1 demande max par projet : si déjà pending → on rouvre le modal du
    //    même request_id au lieu d'en créer un autre.
    //  - approved: on N'AUTO-FERME PAS le modal — l'utilisateur doit cliquer OUI.
    //  - rejected: idem (OUI envoie sa clé à la créa via Profile-style flow).
    if (device.role !== 'creator') {
      try {
        const { withCreatorProof } = await import('../lib/deviceIdentity');
        const body = await withCreatorProof(API, axios, {
          project_id: project.project_id,
          export_kind: exportType,
        });
        const r = await axios.post(`${API}/exports/request`, body);
        if (!r.data?.approved) {
          // Persist per-project pending lock in localStorage so a refresh
          // doesn't allow the user to spam new requests for the same project.
          try {
            const pids = JSON.parse(localStorage.getItem('cf_export_pending_pids') || '{}');
            pids[project.project_id] = r.data?.request_id;
            localStorage.setItem('cf_export_pending_pids', JSON.stringify(pids));
          } catch (_) {}

          // The download closure that will be called when the user clicks
          // OUI on the approved popup. Re-runs the same export flow but
          // marked as already-approved.
          const runRealDownload = async () => {
            // Re-issue the export call ; backend returns approved=true now.
            try {
              const apkBody = await withCreatorProof(API, axios, {
                project_id: project.project_id, export_kind: exportType,
              });
              await axios.post(`${API}/exports/request`, apkBody);
              // Actual download triggered below — just call the same exporter.
              if (exportType === 'source' || exportType === 'zip+github') {
                // ZIP download via /exports/zip-project/{id}
                const resp = await axios.get(
                  `${API}/exports/zip-project/${project.project_id}`,
                  { withCredentials: true, responseType: 'blob' },
                );
                const url = window.URL.createObjectURL(new Blob([resp.data]));
                const link = document.createElement('a');
                link.href = url;
                link.download = `codeforge_${project.name || project.project_id}.zip`;
                document.body.appendChild(link); link.click(); link.remove();
                window.URL.revokeObjectURL(url);
              } else {
                toast.message('Téléchargement APK/EXE bientôt disponible.');
              }
            } catch (e) {
              toast.error(e?.response?.data?.detail || 'Erreur téléchargement');
            }
          };

          setExportReview({
            kind: exportType,
            status: 'pending',
            request_id: r.data?.request_id,
            project_id: project.project_id,
            onDownload: runRealDownload,
          });

          // Poll for decision (max 90 polls × 4s = 6 min).
          let attempts = 0;
          let resolved = false;
          const poll = setInterval(async () => {
            attempts += 1;
            try {
              const b = await withCreatorProof(API, axios, { request_id: r.data?.request_id });
              const s = await axios.post(`${API}/exports/status`, b);
              if (s.data?.status === 'approved') {
                resolved = true;
                clearInterval(poll);
                // iter125 — DO NOT auto-close. User must click OUI.
                setExportReview((prev) => prev ? { ...prev, status: 'approved' } : null);
              } else if (s.data?.status === 'rejected') {
                resolved = true;
                clearInterval(poll);
                setExportReview((prev) => prev ? { ...prev, status: 'rejected' } : null);
              } else if (attempts > 90) {
                clearInterval(poll);
                if (!resolved) setExportReview(null);
              }
            } catch (_) { /* ignore polling errors */ }
          }, 4000);
          return;
        }
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Erreur');
        return;
      }
    }

    try {
      if (exportType === 'source') {
        // 1) Download ZIP locally.
        const response = await axios.post(
          `${API}/export/download`,
          { project_id: project.project_id, export_type: 'source' },
          {
            withCredentials: true,
            responseType: 'blob'
          }
        );

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${project.name}.zip`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);

        toast.success('Code source téléchargé !');

        // 2) Also push to GitHub in the background — non-blocking, silent on failure.
        (async () => {
          const t1 = toast.loading('Sauvegarde sur GitHub…');
          try {
            const gh = await axios.post(
              `${API}/export/github/${project.project_id}`,
              {},
              { withCredentials: true }
            );
            toast.dismiss(t1);
            if (gh.data?.url) {
              toast.success('Sauvegardé sur GitHub', {
                description: gh.data.repository || '',
                action: {
                  label: 'Ouvrir',
                  onClick: () => window.open(gh.data.url, '_blank'),
                },
                duration: 10000,
              });
            }
          } catch (ghErr) {
            toast.dismiss(t1);
            // Silent: ZIP download already succeeded. Only show a discreet hint.
            const detail = ghErr.response?.data?.detail || '';
            if (detail && !/(non configuré|not configured)/i.test(detail)) {
              toast.message('GitHub indisponible', { description: detail, duration: 5000 });
            }
          }
        })();
      } else if (exportType === 'apk') {
        // Open mobile export page
        const exportUrl = `${BACKEND_URL}/api/export/mobile/${project.project_id}`;
        window.open(exportUrl, '_blank');
        toast.success('Page d\'installation mobile ouverte !');
      } else if (exportType === 'exe') {
        // Open desktop export page
        const exportUrl = `${BACKEND_URL}/api/export/desktop/${project.project_id}`;
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
    <div className="h-screen bg-[#050505] text-white flex flex-col overflow-hidden">
      <ViewSimulationBanner role={device.role} viewMode={device.viewMode} />
      {/* iter99 — Panel admin community bots */}
      <BotsAdminPanel open={showBotsAdmin} onClose={() => setShowBotsAdmin(false)} />
      <div className="flex-1 flex overflow-hidden">
      <SiteLockedOverlay siteMode={device.siteMode} role={device.role} kickReason={device.kickReason} onRetry={() => device.refresh()} />
      <ExportApprovalNotifier onOpenAccount={(o) => setVisiting({ key_id: o.key_id })} />
      {visiting && <AccountVisitView target={visiting} onClose={() => setVisiting(null)} />}
      {/* Onboarding retiré du dashboard — l'utilisateur découvre l'interface par lui-même */}
      {/* iter67: on mobile, the sidebar becomes a fixed overlay drawer with
         a backdrop. On desktop (md+) it stays as a normal flex column that
         pushes the main content sideways. */}
      {isSidebarOpen && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          data-testid="sidebar-backdrop"
          aria-hidden="true"
        />
      )}
      {/* Sidebar - Projects */}
      <motion.aside
        initial={false}
        animate={{ width: isSidebarOpen ? 280 : 0 }}
        className="bg-[#0F0F13] border-r border-white/10 flex flex-col overflow-hidden fixed inset-y-0 left-0 z-40 md:relative md:z-auto"
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

        <ScrollArea className="flex-1 px-4 cf-export-blocked">
          {/* Filtres rapides — catégories de projets */}
          {projects.length > 0 && (() => {
            const counts = {
              all: projects.length,
              'chat-online': 0, 'chat-offline': 0, 'web-online': 0, 'web-offline': 0,
            };
            for (const p of projects) {
              const t2 = p.project_type === 'chat' ? 'chat' : 'web';
              const m = p.ai_mode || 'online';
              const k = `${t2}-${m}`;
              if (counts[k] !== undefined) counts[k] += 1;
            }
            const filters = [
              { id: 'all',          label: 'Tout',      dot: 'bg-white' },
              { id: 'chat-online',  label: 'Chat en ligne',   dot: 'bg-yellow-400' },
              { id: 'chat-offline', label: 'Chat hors-ligne',  dot: 'bg-sky-400' },
              { id: 'web-online',   label: 'Création en ligne', dot: 'bg-emerald-400' },
              { id: 'web-offline',  label: 'Création hors-ligne',   dot: 'bg-violet-400' },
            ];
            return (
              <div className="flex flex-wrap gap-1 mb-2" data-testid="sidebar-filters">
                {filters.map((f) => {
                  const active = sidebarFilter === f.id;
                  const count = counts[f.id] || 0;
                  if (f.id !== 'all' && count === 0) return null;
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setSidebarFilter(f.id)}
                      data-testid={`sidebar-filter-${f.id}`}
                      title={`${f.label} (${count})`}
                      className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-sm border transition-colors ${
                        active
                          ? 'bg-white/[0.08] border-white/30 text-white'
                          : 'bg-transparent border-white/10 text-[#A1A1AA] hover:bg-white/[0.04] hover:text-white'
                      }`}
                    >
                      <span className={`w-2 h-2 rounded-full ${f.dot}`} />
                      <span>{f.label}</span>
                      <span className="text-[10px] text-[#71717A]">{count}</span>
                    </button>
                  );
                })}
              </div>
            );
          })()}
          <div className="space-y-2">
            {(() => {
              // iter112 — Sidebar nested visuel : on regroupe les projets par chat parent.
              //   - Chats (project_type === 'chat') affichés au top-level.
              //   - Projets enfants (parent_chat_id === chat.project_id) rendus indentés sous leur chat.
              //   - Projets orphelins (pas un chat, parent_chat_id null) restent au top-level (avec leur dot).
              const filtered = projects.filter((p) => {
                if (sidebarFilter === 'all') return true;
                const t2 = p.project_type === 'chat' ? 'chat' : 'web';
                const m = p.ai_mode || 'online';
                return `${t2}-${m}` === sidebarFilter;
              });
              const byParent = {};
              filtered.forEach((p) => {
                if (p.parent_chat_id) {
                  byParent[p.parent_chat_id] = byParent[p.parent_chat_id] || [];
                  byParent[p.parent_chat_id].push(p);
                }
              });
              const topLevel = filtered.filter((p) => !p.parent_chat_id);
              const flat = [];
              topLevel.forEach((p) => {
                flat.push({ ...p, _depth: 0 });
                const children = byParent[p.project_id] || [];
                children.forEach((c) => flat.push({ ...c, _depth: 1, _parent: p }));
              });
              return flat;
            })().map(project => (
              renameTarget?.project_id === project.project_id ? (
                <div
                  key={project.project_id}
                  data-testid={`project-rename-${project.project_id}`}
                  className={`bg-white/[0.04] border border-[#E4FF00] rounded-sm p-2 flex items-center gap-2 ${project._depth ? 'ml-5 border-l-2 border-l-cyan-400/40' : ''}`}
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
                  } ${project._depth ? 'ml-5 border-l-2 border-l-cyan-400/40 relative' : ''}`}
                >
                  <div className="flex items-center gap-2">
                    {/* Type dot — couleur selon (project_type, ai_mode) */}
                    {(() => {
                      const t2 = project.project_type || 'web';
                      const m = project.ai_mode || 'online';
                      let bg = 'bg-[#A1A1AA]'; let title = 'Projet';
                      if (t2 === 'chat' && m === 'online')  { bg = 'bg-yellow-400';  title = 'Discussion avec l’IA en ligne'; }
                      else if (t2 === 'chat' && m === 'offline') { bg = 'bg-sky-400';    title = 'Discussion avec l’IA hors-ligne'; }
                      else if (t2 !== 'chat' && m === 'online')  { bg = 'bg-emerald-400';title = 'Création avec l’IA en ligne'; }
                      else if (t2 !== 'chat' && m === 'offline') { bg = 'bg-violet-400'; title = 'Création avec l’IA hors-ligne'; }
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
                      <TranslatedProjectName project={project} />
                    </span>
                    {selectedProject?.project_id === project.project_id && (
                      <ChevronRight className="w-4 h-4 text-[#E4FF00] flex-shrink-0" />
                    )}
                  </div>
                  {/* iter97 — Icône œil SOUS chaque projet de CRÉATION (pas pour les chats) */}
                  {project.project_type !== 'chat' && (
                    <div className="flex items-center justify-end gap-1 mt-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // Ouvre la prévisualisation interactive (vue Emergent-like)
                          const m = project.ai_mode || 'online';
                          navigate('/chat', { state: { mode: m, project, openPreview: true } });
                        }}
                        data-testid={`project-eye-${project.project_id}`}
                        title="Voir l'aperçu interactif de cette création"
                        className="inline-flex items-center justify-center w-6 h-6 rounded-sm text-[#A1A1AA] hover:text-emerald-300 hover:bg-emerald-500/10 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </button>
              )
            ))}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-white/10 space-y-2 cf-export-blocked">
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
      <div className="flex-1 flex flex-col min-w-0 overflow-x-hidden">
        {/* Header — [Sidebar toggle + Lang] · [CodeForge AI] · [Tutorial + Exports + UserMenu]
            iter106 — Spacings élargis pour que tous les labels soient visibles sans tronquer. */}
        <header className="bg-[#0F0F13] border-b border-white/10 px-3 sm:px-6 py-3 sm:py-4 overflow-x-auto md:overflow-x-visible">
          <div className="flex items-center justify-between gap-4 sm:gap-8 lg:gap-6 min-w-max md:min-w-0">
            {/* LEFT */}
            <div className="flex items-center gap-3 sm:gap-5 min-w-0">
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
              {/* iter110 — Swap : Theft en premier, Langue 1cm après, 2cm depuis sidebar toggle */}
              <span className="inline-block ml-2 sm:ml-8">
                <TheftButton variant="labelled" />
              </span>
              <span className="inline-block ml-2 sm:ml-4">
                <LanguageToggle placement="bottom" />
              </span>
              <div className="flex items-center gap-3 sm:gap-5 ml-3 sm:ml-2">
                {viewSpec.canSeeAccountsButton && <AccountsButton onVisitAccount={(a) => setVisiting(a)} />}
                <button
                  onClick={() => { setFriendsOpen(false); setGroupsOpen(true); }}
                  data-testid="open-groups-btn"
                  title="Tchats de groupe"
                  className="text-[#A1A1AA] hover:text-[#E4FF00] transition-colors p-1.5 rounded-sm hover:bg-white/[0.04]"
                >
                  <Users className="w-4 h-4" />
                </button>
                {device.viewMode && device.viewMode !== 'creator' && (
                  <button
                    onClick={() => { setGroupsOpen(false); setFriendsOpen(true); }}
                    data-testid="open-friends-btn"
                    title="Amis & demandes"
                    className="text-[#A1A1AA] hover:text-[#E4FF00] transition-colors p-1.5 rounded-sm hover:bg-white/[0.04]"
                  >
                    <UserCog className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            {/* CENTER */}
            <div className="flex flex-col items-center text-center min-w-0">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-[#E4FF00] flex-shrink-0" />
                <h1 className="font-['Chivo'] font-bold text-sm sm:text-xl truncate">{t('dashTitle')}</h1>
              </div>
              <p className="text-[10px] sm:text-xs text-[#A1A1AA] hidden sm:block truncate">{t('dashSubtitle')}</p>
            </div>

            {/* RIGHT — iter106 : élargi pour visibilité totale des labels */}
            <div className="flex items-center gap-3 sm:gap-4 flex-shrink-0">
              {viewSpec.canSeeMegaphone && <AnnounceButton />}
              {viewSpec.canSeeExports && <Button
                onClick={() => exportProject('apk')}
                size="sm"
                variant="outline"
                data-testid="export-apk-btn"
                className="hidden sm:inline-flex border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] px-2 lg:px-3"
                title="Export Mobile (APK)"
              >
                <Smartphone className="w-4 h-4 lg:mr-1" />
                <span className="hidden lg:inline">APK</span>
              </Button>}

              {viewSpec.canSeeExports && <Button
                onClick={() => exportProject('exe')}
                size="sm"
                variant="outline"
                data-testid="export-exe-btn"
                className="hidden sm:inline-flex border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] px-2 lg:px-3"
                title="Export Desktop (EXE)"
              >
                <Monitor className="w-4 h-4 lg:mr-1" />
                <span className="hidden lg:inline">EXE</span>
              </Button>}

              {viewSpec.canSeeExports && <Button
                onClick={() => exportProject('source')}
                size="sm"
                variant="outline"
                data-testid="export-source-btn"
                className="hidden sm:inline-flex border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] px-2 lg:px-3"
                title="Télécharger le code source (ZIP) — sauvegarde GitHub déjà automatique"
              >
                <Download className="w-4 h-4 lg:mr-1" />
                <span className="hidden lg:inline">ZIP</span>
              </Button>}

              <div className="ml-3 sm:ml-12 flex items-center gap-2 sm:gap-3 border-l border-white/10 pl-3 sm:pl-4">
                {/* iter128.1 — CreatorToolbar gère désormais lui-même la
                    visibilité du SiteModeBadge : créa physique + hors
                    simulation de vue. Aucune prop nécessaire ici. */}
                <CreatorToolbar />
                {viewSpec.viewSpec?.see_idea_box !== false && viewSpec.canSeeIdeasLightbulb && <IdeasButton />}
                {/* iter105 — CalyChatbot retiré d'ici : il est désormais un widget flottant bottom-right global, monté dans App.js. */}
                {/* iter101 — Bouton Bots Community : visible selon viewSpec */}
                {viewSpec.canSeeRobotBots && viewSpec.canSeeBotsAdmin && (
                  <button
                    onClick={() => setShowBotsAdmin(true)}
                    data-testid="header-bots-admin-btn"
                    title="Gérer les bots de la communauté"
                    className="inline-flex items-center justify-center w-8 h-8 rounded-sm bg-cyan-500/10 border border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/20 transition-colors"
                  >
                    <span className="text-base">🤖</span>
                  </button>
                )}
                <MessageButton variant="icon" />
                <NotificationBell />
                {/* iter128 — Email + "Mon profil" masqués si on visite un autre
                    compte OU si on simule une vue (creator → user/modo/...). */}
                <UserMenu user={user} onLogout={handleLogout} hideEmailAndProfile={!!visiting || (!!device.viewMode && device.viewMode !== 'creator')} />
              </div>
            </div>
          </div>
        </header>

        {/* Live Preview iframe — shown only when a web project with generated code is selected */}
        {selectedProject && selectedProject.project_type !== 'chat' && selectedProject.generated_code && (
          <div className="border-b border-white/10 bg-[#080808]" data-testid="live-preview-panel">
            <div className="flex items-center justify-between px-4 py-2">
              <div className="flex items-center gap-2 min-w-0">
                <Eye className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span className="text-xs font-['Chivo'] font-bold text-white truncate">
                  Aperçu live : {selectedProject.name}
                </span>
                {selectedProject.is_public && (
                  <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 border border-[#E4FF00]/40 text-[#E4FF00] rounded-sm">
                    Public
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.open(`${API}/preview/project/${selectedProject.project_id}`, '_blank')}
                  data-testid="live-preview-open-new-tab"
                  className="text-xs text-[#A1A1AA] hover:text-white transition-colors"
                >
                  Ouvrir dans un onglet ↗
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedProject(null)}
                  data-testid="live-preview-close"
                  className="text-xs text-[#A1A1AA] hover:text-white transition-colors"
                  title="Fermer l'aperçu"
                >
                  ✕
                </button>
              </div>
            </div>
            <iframe
              src={`${API}/preview/project/${selectedProject.project_id}`}
              title={`Aperçu ${selectedProject.name}`}
              data-testid="live-preview-iframe"
              className="w-full h-[420px] bg-white border-0"
              sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
            />
          </div>
        )}

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

            {/* iter128 — Cards "Programmation de Caly" + "Programmation des bots"
                masquées pour user/guest. Visibles pour modo/admin (lecture seule
                côté pages cibles) et créatrice. */}
            {viewSpec.canSeeAdminProgsCards && (
            <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4 cf-export-blocked" data-testid="admin-prog-row">
              {/* Programmation de Caly */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  // iter114 — Navigate toujours ; la page affiche la grande boîte
                  // "Accès refusé pour des raisons de sécurité" si l'utilisateur
                  // n'a pas les droits (plus de petit toast/icône "i").
                  navigate('/private/caly-programming');
                }}
                data-testid="creator-caly-prog-btn"
                className="group bg-gradient-to-br from-pink-500/[0.06] to-rose-500/[0.06] border border-pink-400/30 rounded-lg p-6 backdrop-blur-xl hover:border-pink-400 hover:shadow-[0_8px_30px_rgba(236,72,153,0.2)] transition-all text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-pink-500/20 border border-pink-400/40 rounded-full flex items-center justify-center">
                    <MessageCircleQuestion className="w-6 h-6 text-pink-300" />
                  </div>
                  <div>
                    <h3 className="text-lg font-['Chivo'] font-bold text-white">Programmation de Caly</h3>
                    <p className="text-xs text-[#A1A1AA]">Chatbot assistant virtuel — code modifiable (admins + créa, masqué en vue simulée)</p>
                  </div>
                </div>
              </motion.button>

              {/* Programmations des bots et chatbots */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  // iter114 — Navigate toujours ; la page affiche la grande boîte d'accès refusé.
                  navigate('/private/bots-programming');
                }}
                data-testid="creator-bots-prog-btn"
                className="group bg-gradient-to-br from-cyan-500/[0.06] to-sky-500/[0.06] border border-cyan-400/30 rounded-lg p-6 backdrop-blur-xl hover:border-cyan-400 hover:shadow-[0_8px_30px_rgba(34,211,238,0.2)] transition-all text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-cyan-500/20 border border-cyan-400/40 rounded-full flex items-center justify-center">
                    <Bot className="w-6 h-6 text-cyan-300" />
                  </div>
                  <div>
                    <h3 className="text-lg font-['Chivo'] font-bold text-white">Programmations des bots et chatbots</h3>
                    <p className="text-xs text-[#A1A1AA]">Code modifiable (admins + créa, masqué en vue simulée)</p>
                  </div>
                </div>
              </motion.button>
            </div>
            )}

            {/* iter78 — Assistant Guidé remis sur demande utilisatrice (création 100% accompagnée IA) */}
            {viewSpec.canSeeQuickWizard && (
            <motion.button
              whileHover={{ y: -2, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => { if (requireWrite()) navigate('/wizard'); }}
              data-testid="guided-wizard-btn"
              className="group w-full bg-gradient-to-br from-fuchsia-500/[0.08] via-purple-500/[0.05] to-cyan-500/[0.08] border-2 border-fuchsia-400/40 rounded-lg p-6 backdrop-blur-xl hover:border-fuchsia-400 hover:shadow-[0_8px_40px_rgba(232,121,249,0.3)] transition-all mb-6 cf-export-blocked"
            >
              <div className="flex items-center gap-4 text-left">
                <div className="w-14 h-14 bg-gradient-to-br from-fuchsia-400 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0">
                  <Wand2 className="w-7 h-7 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="text-xl font-['Chivo'] font-bold text-white mb-1">Création rapide accompagnée</h3>
                  <p className="text-sm text-[#A1A1AA]">100% guidé par l&apos;IA — choisis ton type d&apos;app, on s&apos;occupe du reste.</p>
                </div>
                <Sparkles className="w-5 h-5 text-fuchsia-300 group-hover:rotate-12 transition-transform" />
              </div>
            </motion.button>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 cf-export-blocked">
              {/* Bouton Chat (en ligne uniquement) */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => { if (requireWrite()) navigate('/chat', { state: { mode: 'online' } }); }}
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
                onClick={() => { if (requireWrite()) navigate('/create', { state: { mode: 'online' } }); }}
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

              {/* Bouton Chat hors ligne */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => { if (requireWrite()) navigate('/chat', { state: { mode: 'offline' } }); }}
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

              {/* Bouton Création hors ligne */}
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => { if (requireWrite()) navigate('/create', { state: { mode: 'offline' } }); }}
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

            {/* iter79 — Blocs privés créa (visibles côté UI, refusent l'accès en vue créateur) */}
            {viewSpec.canSeeCreatorProgsCards && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4 cf-export-blocked">
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  // iter114 — Navigate toujours ; la page rend la grande boîte d'accès refusé si pas créa.
                  navigate('/private/site-programming');
                }}
                data-testid="creator-private-site-btn"
                className="group bg-gradient-to-br from-rose-500/[0.06] to-orange-500/[0.06] border border-rose-400/30 rounded-lg p-6 backdrop-blur-xl hover:border-rose-400 hover:shadow-[0_8px_30px_rgba(244,114,182,0.2)] transition-all text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-rose-500/20 border border-rose-400/40 rounded-full flex items-center justify-center"><Code2 className="w-6 h-6 text-rose-300" /></div>
                  <div>
                    <h3 className="text-lg font-['Chivo'] font-bold text-white">Programmation du site</h3>
                    <p className="text-xs text-[#A1A1AA]">Code de fonctionnement de CodeForge AI</p>
                  </div>
                </div>
              </motion.button>
              <motion.button
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  // iter114 — Navigate toujours ; la page rend la grande boîte d'accès refusé si pas créa.
                  navigate('/private/ai-programming');
                }}
                data-testid="creator-private-ai-btn"
                className="group bg-gradient-to-br from-indigo-500/[0.06] to-blue-500/[0.06] border border-indigo-400/30 rounded-lg p-6 backdrop-blur-xl hover:border-indigo-400 hover:shadow-[0_8px_30px_rgba(99,102,241,0.2)] transition-all text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-indigo-500/20 border border-indigo-400/40 rounded-full flex items-center justify-center"><Sparkles className="w-6 h-6 text-indigo-300" /></div>
                  <div>
                    <h3 className="text-lg font-['Chivo'] font-bold text-white">Programmation des IA</h3>
                    <p className="text-xs text-[#A1A1AA]">Architecture, prompts, modules de vérification</p>
                  </div>
                </div>
              </motion.button>

              {/* iter113 — Les 2 tuiles Caly + Bots ont été DÉPLACÉES juste au-dessus
                  de "Création accompagnée" pour éviter la confusion avec Programmation créa. */}
            </div>
            )}
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
            <span>{t('ctx_rename')}</span>
          </button>
          <button
            type="button"
            onClick={async () => {
              const pid = ctxMenu.project.project_id;
              const url = `${window.location.origin}/chat?project=${encodeURIComponent(pid)}`;
              try {
                await navigator.clipboard.writeText(url);
                toast.success(t('ctx_link_copied'));
              } catch {
                toast.error(t('ctx_link_copy_failed'));
              }
              setCtxMenu(null);
            }}
            data-testid="project-ctx-copy-link"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <Link2 className="w-4 h-4 text-cyan-400" />
            <span>{t('ctx_copy_link')}</span>
          </button>
          {(ctxMenu.project?.project_type !== 'chat') && (
            <button
              type="button"
              onClick={() => { const pid = ctxMenu.project.project_id; setCtxMenu(null); navigate(`/preview/${pid}`); }}
              data-testid="project-ctx-preview"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
            >
              <Eye className="w-4 h-4 text-emerald-400" />
              <span>{t('ctx_live_preview')}</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => askExportProjectZip(ctxMenu.project)}
            data-testid="project-ctx-export-zip"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <Download className="w-4 h-4 text-cyan-400" />
            <span>{t('ctx_download_zip')}</span>
          </button>
          {/* iter79 — GitHub push retiré côté UI (le ZIP suffit pour push manuel) */}
          <button
            type="button"
            onClick={() => duplicateProject(ctxMenu.project)}
            data-testid="project-ctx-duplicate"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
          >
            <Copy className="w-4 h-4 text-amber-400" />
            <span>{t('ctx_duplicate')}</span>
          </button>
          {(ctxMenu.project?.project_type !== 'chat') && (
            <button
              type="button"
              onClick={() => togglePublicShare(ctxMenu.project)}
              data-testid="project-ctx-public-share"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/[0.05] transition-colors"
            >
              <Share2 className="w-4 h-4 text-[#E4FF00]" />
              <span>{ctxMenu.project?.is_public ? t('ctx_share_disable') : t('ctx_share_enable')}</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => askDelete(ctxMenu.project)}
            data-testid="project-ctx-delete"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            <span>{t('ctx_delete')}</span>
          </button>
        </div>
      )}

      {/* iter112 — Picker d'export multi-projets : si un chat a plusieurs
          enfants, l'utilisatrice choisit lequel exporter. */}
      {exportPicker && (
        <div
          data-testid="export-picker-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => { exportPicker.resolve(null); setExportPicker(null); }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-md w-full bg-[#0F0F13] border border-[#E4FF00]/40 rounded-sm p-6 space-y-3"
          >
            <h3 className="font-['Chivo'] font-bold text-white text-lg">
              Quel projet exporter en <span className="text-[#E4FF00]">{exportPicker.kind.toUpperCase()}</span> ?
            </h3>
            <p className="text-xs text-[#A1A1AA]">
              Ce chat contient {exportPicker.candidates.length - 1} projet{exportPicker.candidates.length > 2 ? 's' : ''} enfant{exportPicker.candidates.length > 2 ? 's' : ''}. Choisissez la version à exporter.
            </p>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {exportPicker.candidates.map((p) => (
                <button
                  key={p.project_id}
                  data-testid={`export-pick-${p.project_id}`}
                  onClick={() => { exportPicker.resolve(p); }}
                  className="w-full text-left p-3 bg-[#050505] border border-white/10 hover:border-[#E4FF00] rounded-sm transition-colors"
                >
                  <div className="font-['Chivo'] font-bold text-sm text-white truncate">{p.name}</div>
                  <div className="text-[10px] text-[#71717A] mt-0.5">
                    {p.project_type === 'chat' ? '💬 Chat parent' : '⚡ Projet généré'}
                    {' · '}
                    {p.ai_mode === 'offline' ? 'Hors-ligne' : 'En ligne'}
                    {p.created_at && ' · ' + new Date(p.created_at).toLocaleDateString('fr')}
                  </div>
                </button>
              ))}
            </div>
            <button
              data-testid="export-picker-cancel"
              onClick={() => { exportPicker.resolve(null); }}
              className="w-full px-3 py-2 text-xs text-[#A1A1AA] hover:text-white border border-white/10 rounded-sm"
            >
              Annuler
            </button>
          </div>
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
                <h3 className="font-['Chivo'] font-bold text-white">{t('ctx_delete_confirm_title')}</h3>
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
      {/* iter125 — Export in-review : 3 états (pending/approved/rejected),
          OUI button avec actions différenciées, plus de X.
          - pending OUI  → ack visuel, polling continue silencieusement
          - rejected OUI → envoie clé à la créa avec mention "Projet décliné"
          - approved OUI → déclenche le téléchargement réel + cleanup
          Le projet n'est PAS verrouillé (autres projets restent exportables). */}
      <ExportInReviewModal
        open={!!exportReview}
        status={exportReview?.status}
        kind={exportReview?.kind}
        requestId={exportReview?.request_id}
        onAcknowledge={() => {
          if (exportReview?.status === 'approved' || exportReview?.status === 'rejected') {
            // Cleanup pending lock for this project so user can re-request.
            try {
              const pids = JSON.parse(localStorage.getItem('cf_export_pending_pids') || '{}');
              if (exportReview?.project_id) delete pids[exportReview.project_id];
              localStorage.setItem('cf_export_pending_pids', JSON.stringify(pids));
            } catch (_) {}
          }
          setExportReview(null);
        }}
        onApprovedDownload={async () => {
          // Re-trigger the actual export flow now that creator approved.
          // (download triggers below — we just signal the existing handler.)
          if (exportReview?.onDownload) {
            await exportReview.onDownload();
          }
        }}
      />
      {/* iter82 — Group chats panel */}
      <GroupChatsPanel open={groupsOpen} onClose={() => setGroupsOpen(false)} />
      {/* iter82 — Friend system */}
      <FriendsPanel open={friendsOpen} onClose={() => setFriendsOpen(false)} />
      {/* iter80 — C17 ZIP include checkboxes */}
      {zipOptions && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" data-testid="zip-options-modal" onClick={() => setZipOptions(null)}>
          <div onClick={(e) => e.stopPropagation()} className="max-w-md w-full bg-[#0A0A0A] border border-cyan-400/40 rounded-md p-5 space-y-4">
            <h3 className="text-lg font-['Chivo'] font-bold text-white inline-flex items-center gap-2">
              <Download className="w-5 h-5 text-cyan-400" />
              Que veux-tu inclure dans le ZIP ?
            </h3>
            <p className="text-xs text-[#A1A1AA]">Projet : <strong className="text-white">{zipOptions.project?.name || zipOptions.project?.project_id}</strong></p>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={zipOptions.includeCode}
                onChange={(e) => setZipOptions((o) => ({ ...o, includeCode: e.target.checked }))}
                data-testid="zip-include-code"
                className="accent-cyan-400 w-4 h-4"
              />
              <span className="text-sm text-white">Code source (le dossier pour pousser sur GitHub)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={zipOptions.includeChat}
                onChange={(e) => setZipOptions((o) => ({ ...o, includeChat: e.target.checked }))}
                data-testid="zip-include-chat"
                className="accent-cyan-400 w-4 h-4"
              />
              <span className="text-sm text-white">Les discussions / conversations (.docx)</span>
            </label>
            <div className="flex items-center gap-2 pt-2">
              <button onClick={() => setZipOptions(null)} data-testid="zip-cancel" className="flex-1 px-3 py-2 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm text-sm">Annuler</button>
              <button
                onClick={() => { const o = zipOptions; setZipOptions(null); exportProjectZip(o.project, { includeCode: o.includeCode, includeChat: o.includeChat }); }}
                disabled={!zipOptions.includeCode && !zipOptions.includeChat}
                data-testid="zip-confirm"
                className="flex-1 px-3 py-2 bg-cyan-500 hover:bg-cyan-600 text-white font-bold rounded-sm text-sm disabled:opacity-40"
              >Télécharger</button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
