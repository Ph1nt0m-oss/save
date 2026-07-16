/**
 * iter131 — Page « Mes IA » (Registre des IA)
 *
 * Liste les fiches d'identité de toutes les IA du site (13 agents documentés
 * dans `/app/backend/agents/registry.py`). Accessible aux créa/admin/modo
 * pour transparence. Fetch `/api/agents/registry`.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Bot, Wrench, Ban, Layers, Sparkles, Cpu } from 'lucide-react';
import { Button } from '../components/ui/button';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KIND_COLOR = {
  router: 'text-slate-300 border-slate-400/40',
  chat: 'text-cyan-300 border-cyan-400/40',
  dev: 'text-[#E4FF00] border-[#E4FF00]/40',
  planner: 'text-fuchsia-300 border-fuchsia-400/40',
  caly_help: 'text-pink-300 border-pink-400/40',
  app_builder: 'text-orange-300 border-orange-400/40',
  orchestrator: 'text-emerald-300 border-emerald-400/40',
  wizard: 'text-amber-300 border-amber-400/40',
  ocr_device: 'text-blue-300 border-blue-400/40',
  attachment_analyst: 'text-violet-300 border-violet-400/40',
  translator: 'text-teal-300 border-teal-400/40',
  enhancement_advisor: 'text-lime-300 border-lime-400/40',
  community_bots: 'text-rose-300 border-rose-400/40',
};

export default function PrivateAgentRegistry() {
  const navigate = useNavigate();
  const device = useDeviceIdentity();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const allowed = device.role === 'creator' || device.staffKind === 'admin' || device.staffKind === 'modo';

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/agents/registry`, { withCredentials: true });
        if (!cancelled) setAgents(r.data?.agents || []);
      } catch (e) {
        if (!cancelled) setError(e.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!allowed) {
    return (
      <div data-testid="agent-registry-access-denied" className="min-h-screen bg-[#050505] text-white flex items-center justify-center p-8">
        <div className="max-w-md text-center border border-red-400/30 rounded-sm bg-red-400/5 p-8">
          <Ban className="w-12 h-12 mx-auto mb-4 text-red-400" />
          <h1 className="text-2xl font-['Chivo'] font-bold mb-2">Accès refusé</h1>
          <p className="text-sm text-[#A1A1AA] mb-4">Cette page est réservée à la créatrice et au staff.</p>
          <Button data-testid="registry-back-btn" onClick={() => navigate('/dashboard')} className="bg-[#E4FF00] text-[#050505] hover:bg-[#C8E000]">Retour</Button>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="agent-registry-page" className="min-h-screen bg-[#050505] text-white p-4 sm:p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <button
              data-testid="registry-back-dashboard-btn"
              onClick={() => navigate('/dashboard')}
              className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-white mb-2"
            >
              <ArrowLeft className="w-4 h-4" /> Retour dashboard
            </button>
            <h1 className="text-3xl sm:text-4xl font-['Chivo'] font-black tracking-tight">
              Mes IA <span className="text-[#E4FF00]">·</span> Registre des agents
            </h1>
            <p className="text-sm text-[#A1A1AA] mt-1">
              Transparence complète des {agents.length || '…'} agents intelligents actifs sur CodeForge AI. Chaque agent garde son propre rôle et son prompt système.
            </p>
          </div>
          <Sparkles className="hidden sm:block w-12 h-12 text-[#E4FF00]/40" />
        </div>

        {loading && (
          <div data-testid="registry-loading" className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-[#E4FF00] border-t-transparent rounded-full animate-spin"></div>
            <p className="mt-3 text-sm text-[#A1A1AA]">Chargement du registre…</p>
          </div>
        )}

        {error && (
          <div data-testid="registry-error" className="border border-red-400/30 bg-red-400/5 rounded-sm p-4 text-sm text-red-300">
            Erreur : {error}
          </div>
        )}

        {!loading && !error && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {agents.map((a) => {
              const color = KIND_COLOR[a.id] || 'text-white border-white/20';
              return (
                <div
                  key={a.id}
                  data-testid={`agent-card-${a.id}`}
                  className={`border rounded-sm bg-[#0F0F13] p-5 hover:bg-[#141419] transition-colors ${color.split(' ')[1]}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Bot className={`w-5 h-5 ${color.split(' ')[0]}`} />
                      <h2 className={`text-lg font-['Chivo'] font-bold ${color.split(' ')[0]}`}>{a.name}</h2>
                    </div>
                    <code className="text-[10px] text-[#71717A] font-mono">{a.id}</code>
                  </div>

                  <p className="text-sm text-white/90 mb-3">{a.objectif}</p>

                  <div className="space-y-2 text-xs">
                    <Row label="Utilisateur cible" value={a.utilisateur} />
                    <Row label="Expertise" value={a.expertise} />
                    <Row label="Raisonnement" value={a.raisonnement} />
                    <Row label="Format" value={a.format} muted mono />
                    {Array.isArray(a.outils) && a.outils.length > 0 && (
                      <div>
                        <span className="text-[#71717A] uppercase tracking-widest text-[10px]">Outils</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {a.outils.map((t, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 border border-white/10 rounded-sm text-[10px] text-[#D4D4D8]">
                              <Wrench className="w-2.5 h-2.5" /> {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <Row label="Limites" value={a.limites} muted />
                    <Row label="Module" value={a.module} mono muted />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-8 text-center text-xs text-[#71717A]">
          <p className="inline-flex items-center gap-1"><Layers className="w-3 h-3" /> Règle absolue : interdiction de fusion des personnalités. Chaque IA garde son propre prompt système et son propre rôle.</p>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, muted = false, mono = false }) {
  if (!value) return null;
  return (
    <div>
      <span className="text-[#71717A] uppercase tracking-widest text-[10px]">{label}</span>
      <div className={`${mono ? 'font-mono' : ''} ${muted ? 'text-[#A1A1AA]' : 'text-white'} text-xs break-words`}>
        {value}
      </div>
    </div>
  );
}
