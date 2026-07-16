import React, { useState } from 'react';
import axios from 'axios';
import {
  ChevronRight, ChevronDown, FileText, Search, Code2, CheckCircle2,
  AlertTriangle, Loader2, ListChecks, ShieldCheck, FilePlus2, FileDiff, Bot,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter129 — Journal d'activité de l'agent (style Emergent/Cursor).
// Événements compacts streamés en SSE ; détails complets chargés à la
// demande via /orchestrate/event/{id}/details quand on déplie la flèche.

const KIND_META = {
  status: { Icon: Loader2, color: 'text-yellow-300', spin: true },
  status_done: { Icon: CheckCircle2, color: 'text-emerald-300' },
  plan_ready: { Icon: ListChecks, color: 'text-violet-300' },
  search_done: { Icon: Search, color: 'text-cyan-300' },
  file_viewed: { Icon: FileText, color: 'text-sky-300' },
  file_created: { Icon: FilePlus2, color: 'text-emerald-400' },
  file_modified: { Icon: FileDiff, color: 'text-amber-300' },
  code_executed: { Icon: Code2, color: 'text-emerald-300' },
  test_run: { Icon: CheckCircle2, color: 'text-emerald-300' },
  validation: { Icon: ShieldCheck, color: 'text-[#E4FF00]' },
  error: { Icon: AlertTriangle, color: 'text-red-400' },
};

export default function AgentActivityLog({ events = [], running = false, agentName = '' }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!events.length && !running) return null;
  const doneCount = events.filter(e => e.kind !== 'status').length;

  return (
    <div className="mb-3 border border-white/10 rounded-sm bg-black/40 overflow-hidden" data-testid="agent-activity-log">
      <button
        type="button"
        onClick={() => setCollapsed(c => !c)}
        data-testid="agent-activity-toggle"
        className="w-full px-2.5 py-1.5 flex items-center gap-2 text-left hover:bg-white/[0.03] transition-colors"
      >
        {collapsed ? <ChevronRight className="w-3 h-3 text-[#71717A]" /> : <ChevronDown className="w-3 h-3 text-[#71717A]" />}
        <Bot className="w-3.5 h-3.5 text-[#E4FF00]" />
        <span className="text-[11px] uppercase tracking-widest text-[#E4FF00] font-bold">
          Journal d&apos;activité{agentName ? ` · ${agentName}` : ''}
        </span>
        <span className="ml-auto text-[10px] text-[#71717A]">
          {running ? (
            <span className="inline-flex items-center gap-1.5 text-yellow-300">
              <Loader2 className="w-3 h-3 animate-spin" /> en cours…
            </span>
          ) : `${doneCount} action${doneCount > 1 ? 's' : ''}`}
        </span>
      </button>
      {!collapsed && (
        <div className="border-t border-white/10 px-1.5 py-1.5 space-y-1">
          {events.map((evt, idx) => (
            <ActivityRow
              key={evt.event_id || idx}
              evt={evt}
              isLast={idx === events.length - 1}
              running={running}
            />
          ))}
          {running && events.length === 0 && (
            <div className="flex items-center gap-2 text-[11px] text-[#A1A1AA] px-2 py-1">
              <Loader2 className="w-3 h-3 animate-spin" /> Analyse de la demande…
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ActivityRow({ evt, isLast, running }) {
  const [expanded, setExpanded] = useState(false);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const meta = KIND_META[evt.kind] || { Icon: CheckCircle2, color: 'text-white' };
  const Icon = meta.Icon;
  // Un "status" ne spinne que s'il est le dernier événement pendant l'exécution.
  const spin = meta.spin && isLast && running;
  const expandable = ['search_done', 'file_viewed', 'file_created', 'file_modified',
    'code_executed', 'validation', 'plan_ready', 'error'].includes(evt.kind);

  const toggle = async () => {
    if (!expandable) return;
    const willOpen = !expanded;
    setExpanded(willOpen);
    if (willOpen && !details && evt.event_id) {
      setLoading(true);
      try {
        const r = await axios.get(`${API}/orchestrate/event/${evt.event_id}/details`, { withCredentials: true });
        setDetails(r.data?.details || null);
      } catch { /* silent */ }
      finally { setLoading(false); }
    }
  };

  return (
    <div className="rounded-sm overflow-hidden" data-testid={`agent-event-${evt.kind}`}>
      <button
        type="button"
        onClick={toggle}
        className={`w-full px-2 py-1 flex items-center gap-2 text-left transition-colors ${expandable ? 'hover:bg-white/[0.04] cursor-pointer' : 'cursor-default'}`}
      >
        {expandable ? (
          <ChevronRight className={`w-3 h-3 text-[#71717A] transition-transform flex-shrink-0 ${expanded ? 'rotate-90' : ''}`} />
        ) : <span className="w-3 flex-shrink-0" />}
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${meta.color} ${spin ? 'animate-spin' : ''}`} />
        <span className={`text-xs flex-1 min-w-0 truncate ${evt.kind === 'search_done' ? 'font-mono text-cyan-200' : 'text-white/90'}`}>
          {evt.summary || evt.kind}
        </span>
        {(evt.lines_added !== undefined || evt.lines_removed !== undefined) && (
          <span className="text-[10px] font-mono flex-shrink-0">
            <span className="text-emerald-400">+{evt.lines_added || 0}</span>
            {' '}
            <span className="text-red-400">-{evt.lines_removed || 0}</span>
          </span>
        )}
      </button>
      {expanded && (
        <div className="border-l-2 border-white/10 ml-4 pl-2 py-1.5 bg-black/30">
          {loading && (
            <div className="text-[11px] text-[#A1A1AA] inline-flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" /> Chargement du détail…
            </div>
          )}
          {!loading && details && <ActivityDetails details={details} kind={evt.kind} />}
          {!loading && !details && <div className="text-[11px] text-[#71717A]">Aucun détail disponible.</div>}
        </div>
      )}
    </div>
  );
}

function DiffView({ diff, before, after }) {
  const [tab, setTab] = useState('diff');
  return (
    <div className="space-y-1.5">
      <div className="flex gap-1">
        {['diff', before !== null && before !== undefined ? 'avant' : null, 'après'].filter(Boolean).map(tId => (
          <button
            key={tId} type="button" onClick={() => setTab(tId)}
            data-testid={`diff-tab-${tId}`}
            className={`px-2 py-0.5 text-[10px] uppercase tracking-widest rounded-sm border transition-colors ${tab === tId ? 'border-[#E4FF00]/50 text-[#E4FF00]' : 'border-white/10 text-[#71717A] hover:text-white'}`}
          >
            {tId}
          </button>
        ))}
      </div>
      {tab === 'diff' && (
        <pre className="text-[10.5px] font-mono max-h-72 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">
          {(diff || '').split('\n').map((line, i) => {
            let cls = 'text-white/70';
            if (line.startsWith('+') && !line.startsWith('+++')) cls = 'text-emerald-300 bg-emerald-500/10';
            else if (line.startsWith('-') && !line.startsWith('---')) cls = 'text-red-300 bg-red-500/10';
            else if (line.startsWith('@@')) cls = 'text-cyan-300';
            return <div key={i} className={cls}>{line || ' '}</div>;
          })}
        </pre>
      )}
      {tab === 'avant' && (
        <pre className="text-[10.5px] text-white/80 font-mono max-h-72 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">{before}</pre>
      )}
      {tab === 'après' && (
        <pre className="text-[10.5px] text-white font-mono max-h-72 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">{after}</pre>
      )}
    </div>
  );
}

function ActivityDetails({ details, kind }) {
  if (kind === 'file_created' || kind === 'file_modified') {
    return (
      <div className="space-y-1.5">
        <div className="text-[10px] text-[#A1A1AA] font-mono">
          {details.path} · <span className="text-emerald-400">+{details.lines_added || 0}</span>{' '}
          <span className="text-red-400">-{details.lines_removed || 0}</span>
        </div>
        <DiffView diff={details.diff} before={details.before} after={details.after} />
      </div>
    );
  }
  if (kind === 'file_viewed' && details.content) {
    return (
      <div className="space-y-1.5">
        <div className="text-[10px] text-[#A1A1AA] font-mono">
          {details.path} {details.truncated && <span className="text-amber-300">(tronqué)</span>}
        </div>
        <pre className="text-[10.5px] text-white font-mono max-h-72 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">{details.content}</pre>
      </div>
    );
  }
  if (kind === 'search_done' && details.matches) {
    return (
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-widest text-[#A1A1AA]">{details.total} résultat(s)</div>
        <pre className="text-[10.5px] text-white font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">
          {(details.matches || []).join('\n') || '(aucun résultat)'}
        </pre>
      </div>
    );
  }
  if (kind === 'code_executed') {
    return (
      <div className="space-y-1.5">
        {details.code && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-[#A1A1AA]">code</div>
            <pre className="text-[10.5px] text-white font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">{details.code}</pre>
          </div>
        )}
        {details.stdout && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-300">stdout</div>
            <pre className="text-[10.5px] text-white font-mono max-h-40 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">{details.stdout}</pre>
          </div>
        )}
        {details.stderr && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-red-300">stderr</div>
            <pre className="text-[10.5px] text-red-200 font-mono max-h-32 overflow-y-auto bg-black/40 p-2 rounded-sm border border-red-500/30 whitespace-pre-wrap break-all">{details.stderr}</pre>
          </div>
        )}
      </div>
    );
  }
  if (kind === 'plan_ready' && details.steps) {
    return (
      <ol className="space-y-0.5 text-[11px] text-white">
        {details.steps.map((s, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-[#71717A]">{i + 1}.</span>
            <span>{s.label || s.tool}{s.path ? ` — ${s.path}` : ''}{s.query ? ` — "${s.query}"` : ''}</span>
          </li>
        ))}
      </ol>
    );
  }
  if (kind === 'validation') {
    return (
      <div className="space-y-1 text-[11px]">
        {details.score !== undefined && (
          <div className="text-[#E4FF00] font-bold">Score : {details.score}/100</div>
        )}
        {(details.issues || []).map((f, i) => (
          <div key={i} className="text-red-200 flex gap-2"><AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" /><span>{f}</span></div>
        ))}
        {(details.improvements || []).length > 0 && (
          <div className="text-amber-200 text-[10px]">Améliorations : {details.improvements.join(' · ')}</div>
        )}
        {(details.issues || []).length === 0 && <div className="text-emerald-300">Aucun problème détecté.</div>}
      </div>
    );
  }
  return (
    <pre className="text-[10.5px] text-white font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10 whitespace-pre-wrap break-all">
      {typeof details === 'string' ? details : JSON.stringify(details, null, 2)}
    </pre>
  );
}
