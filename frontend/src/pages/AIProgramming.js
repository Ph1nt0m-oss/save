/**
 * iter143 — Page « Programmation des IA »
 *
 * Espace de développement interne pour la Créa : édite le profil
 * comportemental (writing_style, behavior, domains, limits, capabilities,
 * allowed_tools, specializations, custom_system_prompt, response_format,
 * reasoning_mode, notes) de chaque IA/bot déclaré dans agents/registry.py.
 *
 * Versionné en MongoDB via /api/agents/profile/{get,save,versions,revert}.
 * Créa only. Aucune donnée sensible n'est stockée ici — uniquement des
 * instructions comportementales.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowLeft, Save, History, RotateCcw, Bot, Sparkles, Wrench, Menu, X as CloseIcon } from 'lucide-react';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FIELDS = [
  { key: 'writing_style',        label: 'Style d\u2019écriture',      textarea: true },
  { key: 'behavior',             label: 'Comportement',                textarea: true },
  { key: 'domains',              label: 'Domaines',                    list: true },
  { key: 'limits',               label: 'Limites',                     list: true },
  { key: 'capabilities',         label: 'Capacités',                   list: true },
  { key: 'allowed_tools',        label: 'Outils autorisés',            list: true },
  { key: 'specializations',      label: 'Spécialisations',             list: true },
  { key: 'custom_system_prompt', label: 'Prompt système personnalisé', textarea: true },
  { key: 'response_format',      label: 'Format de réponse',           textarea: true },
  { key: 'reasoning_mode',       label: 'Mode de raisonnement',        textarea: true },
  { key: 'notes',                label: 'Notes (Créa)',                textarea: true },
];

function ListEditor({ value, onChange }) {
  const arr = Array.isArray(value) ? value : [];
  const [draft, setDraft] = useState('');
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-1.5">
        {arr.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1 bg-white/[0.06] border border-white/15 rounded-sm text-white/90"
          >
            {v}
            <button
              type="button"
              onClick={() => onChange(arr.filter((_, j) => j !== i))}
              className="text-white/40 hover:text-red-300"
              title="Retirer"
            >×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && draft.trim()) {
              e.preventDefault();
              onChange([...arr, draft.trim()]);
              setDraft('');
            }
          }}
          placeholder="Ajouter… (Entrée)"
          className="flex-1 bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white placeholder-white/30 focus:border-[#E4FF00] focus:outline-none"
        />
        <button
          type="button"
          onClick={() => {
            if (draft.trim()) { onChange([...arr, draft.trim()]); setDraft(''); }
          }}
          className="text-xs px-2 py-1.5 border border-white/15 hover:border-[#E4FF00]/60 text-white/80 rounded-sm"
        >Ajouter</button>
      </div>
    </div>
  );
}

export default function AIProgramming() {
  const navigate = useNavigate();
  const device = useDeviceIdentity();
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState({});
  const [versions, setVersions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [savingNote, setSavingNote] = useState('');
  const [busy, setBusy] = useState(false);
  // iter144 — Sidebar collapsable pour responsive (mobile + demi-écran).
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const allowed = device.role === 'creator' && (!device.viewMode || device.viewMode === 'creator');

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/agents/profile/list-all`, body);
        if (cancelled) return;
        setItems(r.data?.items || []);
        if (!selected && (r.data?.items || []).length) {
          setSelected(r.data.items[0].agent_id);
          setProfile(r.data.items[0].profile || {});
        }
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Impossible de charger les IA');
      }
    })();
    return () => { cancelled = true; };
  }, [allowed]); // eslint-disable-line

  useEffect(() => {
    if (!allowed || !selected) return;
    const found = items.find((it) => it.agent_id === selected);
    if (found) setProfile(found.profile || {});
  }, [selected, items, allowed]);

  const loadVersions = async () => {
    setShowHistory(true);
    try {
      const body = await withCreatorProof(API, axios, { agent_id: selected });
      const r = await axios.post(`${API}/agents/profile/versions`, body);
      setVersions(r.data?.history || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impossible de charger l\u2019historique');
    }
  };

  const save = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {
        agent_id: selected,
        profile,
        note: savingNote,
      });
      await axios.post(`${API}/agents/profile/save`, body);
      // Refresh items with new version_id / updated_at.
      const rBody = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/agents/profile/list-all`, rBody);
      setItems(r.data?.items || []);
      setSavingNote('');
      toast.success('Profil sauvegardé (nouvelle version créée)');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Enregistrement impossible');
    } finally {
      setBusy(false);
    }
  };

  const revert = async (version_id) => {
    if (!window.confirm('Restaurer cette version ?')) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { agent_id: selected, version_id });
      await axios.post(`${API}/agents/profile/revert`, body);
      const rBody = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/agents/profile/list-all`, rBody);
      setItems(r.data?.items || []);
      setShowHistory(false);
      toast.success('Version restaurée');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Revert impossible');
    } finally {
      setBusy(false);
    }
  };

  const currentCard = useMemo(() => {
    const it = items.find((i) => i.agent_id === selected);
    return it?.card || {};
  }, [items, selected]);

  if (!allowed) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center text-[#A1A1AA] text-sm p-8">
        Accès réservé à la Créa.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col">
      <header className="border-b border-white/10 px-3 py-2 sm:px-4 sm:py-3 flex items-center gap-2 sm:gap-3 flex-wrap">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          data-testid="ai-prog-sidebar-toggle"
          className="lg:hidden text-[#A1A1AA] hover:text-white p-1"
          aria-label="Ouvrir la liste des IA"
        >
          {sidebarOpen ? <CloseIcon className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
        </button>
        <button onClick={() => navigate(-1)} className="text-[#A1A1AA] hover:text-white" data-testid="ai-prog-back">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <Bot className="w-4 h-4 text-[#E4FF00]" />
        <h1 className="text-xs sm:text-sm font-['Chivo'] font-bold truncate flex-1">Programmation des IA</h1>
        <span className="text-[10px] sm:text-[11px] text-[#A1A1AA] whitespace-nowrap">
          {items.length} agents
        </span>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        {/* Sidebar : slide-in sur mobile via .translate, fixe sur desktop */}
        <aside
          className={`absolute lg:static inset-y-0 left-0 w-64 sm:w-72 border-r border-white/10 bg-[#050505] overflow-y-auto z-30 transition-transform duration-200 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          }`}
          data-testid="ai-prog-sidebar"
          tabIndex={0}
        >
          {items.map((it) => (
            <button
              key={it.agent_id}
              type="button"
              onClick={() => { setSelected(it.agent_id); setSidebarOpen(false); }}
              data-testid={`ai-prog-select-${it.agent_id}`}
              className={`w-full text-left px-3 py-2 border-b border-white/5 hover:bg-white/[0.04] transition ${
                selected === it.agent_id ? 'bg-[#E4FF00]/10 border-l-2 border-l-[#E4FF00]' : ''
              }`}
            >
              <div className="text-xs font-bold text-white">{it.card?.name || it.agent_id}</div>
              <div className="text-[10px] text-[#A1A1AA] truncate">{it.card?.objectif}</div>
              {it.version_id && (
                <div className="text-[9px] text-[#71717A] mt-0.5 font-mono">{it.version_id}</div>
              )}
            </button>
          ))}
        </aside>

        {/* Overlay clic-out pour mobile */}
        {sidebarOpen && (
          <div
            className="absolute inset-0 bg-black/60 z-20 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Editor */}
        <main
          className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3 min-w-0"
          data-testid="ai-prog-editor"
          tabIndex={0}
        >
          {selected && (
            <>
              <div className="border border-white/10 rounded-sm p-3 bg-white/[0.02]">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-[#E4FF00]" />
                  <h2 className="text-sm font-bold">{currentCard?.name || selected}</h2>
                  <span className="text-[10px] text-[#71717A] ml-auto">{selected}</span>
                </div>
                <div className="text-xs text-[#A1A1AA] space-y-1">
                  <div><span className="text-[#71717A]">Objectif :</span> {currentCard?.objectif}</div>
                  <div><span className="text-[#71717A]">Module :</span> <code className="text-[#A1A1AA]">{currentCard?.module}</code></div>
                  <div><span className="text-[#71717A]">Raisonnement natif :</span> {currentCard?.raisonnement}</div>
                </div>
              </div>

              {FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="block text-[11px] uppercase tracking-widest text-[#A1A1AA] mb-1">
                    {f.label}
                  </label>
                  {f.list ? (
                    <ListEditor
                      value={profile[f.key]}
                      onChange={(v) => setProfile((p) => ({ ...p, [f.key]: v }))}
                    />
                  ) : (
                    <textarea
                      value={profile[f.key] || ''}
                      onChange={(e) => setProfile((p) => ({ ...p, [f.key]: e.target.value }))}
                      data-testid={`ai-prog-field-${f.key}`}
                      rows={f.key === 'custom_system_prompt' ? 6 : 3}
                      className="w-full bg-black/40 border border-white/15 rounded-sm px-2 py-2 text-sm text-white placeholder-white/30 focus:border-[#E4FF00] focus:outline-none font-mono text-xs"
                    />
                  )}
                </div>
              ))}

              <div className="border-t border-white/10 pt-3 flex items-center gap-2 flex-wrap">
                <input
                  type="text"
                  value={savingNote}
                  onChange={(e) => setSavingNote(e.target.value)}
                  placeholder="Note (facultative) — décrit ce changement…"
                  data-testid="ai-prog-note"
                  className="flex-1 min-w-[240px] bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white placeholder-white/30 focus:border-[#E4FF00] focus:outline-none"
                />
                <button
                  type="button"
                  onClick={save}
                  disabled={busy}
                  data-testid="ai-prog-save"
                  className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90 disabled:opacity-40"
                >
                  <Save className="w-3.5 h-3.5" />
                  Nouvelle version
                </button>
                <button
                  type="button"
                  onClick={loadVersions}
                  data-testid="ai-prog-history"
                  className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 border border-white/15 hover:border-[#E4FF00]/60 rounded-sm"
                >
                  <History className="w-3.5 h-3.5" />
                  Historique
                </button>
              </div>

              {showHistory && (
                <div className="border border-white/10 rounded-sm p-3 bg-white/[0.02]" data-testid="ai-prog-history-panel">
                  <div className="text-[11px] uppercase tracking-widest text-[#A1A1AA] mb-2 flex items-center gap-2">
                    <Wrench className="w-3.5 h-3.5" /> Versions archivées
                    <button onClick={() => setShowHistory(false)} className="ml-auto text-[10px] text-white/50 hover:text-white">masquer</button>
                  </div>
                  {versions.length === 0 && <div className="text-xs text-[#71717A]">Aucune version antérieure.</div>}
                  {versions.map((v) => (
                    <div key={v.version_id} className="flex items-center gap-2 py-1.5 border-b border-white/5 last:border-b-0">
                      <span className="text-[10px] font-mono text-white/70">{v.version_id}</span>
                      <span className="text-[10px] text-[#71717A]">{new Date(v.archived_at).toLocaleString()}</span>
                      {v.note && <span className="text-[10px] text-[#A1A1AA] truncate max-w-[220px]">{v.note}</span>}
                      <button
                        onClick={() => revert(v.version_id)}
                        data-testid={`ai-prog-revert-${v.version_id}`}
                        className="ml-auto inline-flex items-center gap-1 text-[10px] px-2 py-1 border border-white/15 hover:border-amber-300/60 hover:text-amber-300 rounded-sm"
                      >
                        <RotateCcw className="w-3 h-3" /> restaurer
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
