import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Megaphone, X, Plus, Trash2, BarChart3, Edit3, Check } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter77 — Groupes d'audience disponibles. Multi-select via cases à cocher.
const AUDIENCE_GROUPS = [
  { id: 'all', label: 'Tout le monde' },
  { id: 'approved', label: 'Clés validées' },
  { id: 'non_validated', label: 'Clés non validées' },
  { id: 'admin', label: 'Admins' },
  { id: 'modo', label: 'Modos' },
];

function AudiencePicker({ value, onChange, testid = 'audience' }) {
  const v = Array.isArray(value) ? value : [value || 'all'];
  const toggle = (id) => {
    if (id === 'all') return onChange(['all']);
    const next = new Set(v.filter((x) => x !== 'all'));
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next.size ? Array.from(next) : ['all']);
  };
  return (
    <div className="flex items-center gap-1.5 flex-wrap" data-testid={testid}>
      <span className="text-xs text-[#A1A1AA] mr-1">Audience :</span>
      {AUDIENCE_GROUPS.map((g) => {
        const on = v.includes(g.id);
        return (
          <label key={g.id} data-testid={`${testid}-${g.id}`} className={`text-[11px] inline-flex items-center gap-1 px-2 py-1 rounded-sm border cursor-pointer transition ${on ? 'border-[#E4FF00]/50 bg-[#E4FF00]/10 text-[#E4FF00]' : 'border-white/10 text-[#A1A1AA] hover:text-white'}`}>
            <input type="checkbox" checked={on} onChange={() => toggle(g.id)} className="accent-[#E4FF00] w-3 h-3" />
            {g.label}
          </label>
        );
      })}
    </div>
  );
}

function formatAud(aud) {
  if (!aud) return 'tout le monde';
  const list = Array.isArray(aud) ? aud : [aud];
  return list.map((g) => AUDIENCE_GROUPS.find((x) => x.id === g)?.label || g).join(', ');
}

/**
 * 📣 Announce + Poll + Scheduled-kick launcher (creator-only). iter77.
 */
