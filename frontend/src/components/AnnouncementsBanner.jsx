import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Megaphone, X, BarChart3, Plus } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DISMISS_KEY = 'codeforge_ann_dismissed';
const FULLSCREEN_SEEN_KEY = 'codeforge_ann_fullscreen_seen';

function readDismissed() {
  try { return JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]'); } catch (_) { return []; }
}
function pushDismissed(id) {
  const arr = readDismissed();
  if (!arr.includes(id)) arr.push(id);
  try { localStorage.setItem(DISMISS_KEY, JSON.stringify(arr.slice(-200))); } catch (_) {}
}
function readFsSeen() {
  try { return JSON.parse(localStorage.getItem(FULLSCREEN_SEEN_KEY) || '[]'); } catch (_) { return []; }
}
function pushFsSeen(id) {
  const arr = readFsSeen();
  if (!arr.includes(id)) arr.push(id);
  try { localStorage.setItem(FULLSCREEN_SEEN_KEY, JSON.stringify(arr.slice(-500))); } catch (_) {}
}

function formatTs(iso) {
  try { return new Date(iso).toLocaleString(); } catch (_) { return ''; }
}

/**
 * iter77 — bannière annonces + sondages.
 *
 * Comportement annonces :
 * - À la 1ʳᵉ apparition (jamais vue fullscreen), on l'affiche en MODAL plein
 *   écran sous le titre CodeForge AI. L'utilisateur clique sur X → on marque
 *   l'annonce comme "vue" et on bascule en bandeau haut. Re-clic X bandeau →
 *   l'annonce disparait (dismissed) jusqu'à modification créa.
 * - Les icônes ✅❌🟠 ne s'affichent PLUS ici (déplacées vers le panneau
 *   « Gérer » côté créa + IdeasButton pour bugs/idées).
 *
 * Sondages :
 * - Multi-sélection (max_selections), 0 = illimité.
 * - Si allow_user_suggestions activé, formulaire de proposition perso visible.
 */
