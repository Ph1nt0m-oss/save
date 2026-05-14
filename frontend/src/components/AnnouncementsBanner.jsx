import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Megaphone, X, BarChart3 } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DISMISS_KEY = 'codeforge_ann_dismissed';

function readDismissed() {
  try { return JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]'); } catch (_) { return []; }
}
function pushDismissed(id) {
  const arr = readDismissed();
  if (!arr.includes(id)) arr.push(id);
  try { localStorage.setItem(DISMISS_KEY, JSON.stringify(arr.slice(-200))); } catch (_) {}
}

/**
 * Top banner showing the latest active announcement + sticky poll cards.
 * Rendered on every page (App.js global slot).
 */
export default function AnnouncementsBanner() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const [announcements, setAnnouncements] = useState([]);
  const [polls, setPolls] = useState([]);
  const [dismissed, setDismissed] = useState(readDismissed());

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const params = device.keyId ? { params: { key_id: device.keyId } } : undefined;
        const [a, p] = await Promise.all([
          axios.get(`${API}/announcements/list`, params),
          axios.get(`${API}/polls/list`, params),
        ]);
        if (cancelled) return;
        setAnnouncements(a.data?.announcements || []);
        setPolls(p.data?.polls || []);
      } catch (_) {}
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, [device.keyId]);

  const dismiss = (id) => {
    pushDismissed(id);
    setDismissed([...readDismissed()]);
  };

  const vote = async (poll_id, option_index) => {
    try {
      const body = await withCreatorProof(API, axios, { poll_id, option_index });
      await axios.post(`${API}/polls/vote`, body);
      toast.success(t('poll_voted'));
      // refresh now
      const params = device.keyId ? { params: { key_id: device.keyId } } : undefined;
      const r = await axios.get(`${API}/polls/list`, params);
      setPolls(r.data?.polls || []);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const visibleAnn = announcements.filter((a) => !dismissed.includes(a.announce_id));
  const visiblePolls = polls.filter((p) => !dismissed.includes(p.poll_id));

  if (visibleAnn.length === 0 && visiblePolls.length === 0) return null;

  return (
    <div className="fixed top-1 inset-x-1 sm:top-2 sm:inset-x-2 z-[78] flex flex-col gap-1.5 pointer-events-none">
      {visibleAnn.slice(0, 2).map((a) => (
        <div key={a.announce_id} data-testid={`ann-banner-${a.announce_id}`} className="pointer-events-auto bg-[#0A0A0A]/95 border border-[#E4FF00]/40 rounded-sm p-2 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
          <div className="flex items-start gap-2">
            <Megaphone className="w-4 h-4 text-[#E4FF00] flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-['Chivo'] font-bold text-white truncate">{a.title}</div>
              {a.body && <div className="text-[11px] text-[#A1A1AA] mt-0.5 whitespace-pre-wrap break-words">{a.body}</div>}
            </div>
            <button onClick={() => dismiss(a.announce_id)} className="text-[#A1A1AA] hover:text-white p-1" aria-label="Close"><X className="w-3.5 h-3.5" /></button>
          </div>
        </div>
      ))}
      {visiblePolls.slice(0, 1).map((p) => {
        const total = (p.tally || []).reduce((s, x) => s + x, 0);
        const voted = typeof p.my_vote === 'number';
        return (
          <div key={p.poll_id} data-testid={`poll-card-${p.poll_id}`} className="pointer-events-auto bg-[#0A0A0A]/95 border border-[#E4FF00]/40 rounded-sm p-2 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
            <div className="flex items-start gap-2">
              <BarChart3 className="w-4 h-4 text-[#E4FF00] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-['Chivo'] font-bold text-white truncate">{p.question}</div>
                <div className="mt-1 space-y-1">
                  {p.options.map((opt, idx) => {
                    const count = p.tally?.[idx] || 0;
                    const pct = total ? Math.round((count / total) * 100) : 0;
                    const isMine = p.my_vote === idx;
                    return (
                      <button
                        key={idx}
                        onClick={() => !voted && vote(p.poll_id, idx)}
                        disabled={voted}
                        data-testid={`poll-opt-vote-${p.poll_id}-${idx}`}
                        className={`w-full text-left text-[11px] px-2 py-1 rounded-sm border transition ${
                          isMine ? 'border-[#E4FF00] bg-[#E4FF00]/15 text-[#E4FF00]' : 'border-white/15 text-white hover:bg-white/5'
                        } ${voted ? 'cursor-default' : ''}`}
                      >
                        <div className="flex justify-between"><span className="truncate">{opt}</span>{voted && <span className="text-[#71717A] ml-2">{count} · {pct}%</span>}</div>
                        {voted && <div className="h-0.5 bg-white/10 mt-1 rounded-sm overflow-hidden"><div className="h-0.5 bg-[#E4FF00]" style={{ width: `${pct}%` }} /></div>}
                      </button>
                    );
                  })}
                </div>
              </div>
              <button onClick={() => dismiss(p.poll_id)} className="text-[#A1A1AA] hover:text-white p-1" aria-label="Close"><X className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
