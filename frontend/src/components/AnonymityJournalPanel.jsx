/**
 * iter142/iter147 — Journal Créa avec 3 onglets.
 *
 *  - Onglet 1 « Alertes bot » : alertes générées automatiquement par
 *    `bot_analyzer` (couche déterministe + couche LLM). Chaque entrée
 *    affiche les 2 couches séparées (`layer_local` + `layer_llm`).
 *    Objectif : la Créa repère les groupes signalés par les bots.
 *  - Onglet 2 « Décisions staff » : décisions finales prises par les
 *    modos/admins (sanction, non-infraction, délégation, refus). Permet
 *    à la Créa de repérer les refus répétés d'un même modo.
 *  - Onglet 3 « Anonymat » : historique des activations Nuit/Soleil
 *    (héritage iter142 — pour comparer).
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  X, Sun, Moon, VenetianMask, ShieldCheck, ShieldAlert, Crown,
  AlertTriangle, Gavel, Bot, Sparkles,
} from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODE_META = {
  sun_mode: { label: 'Soleil', Icon: Sun, color: 'text-amber-300' },
  anonymous: { label: 'Anonyme', Icon: VenetianMask, color: 'text-fuchsia-300' },
  auto_sun: { label: 'Auto Soleil (bot)', Icon: Sun, color: 'text-cyan-300' },
};

const ROLE_META = {
  creator: { label: 'Créa', Icon: Crown, color: 'text-[#E4FF00]' },
  admin: { label: 'Admin', Icon: ShieldCheck, color: 'text-orange-300' },
  modo: { label: 'Modo', Icon: ShieldAlert, color: 'text-cyan-300' },
};

const DECISION_LABEL = {
  sanction: { label: 'Sanction', color: 'text-red-300', border: 'border-red-400/40', bg: 'bg-red-400/10' },
  not_infraction: { label: 'Pas infraction', color: 'text-emerald-300', border: 'border-emerald-400/40', bg: 'bg-emerald-400/10' },
  delegate: { label: 'Délégation', color: 'text-cyan-300', border: 'border-cyan-400/40', bg: 'bg-cyan-400/10' },
  refuse: { label: 'Refus', color: 'text-amber-300', border: 'border-amber-400/40', bg: 'bg-amber-400/10' },
  accept: { label: 'Accepté', color: 'text-white/70', border: 'border-white/20', bg: 'bg-white/[0.04]' },
};

export default function AnonymityJournalPanel({ open, onClose }) {
  const [tab, setTab] = useState('bot'); // 'bot' | 'staff' | 'anon'
  const [botAlerts, setBotAlerts] = useState([]);
  const [staffDecisions, setStaffDecisions] = useState([]);
  const [anonymityEntries, setAnonymityEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [botFilter, setBotFilter] = useState('all'); // all | with_llm | high_score

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    (async () => {
      try {
        const body1 = await withCreatorProof(API, axios, {});
        // Anonymat (héritage iter142)
        const rAnon = await axios.post(`${API}/social/anonymity-journal`, body1);
        setAnonymityEntries(rAnon.data?.entries || []);
      } catch (_e) { setAnonymityEntries([]); }
      try {
        const body2 = await withCreatorProof(API, axios, { limit: 200 });
        const rAlerts = await axios.post(`${API}/moderation/alerts/list`, body2);
        setBotAlerts(rAlerts.data?.alerts || []);
      } catch (_e) { setBotAlerts([]); }
      try {
        const body3 = await withCreatorProof(API, axios, { limit: 200 });
        const rDec = await axios.post(`${API}/moderation/decisions/list`, body3);
        setStaffDecisions(rDec.data?.decisions || []);
      } catch (_e) { setStaffDecisions([]); }
      setLoading(false);
    })();
  }, [open]);

  // Repères Créa : refus répétés par un même modo/admin.
  const refusalHotspots = useMemo(() => {
    const byActor = {};
    for (const d of staffDecisions || []) {
      if (d.decision === 'not_infraction' || d.decision === 'refuse') {
        const k = d.actor_key_id || 'unknown';
        byActor[k] = byActor[k] || { count: 0, pseudo: d.actor_pseudo, role: d.actor_role, handle: d.actor_public_handle };
        byActor[k].count += 1;
      }
    }
    return Object.entries(byActor)
      .filter(([, v]) => v.count >= 3)
      .sort((a, b) => b[1].count - a[1].count);
  }, [staffDecisions]);

  const filteredBot = useMemo(() => {
    if (botFilter === 'all') return botAlerts;
    if (botFilter === 'with_llm') {
      return botAlerts.filter((a) => a.layer_llm && !a.layer_llm.error);
    }
    if (botFilter === 'high_score') return botAlerts.filter((a) => (a.score || 0) >= 70);
    return botAlerts;
  }, [botAlerts, botFilter]);

  if (!open) return null;

  const TabButton = ({ k, label, Icon, count }) => (
    <button
      type="button"
      onClick={() => setTab(k)}
      data-testid={`journal-tab-${k}`}
      className={`inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 border rounded-sm transition ${
        tab === k
          ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00] font-bold'
          : 'text-white/70 border-white/15 hover:border-white/40'
      }`}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
      {typeof count === 'number' && (
        <span className={`text-[10px] px-1 rounded-sm ${
          tab === k ? 'bg-black/30 text-[#050505]' : 'bg-white/10 text-white/60'
        }`}>{count}</span>
      )}
    </button>
  );

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" data-testid="anonymity-journal-overlay">
      <div className="w-full max-w-4xl max-h-[85vh] bg-[#050505] border border-white/20 rounded-sm flex flex-col overflow-hidden">
        <header className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-['Chivo'] font-bold text-white">Journal Créa — modération &amp; anonymat</h3>
            <p className="text-[11px] text-[#A1A1AA]">
              Alertes bot (2 couches) · Décisions staff · Historique Nuit/Soleil
            </p>
          </div>
          <button onClick={onClose} data-testid="anonymity-journal-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </header>
        {/* Tabs */}
        <div className="px-3 py-2 border-b border-white/10 flex items-center gap-1.5 flex-wrap">
          <TabButton k="bot" label="Alertes bot" Icon={Bot} count={botAlerts.length} />
          <TabButton k="staff" label="Décisions staff" Icon={Gavel} count={staffDecisions.length} />
          <TabButton k="anon" label="Anonymat" Icon={VenetianMask} count={anonymityEntries.length} />
        </div>

        {/* Hotspot warning : refus répétés */}
        {tab === 'staff' && refusalHotspots.length > 0 && (
          <div className="mx-3 mt-2 border border-amber-400/40 bg-amber-400/10 rounded-sm px-3 py-2 text-[11px] text-amber-200" data-testid="journal-refusal-hotspots">
            <div className="font-bold flex items-center gap-1.5 mb-1">
              <AlertTriangle className="w-3.5 h-3.5" /> Refus répétés détectés
            </div>
            <ul className="space-y-0.5">
              {refusalHotspots.map(([k, v]) => (
                <li key={k}>
                  <span className="text-white/90">{v.pseudo || '—'}</span>{' '}
                  <span className="text-white/50 font-mono">@{v.handle || '?'}</span>{' '}
                  <span className="uppercase text-white/60">({v.role})</span> →{' '}
                  <span className="font-bold text-red-300">{v.count}</span> refus / non-infractions
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {loading && <div className="text-xs text-[#A1A1AA] text-center py-6">Chargement…</div>}

          {/* --- Onglet BOT --- */}
          {!loading && tab === 'bot' && (
            <>
              <div className="flex items-center gap-1.5 flex-wrap mb-2">
                {[
                  { k: 'all', label: 'Toutes' },
                  { k: 'with_llm', label: 'Détectées par LLM' },
                  { k: 'high_score', label: 'Score ≥ 70' },
                ].map((f) => (
                  <button
                    key={f.k}
                    onClick={() => setBotFilter(f.k)}
                    data-testid={`bot-filter-${f.k}`}
                    className={`text-[10px] px-2 py-1 rounded-sm border ${
                      botFilter === f.k
                        ? 'bg-[#E4FF00]/20 border-[#E4FF00]/60 text-[#E4FF00]'
                        : 'text-[#A1A1AA] border-white/15'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              {filteredBot.length === 0 && <div className="text-xs text-[#71717A] text-center py-6">Aucune alerte bot.</div>}
              {filteredBot.map((a, i) => (
                <BotAlertRow key={a.alert_id || i} alert={a} idx={i} />
              ))}
            </>
          )}

          {/* --- Onglet STAFF --- */}
          {!loading && tab === 'staff' && (
            <>
              {staffDecisions.length === 0 && <div className="text-xs text-[#71717A] text-center py-6">Aucune décision staff.</div>}
              {staffDecisions.map((d, i) => {
                const meta = DECISION_LABEL[d.decision] || DECISION_LABEL.accept;
                const rm = ROLE_META[d.actor_role] || null;
                return (
                  <div
                    key={d.decision_id || i}
                    data-testid={`staff-decision-${i}`}
                    className="bg-black/30 border border-white/10 rounded-sm p-2.5 flex items-center gap-3 flex-wrap"
                  >
                    <span className={`text-[11px] px-2 py-0.5 rounded-sm border ${meta.color} ${meta.border} ${meta.bg} uppercase font-bold`}>{meta.label}</span>
                    {rm && (
                      <span className={`text-[10px] uppercase inline-flex items-center gap-1 ${rm.color}`}>
                        <rm.Icon className="w-3 h-3" /> {rm.label}
                      </span>
                    )}
                    <span className="text-xs text-white truncate max-w-[180px]">{d.actor_pseudo || '—'}</span>
                    {d.actor_public_handle && (
                      <span className="text-[10px] text-white/40 font-mono">@{d.actor_public_handle}</span>
                    )}
                    {d.note && <span className="text-[10px] text-white/60 truncate max-w-[300px]">« {d.note} »</span>}
                    <span className="text-[10px] text-[#71717A] ml-auto">{new Date(d.created_at).toLocaleString()}</span>
                  </div>
                );
              })}
            </>
          )}

          {/* --- Onglet ANONYMAT (héritage) --- */}
          {!loading && tab === 'anon' && (
            <>
              {anonymityEntries.length === 0 && <div className="text-xs text-[#71717A] text-center py-6">Aucun événement.</div>}
              {anonymityEntries.map((e, i) => {
                const mm = MODE_META[e.mode] || { label: e.mode, Icon: Moon, color: 'text-white/60' };
                const rm = ROLE_META[e.actor_role] || null;
                const MIcon = mm.Icon;
                return (
                  <div
                    key={`${e.actor_key_id}-${e.ts}-${i}`}
                    data-testid={`journal-entry-${i}`}
                    className="bg-black/30 border border-white/10 rounded-sm p-2.5 flex items-center gap-3 flex-wrap"
                  >
                    <MIcon className={`w-4 h-4 ${mm.color}`} />
                    <span className={`text-[11px] font-bold uppercase ${mm.color}`}>{mm.label}</span>
                    <span className={`text-[11px] px-1.5 py-0.5 rounded-sm border ${e.enabled ? 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' : 'text-red-300 border-red-400/40 bg-red-400/10'}`}>
                      {e.enabled ? 'ACTIVÉ' : 'DÉSACTIVÉ'}
                    </span>
                    {rm && (
                      <span className={`text-[10px] uppercase inline-flex items-center gap-1 ${rm.color}`}>
                        <rm.Icon className="w-3 h-3" /> {rm.label}
                      </span>
                    )}
                    <span className="text-xs text-white truncate max-w-[180px]">{e.actor_pseudo || '—'}</span>
                    {e.actor_public_handle && (
                      <span className="text-[10px] text-white/40 font-mono">@{e.actor_public_handle}</span>
                    )}
                    <span className="text-[10px] text-[#71717A] ml-auto">{new Date(e.ts).toLocaleString()}</span>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function BotAlertRow({ alert, idx }) {
  const ll = alert.layer_local || {};
  const llm = alert.layer_llm || null;
  const hasLLM = !!(llm && !llm.error);
  const llmError = !!(llm && llm.error);
  return (
    <div
      data-testid={`bot-alert-${idx}`}
      className="bg-black/30 border border-white/10 rounded-sm p-2.5"
    >
      <div className="flex items-center gap-2 flex-wrap mb-1.5">
        <Bot className="w-3.5 h-3.5 text-[#E4FF00]" />
        <span className="text-[11px] uppercase font-bold text-white">#{alert.group_type}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-sm border border-red-400/40 bg-red-400/10 text-red-300 font-bold">
          Score {alert.score || 0}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-sm border ${
          alert.state === 'resolved'
            ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
            : alert.state === 'assigned' ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
            : 'border-amber-400/40 bg-amber-400/10 text-amber-300'
        }`}>{alert.state}</span>
        <span className="text-[10px] text-[#71717A] ml-auto">{new Date(alert.created_at).toLocaleString()}</span>
      </div>
      {/* Couche déterministe */}
      <div className="border border-white/10 rounded-sm px-2 py-1.5 mb-1 bg-white/[0.02]" data-testid={`bot-alert-${idx}-layer-local`}>
        <div className="text-[10px] uppercase tracking-widest text-cyan-300 mb-0.5 flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> Couche déterministe (règles)
        </div>
        <div className="text-[11px] text-white/80">
          Score : <span className="font-mono text-cyan-200">{ll.score ?? 0}</span> — Raisons :{' '}
          {(ll.reasons || []).length ? ll.reasons.join(', ') : '—'}
        </div>
      </div>
      {/* Couche LLM */}
      <div className={`border rounded-sm px-2 py-1.5 ${
        hasLLM ? 'border-fuchsia-400/30 bg-fuchsia-400/[0.03]'
              : (llmError ? 'border-red-400/20 bg-red-400/5' : 'border-white/5 bg-white/[0.01]')
      }`} data-testid={`bot-alert-${idx}-layer-llm`}>
        <div className={`text-[10px] uppercase tracking-widest mb-0.5 flex items-center gap-1 ${
          hasLLM ? 'text-fuchsia-300' : (llmError ? 'text-red-300' : 'text-white/50')
        }`}>
          <Sparkles className="w-3 h-3" /> Couche LLM (harcèlement subtil)
        </div>
        {hasLLM ? (
          <div className="text-[11px] text-white/80">
            Score : <span className="font-mono text-fuchsia-200">{llm.score ?? 0}</span> —{' '}
            {llm.is_suspicious ? (
              <span className="text-fuchsia-300 font-bold">Suspect</span>
            ) : (
              <span className="text-white/50">Rien à signaler</span>
            )}
            {(llm.reasons || []).length > 0 && (
              <span className="text-white/60"> — {llm.reasons.join(', ')}</span>
            )}
          </div>
        ) : llmError ? (
          <div className="text-[11px] text-red-300/80">Non exécutée : {llm.error}</div>
        ) : (
          <div className="text-[11px] text-white/50">Non exécutée sur cette alerte.</div>
        )}
      </div>
    </div>
  );
}
