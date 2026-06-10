import React, { useState, useRef } from 'react';
import axios from 'axios';
import {
  ChevronRight, FileText, Search, Code2, CheckCircle2, AlertTriangle,
  Lightbulb, Sparkles, Play, Loader2, GitCommit, Eye, Brain,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter84 — Mapping kind → icon + couleur + label par défaut
const KIND_META = {
  phase_started: { Icon: Loader2, color: 'text-yellow-300', spin: true },
  phase_done: { Icon: CheckCircle2, color: 'text-emerald-300' },
  file_viewed: { Icon: FileText, color: 'text-sky-300' },
  file_created: { Icon: FileText, color: 'text-emerald-400' },
  file_modified: { Icon: FileText, color: 'text-amber-300' },
  code_executed_start: { Icon: Play, color: 'text-yellow-300', spin: true },
  code_executed: { Icon: Code2, color: 'text-emerald-300' },
  search_done: { Icon: Search, color: 'text-cyan-300' },
  test_run: { Icon: CheckCircle2, color: 'text-emerald-300' },
  thought: { Icon: Lightbulb, color: 'text-violet-300' },
  commit_pushed: { Icon: GitCommit, color: 'text-pink-300' },
  preview_ready: { Icon: Eye, color: 'text-emerald-300' },
  error: { Icon: AlertTriangle, color: 'text-red-400' },
  final: { Icon: Sparkles, color: 'text-[#E4FF00]' },
  complete: { Icon: CheckCircle2, color: 'text-emerald-400' },
};

/**
 * iter84 — Composant qui affiche un journal d'actions de l'orchestrateur
 * en temps réel. Chaque ligne représente une opération (fichier lu, code
 * exécuté, recherche, pensée critique, etc.) avec une FLÈCHE dépliable
 * pour voir le détail complet chargé à la demande via
 * /orchestrate/event/{id}/details.
 *
 * Props :
 *   events: array d'événements typés émis par le backend (chacun a un
 *           event_id, kind, summary, ts).
 *   running: bool — affiche un spinner global en bas si true.
 */
export default function OrchestrationLog({ events = [], running = false, finalAnswer = '' }) {
  return (
    <div className="space-y-1.5" data-testid="orchestration-log">
      {events.map((evt, idx) => (
        <EventRow key={evt.event_id || idx} evt={evt} />
      ))}
      {/* iter85 — Aperçu LIVE du streaming token-par-token du final event.
          S'affiche dès le premier final_chunk reçu et avant que le 'final'
          complet n'arrive. Donne le rendu ChatGPT-style sur le texte final. */}
      {running && finalAnswer && !events.some((e) => e.kind === 'final') && (
        <div className="bg-[#0A0A0A] border border-[#E4FF00]/40 rounded-sm p-3" data-testid="final-streaming">
          <div className="flex items-center gap-1.5 text-[10px] text-[#E4FF00] uppercase tracking-widest mb-1.5">
            <Sparkles className="w-3 h-3" />
            <span>Réponse en cours…</span>
          </div>
          <div className="text-sm text-white whitespace-pre-wrap break-words">
            {finalAnswer}
            <span className="inline-block w-2 h-3 bg-[#E4FF00] animate-pulse ml-0.5 align-middle" />
          </div>
        </div>
      )}
      {running && (
        <div className="flex items-center gap-2 text-[11px] text-[#A1A1AA] px-2 py-1.5">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>L&apos;orchestrateur travaille…</span>
        </div>
      )}
      {events.length === 0 && !running && (
        <div className="text-[11px] text-[#71717A] py-4 text-center">
          Aucune action enregistrée pour cette session.
        </div>
      )}
    </div>
  );
}

function EventRow({ evt }) {
  const [expanded, setExpanded] = useState(false);
  const [details, setDetails] = useState(evt.details || null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const meta = KIND_META[evt.kind] || { Icon: Brain, color: 'text-white' };
  const Icon = meta.Icon;
  const isFinal = evt.kind === 'final';

  const toggle = async () => {
    const willOpen = !expanded;
    setExpanded(willOpen);
    if (willOpen && !details && evt.event_id) {
      setLoadingDetails(true);
      try {
        const r = await axios.get(`${API}/orchestrate/event/${evt.event_id}/details`, { withCredentials: true });
        setDetails(r.data?.details || null);
      } catch (_) { /* silent */ }
      finally { setLoadingDetails(false); }
    }
  };

  return (
    <div className={`bg-[#0A0A0A] border border-white/10 rounded-sm overflow-hidden ${isFinal ? 'border-[#E4FF00]/40' : ''}`} data-testid={`event-${evt.kind}`}>
      <button
        type="button"
        onClick={toggle}
        data-testid={`event-toggle-${evt.event_id || evt.kind}`}
        className="w-full px-2.5 py-1.5 flex items-center gap-2 text-left hover:bg-white/[0.03] transition-colors"
      >
        <ChevronRight className={`w-3 h-3 text-[#71717A] transition-transform flex-shrink-0 ${expanded ? 'rotate-90' : ''}`} />
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${meta.color} ${meta.spin ? 'animate-spin' : ''}`} />
        <span className={`text-xs flex-1 truncate ${isFinal ? 'text-white font-bold' : 'text-white/90'}`}>
          {evt.summary || evt.kind}
        </span>
        {evt.path && <code className="text-[10px] text-[#71717A] font-mono truncate max-w-[200px]">{evt.path}</code>}
        {evt.confidence !== undefined && (
          <span className="text-[10px] text-[#E4FF00] font-bold">{evt.confidence}/100</span>
        )}
      </button>
      {expanded && (
        <div className="border-t border-white/10 px-3 py-2 bg-black/30">
          {loadingDetails && (
            <div className="text-[11px] text-[#A1A1AA] inline-flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" /> Chargement du détail…
            </div>
          )}
          {!loadingDetails && details && <EventDetails details={details} kind={evt.kind} />}
          {!loadingDetails && !details && (
            <div className="text-[11px] text-[#71717A]">Aucun détail disponible.</div>
          )}
        </div>
      )}
    </div>
  );
}

function EventDetails({ details, kind }) {
  if (typeof details === 'string') {
    return <div className="text-[11px] text-white whitespace-pre-wrap break-words font-mono">{details}</div>;
  }
  if (details?.content && (kind === 'file_viewed' || kind === 'file_created' || kind === 'file_modified')) {
    return (
      <div className="space-y-2">
        <div className="text-[10px] text-[#A1A1AA]">
          {details.path} {details.truncated && <span className="text-amber-300">(tronqué)</span>}
        </div>
        <pre className="text-[10.5px] text-white whitespace-pre-wrap break-all font-mono max-h-72 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10">
          {details.content}
        </pre>
      </div>
    );
  }
  if (details?.stdout !== undefined || details?.stderr !== undefined) {
    return (
      <div className="space-y-2">
        {details.stdout && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-300">stdout</div>
            <pre className="text-[10.5px] text-white whitespace-pre-wrap break-all font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10">{details.stdout}</pre>
          </div>
        )}
        {details.stderr && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-red-300">stderr</div>
            <pre className="text-[10.5px] text-red-200 whitespace-pre-wrap break-all font-mono max-h-32 overflow-y-auto bg-black/40 p-2 rounded-sm border border-red-500/30">{details.stderr}</pre>
          </div>
        )}
        {details.code && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-[#A1A1AA]">code</div>
            <pre className="text-[10.5px] text-white whitespace-pre-wrap break-all font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10">{details.code}</pre>
          </div>
        )}
      </div>
    );
  }
  if (details?.matches) {
    return (
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-widest text-[#A1A1AA]">{details.total} résultat(s) pour : {details.pattern}</div>
        <pre className="text-[10.5px] text-white whitespace-pre-wrap break-all font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10">
          {(details.matches || []).join('\n')}
        </pre>
      </div>
    );
  }
  if (details?.hypotheses) {
    return (
      <ul className="space-y-1 text-[11px] text-white">
        {(details.hypotheses || []).map((h, i) => (
          <li key={i} className="flex gap-2"><span className="text-[#71717A]">{i + 1}.</span><span>{h}</span></li>
        ))}
        {details.uncertainties?.length > 0 && (
          <li className="mt-2 text-[10px] text-amber-200">Incertitudes : {details.uncertainties.join(' · ')}</li>
        )}
      </ul>
    );
  }
  if (details?.logical_flaws) {
    return (
      <div className="space-y-1 text-[11px]">
        {details.logical_flaws.map((f, i) => (
          <div key={i} className="text-red-200 flex gap-2"><AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" /><span>{f}</span></div>
        ))}
        {details.edge_cases?.length > 0 && (
          <div className="mt-2 text-amber-200 text-[10px]">Cas limites : {details.edge_cases.join(' · ')}</div>
        )}
      </div>
    );
  }
  // Fallback : JSON
  return (
    <pre className="text-[10.5px] text-white whitespace-pre-wrap break-all font-mono max-h-48 overflow-y-auto bg-black/40 p-2 rounded-sm border border-white/10">
      {JSON.stringify(details, null, 2)}
    </pre>
  );
}
