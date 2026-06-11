import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Lock, FileCode, FolderTree, Search as SearchIcon, Brain, Cpu, Play, Loader2, Save } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';

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
  const isAI = location.pathname.includes('ai-programming');
  const title = isAI ? 'Programmation des IA' : 'Programmation du site';

  // iter89 — Visible UNIQUEMENT pour les DEVICES créa et SEULEMENT quand la
  // créatrice N'EST PAS en vue créa (pour éviter qu'un visiteur regarde
  // par-dessus l'épaule et copie le code). Donc accessible si :
  //   device.role === 'creator' && device.viewMode && device.viewMode !== 'creator'
  const allowed = device.role === 'creator' && device.viewMode && device.viewMode !== 'creator';

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6" data-testid="private-programming-page">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/dashboard')} className="text-[#A1A1AA] hover:text-white text-sm inline-flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" /> Retour
          </button>
          <h1 className="text-2xl font-['Chivo'] font-black">{title}</h1>
        </div>
        {!allowed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-sm p-8 text-center max-w-md mx-auto" data-testid="private-access-denied">
            <Lock className="w-14 h-14 mx-auto text-red-300 mb-4" />
            <h2 className="text-lg font-bold text-red-200 mb-2">Accès refusé</h2>
            <p className="text-sm text-red-100/90 leading-relaxed">
              Pour des raisons de sécurité, le code n&apos;est accessible que pour les
              appareils créateurs et uniquement quand la vue créatrice n&apos;est pas
              active (anti-copie par-dessus l&apos;épaule).
            </p>
            <p className="text-xs text-amber-200/90 mt-3">
              Active une vue simulée (user/modo/admin/guest) depuis le ViewModePicker
              pour débloquer cette page.
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
  const [pattern, setPattern] = useState('');
  const [grepResults, setGrepResults] = useState(null);
  const [filePath, setFilePath] = useState('backend/server.py');
  const [fileContent, setFileContent] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadFile = async (rel) => {
    if (!rel) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { path: rel });
      const r = await axios.post(`${API}/private/code/read-file`, body);
      setFilePath(rel);
      setFileContent(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Lecture impossible'); }
    finally { setBusy(false); }
  };

  const doGrep = async () => {
    if (!pattern.trim()) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { pattern: pattern.trim() });
      const r = await axios.post(`${API}/private/code/grep`, body);
      setGrepResults(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Recherche impossible'); }
    finally { setBusy(false); }
  };

  useEffect(() => { loadFile('backend/server.py'); /* eslint-disable-line */ }, []);

  return (
    <div className="grid grid-cols-12 gap-4 h-[calc(100vh-180px)]">
      <aside className="col-span-12 lg:col-span-4 bg-[#0A0A0A] border border-white/10 rounded-sm flex flex-col overflow-hidden">
        <header className="p-3 border-b border-white/10 flex items-center gap-2">
          <SearchIcon className="w-4 h-4 text-[#E4FF00]" />
          <span className="text-sm font-bold">Recherche dans le code</span>
        </header>
        <div className="p-3 space-y-2">
          <div className="flex gap-2">
            <input
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') doGrep(); }}
              placeholder="Pattern à chercher…"
              data-testid="private-grep-input"
              className="flex-1 px-2 py-1.5 bg-[#0F0F13] border border-white/15 rounded-sm text-xs font-mono focus:outline-none focus:border-[#E4FF00]"
            />
            <button onClick={doGrep} disabled={busy || !pattern.trim()} data-testid="private-grep-btn" className="px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-bold text-xs rounded-sm disabled:opacity-40">
              {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Grep'}
            </button>
          </div>
          {grepResults && (
            <div className="text-[10px] text-[#A1A1AA] space-y-1 max-h-[calc(100vh-380px)] overflow-y-auto">
              <div>{grepResults.total} ligne(s) trouvée(s)</div>
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
          {fileContent?.truncated && <span className="text-[10px] text-amber-300">(tronqué)</span>}
          {fileContent?.bytes && <span className="text-[10px] text-[#71717A]">{fileContent.bytes} octets</span>}
        </header>
        <div className="flex-1 overflow-auto">
          <pre className="text-[11px] font-mono text-white p-3 whitespace-pre-wrap break-all">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            {fileContent?.content || ''}
          </pre>
        </div>
      </main>
    </div>
  );
}

// =============================================================================
// AI PROGRAMMING : config orchestrateur + history + test-loop
// =============================================================================

const AGENT_PROMPTS = [
  { id: 'planner', label: 'Planner', icon: Brain, color: 'text-violet-300', desc: 'Génère le plan structuré en JSON (hypotheses, files_to_inspect, code_to_execute, uncertainties).' },
  { id: 'executor', label: 'Executor', icon: Play, color: 'text-amber-300', desc: 'Exécute le code Python dans une sandbox sécurisée (timeout 8s, AST scan, blocklist).' },
  { id: 'critic', label: 'Critic', icon: SearchIcon, color: 'text-cyan-300', desc: 'Tente de réfuter le plan : logical_flaws, edge_cases, unverifiable + score 0-100.' },
  { id: 'arbiter', label: 'Arbiter', icon: Save, color: 'text-[#E4FF00]', desc: 'Synthèse finale en séparant confirmé/probable/incertain. Streamé token-par-token.' },
];

function AIProgrammingPanel() {
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
    } catch (e) { toast.error(e.message || 'Test-loop failed'); }
    finally { setTestRunning(false); }
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Agents prompts (read-only) */}
      <section className="col-span-12 lg:col-span-6 bg-[#0A0A0A] border border-white/10 rounded-sm p-4">
        <h2 className="font-['Chivo'] font-bold text-sm text-[#E4FF00] mb-3 flex items-center gap-2">
          <Cpu className="w-4 h-4" /> Agents de l&apos;orchestrateur
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
                <p className="text-[11px] text-[#A1A1AA] leading-relaxed">{a.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Test-loop launcher */}
      <section className="col-span-12 lg:col-span-6 bg-[#0A0A0A] border border-white/10 rounded-sm p-4">
        <h2 className="font-['Chivo'] font-bold text-sm text-[#E4FF00] mb-3 flex items-center gap-2">
          <Play className="w-4 h-4" /> Boucle de validation
        </h2>
        <button
          onClick={runTestLoop}
          disabled={testRunning}
          data-testid="ai-run-test-loop"
          className="w-full px-3 py-2 bg-[#E4FF00] text-[#050505] font-bold text-sm rounded-sm hover:bg-[#E4FF00]/90 disabled:opacity-40 inline-flex items-center justify-center gap-2"
        >
          {testRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {testRunning ? 'Tests en cours…' : 'Lancer pytest backend'}
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
          <FolderTree className="w-4 h-4" /> Historique d&apos;exécution
        </h2>
        {history.length === 0 ? (
          <div className="text-[11px] text-[#71717A] py-4 text-center">Aucun événement persisté.</div>
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
      toast.error(e?.response?.data?.detail || 'Changelog inaccessible');
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
      toast.success('Modification enregistrée');
      loadChanges();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec enregistrement');
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
          <Save className="w-4 h-4" /> Modifications du site &amp; IA (sync)
        </h2>
        <button onClick={loadChanges} className="text-xs text-[#A1A1AA] hover:text-white px-2 py-1 rounded-sm border border-white/10">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Recharger'}
        </button>
      </div>
      <p className="text-[11px] text-[#A1A1AA] mb-3 leading-relaxed">
        Suit toutes les modifications faites au site et aux IA (ajouts/retraits de modèles, changement de site_mode, déploiements, code Python/JS modifié sur GitHub ou en local). Ajoute manuellement une entrée quand tu modifies le code directement.
      </p>
      {/* Saisie manuelle */}
      <div className="flex gap-2 mb-3 bg-black/30 border border-white/10 rounded-sm p-2">
        <select
          value={manualCategory}
          onChange={(e) => setManualCategory(e.target.value)}
          data-testid="changelog-category-select"
          className="bg-[#0F0F13] border border-white/10 rounded-sm px-2 py-1 text-xs text-white"
        >
          <option value="manual">Manuel</option>
          <option value="code">Code modifié</option>
          <option value="config">Config / .env</option>
          <option value="model">Modèle IA</option>
          <option value="site_mode">Mode du site</option>
          <option value="deploy">Déploiement</option>
        </select>
        <input
          value={manualSummary}
          onChange={(e) => setManualSummary(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') addManual(); }}
          placeholder="Résumé de la modification (ex: 'Ajout endpoint /api/foo via GitHub')"
          data-testid="changelog-manual-input"
          className="flex-1 bg-[#0F0F13] border border-white/10 rounded-sm px-2 py-1 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
        />
        <button
          onClick={addManual}
          disabled={!manualSummary.trim()}
          data-testid="changelog-add-btn"
          className="px-3 py-1 bg-[#E4FF00] text-[#050505] font-bold text-xs rounded-sm disabled:opacity-40"
        >
          Ajouter
        </button>
      </div>
      {/* Liste */}
      {changes.length === 0 ? (
        <div className="text-[11px] text-[#71717A] py-4 text-center">Aucune modification enregistrée.</div>
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
