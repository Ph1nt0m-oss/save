import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Megaphone, X, Plus, Trash2, BarChart3 } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * 📣 Announce + Poll launcher (creator-only).
 * - Announce: title + body, audience = all | approved
 * - Poll: question + options, audience = all | approved
 *
 * Visitors see the banner via <AnnouncementsBanner /> elsewhere.
 */
export default function AnnounceButton() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const isCreator = device.role === 'creator' && device.viewMode !== 'guest';
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('announce'); // 'announce' | 'poll' | 'manage'

  // Announce form
  const [aTitle, setATitle] = useState('');
  const [aBody, setABody] = useState('');
  const [aAud, setAAud] = useState('all');
  // Poll form
  const [pQ, setPQ] = useState('');
  const [pOpts, setPOpts] = useState(['', '']);
  const [pAud, setPAud] = useState('all');
  const [pMaxSel, setPMaxSel] = useState(1); // iter76 — min 1
  // Scheduled disconnect form
  const [skMinutes, setSkMinutes] = useState(5);
  const [skNote, setSkNote] = useState('');
  const [scheduledKicks, setScheduledKicks] = useState([]);

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
      const body = await withCreatorProof(API, axios, { title: aTitle.trim(), body: aBody.trim(), audience: aAud });
      await axios.post(`${API}/announcements/create`, body);
      toast.success(t('ann_created'));
      setATitle(''); setABody(''); setOpen(false);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const publishPoll = async () => {
    const opts = pOpts.map((o) => o.trim()).filter(Boolean);
    if (!pQ.trim() || opts.length < 2) return toast.error('?');
    const maxSel = Math.max(1, Math.min(parseInt(pMaxSel || 1, 10), opts.length));
    try {
      const body = await withCreatorProof(API, axios, { question: pQ.trim(), options: opts, audience: pAud, max_selections: maxSel });
      await axios.post(`${API}/polls/create`, body);
      toast.success(t('ann_created'));
      setPQ(''); setPOpts(['', '']); setPMaxSel(1); setOpen(false);
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
      const body = await withCreatorProof(API, axios, { minutes: parseInt(skMinutes || 0, 10), note: skNote.trim() });
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
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#A1A1AA]">{t('ann_audience')}</span>
                    {['all', 'approved'].map((v) => (
                      <button key={v} onClick={() => setAAud(v)} data-testid={`ann-aud-${v}`} className={`text-[11px] px-2 py-1 rounded-sm border ${aAud === v ? 'border-[#E4FF00]/40 text-[#E4FF00] bg-[#E4FF00]/10' : 'border-white/10 text-[#A1A1AA]'}`}>{t(v === 'all' ? 'ann_aud_all' : 'ann_aud_approved')}</button>
                    ))}
                  </div>
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
                  {pOpts.length < 10 && (
                    <button onClick={() => setPOpts((arr) => [...arr, ''])} data-testid="poll-add-opt" className="inline-flex items-center gap-1 text-xs text-[#E4FF00] hover:text-white transition"><Plus className="w-3 h-3" />{t('poll_add_option')}</button>
                  )}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-[#A1A1AA]">{t('ann_audience')}</span>
                    {['all', 'approved'].map((v) => (
                      <button key={v} onClick={() => setPAud(v)} className={`text-[11px] px-2 py-1 rounded-sm border ${pAud === v ? 'border-[#E4FF00]/40 text-[#E4FF00] bg-[#E4FF00]/10' : 'border-white/10 text-[#A1A1AA]'}`}>{t(v === 'all' ? 'ann_aud_all' : 'ann_aud_approved')}</button>
                    ))}
                    <span className="text-xs text-[#A1A1AA] ml-2">Choix max/voter</span>
                    <input
                      type="number"
                      min={1}
                      max={Math.max(2, pOpts.filter((o) => o.trim()).length || 2)}
                      value={pMaxSel}
                      onChange={(e) => setPMaxSel(Math.max(1, parseInt(e.target.value || '1', 10) || 1))}
                      data-testid="poll-max-sel"
                      className="w-16 bg-black/40 border border-white/10 rounded-sm px-2 py-1 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
                    />
                  </div>
                  <button onClick={publishPoll} data-testid="poll-publish" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm hover:bg-white transition">{t('ann_create_btn')}</button>
                </>
              )}

              {tab === 'kick' && (
                <>
                  <div className="text-xs text-[#A1A1AA]">Programme la déconnexion de tous les utilisateurs (toi exclue) dans X minutes. Optionnel : ajouter une annonce publiée tout de suite.</div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-white">Dans</label>
                    <input type="number" min={0} max={1440} value={skMinutes} onChange={(e) => setSkMinutes(Math.max(0, parseInt(e.target.value || '0', 10) || 0))} data-testid="kick-minutes" className="w-20 bg-black/40 border border-white/10 rounded-sm px-2 py-1 text-sm text-white focus:outline-none focus:border-[#E4FF00]" />
                    <label className="text-xs text-white">min</label>
                  </div>
                  <input value={skNote} onChange={(e) => setSkNote(e.target.value)} placeholder="Message d'annonce (facultatif)" data-testid="kick-note" className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white placeholder-[#71717A] focus:outline-none focus:border-[#E4FF00]" />
                  <button onClick={scheduleKick} data-testid="kick-schedule" className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm hover:bg-white transition">Programmer</button>
                  {scheduledKicks.length > 0 && (
                    <div className="mt-2 space-y-1">
                      <div className="text-[10px] uppercase tracking-widest text-[#71717A]">En cours</div>
                      {scheduledKicks.map((k) => (
                        <div key={k.kick_id} data-testid={`kick-row-${k.kick_id}`} className="flex items-center justify-between bg-black/30 border border-white/10 rounded-sm p-2 text-xs">
                          <span className="text-white">Dans {k.minutes} min — à {new Date(k.execute_at).toLocaleTimeString()}</span>
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
                  {items.announcements.map((a) => (
                    <div key={a.announce_id} className="bg-black/30 border border-white/10 rounded-sm p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-['Chivo'] font-bold text-white truncate">{a.title}</div>
                        <button onClick={() => deleteAnn(a.announce_id)} className="text-[#A1A1AA] hover:text-red-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                      {a.body && <div className="text-xs text-[#A1A1AA] mt-1 whitespace-pre-wrap break-words">{a.body}</div>}
                      <div className="text-[9px] text-[#71717A] mt-1 uppercase tracking-widest">{a.audience} · {new Date(a.ts).toLocaleString()}</div>
                    </div>
                  ))}
                  {items.polls.map((p) => (
                    <div key={p.poll_id} className="bg-black/30 border border-white/10 rounded-sm p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-['Chivo'] font-bold text-white truncate inline-flex items-center gap-2"><BarChart3 className="w-3.5 h-3.5 text-[#E4FF00]" />{p.question}</div>
                        <button onClick={() => deletePoll(p.poll_id)} className="text-[#A1A1AA] hover:text-red-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
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
                      <div className="text-[9px] text-[#71717A] mt-1 uppercase tracking-widest">{p.audience} · max {p.max_selections || 1} choix · {p.voters || 0} vote{(p.voters || 0) > 1 ? 's' : ''} · {new Date(p.ts).toLocaleString()}</div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
