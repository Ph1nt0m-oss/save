import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Lightbulb, X, Send, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Ideas / feedback button.
 *
 * - Non-creator devices: opens a composer panel — unlimited length, sends
 *   one idea to the creator with the sender's pseudo attached.
 * - Creator devices: opens an inbox of received ideas with mark-as-read
 *   and per-item delete actions.
 */
export default function IdeasButton() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [ideas, setIdeas] = useState([]);
  const isCreator = device.role === 'creator';
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!isCreator || !device.keyId) return undefined;
    let cancelled = false;
    const tick = async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/ideas/inbox`, body);
        if (cancelled) return;
        const list = r.data?.ideas || [];
        setIdeas(list);
        setUnread(list.filter((x) => !x.read).length);
      } catch (_) { /* silent */ }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, [isCreator, device.keyId, open]);

  const sendIdea = async () => {
    const content = draft.trim();
    if (!content || sending) return;
    setSending(true);
    try {
      const body = await withCreatorProof(API, axios, { content });
      await axios.post(`${API}/ideas/send`, body);
      setDraft('');
      toast.success(t('ideas_sent'));
      setOpen(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('ideas_send_failed'));
    } finally { setSending(false); }
  };

  const markAllRead = async () => {
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/ideas/mark-read`, body);
      setUnread(0);
      setIdeas((ls) => ls.map((x) => ({ ...x, read: true })));
    } catch (_) {}
  };

  const deleteIdea = async (idea_id) => {
    try {
      const body = await withCreatorProof(API, axios, { idea_id });
      await axios.post(`${API}/ideas/delete`, body);
      setIdeas((ls) => ls.filter((x) => x.idea_id !== idea_id));
    } catch (_) {}
  };

  if (!device.keyId) {
    return (
      <button
        type="button"
        data-testid="ideas-btn"
        className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] opacity-60 cursor-not-allowed"
        title={t('ideas_title')}
        disabled
      >
        <Lightbulb className="w-4 h-4" />
      </button>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => { setOpen(true); if (isCreator) markAllRead(); }}
        data-testid="ideas-btn"
        title={t('ideas_title')}
        className="relative inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-amber-300 hover:border-amber-400/40 transition-colors"
      >
        <Lightbulb className="w-4 h-4" />
        {isCreator && unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] bg-amber-400 text-[#050505] text-[9px] font-bold rounded-full inline-flex items-center justify-center px-1">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 backdrop-blur-sm p-2 sm:p-4" onClick={() => setOpen(false)} data-testid="ideas-panel">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-xl max-h-[85vh] bg-[#0A0A0A] border border-white/15 rounded-sm flex flex-col">
            <header className="px-3 py-3 border-b border-white/10 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-300" />
                <h2 className="text-sm font-['Chivo'] font-bold text-white">{t('ideas_title')}</h2>
              </div>
              <button onClick={() => setOpen(false)} className="text-[#A1A1AA] hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </header>

            {!isCreator && (
              <div className="p-3 space-y-3 flex flex-col flex-1 min-h-0">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  data-testid="ideas-composer"
                  rows={10}
                  placeholder={t('ideas_send_placeholder')}
                  className="flex-1 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#A1A1AA]/50 focus:outline-none focus:border-amber-300 resize-none min-h-[200px]"
                />
                <button
                  onClick={sendIdea}
                  disabled={sending || !draft.trim()}
                  data-testid="ideas-send-btn"
                  className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-400 text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm hover:bg-white transition disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  {t('ideas_send_btn')}
                </button>
              </div>
            )}

            {isCreator && (
              <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[200px]">
                {ideas.length === 0 && (
                  <div className="text-xs text-[#A1A1AA] py-4 text-center">{t('ideas_empty_inbox')}</div>
                )}
                {ideas.map((idea) => (
                  <div key={idea.idea_id} className="bg-black/30 border border-white/10 rounded-sm p-3 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-[11px] text-amber-300 truncate">
                        {idea.sender_label || idea.sender_key_id?.slice(0, 14)}
                        <span className="text-[#71717A] ml-2">{new Date(idea.ts).toLocaleString()}</span>
                      </div>
                      <button
                        onClick={() => deleteIdea(idea.idea_id)}
                        data-testid={`ideas-delete-${idea.idea_id}`}
                        title={t('ideas_delete_one')}
                        className="text-[#A1A1AA] hover:text-red-400 transition p-1 flex-shrink-0"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="text-sm text-white whitespace-pre-wrap break-words">{idea.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