export default function AnnouncementsBanner() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const [announcements, setAnnouncements] = useState([]);
  const [polls, setPolls] = useState([]);
  const [dismissed, setDismissed] = useState(readDismissed());
  const [fsSeen, setFsSeen] = useState(readFsSeen());
  const [draftSel, setDraftSel] = useState({});
  const [suggestText, setSuggestText] = useState({});

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
    const tick = async () => { if (!cancelled) await refresh(); };
    tick();
    const id = setInterval(tick, 30000);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device.keyId]);

  const dismiss = (id) => { pushDismissed(id); setDismissed([...readDismissed()]); };
  const markFsSeen = (id) => { pushFsSeen(id); setFsSeen([...readFsSeen()]); };

  const toggleSel = (pid, idx, max) => {
    setDraftSel((d) => {
      const cur = new Set(d[pid] || []);
      if (cur.has(idx)) cur.delete(idx);
      else {
        if (max > 0 && cur.size >= max) {
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

  const submitSuggestion = async (poll_id) => {
    const text = (suggestText[poll_id] || '').trim();
    if (!text) { toast.error('Texte requis.'); return; }
    try {
      const body = await withCreatorProof(API, axios, { poll_id, text });
      await axios.post(`${API}/polls/suggest-option`, body);
      toast.success('Proposition envoyée — en attente de validation créa');
      setSuggestText((s) => ({ ...s, [poll_id]: '' }));
      await refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const visibleAnn = announcements.filter((a) => !dismissed.includes(a.announce_id));
  const visiblePolls = polls.filter((p) => !dismissed.includes(p.poll_id));

  const fullscreenAnn = visibleAnn.find((a) => !fsSeen.includes(a.announce_id));

  if (visibleAnn.length === 0 && visiblePolls.length === 0 && !fullscreenAnn) return null;

  return (
    <>
      {fullscreenAnn && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/90 backdrop-blur-md p-3 sm:p-6" data-testid={`ann-fullscreen-${fullscreenAnn.announce_id}`}>
          <div className="w-full max-w-3xl bg-[#0A0A0A] border-2 border-[#E4FF00]/60 rounded-md p-6 sm:p-10 shadow-[0_20px_80px_rgba(228,255,0,0.3)] max-h-[95vh] overflow-y-auto relative">
            <button onClick={() => markFsSeen(fullscreenAnn.announce_id)} data-testid="ann-fullscreen-close" className="absolute top-3 right-3 text-[#A1A1AA] hover:text-white p-2" aria-label="J'ai vu">
              <X className="w-6 h-6" />
            </button>
            <div className="flex flex-col items-center text-center gap-4">
              <Megaphone className="w-12 h-12 text-[#E4FF00]" />
              <h2 className="text-3xl sm:text-5xl font-['Chivo'] font-black text-white leading-tight">{fullscreenAnn.title}</h2>
              {fullscreenAnn.body && <p className="text-base sm:text-lg text-[#E4E4E7] mt-2 whitespace-pre-wrap break-words leading-relaxed">{fullscreenAnn.body}</p>}
              <div className="text-xs text-[#71717A] uppercase tracking-widest mt-4">{formatTs(fullscreenAnn.ts)}{fullscreenAnn.updated_at ? ' · modifiée' : ''}</div>
              <div className="text-[11px] text-[#71717A] italic mt-6">Clique sur X pour passer en bandeau (reste visible jusqu'à ce que tu le fermes complètement).</div>
            </div>
          </div>
        </div>
      )}

      <div className="fixed top-1 inset-x-1 sm:top-2 sm:inset-x-2 z-[78] flex flex-col gap-1.5 pointer-events-none">
        {visibleAnn.filter((a) => fsSeen.includes(a.announce_id)).slice(0, 3).map((a) => (
          <div key={a.announce_id} data-testid={`ann-banner-${a.announce_id}`} className="pointer-events-auto bg-[#0A0A0A]/95 border border-[#E4FF00]/40 rounded-sm p-2 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
            <div className="flex items-start gap-2">
              <Megaphone className="w-4 h-4 text-[#E4FF00] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-['Chivo'] font-bold text-white truncate">{a.title}{a.updated_at && <span className="text-[9px] text-amber-300 ml-1.5">(modifiée)</span>}</div>
                {a.body && <div className="text-[11px] text-[#A1A1AA] mt-0.5 whitespace-pre-wrap break-words">{a.body}</div>}
                <div className="text-[9px] text-[#71717A] mt-0.5 uppercase tracking-widest">{formatTs(a.ts)}</div>
              </div>
              <button onClick={() => dismiss(a.announce_id)} className="text-[#A1A1AA] hover:text-white p-1" aria-label="Close"><X className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        ))}
        {visiblePolls.slice(0, 2).map((p) => {
          const total = p.voters || (p.tally || []).reduce((s, x) => s + x, 0);
          const my = Array.isArray(p.my_vote) ? p.my_vote : (p.my_vote != null ? [p.my_vote] : null);
          const voted = my && my.length > 0;
          const max = parseInt(p.max_selections || 0, 10);
          const draft = draftSel[p.poll_id] || [];
          const allowSugg = !!p.allow_user_suggestions;
          const approvedSuggs = (p.suggestions || []).filter((s) => s.status === 'approved').length;
          return (
            <div key={p.poll_id} data-testid={`poll-card-${p.poll_id}`} className="pointer-events-auto bg-[#0A0A0A]/95 border border-[#E4FF00]/40 rounded-sm p-2 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
              <div className="flex items-start gap-2">
                <BarChart3 className="w-4 h-4 text-[#E4FF00] flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-['Chivo'] font-bold text-white truncate">{p.question}{p.updated_at && <span className="text-[9px] text-amber-300 ml-1.5">(modifié)</span>}</div>
                  <div className="text-[9px] text-[#71717A] uppercase tracking-widest">
                    Publié {formatTs(p.ts)} · {total} vote{total > 1 ? 's' : ''} · {max === 0 ? '∞ choix possibles' : `tu peux choisir ${max} option${max > 1 ? 's' : ''}`}
                    {allowSugg && <span className="ml-1 text-amber-300 normal-case">· tu peux écrire ta propre réponse</span>}
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
                          className={`w-full text-left text-[11px] px-2 py-1 rounded-sm border transition ${isMine ? 'border-[#E4FF00] bg-[#E4FF00]/15 text-[#E4FF00]' : isDraft ? 'border-[#E4FF00]/60 bg-[#E4FF00]/5 text-white' : 'border-white/15 text-white hover:bg-white/5'} ${voted ? 'cursor-default' : ''}`}
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
                    <button onClick={() => submitVote(p.poll_id)} disabled={!(draftSel[p.poll_id] || []).length} data-testid={`poll-submit-${p.poll_id}`} className="mt-1.5 px-2 py-1 text-[10px] rounded-sm bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold disabled:opacity-40 hover:bg-white transition">Voter</button>
                  )}
                  {allowSugg && (
                    <div className="mt-2 pt-2 border-t border-white/10 space-y-1">
                      <div className="text-[10px] text-[#A1A1AA]">Propose ta propre réponse ({approvedSuggs} validée{approvedSuggs > 1 ? 's' : ''}) :</div>
                      <div className="flex items-center gap-1">
                        <input value={suggestText[p.poll_id] || ''} onChange={(e) => setSuggestText((s) => ({ ...s, [p.poll_id]: e.target.value }))} placeholder="Mon idée…" data-testid={`poll-sugg-input-${p.poll_id}`} className="flex-1 bg-black/40 border border-white/10 rounded-sm px-2 py-1 text-[11px] text-white focus:outline-none focus:border-[#E4FF00]" maxLength={200} />
                        <button onClick={() => submitSuggestion(p.poll_id)} data-testid={`poll-sugg-submit-${p.poll_id}`} className="text-[10px] px-2 py-1 rounded-sm bg-amber-400 text-[#050505] font-bold hover:bg-white transition"><Plus className="w-3 h-3" /></button>
                      </div>
                    </div>
                  )}
                </div>
                <button onClick={() => dismiss(p.poll_id)} className="text-[#A1A1AA] hover:text-white p-1" aria-label="Close"><X className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
