import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, Trash2, Languages, MessageSquare, FolderOpen } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Full-screen "visit a user's account" view for the creator. Shows the
 * user's projects (incl. soft-deleted in muted style) + chat history;
 * offers per-project deletion + per-message auto-translation.
 */
export default function AccountVisitView({ target, onClose }) {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [translations, setTranslations] = useState({}); // msg_id -> text

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
      // Optimistic refresh
      setData((d) => d && ({ ...d, projects: d.projects.map((p) => p.project_id === project_id ? { ...p, deleted_by_creator: true } : p) }));
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

  return (
    <div className="fixed inset-0 z-[95] bg-[#050505] overflow-y-auto" data-testid="visit-view">
      <div className="sticky top-0 z-10 bg-[#0A0A0A]/95 backdrop-blur-md border-b border-white/10 px-4 py-3 flex items-center gap-3">
        <button onClick={onClose} data-testid="visit-back" className="inline-flex items-center gap-2 text-[#A1A1AA] hover:text-white">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-xs font-['Chivo'] font-bold">{t('visit_back')}</span>
        </button>
        <h1 className="text-sm font-['Chivo'] font-bold text-[#E4FF00] truncate">
          {t('visit_title').replace('{pseudo}', data?.target?.pseudo || target.key_id.slice(0, 14))}
        </h1>
      </div>

      <div className="max-w-5xl mx-auto p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Projects */}
        <section className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3">
          <h2 className="text-sm font-['Chivo'] font-bold text-white flex items-center gap-2 mb-2">
            <FolderOpen className="w-4 h-4 text-[#E4FF00]" />{t('visit_projects')}
            <span className="text-[10px] text-[#71717A]">({data?.projects?.length || 0})</span>
          </h2>
          <div className="space-y-1.5 max-h-[60vh] overflow-y-auto">
            {(data?.projects || []).map((p) => (
              <div key={p.project_id} className={`bg-black/30 border border-white/10 rounded-sm p-2.5 ${p.deleted_by_creator ? 'opacity-50' : ''}`} data-testid={`visit-project-${p.project_id}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm text-white truncate font-['Chivo'] font-bold">{p.name}</div>
                  <button disabled={busy || p.deleted_by_creator} onClick={() => deleteProject(p.project_id)} title={t('visit_delete_project')} data-testid={`visit-delete-${p.project_id}`} className="text-[#A1A1AA] hover:text-red-400 transition p-1 disabled:opacity-40">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="text-[10px] text-[#71717A] truncate">{p.project_type} · {new Date(p.created_at).toLocaleString()}</div>
                {p.deleted_by_creator && <div className="text-[10px] text-red-300 mt-1">{t('visit_project_deleted')}</div>}
              </div>
            ))}
            {data?.projects?.length === 0 && <div className="text-xs text-[#A1A1AA] py-3 text-center">—</div>}
          </div>
        </section>

        {/* Messages */}
        <section className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3">
          <h2 className="text-sm font-['Chivo'] font-bold text-white flex items-center gap-2 mb-2">
            <MessageSquare className="w-4 h-4 text-[#E4FF00]" />{t('visit_messages')}
            <span className="text-[10px] text-[#71717A]">({data?.messages?.length || 0})</span>
          </h2>
          <div className="space-y-1.5 max-h-[60vh] overflow-y-auto">
            {(data?.messages || []).map((m) => (
              <div key={m.message_id} className={`bg-black/30 border border-white/10 rounded-sm p-2.5 ${m.deleted ? 'opacity-50' : ''}`}>
                <div className="text-[10px] text-[#71717A] flex items-center gap-2">
                  <span className="uppercase tracking-widest">{m.role}</span>
                  <span>{new Date(m.timestamp).toLocaleString()}</span>
                  <button onClick={() => translate(m)} title={t('visit_translate')} className="ml-auto text-sky-300 hover:text-sky-200 inline-flex items-center gap-1"><Languages className="w-3 h-3" /></button>
                </div>
                <div className="text-xs text-white whitespace-pre-wrap break-words mt-1">{m.deleted ? t('visit_msg_deleted') : m.content}</div>
                {translations[m.message_id] && (
                  <div className="text-xs text-sky-200 italic whitespace-pre-wrap break-words mt-1 border-l-2 border-sky-400/40 pl-2">{translations[m.message_id]}</div>
                )}
              </div>
            ))}
            {data?.messages?.length === 0 && <div className="text-xs text-[#A1A1AA] py-3 text-center">—</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
