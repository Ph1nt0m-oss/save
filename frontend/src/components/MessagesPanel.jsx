import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { X, Send, Trash2, ChevronLeft, Mail, User, Crown, Edit3, Ban, ShieldCheck, UserX } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Two-panel messaging UI.
 *
 *  - For the creator: full inbox (thread list on the left, conversation on
 *    the right) with reply input + delete-thread.
 *  - For non-creators: their single thread with the creator, prefilled and
 *    ready to type into.
 *
 * Auto-refreshes every 4s while open. All endpoints are device-signed.
 */
export default function MessagesPanel({ open, onClose, isCreator, currentKeyId }) {
  const { t } = useLanguage();
  const [threads, setThreads] = useState([]);
  const [selected, setSelected] = useState(null);  // thread_key_id
  const [thread, setThread] = useState(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  // For non-creators, the thread IS themselves.
  useEffect(() => {
    if (open && !isCreator) setSelected(currentKeyId);
  }, [open, isCreator, currentKeyId]);

  const loadInbox = async () => {
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/messages/inbox`, body);
      setThreads(r.data?.threads || []);
    } catch (e) { /* silent */ }
  };

  const loadThread = async (thread_key_id) => {
    try {
      const body = await withCreatorProof(API, axios, { thread_key_id: isCreator ? thread_key_id : undefined });
      const r = await axios.post(`${API}/messages/thread`, body);
      setThread(r.data);
      setTimeout(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
      }, 50);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_load_failed'));
    }
  };

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      if (isCreator) await loadInbox();
      if (selected) await loadThread(selected);
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selected, isCreator]);

  const send = async () => {
    const content = draft.trim();
    if (!content || sending) return;
    setSending(true);
    try {
      const body = await withCreatorProof(API, axios, {
        content,
        target_key_id: isCreator ? selected : undefined,
      });
      await axios.post(`${API}/messages/send`, body);
      setDraft('');
      await loadThread(selected);
      if (isCreator) await loadInbox();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_send_failed'));
    } finally {
      setSending(false);
    }
  };

  const deleteThread = async () => {
    if (!selected) return;
    if (!window.confirm(t('msg_delete_thread_confirm'))) return;
    try {
      const body = await withCreatorProof(API, axios, { thread_key_id: selected });
      await axios.post(`${API}/messages/delete-thread`, body);
      toast.success(t('msg_thread_deleted'));
      setSelected(null);
      setThread(null);
      loadInbox();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_op_failed'));
    }
  };

  const renameContact = async () => {
    if (!selected) return;
    const currentLabel = threads.find((th) => th.thread_key_id === selected)?.label || '';
    const next = window.prompt(t('msg_rename_prompt'), currentLabel);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed) return;
    try {
      const body = await withCreatorProof(API, axios, { thread_key_id: selected, new_label: trimmed });
      await axios.post(`${API}/messages/rename-contact`, body);
      toast.success(t('msg_renamed'));
      loadInbox();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_op_failed'));
    }
  };

  const blockContact = async () => {
    if (!selected) return;
    if (!window.confirm(t('msg_block_confirm'))) return;
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: selected });
      await axios.post(`${API}/devices/block`, body);
      toast.success(t('hist_blocked'));
      loadInbox();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_op_failed'));
    }
  };

  const unblockContact = async () => {
    if (!selected) return;
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: selected });
      await axios.post(`${API}/devices/unblock`, body);
      toast.success(t('hist_unblocked'));
      loadInbox();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_op_failed'));
    }
  };

  const deleteContact = async () => {
    if (!selected) return;
    if (!window.confirm(t('msg_delete_contact_confirm'))) return;
    try {
      // "Supprimer le contact" : ne révoque PLUS le device — on efface
      // simplement le fil de discussion côté créatrice. Le pseudo n'apparaît
      // plus dans la liste tant que la personne ne renvoie pas de message.
      // L'utilisateur peut toujours écrire à la créatrice (sauf s'il est
      // déjà bloqué, auquel cas le combo Bloquer + Supprimer rend la
      // récupération impossible sans débloquer manuellement).
      const tBody = await withCreatorProof(API, axios, { thread_key_id: selected });
      await axios.post(`${API}/messages/delete-thread`, tBody);
      toast.success(t('msg_contact_deleted'));
      setSelected(null);
      setThread(null);
      loadInbox();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('msg_op_failed'));
    }
  };

  if (!open) return null;
  const showInbox = isCreator && !selected;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 backdrop-blur-sm p-2 sm:p-4"
      onClick={onClose}
      data-testid="messages-panel"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl h-[85vh] sm:h-[80vh] bg-[#0A0A0A] border border-white/15 rounded-sm flex overflow-hidden"
      >
        {/* Inbox (creator) */}
        {isCreator && (
          <aside className={`${selected ? 'hidden sm:flex' : 'flex'} w-full sm:w-[280px] flex-shrink-0 border-r border-white/10 flex-col`}>
            <header className="px-3 py-3 border-b border-white/10 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-[#E4FF00]" />
                <h2 className="text-sm font-['Chivo'] font-bold text-white">{t('msg_inbox')}</h2>
              </div>
              <button onClick={onClose} className="text-[#A1A1AA] hover:text-white sm:hidden">
                <X className="w-4 h-4" />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto">
              {threads.length === 0 && (
                <div className="p-3 text-xs text-[#A1A1AA]">{t('msg_inbox_empty')}</div>
              )}
              {threads.map((th) => (
                <button
                  key={th.thread_key_id}
                  onClick={() => setSelected(th.thread_key_id)}
                  data-testid={`thread-row-${th.thread_key_id}`}
                  className={`w-full text-left px-3 py-2 border-b border-white/5 hover:bg-white/[0.04] transition ${
                    selected === th.thread_key_id ? 'bg-white/[0.05]' : ''
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <User className="w-3 h-3 text-[#A1A1AA] flex-shrink-0" />
                    <span className="text-xs text-white truncate flex-1">
                      {th.label || th.thread_key_id.slice(0, 14)}
                    </span>
                    {th.unread > 0 && (
                      <span className="text-[9px] bg-[#E4FF00] text-[#050505] font-bold px-1.5 rounded-full">
                        {th.unread}
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-[#71717A] mt-0.5 truncate">
                    {th.last_is_from_creator && <span className="text-[#E4FF00]">{t('msg_you_short')}: </span>}
                    {th.last_content}
                  </div>
                  <div className="text-[9px] text-[#71717A] mt-0.5">
                    {new Date(th.last_ts).toLocaleString()}
                  </div>
                </button>
              ))}
            </div>
          </aside>
        )}

        {/* Conversation */}
        <section className={`${showInbox ? 'hidden sm:flex' : 'flex'} flex-1 flex-col min-w-0`}>
          <header className="px-3 py-3 border-b border-white/10 flex items-center gap-2 flex-shrink-0">
            {isCreator && selected && (
              <button
                onClick={() => { setSelected(null); setThread(null); }}
                className="text-[#A1A1AA] hover:text-white sm:hidden"
                data-testid="back-to-inbox"
                aria-label="Back"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            )}
            <div className="flex items-center gap-1.5 min-w-0">
              {isCreator ? <User className="w-4 h-4 text-[#A1A1AA] flex-shrink-0" /> : <Crown className="w-4 h-4 text-[#E4FF00] flex-shrink-0" />}
              <h3 className="text-sm font-['Chivo'] font-bold text-white truncate">
                {isCreator
                  ? (threads.find((th) => th.thread_key_id === selected)?.label || (selected || '').slice(0, 16))
                  : t('msg_chat_with_creator')}
              </h3>
            </div>
            {isCreator && selected && (
              <div className="ml-auto flex items-center gap-1">
                <button
                  onClick={renameContact}
                  data-testid="rename-contact-btn"
                  title={t('msg_rename')}
                  className="text-[#A1A1AA] hover:text-[#E4FF00] transition p-1"
                >
                  <Edit3 className="w-4 h-4" />
                </button>
                {(() => {
                  const sel = threads.find((th) => th.thread_key_id === selected);
                  const isBlocked = sel?.role === 'blocked';
                  return isBlocked ? (
                    <button
                      onClick={unblockContact}
                      data-testid="unblock-contact-btn"
                      title={t('hist_unblock')}
                      className="text-emerald-300 hover:text-emerald-200 transition p-1"
                    >
                      <ShieldCheck className="w-4 h-4" />
                    </button>
                  ) : (
                    <button
                      onClick={blockContact}
                      data-testid="block-contact-btn"
                      title={t('hist_block')}
                      className="text-[#A1A1AA] hover:text-red-400 transition p-1"
                    >
                      <Ban className="w-4 h-4" />
                    </button>
                  );
                })()}
                <button
                  onClick={deleteContact}
                  data-testid="delete-contact-btn"
                  title={t('msg_delete_contact')}
                  className="text-[#A1A1AA] hover:text-red-400 transition p-1"
                >
                  <UserX className="w-4 h-4" />
                </button>
                <button
                  onClick={deleteThread}
                  data-testid="delete-thread-btn"
                  title={t('msg_delete_thread')}
                  className="text-[#A1A1AA] hover:text-red-400 transition p-1"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
            <button
              onClick={onClose}
              className={`text-[#A1A1AA] hover:text-white ${isCreator && selected ? '' : 'ml-auto'}`}
              data-testid="messages-close"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </header>

          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-3 space-y-2"
            data-testid="messages-list"
          >
            {!thread && <div className="text-xs text-[#A1A1AA] py-4 text-center">{t('msg_select_thread')}</div>}
            {thread && thread.messages.length === 0 && (
              <div className="text-xs text-[#A1A1AA] py-4 text-center">{t('msg_thread_empty')}</div>
            )}
            {thread?.messages?.map((m, idx, arr) => {
              const mine = isCreator ? m.is_from_creator : !m.is_from_creator;
              // Group consecutive messages from the same sender — display
              // the header (label + timestamp) only when the sender changes
              // or when ≥10 minutes have passed since the previous message.
              const prev = arr[idx - 1];
              const sameSender = prev && prev.is_from_creator === m.is_from_creator;
              const dt = prev ? (new Date(m.ts) - new Date(prev.ts)) / 60000 : Infinity;
              const showHeader = !sameSender || dt > 10;
              return (
                <div
                  key={m.message_id}
                  data-testid="msg-row"
                  className={`flex ${mine ? 'justify-end' : 'justify-start'} ${sameSender && !showHeader ? '-mt-1.5' : ''}`}
                >
                  <div className={`max-w-[78%] px-3 py-2 rounded-sm ${
                    mine
                      ? 'bg-[#E4FF00]/15 border border-[#E4FF00]/30 text-white'
                      : 'bg-white/[0.05] border border-white/10 text-white'
                  }`}>
                    {showHeader && (
                      <div className="text-[10px] text-[#A1A1AA] mb-0.5">
                        {m.is_from_creator ? t('msg_from_creator') : (m.sender_label || t('msg_from_user'))}
                        <span className="ml-2 opacity-60">{new Date(m.ts).toLocaleString()}</span>
                      </div>
                    )}
                    <div className="text-sm whitespace-pre-wrap break-words">{m.content}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Composer — hidden when creator has no thread selected */}
          {selected !== null && (
            <div className="border-t border-white/10 p-3 flex-shrink-0">
              <div className="flex items-end gap-2">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send();
                  }}
                  data-testid="msg-composer"
                  rows={2}
                  maxLength={2000}
                  placeholder={isCreator ? t('msg_reply_placeholder') : t('msg_send_to_creator_placeholder')}
                  className="flex-1 bg-black/40 border border-white/10 rounded-sm px-2 py-2 text-xs text-white placeholder-[#A1A1AA]/50 focus:outline-none focus:border-[#E4FF00] resize-none"
                />
                <button
                  onClick={send}
                  disabled={sending || draft.trim().length === 0}
                  data-testid="msg-send-btn"
                  className="flex-shrink-0 inline-flex items-center justify-center w-10 h-10 bg-[#E4FF00] text-[#050505] rounded-sm hover:bg-white transition disabled:opacity-50"
                  aria-label="Send"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
              <div className="text-[10px] text-[#71717A] mt-1">{draft.length}/2000 — Ctrl+Enter</div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
