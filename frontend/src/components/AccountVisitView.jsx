import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, Trash2, Languages, MessageSquare, FolderOpen, Eye, Shield, Crown } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter81 C13/C20 — Vue créatrice « visite » qui imite le Dashboard du user
 * visité : sidebar style projets avec les dots de couleur identiques au vrai
 * dashboard, et zone centrale avec les messages dans le même style que le
 * Chat. Les éléments supprimés (is_deleted=true) apparaissent en contraste
 * fortement réduit pour permettre à la créatrice de voir TOUT l'historique
 * sans confusion avec l'actif.
 */
function projectDotClass(p) {
  const t2 = p.project_type === 'chat' ? 'chat' : 'web';
  const m = p.ai_mode || 'online';
  if (t2 === 'chat' && m === 'online') return 'bg-yellow-400';
  if (t2 === 'chat' && m === 'offline') return 'bg-sky-400';
  if (t2 !== 'chat' && m === 'online') return 'bg-emerald-400';
  if (t2 !== 'chat' && m === 'offline') return 'bg-violet-400';
  return 'bg-[#A1A1AA]';
}

export default function AccountVisitView({ target, onClose }) {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null); // project_id sélectionné
  const [translations, setTranslations] = useState({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, { target_key_id: target.key_id });
        const r = await axios.post(`${API}/accounts/visit`, body);
        if (!cancelled) setData(r.data);
      } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
    })();
    return () => { cancelled = true; };
  }, [target.key_id]);

  const deleteProject = async (project_id) => {
    if (!window.confirm(t('visit_delete_project'))) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: target.key_id, project_id });
      await axios.post(`${API}/accounts/delete-user-project`, body);
      toast.success(t('visit_project_deleted'));
      setData((d) => d && ({
        ...d,
        projects: d.projects.map((p) => p.project_id === project_id ? { ...p, deleted_by_creator: true, is_deleted: true } : p)
      }));
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
    finally { setBusy(false); }
  };

  const translate = async (m) => {
    try {
      const body = await withCreatorProof(API, axios, { text: m.content, target_lang: 'fr' });
      const r = await axios.post(`${API}/creator/translate`, body);
      if (r.data?.error === 'translate_unavailable') {
        toast.warning(t('visit_translate') + ' — indisponible');
        return;
      }
      setTranslations((tr) => ({ ...tr, [m.message_id]: r.data?.translated || m.content }));
    } catch (_) { toast.error('Échec de la traduction.'); }
  };

  const projects = data?.projects || [];
  const messages = data?.messages || [];

  // Filtre messages pour le projet sélectionné (ou tous si aucun sélectionné)
  const visibleMessages = selected
    ? messages.filter((m) => m.project_id === selected)
    : messages;

  const targetPseudo = data?.target?.pseudo || target.key_id.slice(0, 14);
  const staffKind = data?.target?.staff_kind;
  const role = data?.target?.role;

  return (
    <div className="fixed inset-0 z-[95] bg-[#050505] text-white flex flex-col" data-testid="visit-view">
      {/* Bandeau de vue créa — visible et persistant */}
      <div className="bg-[#E4FF00]/10 border-b border-[#E4FF00]/40 px-4 py-2 flex items-center gap-3 flex-wrap">
        <button
          onClick={onClose}
          data-testid="visit-back"
          className="inline-flex items-center gap-2 text-[#A1A1AA] hover:text-white text-xs font-['Chivo'] font-bold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t('visit_back')}</span>
        </button>
        <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 border border-[#E4FF00]/60 text-[#E4FF00] bg-[#E4FF00]/10 rounded-sm inline-flex items-center gap-1">
          <Eye className="w-3 h-3" /> Mode visite
        </span>
        <h1 className="text-sm font-['Chivo'] font-bold text-white truncate">
          {t('visit_title').replace('{pseudo}', targetPseudo)}
        </h1>
        {role === 'creator' && (
          <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 border border-[#E4FF00]/60 text-[#E4FF00] bg-[#E4FF00]/10 rounded-sm inline-flex items-center gap-1">
            <Crown className="w-3 h-3" /> créatrice
          </span>
        )}
        {staffKind === 'admin' && (
          <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 border border-orange-400/60 text-orange-300 bg-orange-400/10 rounded-sm inline-flex items-center gap-1">
            <Shield className="w-3 h-3" /> admin
          </span>
        )}
        {staffKind === 'modo' && (
          <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 border border-cyan-400/60 text-cyan-300 bg-cyan-400/10 rounded-sm inline-flex items-center gap-1">
            <Shield className="w-3 h-3" /> modo
          </span>
        )}
        <span className="ml-auto text-[10px] text-[#71717A]">
          {projects.length} projet{projects.length > 1 ? 's' : ''} · {messages.length} message{messages.length > 1 ? 's' : ''}
        </span>
      </div>

      {/* Layout dashboard-like : sidebar projets + main chat */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar Projets, identique au Dashboard */}
        <aside className="w-72 bg-[#0F0F13] border-r border-white/10 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-white/10 flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-[#E4FF00]" />
            <span className="font-['Chivo'] font-bold text-sm">{t('visit_projects')}</span>
            <span className="ml-auto text-[10px] text-[#71717A]">({projects.length})</span>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
            <button
              onClick={() => setSelected(null)}
              className={`w-full text-left text-xs p-2 rounded-sm border transition ${
                selected === null
                  ? 'bg-white/[0.06] border-white/30 text-white'
                  : 'border-white/10 text-[#A1A1AA] hover:border-white/20'
              }`}
            >
              Tous les messages
            </button>
            {projects.map((p) => {
              const isDel = !!p.is_deleted;
              const active = selected === p.project_id;
              return (
                <div
                  key={p.project_id}
                  data-testid={`visit-project-${p.project_id}`}
                  className={`flex items-start gap-2 p-2 rounded-sm border transition cursor-pointer ${
                    active ? 'bg-white/[0.06] border-white/30' : 'border-white/10 hover:border-white/20'
                  } ${isDel ? 'opacity-30 grayscale' : ''}`}
                  onClick={() => setSelected(p.project_id)}
                >
                  <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${projectDotClass(p)}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate font-['Chivo'] font-bold flex items-center gap-1">
                      <span className="truncate">{p.name}</span>
                      {isDel && <span className="text-[9px] uppercase tracking-widest text-red-300/80 px-1 border border-red-300/40 rounded-sm">supprimé</span>}
                    </div>
                    <div className="text-[10px] text-[#71717A] truncate">
                      {p.project_type === 'chat' ? 'Chat' : 'Création'} · {p.ai_mode || 'online'} · {new Date(p.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    disabled={busy || isDel}
                    onClick={(e) => { e.stopPropagation(); deleteProject(p.project_id); }}
                    title={t('visit_delete_project')}
                    data-testid={`visit-delete-${p.project_id}`}
                    className="text-[#A1A1AA] hover:text-red-400 transition p-1 disabled:opacity-40 flex-shrink-0"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
            {projects.length === 0 && (
              <div className="text-xs text-[#A1A1AA] py-6 text-center">Aucun projet</div>
            )}
          </div>
        </aside>

        {/* Zone messages — style Chat */}
        <main className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
          <div className="px-4 py-2 border-b border-white/10 flex items-center gap-2 bg-[#0A0A0A]">
            <MessageSquare className="w-4 h-4 text-[#E4FF00]" />
            <span className="text-sm font-['Chivo'] font-bold">
              {selected ? (projects.find((p) => p.project_id === selected)?.name || 'Projet') : 'Toutes les conversations'}
            </span>
            <span className="ml-auto text-[10px] text-[#71717A]">{visibleMessages.length} message(s)</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {visibleMessages.map((m) => {
              const isDel = !!m.is_deleted;
              const isUser = m.role === 'user';
              return (
                <div
                  key={m.message_id}
                  className={`max-w-3xl ${isUser ? 'ml-auto' : 'mr-auto'} bg-[#0A0A0A] border rounded-sm p-3 ${
                    isUser ? 'border-[#E4FF00]/30' : 'border-white/10'
                  } ${isDel ? 'opacity-25 grayscale' : ''}`}
                >
                  <div className="text-[10px] text-[#71717A] flex items-center gap-2 mb-1">
                    <span className="uppercase tracking-widest font-bold">{isUser ? 'User' : 'IA'}</span>
                    <span>{new Date(m.timestamp).toLocaleString()}</span>
                    {isDel && (
                      <span className="text-[9px] uppercase tracking-widest text-red-300/80 px-1 border border-red-300/40 rounded-sm">supprimé</span>
                    )}
                    <button
                      onClick={() => translate(m)}
                      title={t('visit_translate')}
                      className="ml-auto text-sky-300 hover:text-sky-200 inline-flex items-center gap-1"
                    >
                      <Languages className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="text-sm text-white whitespace-pre-wrap break-words">
                    {isDel ? `[${t('visit_msg_deleted')}] ${m.content || ''}` : m.content}
                  </div>
                  {translations[m.message_id] && (
                    <div className="text-xs text-sky-200 italic whitespace-pre-wrap break-words mt-2 border-l-2 border-sky-400/40 pl-2">
                      {translations[m.message_id]}
                    </div>
                  )}
                </div>
              );
            })}
            {visibleMessages.length === 0 && (
              <div className="text-xs text-[#A1A1AA] py-12 text-center">Aucun message</div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
