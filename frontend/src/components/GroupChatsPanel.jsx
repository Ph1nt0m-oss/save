import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { X, Users, Lock, Shield, Globe2 } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import InvisibleModeToggle from './InvisibleModeToggle';
import AnonymousModeToggle from './AnonymousModeToggle';
import SunNightModeToggle from './SunNightModeToggle';
import MessageBubble from './MessageBubble';
import GroupMembersList from './GroupMembersList';
import { MentionInputWithSend } from './MentionInput';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { useUnreadCounts, UnreadBadge } from '../hooks/useUnreadCounts';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter86 C19 / iter140 — Refonte : 'users' + 3 nouveaux hybrides ; 'public_private' retiré.
const GROUP_META = {
  public: { label: 'Public', icon: Globe2, color: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  private: { label: 'Privé', icon: Lock, color: 'text-violet-300', bg: 'bg-violet-500/10', border: 'border-violet-500/30' },
  users: { label: 'Utilisateurs', icon: Users, color: 'text-lime-300', bg: 'bg-lime-500/10', border: 'border-lime-500/30' },
  staff: { label: 'Staff', icon: Shield, color: 'text-orange-300', bg: 'bg-orange-500/10', border: 'border-orange-500/30' },
  modo: { label: 'Modo', icon: Shield, color: 'text-cyan-300', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' },
  admin: { label: 'Admin', icon: Shield, color: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-400/40' },
  public_staff: { label: 'Public + Staff', icon: Users, color: 'text-yellow-300', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
  private_staff: { label: 'Privé + Staff', icon: Users, color: 'text-sky-300', bg: 'bg-sky-500/10', border: 'border-sky-500/30' },
  users_staff: { label: 'Utilisateurs + Staff', icon: Users, color: 'text-pink-300', bg: 'bg-pink-500/10', border: 'border-pink-500/30' },
  users_private: { label: 'Utilisateurs + Privé', icon: Users, color: 'text-fuchsia-300', bg: 'bg-fuchsia-500/10', border: 'border-fuchsia-500/30' },
};

// iter140 — Ordre imposé : Utilisateurs entre Privé et Staff.
const ORDER = ['public', 'private', 'users', 'staff', 'modo', 'admin', 'public_staff', 'private_staff', 'users_staff', 'users_private'];

export default function GroupChatsPanel({ open, onClose }) {
  const device = useDeviceIdentity();
  const unread = useUnreadCounts(device);
  const viewMode = device?.viewMode || null;
  const [groups, setGroups] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, { view_mode: viewMode });
        const r = await axios.post(`${API}/groups/list`, body);
        if (cancelled) return;
        const groupList = (r.data?.groups || []).filter((g) => GROUP_META[g]);
        setGroups(groupList);
        // iter150 — Si une mention a demandé un salon spécifique, on l'ouvre.
        try {
          const hint = typeof window !== 'undefined' ? window.__codeforgeOpenGroupHint : null;
          if (hint && groupList.includes(hint)) {
            setActive(hint);
            window.__codeforgeOpenGroupHint = null;
          } else if (!active && groupList.length > 0) {
            setActive(groupList[0]);
          }
        } catch (_) {
          if (!active && groupList.length > 0) setActive(groupList[0]);
        }
        // Si le groupe actif n'est plus accessible (changement de simulation),
        // bascule automatiquement.
        if (active && !groupList.includes(active)) {
          setActive(groupList[0] || null);
        }
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Impossible de charger les groupes');
      }
    })();
    return () => { cancelled = true; };
  }, [open, viewMode]); // eslint-disable-line

  const loadMessages = async (group_type) => {
    try {
      const body = await withCreatorProof(API, axios, { group_type, view_mode: viewMode });
      const r = await axios.post(`${API}/groups/messages`, body);
      setMessages(r.data?.messages || []);
      setTimeout(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
      }, 60);
    } catch (e) {
      // iter142 — Silencieux sur 403 (changement de simulation) : évite
      // "Tu n'as pas accès à ce groupe" qui rend le user méfiant.
      const status = e?.response?.status;
      if (status !== 403 && status !== 400) {
        toast.error(e?.response?.data?.detail || 'Impossible de charger les messages');
      }
      setMessages([]);
    }
  };

  useEffect(() => {
    if (!open || !active) return undefined;
    // iter150 — Marque le salon actif comme lu à l'ouverture.
    unread.markRead('group', active);
    let cancelled = false;
    const tick = async () => { if (!cancelled) await loadMessages(active); };
    tick();
    const id = setInterval(tick, 4000);
    return () => { cancelled = true; clearInterval(id); };
  }, [open, active, viewMode]); // eslint-disable-line

  const send = async () => {
    const content = draft.trim();
    if (!content || !active || sending) return;
    setSending(true);
    try {
      const body = await withCreatorProof(API, axios, { group_type: active, content, view_mode: viewMode });
      await axios.post(`${API}/groups/send`, body);
      setDraft('');
      await loadMessages(active);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Envoi impossible");
    } finally {
      setSending(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[80] bg-black/40 backdrop-blur-sm"
      onClick={onClose}
      data-testid="groups-panel"
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        className="absolute top-0 right-0 bottom-0 w-full sm:w-[640px] bg-[#0A0A0A] border-l border-white/15 shadow-[-20px_0_60px_rgba(0,0,0,0.6)] flex overflow-hidden"
      >
        {/* Group selector */}
        <aside className="w-[180px] flex-shrink-0 border-r border-white/10 flex flex-col">
          <header className="px-3 py-3 border-b border-white/10 flex items-center gap-2">
            <Users className="w-4 h-4 text-[#E4FF00]" />
            <h2 className="text-xs font-['Chivo'] font-bold text-white">Groupes</h2>
          </header>
          <div className="flex-1 overflow-y-auto py-2">
            {ORDER.filter((g) => groups.includes(g)).map((g) => {
              const meta = GROUP_META[g];
              const Icon = meta.icon;
              return (
                <button
                  key={g}
                  onClick={() => { setActive(g); unread.markRead('group', g); }}
                  data-testid={`group-tab-${g}`}
                  className={`w-full text-left px-3 py-2 flex items-center gap-2 border-l-2 transition ${
                    active === g
                      ? `${meta.bg} ${meta.border.replace('border-', 'border-l-')} text-white`
                      : 'border-l-transparent text-[#A1A1AA] hover:bg-white/[0.04]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${meta.color}`} />
                  <span className="text-xs font-bold flex-1 truncate">{meta.label}</span>
                  <UnreadBadge count={unread.groups?.[g] || 0} testId={`unread-badge-${g}`} />
                </button>
              );
            })}
            {groups.length === 0 && (
              <div className="px-3 py-4 text-[10px] text-[#71717A] text-center">
                Aucun groupe accessible
              </div>
            )}
          </div>
        </aside>

        {/* Messages */}
        <section className="flex-1 flex flex-col min-w-0">
          <header className="px-3 py-3 border-b border-white/10 flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2 truncate min-w-0">
                {active && (() => {
                  const meta = GROUP_META[active];
                  const Icon = meta.icon;
                  return (
                    <>
                      <Icon className={`w-4 h-4 ${meta.color}`} />
                      <h3 className="text-sm font-['Chivo'] font-bold text-white">{meta.label}</h3>
                    </>
                  );
                })()}
              </div>
              <button onClick={onClose} data-testid="groups-close" className="text-[#A1A1AA] hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            {/* iter141 — Rangée de toggles : Anonyme (tous) + Soleil/Nuit (staff)
                + Invisible (admin/créa) */}
            <div className="flex items-center gap-4 flex-wrap">
              <AnonymousModeToggle />
              <SunNightModeToggle role={device?.role} staffKind={device?.staffKind} />
              {active && (
                <InvisibleModeToggle
                  role={device?.role}
                  staffKind={device?.staffKind}
                  groupType={active}
                />
              )}
            </div>
          </header>
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2 bg-[#0A0A0A]">
            {viewMode && viewMode !== 'creator' ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12" data-testid="chat-simulation-locked">
                <Lock className="w-8 h-8 text-white/30 mb-3" />
                <p className="text-sm text-white/60 font-bold">Historique verrouillé</p>
                <p className="text-xs text-white/40 mt-1 max-w-xs">
                  L&apos;historique des messages et les messages privés sont
                  masqués pendant une simulation.
                </p>
              </div>
            ) : (
              <>
                {messages.map((m) => (
                  <MessageBubble key={m.message_id} message={m} revealAnonymous />
                ))}
                {messages.length === 0 && (
                  <div className="text-xs text-[#71717A] text-center py-8">Aucun message dans ce groupe</div>
                )}
              </>
            )}
          </div>
          <MentionInputWithSend
            value={draft}
            onChange={setDraft}
            onSend={send}
            disabled={!active || sending}
            groupType={active}
            viewMode={viewMode}
          />
          {/* iter146 Sprint 2 — Liste des membres avec filtres par rôle */}
          {active && (
            <GroupMembersList groupType={active} viewMode={viewMode} />
          )}
        </section>
      </aside>
    </div>
  );
}
