import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Lightbulb, X, Send, Trash2, Bug, MoreHorizontal, ListFilter, Check, AlertTriangle, KeyRound } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KIND_META = {
  bug:    { label: 'Bug',    icon: Bug,             color: '#FF6B6B' },
  report: { label: 'Report', icon: AlertTriangle,   color: '#FF8800' },
  idea:   { label: 'Idée',   icon: Lightbulb,       color: '#E4FF00' },
  other:  { label: 'Autre',  icon: MoreHorizontal,  color: '#00D4FF' },
};

/**
 * Ideas / feedback button.
 *
 * - Non-creator devices: opens a composer panel — unlimited length, sends
 *   one idea to the creator with the sender's pseudo attached.
 * - Creator devices: opens an inbox of received ideas with mark-as-read
 *   and per-item delete actions. iter64 — adds per-kind colour badges
 *   (Bug/Idée/Autre), checkbox filters and an optional "type-grouped"
 *   sort so the creator can isolate or prioritise one category.
 */
export default function IdeasButton() {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [draftKind, setDraftKind] = useState('idea');
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [ideas, setIdeas] = useState([]);
  const isCreator = device.role === 'creator' && device.viewMode !== 'guest';
  // iter78 — Staff (admin+modo) ouvre aussi la boîte à idées en mode "Inbox".
  const isStaff = isCreator || device.staffKind === 'admin' || device.staffKind === 'modo';
  const [unread, setUnread] = useState(0);
  // iter64 — creator-side filters (persisted in localStorage so they survive reloads)
  const [filters, setFilters] = useState(() => {
    try {
      const raw = localStorage.getItem('codeforge_ideas_filters');
      if (raw) return { bug: true, idea: true, report: true, other: true, ...JSON.parse(raw) };
    } catch (_) { /* ignore */ }
    return { bug: true, idea: true, report: true, other: true };
  });
  const [sortByKind, setSortByKind] = useState(() => {
    try { return localStorage.getItem('codeforge_ideas_sort_kind') === '1'; } catch (_) { return false; }
  });
  const [sortByDate, setSortByDate] = useState(() => {
    try { return localStorage.getItem('codeforge_ideas_sort_date') !== '0'; } catch (_) { return true; }
  });
  useEffect(() => {
    try { localStorage.setItem('codeforge_ideas_filters', JSON.stringify(filters)); } catch (_) { /* ignore */ }
  }, [filters]);
  useEffect(() => {
    try { localStorage.setItem('codeforge_ideas_sort_kind', sortByKind ? '1' : '0'); } catch (_) { /* ignore */ }
  }, [sortByKind]);
  useEffect(() => {
    try { localStorage.setItem('codeforge_ideas_sort_date', sortByDate ? '1' : '0'); } catch (_) { /* ignore */ }
  }, [sortByDate]);

  const visibleIdeas = useMemo(() => {
    const filtered = ideas.filter((x) => filters[(x.kind || 'idea')] !== false);
    if (sortByKind) {
      // iter78 — bugs > reports > ideas > others (preserve ts order within each group)
      const order = { bug: 0, report: 1, idea: 2, other: 3 };
      return [...filtered].sort((a, b) => (order[a.kind || 'idea'] ?? 4) - (order[b.kind || 'idea'] ?? 4));
    }
    if (sortByDate) {
      return [...filtered].sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
    }
    return filtered;
  }, [ideas, filters, sortByKind, sortByDate]);

  const allOn = filters.bug && filters.idea && filters.report && filters.other;

  useEffect(() => {
    if (!isStaff || !device.keyId) return undefined;
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
      const body = await withCreatorProof(API, axios, { content, kind: draftKind });
      await axios.post(`${API}/ideas/send`, body);
      setDraft('');
      setDraftKind('idea');
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
    } catch (_) { /* ignore */ }
  };

  const deleteIdea = async (idea_id) => {
    try {
      const body = await withCreatorProof(API, axios, { idea_id });
      await axios.post(`${API}/ideas/delete`, body);
      setIdeas((ls) => ls.filter((x) => x.idea_id !== idea_id));
    } catch (_) { /* ignore */ }
  };

  const setIdeaState = async (idea_id, state) => {
    try {
      const body = await withCreatorProof(API, axios, { idea_id, state });
      await axios.post(`${API}/ideas/set-state`, body);
      // Optimistic update
      setIdeas((ls) => ls.map((x) => x.idea_id === idea_id ? { ...x, state: state === 'reset' ? null : state } : x));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  // iter80 — Clear modal (créa-only). scope: 'all'|'resolved'|'unresolved'.
  // Demande mot de passe uniquement si le scope inclut des non-traités.
  const [clearStep, setClearStep] = useState(null);  // {scope, requiresPwd, error}
  const [clearPwd, setClearPwd] = useState('');

  const unresolvedCount = useMemo(() => ideas.filter((i) => i.state !== 'validated').length, [ideas]);
  const resolvedCount = ideas.length - unresolvedCount;

  const doClear = async (scope) => {
    try {
      const body = await withCreatorProof(API, axios, { scope });
      await axios.post(`${API}/ideas/clear`, body);
      toast.success('Retours vidés');
      setIdeas([]);
      setClearStep(null);
      setClearPwd('');
    } catch (e) {
      const code = e?.response?.status;
      if (code === 428) {
        // Need password.
        setClearStep((s) => ({ ...(s || { scope }), requiresPwd: true, error: null }));
      } else if (code === 403 && /Mot de passe incorrect/i.test(e?.response?.data?.detail || '')) {
        setClearStep((s) => ({ ...(s || { scope }), requiresPwd: true, error: 'Mot de passe incorrect. Veuillez réessayer' }));
      } else {
        toast.error(e?.response?.data?.detail || 'Erreur');
      }
    }
  };

  const doClearWithPwd = async () => {
    if (!clearStep) return;
    try {
      const body = await withCreatorProof(API, axios, { scope: clearStep.scope, password: clearPwd });
      await axios.post(`${API}/ideas/clear`, body);
      toast.success('Retours vidés');
      setIdeas([]);
      setClearStep(null);
      setClearPwd('');
    } catch (e) {
      const code = e?.response?.status;
      if (code === 403 && /Mot de passe incorrect/i.test(e?.response?.data?.detail || '')) {
        setClearStep((s) => ({ ...s, error: 'Mot de passe incorrect. Veuillez réessayer' }));
      } else {
        toast.error(e?.response?.data?.detail || 'Erreur');
      }
    }
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
        onClick={() => { setOpen(true); if (isStaff) markAllRead(); }}
        data-testid="ideas-btn"
        title={t('ideas_title')}
        className="relative inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-amber-300 hover:border-amber-400/40 transition-colors"
      >
        <Lightbulb className="w-4 h-4" />
        {isStaff && unread > 0 && (
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

            {!isStaff && (
              <div className="p-3 space-y-3 flex flex-col flex-1 min-h-0">
                {/* iter78 — kind picker */}
                <div className="flex items-center gap-1.5 flex-wrap text-[11px]">
                  <span className="text-[#A1A1AA] mr-1">Type :</span>
                  {(['bug', 'report', 'idea', 'other']).map((k) => {
                    const meta = KIND_META[k];
                    const Icon = meta.icon;
                    const on = draftKind === k;
                    return (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setDraftKind(k)}
                        data-testid={`ideas-kind-${k}`}
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-sm border transition ${on ? 'border-white/30 bg-white/[0.05] text-white' : 'border-white/10 text-[#71717A] hover:text-white'}`}
                        style={on ? { color: meta.color, borderColor: `${meta.color}66`, background: `${meta.color}12` } : undefined}
                      >
                        <Icon className="w-3 h-3" />
                        {meta.label}
                      </button>
                    );
                  })}
                </div>
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

            {isStaff && (
              <>
                {/* iter64 — filter bar */}
                <div className="px-3 py-2 border-b border-white/10 flex items-center gap-2 flex-wrap text-[11px]">
                  <ListFilter className="w-3 h-3 text-[#A1A1AA] flex-shrink-0" />
                  {(['bug', 'report', 'idea', 'other']).map((k) => {
                    const meta = KIND_META[k];
                    const Icon = meta.icon;
                    const on = filters[k];
                    return (
                      <label
                        key={k}
                        data-testid={`ideas-filter-${k}`}
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-sm border cursor-pointer transition ${
                          on ? 'border-white/30 bg-white/[0.05] text-white' : 'border-white/10 text-[#71717A]'
                        }`}
                        style={on ? { color: meta.color, borderColor: `${meta.color}55` } : undefined}
                      >
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={() => setFilters((f) => ({ ...f, [k]: !f[k] }))}
                          className="accent-current w-3 h-3"
                        />
                        <Icon className="w-3 h-3" />
                        {meta.label}
                      </label>
                    );
                  })}
                  <div className="ml-auto flex items-center gap-2">
                    {/* iter80 — Tri résolus / non-traités (créa-only — staff voit le contenu mais ne peut pas clear) */}
                    {isCreator && ideas.length > 0 && (
                      <div className="flex items-center gap-1">
                        <button onClick={() => setClearStep({ scope: 'resolved', requiresPwd: false })} data-testid="ideas-clear-resolved" title="Vider les retours traités" disabled={resolvedCount === 0} className="text-[10px] px-1.5 py-0.5 rounded-sm border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-30">Traités ({resolvedCount})</button>
                        <button onClick={() => setClearStep({ scope: 'unresolved', requiresPwd: unresolvedCount > 0 })} data-testid="ideas-clear-unresolved" title="Vider les retours non-traités (mot de passe requis)" disabled={unresolvedCount === 0} className="text-[10px] px-1.5 py-0.5 rounded-sm border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 disabled:opacity-30">Non-traités ({unresolvedCount})</button>
                        <button onClick={() => setClearStep({ scope: 'all', requiresPwd: unresolvedCount > 0 })} data-testid="ideas-clear-all" title="Vider tous les retours" className="text-[10px] px-1.5 py-0.5 rounded-sm border border-red-500/40 text-red-300 hover:bg-red-500/10">Tout</button>
                      </div>
                    )}
                    <label
                      data-testid="ideas-sort-by-kind"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-[#A1A1AA] cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={sortByKind}
                        onChange={() => { setSortByKind(true); setSortByDate(false); }}
                        className="accent-amber-300 w-3 h-3"
                      />
                      Trier par type
                    </label>
                    <label
                      data-testid="ideas-sort-by-date"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-[#A1A1AA] cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={sortByDate}
                        onChange={() => { setSortByDate(true); setSortByKind(false); }}
                        className="accent-amber-300 w-3 h-3"
                      />
                      Trier par date
                    </label>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[200px]">
                  {visibleIdeas.length === 0 && (
                    <div className="text-xs text-[#A1A1AA] py-4 text-center">
                      {ideas.length === 0 ? t('ideas_empty_inbox') : 'Aucun message ne correspond aux filtres.'}
                    </div>
                  )}
                  {visibleIdeas.map((idea) => {
                    const meta = KIND_META[idea.kind] || KIND_META.idea;
                    const KIcon = meta.icon;
                    return (
                      <div key={idea.idea_id} data-testid={`ideas-row-${idea.idea_id}`} className="bg-black/30 border border-white/10 rounded-sm p-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span
                              data-testid={`ideas-kind-${idea.idea_id}`}
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 border rounded-sm text-[10px] font-bold uppercase tracking-wider flex-shrink-0"
                              style={{ color: meta.color, borderColor: `${meta.color}55`, background: `${meta.color}10` }}
                            >
                              <KIcon className="w-3 h-3" />
                              {meta.label}
                            </span>
                            <div className="text-[11px] text-amber-300 truncate">
                              {idea.sender_label || idea.sender_key_id?.slice(0, 14)}
                              <span className="text-[#71717A] ml-2">{new Date(idea.ts).toLocaleString()}</span>
                            </div>
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
                        <div className="text-sm text-white whitespace-pre-wrap break-words">{idea.content || <em className="text-[#71717A]">(message vide)</em>}</div>
                        {isStaff && (
                          <div className="flex items-center gap-1 mt-1.5">
                            <button onClick={() => setIdeaState(idea.idea_id, 'validated')} data-testid={`idea-validate-${idea.idea_id}`} title="Validé" className={`text-[11px] px-1.5 py-0.5 rounded-sm border ${idea.state === 'validated' ? 'border-green-500 bg-green-500/15 text-green-300' : 'border-green-500/40 text-green-300 hover:bg-green-500/10'}`}><Check className="w-3 h-3 inline" /></button>
                            <button onClick={() => setIdeaState(idea.idea_id, 'refused')} data-testid={`idea-refuse-${idea.idea_id}`} title="Refusé" className={`text-[11px] px-1.5 py-0.5 rounded-sm border ${idea.state === 'refused' ? 'border-red-500 bg-red-500/15 text-red-300' : 'border-red-500/40 text-red-300 hover:bg-red-500/10'}`}><X className="w-3 h-3 inline" /></button>
                            <button onClick={() => setIdeaState(idea.idea_id, 'orange')} data-testid={`idea-orange-${idea.idea_id}`} title="Seule la créa peut" className={`text-[11px] px-1.5 py-0.5 rounded-sm border ${idea.state === 'orange' ? 'border-orange-500 bg-orange-500/15 text-orange-300' : 'border-orange-500/40 text-orange-300 hover:bg-orange-500/10'}`}><KeyRound className="w-3 h-3 inline" /></button>
                            {idea.state && idea.state !== null && (
                              <button onClick={() => setIdeaState(idea.idea_id, 'reset')} title="Réinitialiser" className="text-[10px] text-[#A1A1AA] hover:text-white ml-1"><AlertTriangle className="w-3 h-3 inline" /></button>
                            )}
                            {idea.state_actor && idea.state && (
                              <span className="text-[9px] text-[#71717A] uppercase tracking-widest ml-auto">par {idea.state_actor}</span>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      )}
      {/* iter80 — Clear confirmation modal */}
      {clearStep && (
        <div className="fixed inset-0 z-[140] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" data-testid="ideas-clear-modal" onClick={() => { setClearStep(null); setClearPwd(''); }}>
          <div onClick={(e) => e.stopPropagation()} className="max-w-md w-full bg-[#0A0A0A] border border-red-500/40 rounded-md p-5 space-y-4">
            <h3 className="text-lg font-['Chivo'] font-bold text-white">
              {clearStep.scope === 'resolved' && 'Vider les retours traités ?'}
              {clearStep.scope === 'unresolved' && 'Vider les retours non-traités ?'}
              {clearStep.scope === 'all' && 'Vider TOUS les retours ?'}
            </h3>
            <p className="text-sm text-[#A1A1AA] leading-relaxed">
              {clearStep.scope === 'all'
                ? 'Cette case supprimera les retours actuellement non-traités ou en cours. Êtes-vous sûre de vouloir faire ceci ?'
                : clearStep.scope === 'unresolved'
                  ? 'Tu supprimes les retours en attente ou refusés non traités par le staff. Cette action est irréversible.'
                  : 'Tu supprimes les retours marqués validés. Pas de mot de passe requis.'}
            </p>
            {clearStep.requiresPwd ? (
              <>
                <input
                  type="password"
                  value={clearPwd}
                  onChange={(e) => setClearPwd(e.target.value)}
                  placeholder="Mot de passe créatrice"
                  data-testid="ideas-clear-pwd"
                  className="w-full bg-black/40 border border-white/15 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-red-400"
                  autoFocus
                />
                {clearStep.error && <p className="text-xs text-red-300" data-testid="ideas-clear-err">{clearStep.error}</p>}
                <div className="flex items-center gap-2">
                  <button onClick={() => { setClearStep(null); setClearPwd(''); }} data-testid="ideas-clear-cancel" className="flex-1 px-3 py-2 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm text-sm">Non</button>
                  <button onClick={doClearWithPwd} disabled={!clearPwd} data-testid="ideas-clear-confirm-pwd" className="flex-1 px-3 py-2 bg-red-500 hover:bg-red-600 text-white font-bold rounded-sm text-sm disabled:opacity-40">Oui — confirmer</button>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <button onClick={() => setClearStep(null)} data-testid="ideas-clear-no" className="flex-1 px-3 py-2 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm text-sm">Non</button>
                <button onClick={() => doClear(clearStep.scope)} data-testid="ideas-clear-yes" className="flex-1 px-3 py-2 bg-red-500 hover:bg-red-600 text-white font-bold rounded-sm text-sm">Oui</button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
