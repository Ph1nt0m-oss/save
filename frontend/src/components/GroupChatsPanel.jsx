import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { X, Send, Users, Lock, Crown, Shield, Globe2 } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter86 C19 — 6 → 7 types de tchats de groupe (ajout 'admin').
const GROUP_META = {
  public: { label: 'Public', icon: Globe2, color: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  private: { label: 'Privé', icon: Lock, color: 'text-violet-300', bg: 'bg-violet-500/10', border: 'border-violet-500/30' },
  staff: { label: 'Staff', icon: Shield, color: 'text-orange-300', bg: 'bg-orange-500/10', border: 'border-orange-500/30' },
  modo: { label: 'Modo', icon: Shield, color: 'text-cyan-300', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' },
  admin: { label: 'Admin', icon: Shield, color: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-400/40' },
  public_staff: { label: 'Public + Staff', icon: Users, color: 'text-yellow-300', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
  public_private: { label: 'Public + Privé', icon: Users, color: 'text-sky-300', bg: 'bg-sky-500/10', border: 'border-sky-500/30' },
};

const ORDER = ['public', 'private', 'staff', 'modo', 'admin', 'public_staff', 'public_private'];

export default function GroupChatsPanel({ open, onClose }) {
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
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/groups/list`, body);
        if (cancelled) return;
        const groupList = (r.data?.groups || []).filter((g) => GROUP_META[g]);
        setGroups(groupList);
        if (!active && groupList.length > 0) setActive(groupList[0]);
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Impossible de charger les groupes');
      }
    })();
    return () => { cancelled = true; };
  }, [open]); // eslint-disable-line

  const loadMessages = async (group_type) => {
    try {
      const body = await withCreatorProof(API, axios, { group_type });
      const r = await axios.post(`${API}/groups/messages`, body);
      setMessages(r.data?.messages || []);
      setTimeout(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
      }, 60);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impossible de charger les messages');
    }
  };

  useEffect(() => {
    if (!open || !active) return undefined;
    let cancelled = false;
    const tick = async () => { if (!cancelled) await loadMessages(active); };
    tick();
    const id = setInterval(tick, 4000);
    return () => { cancelled = true; clearInterval(id); };
  }, [open, active]); // eslint-disable-line

  const send = async () => {
    const content = draft.trim();
    if (!content || !active || sending) return;
    setSending(true);
    try {
      const body = await withCreatorProof(API, axios, { group_type: active, content });
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
                  onClick={() => setActive(g)}
                  data-testid={`group-tab-${g}`}
                  className={`w-full text-left px-3 py-2 flex items-center gap-2 border-l-2 transition ${
                    active === g
                      ? `${meta.bg} ${meta.border.replace('border-', 'border-l-')} text-white`
                      : 'border-l-transparent text-[#A1A1AA] hover:bg-white/[0.04]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${meta.color}`} />
                  <span className="text-xs font-bold">{meta.label}</span>
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
          <header className="px-3 py-3 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2 truncate">
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
          </header>
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2">
            {messages.map((m) => (
              <div key={m.message_id} className="bg-black/30 border border-white/10 rounded-sm p-2.5">
                <div className="text-[10px] text-[#71717A] flex items-center gap-2 mb-1">
                  {m.from_role === 'creator' && <Crown className="w-2.5 h-2.5 text-[#E4FF00]" />}
                  {m.from_staff_kind === 'admin' && <Shield className="w-2.5 h-2.5 text-orange-300" />}
                  {m.from_staff_kind === 'modo' && <Shield className="w-2.5 h-2.5 text-cyan-300" />}
                  <span className="font-bold text-white">{m.from_pseudo || m.from_key_id?.slice(0, 10)}</span>
                  <span>{new Date(m.ts).toLocaleString()}</span>
                </div>
                <div className="text-sm text-white whitespace-pre-wrap break-words">{m.content}</div>
              </div>
            ))}
            {messages.length === 0 && (
              <div className="text-xs text-[#71717A] text-center py-8">Aucun message dans ce groupe</div>
            )}
          </div>
          <div className="border-t border-white/10 p-2 flex gap-2">
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
              placeholder="Message…"
              data-testid="group-input"
              disabled={!active || sending}
              className="flex-1 px-3 py-2 bg-[#0F0F13] border border-white/15 rounded-sm text-sm focus:outline-none focus:border-[#E4FF00]"
            />
            <button
              onClick={send}
              disabled={!active || sending || !draft.trim()}
              data-testid="group-send"
              className="px-3 py-2 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90 disabled:opacity-40"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </section>
      </aside>
    </div>
  );
}
