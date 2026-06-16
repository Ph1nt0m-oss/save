import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  ArrowLeft, Trash2, Languages, MessageSquare, FolderOpen,
  Eye, Shield, Crown, Mail, Key, Copy, UserPlus, Users
} from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function projectDotClass(p) {
  const t2 = p.project_type === 'chat' ? 'chat' : 'web';
  const m = p.ai_mode || 'online';
  if (t2 === 'chat' && m === 'online') return 'bg-yellow-400';
  if (t2 === 'chat' && m === 'offline') return 'bg-sky-400';
  if (t2 !== 'chat' && m === 'online') return 'bg-emerald-400';
  if (t2 !== 'chat' && m === 'offline') return 'bg-violet-400';
  return 'bg-[#A1A1AA]';
}

function copyTo(value, label) {
  try {
    navigator.clipboard.writeText(value);
    toast.success(`${label} copié`);
  } catch (_) { toast.error('Copie impossible'); }
}

export default function AccountVisitView({ target, onClose }) {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null);
  const [translations, setTranslations] = useState({});
  // Onglets : 'projects' | 'chat' | 'private' | 'groups' | 'friends' | 'info'
  const [tab, setTab] = useState('info');

  useEffect(() => {
    let cancelled = false;
    let pollId = null;
    const fetch = async () => {
      try {
        const body = await withCreatorProof(API, axios, { target_key_id: target.key_id });
        const r = await axios.post(`${API}/accounts/visit`, body);
        if (!cancelled) setData(r.data);
      } catch (e) {
        // Silencieux après le premier load — évite de spammer la toast en polling.
        if (!data) toast.error(e?.response?.data?.detail || 'Erreur');
      }
    };
    fetch();
    // iter114 — Polling toutes les 5 secondes : la créatrice voit en direct
    // les nouveaux chats / messages / projets du compte visité, même si la
    // génération est en cours côté utilisateur.
    pollId = setInterval(fetch, 5000);
    return () => { cancelled = true; if (pollId) clearInterval(pollId); };
    /* eslint-disable-next-line */
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

  const directMessage = async () => {
    const content = window.prompt(`Écrire un message à ${data?.target?.pseudo || target.key_id.slice(0, 10)} :`);
    if (!content || !content.trim()) return;
    try {
      const body = await withCreatorProof(API, axios, { content: content.trim(), target_key_id: target.key_id });
      await axios.post(`${API}/messages/send`, body);
      toast.success('Message envoyé');
    } catch (e) { toast.error(e?.response?.data?.detail || 'Échec'); }
  };

  const projects = data?.projects || [];
  const messages = data?.messages || [];
  const privateMsgs = data?.private_messages || [];
  const friendReqs = data?.friend_requests || [];
  const groupPosts = data?.group_posts || [];

  const visibleMessages = selected ? messages.filter((m) => m.project_id === selected) : messages;

  const targetPseudo = data?.target?.pseudo || target.key_id.slice(0, 14);
  const staffKind = data?.target?.staff_kind;
  const role = data?.target?.role;

  // iter128 — Filtrage des onglets selon le rôle de la cible visitée.
  //   - Invité/visiteur (guest) ou non-approved : pas d'amis ni groupes
  //     privés (pas pertinent), pas de "Caly" code… L'onglet "Annonces"
  //     n'existe pas ici en tant qu'onglet ; il s'agissait du bouton
  //     megaphone (déjà filtré en amont). On masque MP privés + Amis +
  //     Groupes si la cible n'a pas d'accès écriture (cf. image 4).
  const targetRole = data?.target?.role;
  const targetIsLimited = ['guest', 'inactive', 'pending'].includes(targetRole);
  const tabs = [
    { id: 'info', label: 'Infos compte', icon: Eye },
    { id: 'projects', label: 'Projets', icon: FolderOpen, count: projects.length },
    { id: 'chat', label: 'Chat IA', icon: MessageSquare, count: messages.length },
    ...(targetIsLimited ? [] : [
      { id: 'private', label: 'MP privés', icon: Mail, count: privateMsgs.length },
      { id: 'groups', label: 'Groupes', icon: Users, count: groupPosts.length },
      { id: 'friends', label: 'Amis', icon: UserPlus, count: friendReqs.length },
    ]),
  ];

  return (
    <div className="fixed inset-0 z-[95] bg-[#050505] text-white flex flex-col" data-testid="visit-view">
      {/* Bandeau de vue créa */}
      <div className="bg-[#E4FF00]/10 border-b border-[#E4FF00]/40 px-4 py-2 flex items-center gap-3 flex-wrap">
        <button onClick={onClose} data-testid="visit-back" className="inline-flex items-center gap-2 text-[#A1A1AA] hover:text-white text-xs font-['Chivo'] font-bold">
          <ArrowLeft className="w-4 h-4" />
          <span>{t('visit_back')}</span>
        </button>
        {/* iter128.3 — Badge "Mode visite (invisible aux admins)" retiré :
            seule la créa physique peut visiter, donc le rappel est superflu
            (image 4). */}
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
        <button onClick={directMessage} data-testid="visit-direct-message" className="ml-auto text-[11px] px-2 py-1 border border-cyan-400/60 text-cyan-300 hover:bg-cyan-400/10 rounded-sm inline-flex items-center gap-1">
          <MessageSquare className="w-3 h-3" /> Parler en privé
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-white/10 bg-[#0A0A0A]">
        {tabs.map((tt) => {
          const Icon = tt.icon;
          const active = tab === tt.id;
          return (
            <button
              key={tt.id}
              onClick={() => setTab(tt.id)}
              data-testid={`visit-tab-${tt.id}`}
              className={`px-3 py-2 text-xs font-bold inline-flex items-center gap-1.5 border-b-2 transition ${
                active ? 'border-[#E4FF00] text-[#E4FF00] bg-[#E4FF00]/5' : 'border-transparent text-[#A1A1AA] hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tt.label}</span>
              {typeof tt.count === 'number' && <span className="text-[10px] text-[#71717A]">({tt.count})</span>}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-hidden">
        {/* Onglet Infos compte (clé/email/biométrie/dates) */}
        {tab === 'info' && (
          <div className="p-4 max-w-3xl mx-auto space-y-3 overflow-y-auto h-full">
            <h2 className="text-sm font-['Chivo'] font-bold text-[#E4FF00] uppercase tracking-widest">Informations brutes</h2>
            <p className="text-[11px] text-[#A1A1AA]">Visible uniquement par la créatrice. Permet la récupération en cas de vol / verrouillage de compte.</p>
            <InfoRow label="Pseudo" value={data?.target?.pseudo} icon={Crown} />
            <InfoRow label="Label appareil" value={data?.target?.label} icon={Eye} />
            <InfoRow label="Email" value={data?.target?.email} icon={Mail} copyable />
            <InfoRow label="Clé device (publique)" value={data?.target?.key_id} icon={Key} copyable mono />
            <InfoRow label="Rôle" value={data?.target?.role} />
            <InfoRow label="Type staff" value={data?.target?.staff_kind || '—'} />
            <InfoRow label="Décidé par" value={data?.target?.approved_by_label ? `${data?.target?.approved_by_kind} · ${data?.target?.approved_by_label}` : '—'} />
            <InfoRow label="Biométrie" value={data?.target?.biometric_kind || '—'} />
            <InfoRow label="Muted" value={data?.target?.muted ? 'oui' : 'non'} />
            <InfoRow label="Banni" value={data?.target?.banned ? 'oui' : 'non'} />
            <InfoRow label="Visiteur forcé" value={data?.target?.force_visitor ? 'oui' : 'non'} />
            <InfoRow label="Dernière connexion" value={data?.target?.last_seen_at ? new Date(data.target.last_seen_at).toLocaleString() : '—'} />
            <InfoRow label="Créé le" value={data?.target?.created_at ? new Date(data.target.created_at).toLocaleString() : '—'} />
          </div>
        )}

        {/* Onglet Projets */}
        {tab === 'projects' && (
          <div className="flex h-full overflow-hidden">
            <aside className="w-full border-r border-white/10 overflow-y-auto p-3 space-y-1.5">
              {projects.map((p) => {
                const isDel = !!p.is_deleted;
                return (
                  <div
                    key={p.project_id}
                    data-testid={`visit-project-${p.project_id}`}
                    className={`flex items-start gap-2 p-2 rounded-sm border border-white/10 hover:border-white/20 ${
                      isDel ? 'opacity-30 grayscale' : ''
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${projectDotClass(p)}`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate font-['Chivo'] font-bold flex items-center gap-1">
                        <span className="truncate">{p.name}</span>
                        {isDel && <span className="text-[9px] uppercase tracking-widest text-red-300/80 px-1 border border-red-300/40 rounded-sm">supprimé</span>}
                      </div>
                      <div className="text-[10px] text-[#71717A] truncate">
                        {p.project_type === 'chat' ? 'Chat' : 'Création'} · {p.ai_mode || 'online'} · {new Date(p.created_at).toLocaleString()}
                      </div>
                    </div>
                    <button
                      disabled={busy || isDel}
                      onClick={() => deleteProject(p.project_id)}
                      data-testid={`visit-delete-${p.project_id}`}
                      className="text-[#A1A1AA] hover:text-red-400 transition p-1 disabled:opacity-40"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                );
              })}
              {projects.length === 0 && (
                <div className="text-xs text-[#A1A1AA] py-6 text-center">Aucun projet</div>
              )}
            </aside>
          </div>
        )}

        {/* Onglet Chat IA */}
        {tab === 'chat' && (
          <div className="flex h-full overflow-hidden">
            <aside className="w-60 border-r border-white/10 overflow-y-auto p-3 space-y-1.5 flex-shrink-0">
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
              {projects.map((p) => (
                <button
                  key={p.project_id}
                  onClick={() => setSelected(p.project_id)}
                  className={`w-full text-left text-xs p-2 rounded-sm border transition flex items-center gap-2 ${
                    selected === p.project_id ? 'bg-white/[0.06] border-white/30' : 'border-white/10 hover:border-white/20'
                  } ${p.is_deleted ? 'opacity-40 grayscale' : ''}`}
                >
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${projectDotClass(p)}`} />
                  <span className="truncate">{p.name}</span>
                </button>
              ))}
            </aside>
            <main className="flex-1 overflow-y-auto p-4 space-y-2">
              {visibleMessages.map((m) => {
                const isDel = !!m.is_deleted;
                const isUser = m.role === 'user';
                return (
                  <div key={m.message_id} className={`max-w-3xl ${isUser ? 'ml-auto' : 'mr-auto'} bg-[#0A0A0A] border rounded-sm p-3 ${
                    isUser ? 'border-[#E4FF00]/30' : 'border-white/10'
                  } ${isDel ? 'opacity-25 grayscale' : ''}`}>
                    <div className="text-[10px] text-[#71717A] flex items-center gap-2 mb-1">
                      <span className="uppercase tracking-widest font-bold">{isUser ? 'User' : 'IA'}</span>
                      <span>{new Date(m.timestamp).toLocaleString()}</span>
                      {isDel && <span className="text-[9px] uppercase tracking-widest text-red-300/80 px-1 border border-red-300/40 rounded-sm">supprimé</span>}
                      <button onClick={() => translate(m)} className="ml-auto text-sky-300 hover:text-sky-200">
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
              {visibleMessages.length === 0 && <div className="text-xs text-[#A1A1AA] py-12 text-center">Aucun message</div>}
            </main>
          </div>
        )}

        {/* Onglet MP privés */}
        {tab === 'private' && (
          <div className="p-4 max-w-3xl mx-auto overflow-y-auto h-full space-y-2">
            {privateMsgs.map((m) => (
              <div key={m.message_id} data-testid={`visit-pm-${m.message_id}`} className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3">
                <div className="text-[10px] text-[#71717A] flex items-center gap-2 mb-1">
                  <span className="uppercase tracking-widest font-bold">
                    {m.is_from_creator ? 'Créa' : (m.sender_label || m.from_key_id?.slice(0, 10))}
                  </span>
                  <span>→</span>
                  <span className="text-[#A1A1AA]">{m.to_key_id?.slice(0, 10) || m.thread_key_id?.slice(0, 10)}</span>
                  <span className="ml-2">{new Date(m.ts).toLocaleString()}</span>
                  {m.recipient_kind && <span className="ml-1 text-[9px] uppercase px-1 border border-cyan-400/40 text-cyan-300 rounded-sm">{m.recipient_kind}</span>}
                </div>
                <div className="text-sm text-white whitespace-pre-wrap break-words">{m.content}</div>
              </div>
            ))}
            {privateMsgs.length === 0 && <div className="text-xs text-[#A1A1AA] py-12 text-center">Aucun message privé</div>}
          </div>
        )}

        {/* Onglet Groupes */}
        {tab === 'groups' && (
          <div className="p-4 max-w-3xl mx-auto overflow-y-auto h-full space-y-2">
            {groupPosts.map((m) => (
              <div key={m.message_id} className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3">
                <div className="text-[10px] text-[#71717A] flex items-center gap-2 mb-1">
                  <span className="text-[9px] uppercase px-1 border border-emerald-400/40 text-emerald-300 rounded-sm">{m.group_type}</span>
                  <span>{new Date(m.ts).toLocaleString()}</span>
                </div>
                <div className="text-sm text-white whitespace-pre-wrap break-words">{m.content}</div>
              </div>
            ))}
            {groupPosts.length === 0 && <div className="text-xs text-[#A1A1AA] py-12 text-center">Aucune publication dans un groupe</div>}
          </div>
        )}

        {/* Onglet Amis */}
        {tab === 'friends' && (
          <div className="p-4 max-w-3xl mx-auto overflow-y-auto h-full space-y-2">
            {friendReqs.map((r) => {
              const out = r.from_key_id === target.key_id;
              return (
                <div key={r.request_id} className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3 flex items-center gap-2">
                  <span className={`text-[9px] uppercase px-1 border rounded-sm ${
                    r.status === 'accepted' ? 'border-emerald-400/40 text-emerald-300'
                    : r.status === 'refused' ? 'border-red-400/40 text-red-300'
                    : 'border-yellow-400/40 text-yellow-300'
                  }`}>{r.status}</span>
                  <span className="text-xs text-[#A1A1AA]">{out ? 'Envoyée à' : 'Reçue de'}</span>
                  <code className="text-[11px] text-white font-mono truncate">{out ? r.to_pseudo || r.to_key_id : r.from_pseudo || r.from_key_id}</code>
                  <span className="ml-auto text-[10px] text-[#71717A]">{new Date(r.created_at).toLocaleString()}</span>
                </div>
              );
            })}
            {friendReqs.length === 0 && <div className="text-xs text-[#A1A1AA] py-12 text-center">Aucune demande d&apos;ami</div>}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value, icon: Icon, copyable, mono }) {
  return (
    <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3 flex items-start gap-3">
      {Icon && <Icon className="w-3.5 h-3.5 text-[#A1A1AA] mt-0.5 flex-shrink-0" />}
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-widest text-[#71717A]">{label}</div>
        <div className={`text-sm text-white break-all ${mono ? 'font-mono' : ''}`}>{value || '—'}</div>
      </div>
      {copyable && value && (
        <button onClick={() => copyTo(value, label)} className="text-[#A1A1AA] hover:text-white p-1" title="Copier">
          <Copy className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
