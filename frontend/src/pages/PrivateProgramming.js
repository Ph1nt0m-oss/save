import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Lock, FileCode, FolderTree, Search as SearchIcon, Brain, Cpu, Play, Loader2, Save } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import useViewSpec from '../hooks/useViewSpec';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter86 — Pages privées créa réellement implémentées :
 *   - /private-programming : éditeur de code source (lecture seule).
 *     Explore l'arbre /app, ouvre un fichier, affiche son contenu, grep
 *     dans la base de code.
 *   - /ai-programming : config orchestrateur. Voir les prompts système des
 *     4 agents (planner/executor/critic/arbiter), lancer un test-loop, voir
 *     l'historique d'exécution.
 *
 * Visibles uniquement pour le device créatrice (role==='creator' &&
 * viewMode==='creator'). Tout autre cas → écran "Accès refusé".
 */
export default function PrivateProgramming() {
  const device = useDeviceIdentity();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useLanguage();
  // iter101 — Use spec hook : canSeeProgramming est strictement lié au role physique créa
  const { canSeeProgramming } = useViewSpec();
  const isAI = location.pathname.includes('ai-programming');
  const title = isAI ? (t('prog_ai_title') || 'Programmation des IA') : (t('prog_site_title') || 'Programmation du site');

  // iter89 — Visible UNIQUEMENT pour les DEVICES créa ET quand la créatrice
  // N'EST PAS en simulation (anti-copie par-dessus l'épaule).
  // iter107 — Bug fix sécurité : modos/users peuvent voir L'ONGLET mais
  // PAS LE CODE. Même la créatrice en vue simulée (modo/admin/user/guest)
  // ne doit pas voir le code pour éviter de l'exposer accidentellement.
  // → allowed = canSeeProgramming (créa physique) ET pas en simulation.
  const isInSimulation = device.viewMode && device.viewMode !== 'creator';
  const allowed = canSeeProgramming && !isInSimulation;

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6" data-testid="private-programming-page">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/dashboard')} className="text-[#A1A1AA] hover:text-white text-sm inline-flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" /> {t('back')}
          </button>
          <h1 className="text-2xl font-['Chivo'] font-black">{title}</h1>
        </div>
        {!allowed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-sm p-8 text-center max-w-md mx-auto" data-testid="private-access-denied">
            <Lock className="w-14 h-14 mx-auto text-red-300 mb-4" />
            <h2 className="text-lg font-bold text-red-200 mb-2">{t('prog_access_denied')}</h2>
            <p className="text-sm text-red-100/90 leading-relaxed">
              {t('prog_access_body')}
            </p>
            <p className="text-xs text-amber-200/90 mt-3">
              {t('prog_access_hint')}
            </p>
          </div>
        ) : (
          isAI ? <AIProgrammingPanel /> : <SiteProgrammingPanel />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// SITE PROGRAMMING : code browser + grep + viewer (read-only)
// =============================================================================

function SiteProgrammingPanel() {
  const { t } = useLanguage();
  const [pattern, setPattern] = useState('');
  const [grepResults, setGrepResults] = useState(null);
  const [filePath, setFilePath] = useState('backend/server.py');
  const [fileContent, setFileContent] = useState(null);
  const [editBuffer, setEditBuffer] = useState('');
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadFile = async (rel) => {
    if (!rel) return;
    if (dirty && !window.confirm('Modifications non sauvegardées. Charger un autre fichier ?')) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { path: rel });
      const r = await axios.post(`${API}/private/code/read-file`, body);
      setFilePath(rel);
      setFileContent(r.data);
      setEditBuffer(r.data?.content || '');
      setDirty(false);
    } catch (e) { toast.error(e?.response?.data?.detail || t('prog_read_failed')); }
    finally { setBusy(false); }
  };

  const saveFile = async () => {
    if (!filePath || !dirty) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { path: filePath, content: editBuffer });
      const r = await axios.post(`${API}/private/code/write-file`, body);
      toast.success(`Sauvegardé (${r.data.bytes} octets, backup: ${r.data.backup || 'aucun'})`);
      setDirty(false);
      // Recharge pour avoir l'état canonique
      setFileContent({ ...fileContent, content: editBuffer, bytes: r.data.bytes });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec écriture');
    } finally { setBusy(false); }
  };

  const doGrep = async () => {
    if (!pattern.trim()) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { pattern: pattern.trim() });
      const r = await axios.post(`${API}/private/code/grep`, body);
      setGrepResults(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || t('prog_grep_failed')); }
    finally { setBusy(false); }
  };

  useEffect(() => { loadFile('backend/server.py'); /* eslint-disable-line */ }, []);

  return (
    <div className="grid grid-cols-12 gap-4 h-[calc(100vh-180px)]">
      <aside className="col-span-12 lg:col-span-4 bg-[#0A0A0A] border border-white/10 rounded-sm flex flex-col overflow-hidden">
        <header className="p-3 border-b border-white/10 flex items-center gap-2">
          <SearchIcon className="w-4 h-4 text-[#E4FF00]" />
          <span className="text-sm font-bold">{t('prog_search_in_code')}</span>
        </header>
        <div className="p-3 space-y-2">
          <div className="flex gap-2">
            <input
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') doGrep(); }}
              placeholder={t('prog_search_placeholder')}
              data-testid="private-grep-input"
              className="flex-1 px-2 py-1.5 bg-[#0F0F13] border border-white/15 rounded-sm text-xs font-mono focus:outline-none focus:border-[#E4FF00]"
            />
            <button onClick={doGrep} disabled={busy || !pattern.trim()} data-testid="private-grep-btn" className="px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-bold text-xs rounded-sm disabled:opacity-40">
              {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : t('prog_grep_btn')}
            </button>
          </div>
          {grepResults && (
            <div className="text-[10px] text-[#A1A1AA] space-y-1 max-h-[calc(100vh-380px)] overflow-y-auto">
              <div>{grepResults.total} {t('prog_search_lines_found')}</div>
              {(grepResults.matches || []).map((line, i) => {
                const [path, lineNum] = line.split(':', 2);
                const rel = path.startsWith('/app/') ? path.slice(5) : path;
                return (
                  <button
                    key={i}
                    onClick={() => loadFile(rel)}
                    className="block w-full text-left text-[10px] font-mono text-white hover:bg-white/[0.05] px-1 py-0.5 break-all"
                  >
                    <span className="text-cyan-300">{rel}</span>
                    <span className="text-[#71717A]">:{lineNum}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </aside>
      <main className="col-span-12 lg:col-span-8 bg-[#0A0A0A] border border-white/10 rounded-sm flex flex-col overflow-hidden">
        <header className="p-3 border-b border-white/10 flex items-center gap-2">
          <FileCode className="w-4 h-4 text-[#E4FF00]" />
          <span className="text-sm font-bold truncate flex-1">{filePath}</span>
          {dirty && <span className="text-[10px] text-amber-300">● modifié</span>}
          {fileContent?.truncated && <span className="text-[10px] text-amber-300">{t('prog_file_truncated')}</span>}
          {fileContent?.bytes && !dirty && <span className="text-[10px] text-[#71717A]">{fileContent.bytes} {t('prog_file_bytes')}</span>}
          <button
            onClick={saveFile}
            disabled={!dirty || busy}
            data-testid="private-save-file-btn"
            className="ml-1 inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold bg-[#E4FF00] text-[#050505] rounded-sm disabled:opacity-40 hover:bg-[#E4FF00]/90"
          >
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Sauvegarder
          </button>
        </header>
        <div className="flex-1 overflow-hidden">
          <textarea
            value={editBuffer}
            onChange={(e) => { setEditBuffer(e.target.value); setDirty(true); }}
            data-testid="private-code-textarea"
            spellCheck="false"
            className="w-full h-full text-[11px] font-mono text-white bg-[#050505] p-3 resize-none focus:outline-none border-0"
            placeholder="Sélectionne un fichier dans la sidebar…"
          />
        </div>
      </main>
    </div>
  );
}

// =============================================================================
// AI PROGRAMMING : config orchestrateur + history + test-loop
// =============================================================================

const AGENT_PROMPTS = [
  { id: 'planner', label: 'Planner', icon: Brain, color: 'text-violet-300', descKey: 'prog_agent_planner_desc' },
  { id: 'executor', label: 'Executor', icon: Play, color: 'text-amber-300', descKey: 'prog_agent_executor_desc' },
  { id: 'critic', label: 'Critic', icon: SearchIcon, color: 'text-cyan-300', descKey: 'prog_agent_critic_desc' },
  { id: 'arbiter', label: 'Arbiter', icon: Save, color: 'text-[#E4FF00]', descKey: 'prog_agent_arbiter_desc' },
];

function AIProgrammingPanel() {
  const { t } = useLanguage();
  const [history, setHistory] = useState([]);
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await axios.post(`${API}/orchestrate/history`, { limit: 30 }, { withCredentials: true });
        if (mounted) setHistory(r.data?.events || []);
      } catch (_) { /* silent */ }
    })();
    return () => { mounted = false; };
  }, []);

  const runTestLoop = async () => {
    setTestRunning(true);
    setTestResult(null);
    try {
      const response = await fetch(`${API}/orchestrate/test-loop`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: 'backend', path: 'tests/' }),
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      const events = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const raw = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const line = raw.split('\n').find((l) => l.startsWith('data:'));
          if (!line) continue;
          try { events.push(JSON.parse(line.slice(5).trim())); } catch (_) { /* ignore */ }
        }
      }
      setTestResult(events);
    } catch (e) { toast.error(e.message || t('prog_test_loop_failed')); }
    finally { setTestRunning(false); }
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Agents prompts (read-only) */}
      <section className="col-span-12 lg:col-span-6 bg-[#0A0A0A] border border-white/10 rounded-sm p-4">
        <h2 className="font-['Chivo'] font-bold text-sm text-[#E4FF00] mb-3 flex items-center gap-2">
          <Cpu className="w-4 h-4" /> {t('prog_agents_title')}
        </h2>
        <div className="space-y-3">
          {AGENT_PROMPTS.map((a) => {
            const Ai = a.icon;
            return (
              <div key={a.id} className="bg-black/30 border border-white/10 rounded-sm p-3" data-testid={`ai-agent-${a.id}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Ai className={`w-4 h-4 ${a.color}`} />
                  <span className="font-bold text-sm">{a.label}</span>
                </div>
                <p className="text-[11px] text-[#A1A1AA] leading-relaxed">{t(a.descKey)}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Test-loop launcher */}
      <section className="col-span-12 lg:col-span-6 bg-[#0A0A0A] border border-white/10 rounded-sm p-4">
        <h2 className="font-['Chivo'] font-bold text-sm text-[#E4FF00] mb-3 flex items-center gap-2">
          <Play className="w-4 h-4" /> {t('prog_test_loop_title')}
        </h2>
        <button
          onClick={runTestLoop}
          disabled={testRunning}
          data-testid="ai-run-test-loop"
          className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] font-bold text-sm rounded-sm hover:bg-[#E4FF00]/90 disabled:opacity-40 inline-flex items-center justify-center gap-2"
        >
          {testRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {testRunning ? t('prog_test_running') : t('prog_test_launch')}
        </button>
        {testResult && (
          <div className="mt-3 space-y-1 max-h-64 overflow-y-auto">
            {testResult.map((e, i) => (
              <div key={i} className="text-[11px] text-white bg-black/40 border border-white/10 rounded-sm p-2">
                <span className="text-[#71717A] mr-1">[{e.kind}]</span>
                {e.summary}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* History */}
      <section className="col-span-12 bg-[#0A0A0A] border border-white/10 rounded-sm p-4">
        <h2 className="font-['Chivo'] font-bold text-sm text-[#E4FF00] mb-3 flex items-center gap-2">
          <FolderTree className="w-4 h-4" /> {t('prog_history_title') || "Historique d'exécution"}
        </h2>
        {history.length === 0 ? (
          <div className="text-[11px] text-[#71717A] py-4 text-center">{t('prog_history_empty')}</div>
        ) : (
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {history.map((e, i) => (
              <div key={i} className="text-[11px] text-white bg-black/30 border border-white/10 rounded-sm p-2 flex items-center gap-2">
                <span className="text-[#71717A] flex-shrink-0">[{e.kind}]</span>
                <span className="flex-1 truncate">{e.summary}</span>
                <span className="text-[10px] text-[#71717A] flex-shrink-0">{new Date(e.ts).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* iter92 — Changelog modifications site/IA (sync bidirectionnelle) */}
      <ChangelogPanel />
    </div>
  );
}

// =============================================================================
// iter92 — CHANGELOG modifications site/IA (sync bidirectionnelle)
// =============================================================================
function ChangelogPanel() {
  const { t } = useLanguage();
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [manualCategory, setManualCategory] = useState('manual');
  const [manualSummary, setManualSummary] = useState('');

  const loadChanges = async () => {
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, { limit: 100 });
      const r = await axios.post(`${API}/private/changelog`, body);
      setChanges(r.data?.changes || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('prog_changelog_unavailable'));
    } finally { setLoading(false); }
  };

  const addManual = async () => {
    if (!manualSummary.trim()) return;
    try {
      const body = await withCreatorProof(API, axios, {
        category: manualCategory,
        summary: manualSummary.trim(),
      });
      await axios.post(`${API}/private/changelog/log`, body);
      setManualSummary('');
      toast.success(t('prog_changelog_saved'));
      loadChanges();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('prog_changelog_save_failed'));
    }
  };

  useEffect(() => { loadChanges(); /* eslint-disable-line */ }, []);

  const CATEGORY_COLORS = {
    model: 'text-violet-300 bg-violet-500/10 border-violet-400/30',
    site_mode: 'text-cyan-300 bg-cyan-500/10 border-cyan-400/30',
    deploy: 'text-emerald-300 bg-emerald-500/10 border-emerald-400/30',
    code: 'text-amber-300 bg-amber-500/10 border-amber-400/30',
    config: 'text-blue-300 bg-blue-500/10 border-blue-400/30',
    manual: 'text-rose-300 bg-rose-500/10 border-rose-400/30',
  };

  return (
    <section className="col-span-12 bg-[#0A0A0A] border border-white/10 rounded-sm p-4" data-testid="changelog-panel">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-['Chivo'] font-bold text-sm text-[#E4FF00] flex items-center gap-2">
          <Save className="w-4 h-4" /> {t('prog_changelog_title')}
        </h2>
        <button onClick={loadChanges} className="text-xs text-[#A1A1AA] hover:text-white px-2 py-1 rounded-sm border border-white/10">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : t('prog_changelog_reload')}
        </button>
      </div>
      <p className="text-[11px] text-[#A1A1AA] mb-3 leading-relaxed">
        {t('prog_changelog_subtitle')}
      </p>
      {/* Saisie manuelle */}
      <div className="flex gap-2 mb-3 bg-black/30 border border-white/10 rounded-sm p-2">
        <select
          value={manualCategory}
          onChange={(e) => setManualCategory(e.target.value)}
          data-testid="changelog-category-select"
          className="bg-[#0F0F13] border border-white/10 rounded-sm px-2 py-1 text-xs text-white"
        >
          <option value="manual">{t('prog_changelog_cat_manual')}</option>
          <option value="code">{t('prog_changelog_cat_code')}</option>
          <option value="config">{t('prog_changelog_cat_config')}</option>
          <option value="model">{t('prog_changelog_cat_model')}</option>
          <option value="site_mode">{t('prog_changelog_cat_mode')}</option>
          <option value="deploy">{t('prog_changelog_cat_deploy')}</option>
        </select>
        <input
          value={manualSummary}
          onChange={(e) => setManualSummary(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') addManual(); }}
          placeholder={t('prog_changelog_placeholder')}
          data-testid="changelog-manual-input"
          className="flex-1 bg-[#0F0F13] border border-white/10 rounded-sm px-2 py-1 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
        />
        <button
          onClick={addManual}
          disabled={!manualSummary.trim()}
          data-testid="changelog-add-btn"
          className="px-3 py-1 bg-[#E4FF00] text-[#050505] font-bold text-xs rounded-sm disabled:opacity-40"
        >
          {t('prog_changelog_add')}
        </button>
      </div>
      {/* Liste */}
      {changes.length === 0 ? (
        <div className="text-[11px] text-[#71717A] py-4 text-center">{t('prog_changelog_empty')}</div>
      ) : (
        <div className="space-y-1.5 max-h-80 overflow-y-auto">
          {changes.map((c, i) => (
            <div key={i} className="text-xs text-white bg-black/30 border border-white/10 rounded-sm p-2 flex items-start gap-2" data-testid={`changelog-entry-${i}`}>
              <span className={`flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded-sm border font-bold uppercase ${CATEGORY_COLORS[c.category] || 'text-white border-white/10'}`}>
                {c.category}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-white">{c.summary}</div>
                {c.details && Object.keys(c.details).length > 0 && (
                  <pre className="text-[10px] text-[#71717A] mt-0.5 font-mono break-all whitespace-pre-wrap">
                    {JSON.stringify(c.details, null, 0).slice(0, 200)}
                  </pre>
                )}
              </div>
              <span className="text-[10px] text-[#71717A] flex-shrink-0">
                {new Date(c.ts).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