export default function AnnounceButton() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  // iter85 — Annonces : créa (vue creator) OU staff réel ou simulé peut publier
  // selon l'audience choisie. La créa qui simule guest/user n'a pas accès.
  const isCreator = device.role === 'creator' && device.viewMode === 'creator';
  const isStaff = isCreator || ['modo', 'admin'].includes(device.effectiveStaffKind);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('announce'); // 'announce' | 'poll' | 'manage'

  // Announce form
  const [aTitle, setATitle] = useState('');
  const [aBody, setABody] = useState('');
  const [aAud, setAAud] = useState(['all']);  // iter77 — multi-select
  // Poll form
  const [pQ, setPQ] = useState('');
  const [pOpts, setPOpts] = useState(['', '']);
  const [pAud, setPAud] = useState(['all']);  // iter77 — multi-select
  const [pMaxSel, setPMaxSel] = useState(0);  // iter77 — 0 = illimité
  const [pAllowSugg, setPAllowSugg] = useState(false);  // iter77
  // Scheduled disconnect form
  const [skMinutes, setSkMinutes] = useState(5);
  const [skNote, setSkNote] = useState('');
  const [skAud, setSkAud] = useState(['all']);  // iter77 — multi-select
  const [scheduledKicks, setScheduledKicks] = useState([]);
  // Edit state
  const [editing, setEditing] = useState(null);  // {kind:'ann'|'poll', id, payload}

  const [items, setItems] = useState({ announcements: [], polls: [] });

  const loadManage = useCallback(async () => {
    try {
      const [a, p, k] = await Promise.all([
        axios.get(`${API}/announcements/list`, { params: { key_id: device.keyId } }),
        axios.get(`${API}/polls/list`, { params: { key_id: device.keyId } }),
        axios.get(`${API}/system/scheduled-kicks`),
      ]);
      setItems({ announcements: a.data?.announcements || [], polls: p.data?.polls || [] });
      setScheduledKicks(k.data?.scheduled_kicks || []);
    } catch (_) {}
  }, [device.keyId]);

  useEffect(() => { if (open && tab === 'manage') loadManage(); }, [open, tab, loadManage]);

  if (!isCreator) return null;

  const publishAnnounce = async () => {
    if (!aTitle.trim()) return toast.error(t('ann_subject') + ' ?');
    try {
      const aud = aAud.length ? aAud : ['all'];
      const body = await withCreatorProof(API, axios, { title: aTitle.trim(), body: aBody.trim(), audience: aud });
      await axios.post(`${API}/announcements/create`, body);
      toast.success(t('ann_created'));
      setATitle(''); setABody(''); setOpen(false);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const publishPoll = async () => {
    const opts = pOpts.map((o) => o.trim()).filter(Boolean);
    if (!pQ.trim() || opts.length < 2) return toast.error('Question + 2 options requis');
    const maxSel = Math.max(0, parseInt(pMaxSel || 0, 10) || 0);  // iter77 — 0 = illimité
    try {
      const aud = pAud.length ? pAud : ['all'];
      const body = await withCreatorProof(API, axios, {
        question: pQ.trim(), options: opts, audience: aud,
        max_selections: maxSel, allow_user_suggestions: pAllowSugg,
      });
      await axios.post(`${API}/polls/create`, body);
      toast.success(t('ann_created'));
      setPQ(''); setPOpts(['', '']); setPMaxSel(0); setPAllowSugg(false); setOpen(false);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const editAnnSave = async () => {
    if (!editing || editing.kind !== 'ann') return;
    try {
      const body = await withCreatorProof(API, axios, {
        announce_id: editing.id,
        title: editing.payload.title, body: editing.payload.body,
        audience: editing.payload.audience,
      });
      await axios.post(`${API}/announcements/edit`, body);
      toast.success('Annonce modifiée — réenvoyée à tous');
      setEditing(null);
      loadManage();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const editPollSave = async () => {
    if (!editing || editing.kind !== 'poll') return;
    try {
      const body = await withCreatorProof(API, axios, {
        poll_id: editing.id,
        question: editing.payload.question,
        options: editing.payload.options,
        audience: editing.payload.audience,
        max_selections: editing.payload.max_selections,
        allow_user_suggestions: editing.payload.allow_user_suggestions,
      });
      await axios.post(`${API}/polls/edit`, body);
      toast.success('Sondage modifié — votes réinitialisés si options changent');
      setEditing(null);
      loadManage();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const decideSuggestion = async (suggestion_id, decision) => {
    try {
      const body = await withCreatorProof(API, axios, { suggestion_id, decision });
      await axios.post(`${API}/polls/decide-suggestion`, body);
      loadManage();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const clearAnnHistory = async () => {
    if (!window.confirm('Supprimer TOUT l\'historique des annonces et leurs états ? Action irréversible.')) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/announcements/clear-history`, body);
      toast.success('Historique vidé');
      loadManage();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const scheduleKick = async () => {
    try {
      const aud = skAud.length ? skAud : ['all'];
      const body = await withCreatorProof(API, axios, {
        minutes: parseInt(skMinutes || 0, 10),
        note: skNote.trim(),
        audience: aud,
      });
      await axios.post(`${API}/system/schedule-kick`, body);
      toast.success(`Déconnexion programmée dans ${skMinutes} min`);
      setSkNote('');
      loadManage();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const cancelKick = async (kick_id) => {
    try {
      const body = await withCreatorProof(API, axios, { kick_id });
      await axios.post(`${API}/system/cancel-scheduled-kick`, body);
      loadManage();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const deleteAnn = async (id) => {
    try {
      const body = await withCreatorProof(API, axios, { announce_id: id });
      await axios.post(`${API}/announcements/delete`, body);
      loadManage();
    } catch (_) {}
  };

  const deletePoll = async (id) => {
    try {
      const body = await withCreatorProof(API, axios, { poll_id: id });
      await axios.post(`${API}/polls/delete`, body);
      loadManage();
    } catch (_) {}
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="announce-btn"
        title={t('ann_title')}
        className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-[#E4FF00] hover:border-[#E4FF00]/40 transition-colors"
      >
        <Megaphone className="w-4 h-4" />
      </button>

      {open && (
        <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/75 backdrop-blur-sm p-2 sm:p-4" onClick={() => setOpen(false)} data-testid="announce-panel">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-xl max-h-[85vh] bg-[#0A0A0A] border border-white/15 rounded-sm flex flex-col overflow-hidden">
            <header className="px-3 py-3 border-b border-white/10 flex items-center gap-2 flex-shrink-0">
              <Megaphone className="w-4 h-4 text-[#E4FF00]" />
              <h2 className="text-sm font-['Chivo'] font-bold text-white">{t('ann_title')}</h2>
              <div className="ml-2 flex items-center gap-1 flex-wrap">
                {[['announce', t('ann_create')], ['poll', t('poll_create')], ['kick', 'Déco. progr.'], ['manage', 'Gérer']].map(([k, lbl]) => (
                  <button key={k} onClick={() => setTab(k)} data-testid={`ann-tab-${k}`} className={`px-2 py-1 text-[11px] rounded-sm border ${tab === k ? 'border-[#E4FF00]/40 text-[#E4FF00] bg-[#E4FF00]/10' : 'border-white/10 text-[#A1A1AA]'}`}>{lbl}</button>
                ))}
              </div>
              <button onClick={() => setOpen(false)} className="ml-auto text-[#A1A1AA] hover:text-white" aria-label="Close"><X className="w-4 h-4" /></button>
            </header>

            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {tab === 'announce' && (
                <>
                  <input value={aTitle} onChange={(e) => setATitle(e.target.value)} placeholder={t('ann_subject')} data-testid="ann-title" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#71717A] focus:outline-none focus:border-[#E4FF00]" />
                  <textarea value={aBody} onChange={(e) => setABody(e.target.value)} placeholder={t('ann_body')} data-testid="ann-body" rows={5} className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#71717A] focus:outline-none focus:border-[#E4FF00] resize-none" />
                  <AudiencePicker value={aAud} onChange={setAAud} testid="ann-aud" />
                  <button onClick={publishAnnounce} data-testid="ann-publish" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm hover:bg-white transition">{t('ann_create_btn')}</button>
                </>
              )}

              {tab === 'poll' && (
                <>
                  <input value={pQ} onChange={(e) => setPQ(e.target.value)} placeholder={t('poll_question')} data-testid="poll-question" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#71717A] focus:outline-none focus:border-[#E4FF00]" />
                  {pOpts.map((o, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input value={o} onChange={(e) => setPOpts((arr) => arr.map((x, idx) => idx === i ? e.target.value : x))} placeholder={t('poll_option').replace('{n}', String(i + 1))} className="flex-1 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#71717A] focus:outline-none focus:border-[#E4FF00]" data-testid={`poll-opt-${i}`} />
                      {pOpts.length > 2 && <button onClick={() => setPOpts((arr) => arr.filter((_, idx) => idx !== i))} className="text-red-300 p-1"><X className="w-3.5 h-3.5" /></button>}
                    </div>
                  ))}
                  {pOpts.length < 50 && (
                    <button onClick={() => setPOpts((arr) => [...arr, ''])} data-testid="poll-add-opt" className="inline-flex items-center gap-1 text-xs text-[#E4FF00] hover:text-white transition"><Plus className="w-3 h-3" />{t('poll_add_option')}</button>
                  )}
                  <AudiencePicker value={pAud} onChange={setPAud} testid="poll-aud" />
                  <div className="flex items-center gap-3 flex-wrap text-xs">
                    <label className="inline-flex items-center gap-1.5 text-[#A1A1AA]">
                      Choix max/voter
                      <input type="number" min={0} max={50} value={pMaxSel} onChange={(e) => setPMaxSel(Math.max(0, parseInt(e.target.value || '0', 10) || 0))} data-testid="poll-max-sel" className="w-16 bg-black/40 border border-white/10 rounded-sm px-2 py-1 text-xs text-white focus:outline-none focus:border-[#E4FF00]" />
                      <span className="text-[10px] text-[#71717A]">(0 = illimité)</span>
                    </label>
                    <label className="inline-flex items-center gap-1.5 text-[#A1A1AA] cursor-pointer">
                      <input type="checkbox" checked={pAllowSugg} onChange={(e) => setPAllowSugg(e.target.checked)} data-testid="poll-allow-sugg" className="accent-[#E4FF00]" />
                      Autoriser réponses perso (validation créa)
                    </label>
                  </div>
                  <button onClick={publishPoll} data-testid="poll-publish" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm hover:bg-white transition">{t('ann_create_btn')}</button>
                </>
              )}

              {tab === 'kick' && (
                <>
                  <div className="text-xs text-[#A1A1AA]">Programme la déconnexion dans X minutes pour l'audience cochée (toi exclue).</div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-white">Dans</label>
                    <input type="number" min={0} max={1440} value={skMinutes} onChange={(e) => setSkMinutes(Math.max(0, parseInt(e.target.value || '0', 10) || 0))} data-testid="kick-minutes" className="w-20 bg-black/40 border border-white/10 rounded-sm px-2 py-1 text-sm text-white focus:outline-none focus:border-[#E4FF00]" />
                    <label className="text-xs text-white">min</label>
                  </div>
                  <input value={skNote} onChange={(e) => setSkNote(e.target.value)} placeholder="Message d'annonce (facultatif)" data-testid="kick-note" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#71717A] focus:outline-none focus:border-[#E4FF00]" />
                  <AudiencePicker value={skAud} onChange={setSkAud} testid="kick-aud" />
                  <button onClick={scheduleKick} data-testid="kick-schedule" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm hover:bg-white transition">Programmer</button>
                  {scheduledKicks.length > 0 && (
                    <div className="mt-2 space-y-1">
                      <div className="text-[10px] uppercase tracking-widest text-[#71717A]">En cours</div>
                      {scheduledKicks.map((k) => (
                        <div key={k.kick_id} data-testid={`kick-row-${k.kick_id}`} className="flex items-center justify-between bg-black/30 border border-white/10 rounded-sm p-2 text-xs">
                          <span className="text-white">Dans {k.minutes} min — à {new Date(k.execute_at).toLocaleTimeString()} → {formatAud(k.audience)}</span>
                          <button onClick={() => cancelKick(k.kick_id)} data-testid={`kick-cancel-${k.kick_id}`} className="text-red-300 hover:text-red-400 p-1"><X className="w-3.5 h-3.5" /></button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {tab === 'manage' && (
                <>
                  {(items.announcements.length > 0 || items.polls.length > 0) && (
                    <div className="flex justify-end">
                      <button onClick={clearAnnHistory} data-testid="ann-clear-history" className="text-[11px] inline-flex items-center gap-1 px-2 py-1 rounded-sm border border-red-500/40 text-red-300 hover:bg-red-500/10"><Trash2 className="w-3 h-3" />Supprimer l'historique</button>
                    </div>
                  )}
                  {items.announcements.length === 0 && items.polls.length === 0 && (
                    <div className="text-xs text-[#A1A1AA] py-4 text-center">{t('ann_empty')}</div>
                  )}
                  {items.announcements.map((a) => {
                    return (
                      <div key={a.announce_id} data-testid={`manage-ann-${a.announce_id}`} className="bg-black/30 border border-white/10 rounded-sm p-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-sm font-['Chivo'] font-bold text-white truncate flex-1">{a.title}</div>
                          <button onClick={() => setEditing({ kind: 'ann', id: a.announce_id, payload: { title: a.title, body: a.body || '', audience: a.audience } })} data-testid={`ann-edit-${a.announce_id}`} title="Modifier" className="text-[#A1A1AA] hover:text-[#E4FF00] p-1"><Edit3 className="w-3.5 h-3.5" /></button>
                          <button onClick={() => deleteAnn(a.announce_id)} title="Supprimer" className="text-[#A1A1AA] hover:text-red-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                        {a.body && <div className="text-xs text-[#A1A1AA] mt-1 whitespace-pre-wrap break-words">{a.body}</div>}
                        <div className="text-[9px] text-[#71717A] mt-1 uppercase tracking-widest">→ {formatAud(a.audience)} · {new Date(a.ts).toLocaleString()}{a.updated_at ? ' (modifiée)' : ''}</div>
                      </div>
                    );
                  })}
                  {items.polls.map((p) => (
                    <div key={p.poll_id} data-testid={`manage-poll-${p.poll_id}`} className="bg-black/30 border border-white/10 rounded-sm p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-['Chivo'] font-bold text-white truncate flex-1 inline-flex items-center gap-2"><BarChart3 className="w-3.5 h-3.5 text-[#E4FF00]" />{p.question}</div>
                        <button onClick={() => setEditing({ kind: 'poll', id: p.poll_id, payload: { question: p.question, options: [...(p.options || [])], audience: p.audience, max_selections: p.max_selections || 0, allow_user_suggestions: !!p.allow_user_suggestions } })} data-testid={`poll-edit-${p.poll_id}`} title="Modifier" className="text-[#A1A1AA] hover:text-[#E4FF00] p-1"><Edit3 className="w-3.5 h-3.5" /></button>
                        <button onClick={() => deletePoll(p.poll_id)} title="Supprimer" className="text-[#A1A1AA] hover:text-red-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                      <div className="mt-1 space-y-1">
                        {p.options.map((o, idx) => {
                          const count = p.tally?.[idx] || 0;
                          const total = (p.tally || []).reduce((s, x) => s + x, 0);
                          const pct = total ? Math.round((count / total) * 100) : 0;
                          return (
                            <div key={idx} className="text-[11px] text-white">
                              <div className="flex justify-between"><span>{o}</span><span className="text-[#71717A]">{count} ({pct}%)</span></div>
                              <div className="h-1 bg-white/10 rounded-sm overflow-hidden"><div className="h-1 bg-[#E4FF00]" style={{ width: `${pct}%` }} /></div>
                            </div>
                          );
                        })}
                      </div>
                      <div className="text-[9px] text-[#71717A] mt-1 uppercase tracking-widest">→ {formatAud(p.audience)} · max {p.max_selections === 0 ? '∞' : (p.max_selections || 1)} · {p.voters || 0} vote{(p.voters || 0) > 1 ? 's' : ''} · {new Date(p.ts).toLocaleString()}</div>
                      {/* Propositions perso */}
                      {p.suggestions && p.suggestions.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-white/10 space-y-1">
                          <div className="text-[10px] uppercase tracking-widest text-[#71717A]">Propositions</div>
                          {p.suggestions.map((s) => (
                            <div key={s.suggestion_id} data-testid={`sugg-${s.suggestion_id}`} className="flex items-center gap-2 text-[11px]">
                              <span className="flex-1 text-white truncate">« {s.text} » — {s.pseudo}</span>
                              <span className={`text-[9px] uppercase ${s.status === 'approved' ? 'text-green-400' : s.status === 'removed' ? 'text-red-400' : 'text-amber-300'}`}>{s.status}</span>
                              {s.status === 'pending' && (
                                <>
                                  <button onClick={() => decideSuggestion(s.suggestion_id, 'approve')} data-testid={`sugg-approve-${s.suggestion_id}`} className="text-green-300 hover:bg-green-500/10 p-0.5 rounded-sm"><Check className="w-3 h-3" /></button>
                                  <button onClick={() => decideSuggestion(s.suggestion_id, 'remove')} data-testid={`sugg-remove-${s.suggestion_id}`} className="text-red-300 hover:bg-red-500/10 p-0.5 rounded-sm"><X className="w-3 h-3" /></button>
                                </>
                              )}
                              {s.status === 'approved' && (
                                <button onClick={() => decideSuggestion(s.suggestion_id, 'remove')} title="Retirer" className="text-red-300 hover:bg-red-500/10 p-0.5 rounded-sm"><X className="w-3 h-3" /></button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Voters detail */}
                      {p.voters_detail && p.voters_detail.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-white/10">
                          <div className="text-[10px] uppercase tracking-widest text-[#71717A] mb-0.5">Qui a voté</div>
                          <div className="text-[10px] text-white space-y-0.5 max-h-32 overflow-y-auto">
                            {p.voters_detail.map((v) => (
                              <div key={v.voter_key_id} className="flex justify-between gap-2">
                                <span className="truncate">{v.pseudo}</span>
                                <span className="text-[#71717A]">→ {(v.option_indices || []).map((i) => p.options[i]).filter(Boolean).join(', ')}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}
      {/* iter77 — Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/85 backdrop-blur-sm p-2 sm:p-4" onClick={() => setEditing(null)} data-testid="edit-modal">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-xl max-h-[85vh] bg-[#0A0A0A] border border-[#E4FF00]/30 rounded-sm flex flex-col overflow-hidden">
            <header className="px-3 py-3 border-b border-white/10 flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-[#E4FF00]" />
              <h2 className="text-sm font-['Chivo'] font-bold text-white">Modifier {editing.kind === 'ann' ? 'annonce' : 'sondage'}</h2>
              <button onClick={() => setEditing(null)} className="ml-auto text-[#A1A1AA] hover:text-white"><X className="w-4 h-4" /></button>
            </header>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {editing.kind === 'ann' ? (
                <>
                  <input value={editing.payload.title} onChange={(e) => setEditing((p) => ({ ...p, payload: { ...p.payload, title: e.target.value } }))} placeholder="Titre" data-testid="edit-ann-title" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-[#E4FF00]" />
                  <textarea value={editing.payload.body} onChange={(e) => setEditing((p) => ({ ...p, payload: { ...p.payload, body: e.target.value } }))} rows={4} placeholder="Détails" data-testid="edit-ann-body" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-[#E4FF00] resize-none" />
                  <AudiencePicker value={editing.payload.audience} onChange={(aud) => setEditing((p) => ({ ...p, payload: { ...p.payload, audience: aud } }))} testid="edit-ann-aud" />
                  <button onClick={editAnnSave} data-testid="edit-ann-save" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm">Enregistrer + renvoyer</button>
                </>
              ) : (
                <>
                  <input value={editing.payload.question} onChange={(e) => setEditing((p) => ({ ...p, payload: { ...p.payload, question: e.target.value } }))} placeholder="Question" data-testid="edit-poll-q" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-[#E4FF00]" />
                  {editing.payload.options.map((o, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input value={o} onChange={(e) => setEditing((p) => ({ ...p, payload: { ...p.payload, options: p.payload.options.map((x, idx) => idx === i ? e.target.value : x) } }))} className="flex-1 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white" />
                      {editing.payload.options.length > 2 && <button onClick={() => setEditing((p) => ({ ...p, payload: { ...p.payload, options: p.payload.options.filter((_, idx) => idx !== i) } }))} className="text-red-300 p-1"><X className="w-3.5 h-3.5" /></button>}
                    </div>
                  ))}
                  <button onClick={() => setEditing((p) => ({ ...p, payload: { ...p.payload, options: [...p.payload.options, ''] } }))} className="inline-flex items-center gap-1 text-xs text-[#E4FF00]"><Plus className="w-3 h-3" />Ajouter option</button>
                  <AudiencePicker value={editing.payload.audience} onChange={(aud) => setEditing((p) => ({ ...p, payload: { ...p.payload, audience: aud } }))} testid="edit-poll-aud" />
                  <div className="flex items-center gap-3 flex-wrap text-xs">
                    <label className="inline-flex items-center gap-1.5 text-[#A1A1AA]">
                      Choix max
                      <input type="number" min={0} value={editing.payload.max_selections} onChange={(e) => setEditing((p) => ({ ...p, payload: { ...p.payload, max_selections: Math.max(0, parseInt(e.target.value || '0', 10) || 0) } }))} className="w-16 bg-black/40 border border-white/10 rounded-sm px-2 py-1 text-xs text-white" />
                      <span className="text-[10px] text-[#71717A]">(0 = illimité)</span>
                    </label>
                    <label className="inline-flex items-center gap-1.5 text-[#A1A1AA] cursor-pointer">
                      <input type="checkbox" checked={!!editing.payload.allow_user_suggestions} onChange={(e) => setEditing((p) => ({ ...p, payload: { ...p.payload, allow_user_suggestions: e.target.checked } }))} className="accent-[#E4FF00]" />
                      Réponses perso
                    </label>
                  </div>
                  <button onClick={editPollSave} data-testid="edit-poll-save" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm">Enregistrer + renvoyer</button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
