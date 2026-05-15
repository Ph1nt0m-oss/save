import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Megaphone, X, BarChart3, Check, AlertTriangle, KeyRound, RotateCcw } from 'lucide-react';
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

function formatTs(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch (_) { return ''; }
}

/**
 * Top banner showing the latest active announcement + sticky poll cards.
 * Rendered on every page (App.js global slot).
 *
 * iter76 — Annonces enrichies :
 * - Émojis ✅ Validé (vert) / ❌ Refusé (rouge) / 🟠 Orange (escalade)
 * - Asymétrie: staff valide → disparait pour staff, créatrice voit avec badge
 * - Sondages: multi-select selon max_selections + voters count
 */
export default function AnnouncementsBanner() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const [announcements, setAnnouncements] = useState([]);
  const [polls, setPolls] = useState([]);
  const [dismissed, setDismissed] = useState(readDismissed());
  const [draftSel, setDraftSel] = useState({}); // poll_id -> [idx]
  const isCreator = device.role === 'creator' && device.viewMode !== 'guest';

  const refresh = async () => {
    try {
      const params = device.keyId ? { params: { key_id: device.keyId } } : undefined;
      const [a, p] = await Promise.all([
        axios.get(`${API}/announcements/list`, params),
        axios.get(`${API}/polls/list`, params),
      ]);
      setAnnouncements(a.data?.announcements || []);
      setPolls(p.data?.polls || []);
    } catch (_) {}
  };

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await refresh();
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device.keyId]);

  const dismiss = (id) => {
    pushDismissed(id);
    setDismissed([...readDismissed()]);
  };

  const setAnnState = async (announce_id, state) => {
    if (!device.keyId) { toast.error('Clé appareil manquante.'); return; }
    try {
      const body = await withCreatorProof(API, axios, { announce_id, state });
      await axios.post(`${API}/announcements/set-state`, body);
      await refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const toggleSel = (pid, idx, max) => {
    setDraftSel((d) => {
      const cur = new Set(d[pid] || []);
      if (cur.has(idx)) cur.delete(idx);
      else {
        if (cur.size >= max) {
          // si max=1, remplace ; sinon ignore
          if (max === 1) { cur.clear(); cur.add(idx); }
          else { toast.error(`Max ${max} sélection(s).`); return d; }
        } else cur.add(idx);
      }
      return { ...d, [pid]: Array.from(cur).sort((a, b) => a - b) };
    });
  };

  const submitVote = async (poll_id) => {
    const sel = draftSel[poll_id] || [];
    if (!sel.length) { toast.error('Sélectionne au moins une option.'); return; }
    try {
      const body = await withCreatorProof(API, axios, { poll_id, option_indices: sel });
      await axios.post(`${API}/polls/vote`, body);
      toast.success(t('poll_voted') || 'Vote enregistré');
      setDraftSel((d) => ({ ...d, [poll_id]: undefined }));
      await refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const visibleAnn = announcements.filter((a) => !dismissed.includes(a.announce_id));
  const visiblePolls = polls.filter((p) => !dismissed.includes(p.poll_id));

  if (visibleAnn.length === 0 && visiblePolls.length === 0) return null;

  return (
    <div className="fixed top-1 inset-x-1 sm:top-2 sm:inset-x-2 z-[78] flex flex-col gap-1.5 pointer-events-none">
      {visibleAnn.slice(0, 3).map((a) => {
        const my = a.my_state || null;
        const staffStates = a.staff_states || [];
        const hasStaffValidated = staffStates.some((s) => s.state === 'validated' && s.actor === 'staff');
        return (
          <div key={a.announce_id} data-testid={`ann-banner-${a.announce_id}`} className="pointer-events-auto bg-[#0A0A0A]/95 border border-[#E4FF00]/40 rounded-sm p-2 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
            <div className="flex items-start gap-2">
              <Megaphone className="w-4 h-4 text-[#E4FF00] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-['Chivo'] font-bold text-white truncate flex items-center gap-1.5">
                  {a.title}
                  {my === 'validated' && <Check className="w-3 h-3 text-green-400" data-testid="ann-state-validated" />}
                  {my === 'refused' && <X className="w-3 h-3 text-red-400" data-testid="ann-state-refused" />}
                  {my === 'orange' && <AlertTriangle className="w-3 h-3 text-orange-400" data-testid="ann-state-orange" />}
                </div>
                {a.body && <div className="text-[11px] text-[#A1A1AA] mt-0.5 whitespace-pre-wrap break-words">{a.body}</div>}
                <div className="text-[9px] text-[#71717A] mt-0.5 uppercase tracking-widest">{formatTs(a.ts)}</div>
                {isCreator && hasStaffValidated && (
                  <div data-testid={`ann-staff-validated-${a.announce_id}`} className="mt-1 text-[10px] text-green-400 flex items-center gap-1"><Check className="w-3 h-3" /> Coché par le staff</div>
                )}
                {/* Boutons d'état */}
                <div className="mt-1.5 flex items-center gap-1 flex-wrap">
                  <button onClick={() => setAnnState(a.announce_id, 'validated')} data-testid={`ann-btn-validate-${a.announce_id}`} title="Validé" className="text-[10px] px-1.5 py-0.5 rounded-sm border border-green-500/40 text-green-300 hover:bg-green-500/10">✅</button>
                  <button onClick={() => setAnnState(a.announce_id, 'refused')} data-testid={`ann-btn-refuse-${a.announce_id}`} title="Refusé (non supprimable)" className="text-[10px] px-1.5 py-0.5 rounded-sm border border-red-500/40 text-red-300 hover:bg-red-500/10">❌</button>
                  <button onClick={() => setAnnState(a.announce_id, 'orange')} data-testid={`ann-btn-orange-${a.announce_id}`} title="Le staff n'a pas les codes — seule la créatrice peut" className="text-[10px] px-1.5 py-0.5 rounded-sm border border-orange-500/40 text-orange-300 hover:bg-orange-500/10"><KeyRound className="w-3 h-3" /></button>
                  {(my || (isCreator && staffStates.length > 0)) && (
                    <button onClick={() => setAnnState(a.announce_id, 'reset')} data-testid={`ann-btn-reset-${a.announce_id}`} title="Réinitialiser" className="text-[10px] px-1.5 py-0.5 rounded-sm border border-white/15 text-[#A1A1AA] hover:bg-white/5"><RotateCcw className="w-3 h-3" /></button>
                  )}
                </div>
              </div>
              <button onClick={() => dismiss(a.announce_id)} className="text-[#A1A1AA] hover:text-white p-1" aria-label="Close"><X className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        );
      })}
      {visiblePolls.slice(0, 2).map((p) => {
        const total = p.voters || (p.tally || []).reduce((s, x) => s + x, 0);
        const my = Array.isArray(p.my_vote) ? p.my_vote : (p.my_vote != null ? [p.my_vote] : null);
        const voted = my && my.length > 0;
        const max = Math.max(1, parseInt(p.max_selections || 1, 10));
        const draft = draftSel[p.poll_id] || [];
        return (
          <div key={p.poll_id} data-testid={`poll-card-${p.poll_id}`} className="pointer-events-auto bg-[#0A0A0A]/95 border border-[#E4FF00]/40 rounded-sm p-2 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
            <div className="flex items-start gap-2">
              <BarChart3 className="w-4 h-4 text-[#E4FF00] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-['Chivo'] font-bold text-white truncate">{p.question}</div>
                <div className="text-[9px] text-[#71717A] uppercase tracking-widest">
                  Publié {formatTs(p.ts)} · {total} vote{total > 1 ? 's' : ''} · max {max} choix
                </div>
                <div className="mt-1 space-y-1">
                  {p.options.map((opt, idx) => {
                    const count = p.tally?.[idx] || 0;
                    const pct = total ? Math.round((count / total) * 100) : 0;
                    const isMine = my && my.includes(idx);
                    const isDraft = draft.includes(idx);
                    return (
                      <button
                        key={idx}
                        onClick={() => !voted && toggleSel(p.poll_id, idx, max)}
                        disabled={voted}
                        data-testid={`poll-opt-vote-${p.poll_id}-${idx}`}
                        className={`w-full text-left text-[11px] px-2 py-1 rounded-sm border transition ${
                          isMine ? 'border-[#E4FF00] bg-[#E4FF00]/15 text-[#E4FF00]'
                          : isDraft ? 'border-[#E4FF00]/60 bg-[#E4FF00]/5 text-white'
                          : 'border-white/15 text-white hover:bg-white/5'
                        } ${voted ? 'cursor-default' : ''}`}
                      >
                        <div className="flex justify-between">
                          <span className="truncate inline-flex items-center gap-1.5">
                            {!voted && <span className={`inline-block w-3 h-3 rounded-sm border ${isDraft ? 'bg-[#E4FF00] border-[#E4FF00]' : 'border-white/30'}`} />}
                            {opt}
                          </span>
                          {voted && <span className="text-[#71717A] ml-2">{count} · {pct}%</span>}
                        </div>
                        {voted && <div className="h-0.5 bg-white/10 mt-1 rounded-sm overflow-hidden"><div className="h-0.5 bg-[#E4FF00]" style={{ width: `${pct}%` }} /></div>}
                      </button>
                    );
                  })}
                </div>
                {!voted && (
                  <button
                    onClick={() => submitVote(p.poll_id)}
                    disabled={!(draftSel[p.poll_id] || []).length}
                    data-testid={`poll-submit-${p.poll_id}`}
                    className="mt-1.5 px-2 py-1 text-[10px] rounded-sm bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold disabled:opacity-40 hover:bg-white transition"
                  >Voter</button>
                )}
              </div>
              <button onClick={() => dismiss(p.poll_id)} className="text-[#A1A1AA] hover:text-white p-1" aria-label="Close"><X className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
