import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Shield, FlaskConical, Play, Trash2, LogIn, LogOut, Crown, ShieldCheck, User, Eye, Ban, VolumeX } from 'lucide-react';
import {
  withCreatorProof, enterSandboxIdentity, exitSandboxIdentity, getSandboxSlug,
} from '../lib/deviceIdentity';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ROLE_ICON = {
  owner: Crown, delegate: Crown, admin: ShieldCheck, modo: Shield,
  approved: User, pending: User, guest: Eye, muted: VolumeX, excluded: Ban, banned: Ban,
};

export default function Sandbox() {
  const navigate = useNavigate();
  const [isOwner, setIsOwner] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [incarnations, setIncarnations] = useState([]);
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState(getSandboxSlug());

  const load = useCallback(async () => {
    try {
      const body = await withCreatorProof(API, axios, {});
      const st = await axios.post(`${API}/ownership/status`, body);
      setIsOwner(!!st.data?.is_owner);
      if (!st.data?.is_owner) return;
      const b2 = await withCreatorProof(API, axios, {});
      const s = await axios.post(`${API}/sandbox/status`, b2);
      setEnabled(!!s.data?.enabled);
      setAccounts(s.data?.accounts || []);
    } catch (e) {
      setIsOwner(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const seed = async () => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/sandbox/seed`, body);
      setIncarnations(r.data?.incarnations || []);
      try { localStorage.setItem('cf_sandbox_incarnations', JSON.stringify(r.data?.incarnations || [])); } catch (_) {}
      toast.success(`${r.data?.created?.length || 0} profils de test créés`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec du seed');
    } finally { setBusy(false); }
  };

  const teardown = async () => {
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/sandbox/teardown`, body);
      exitSandboxIdentity(); setCurrent(null);
      setIncarnations([]); setAccounts([]);
      try { localStorage.removeItem('cf_sandbox_incarnations'); } catch (_) {}
      toast.success('Sandbox nettoyé');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec du teardown');
    } finally { setBusy(false); }
  };

  const incarnate = (inc) => {
    enterSandboxIdentity({ slug: inc.slug, keyId: inc.key_id, privateJwk: inc.private_jwk, publicJwk: inc.public_jwk });
    setCurrent(inc.slug);
    toast.success(`Tu incarnes désormais : ${inc.slug}`);
    navigate('/dashboard');
  };

  const stopIncarnation = () => {
    exitSandboxIdentity(); setCurrent(null);
    toast.message('Retour à ton identité propriétaire réelle');
  };

  // Merge accounts (from status) with incarnations (from last seed, has private keys).
  const savedInc = (() => {
    try { return JSON.parse(localStorage.getItem('cf_sandbox_incarnations') || '[]'); } catch (_) { return []; }
  })();
  const incList = incarnations.length ? incarnations : savedInc;
  const incBySlug = Object.fromEntries(incList.map((i) => [i.slug, i]));

  if (isOwner === null) {
    return <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center">Vérification…</div>;
  }
  if (!isOwner) {
    return (
      <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center p-6" data-testid="sandbox-denied">
        <div className="max-w-md text-center space-y-3">
          <Shield className="w-10 h-10 text-red-400 mx-auto" />
          <h1 className="text-xl font-bold">Accès réservé au propriétaire réel</h1>
          <p className="text-sm text-[#A1A1AA]">Cet environnement de test n'est accessible qu'aux appareils propriétaires de l'espace.</p>
          <button onClick={() => navigate('/dashboard')} className="px-4 py-2 border border-white/20 rounded-sm text-sm">Retour</button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6" data-testid="sandbox-page">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <FlaskConical className="w-7 h-7 text-cyan-400" />
          <div>
            <h1 className="text-2xl font-['Chivo'] font-bold">Environnement de test (Sandbox)</h1>
            <p className="text-sm text-[#A1A1AA]">Incarne n'importe quel profil pour tester toutes les vues et interactions. Données 100% isolées.</p>
          </div>
        </div>

        {!enabled && (
          <div className="border border-amber-500/40 bg-amber-500/10 rounded-sm p-4 text-sm text-amber-200" data-testid="sandbox-disabled-banner">
            Le mode test est désactivé (variable serveur <code>CODEFORGE_TEST_MODE</code> requise). Il doit rester désactivé en production.
          </div>
        )}

        {current && (
          <div className="border border-cyan-400/50 bg-cyan-500/10 rounded-sm p-4 flex items-center justify-between" data-testid="sandbox-active-banner">
            <span className="text-sm text-cyan-200">Incarnation active : <b>{current}</b></span>
            <button onClick={stopIncarnation} data-testid="sandbox-stop-incarnation" className="inline-flex items-center gap-2 px-3 py-1.5 border border-cyan-400/40 text-cyan-200 rounded-sm text-sm hover:bg-cyan-500/20">
              <LogOut className="w-4 h-4" /> Quitter l'incarnation
            </button>
          </div>
        )}

        <div className="flex gap-3">
          <button onClick={seed} disabled={busy || !enabled} data-testid="sandbox-seed-btn" className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-500/15 border border-cyan-400/40 text-cyan-200 rounded-sm text-sm hover:bg-cyan-500/25 disabled:opacity-50">
            <Play className="w-4 h-4" /> Générer / réinitialiser les profils
          </button>
          <button onClick={teardown} disabled={busy || !enabled} data-testid="sandbox-teardown-btn" className="inline-flex items-center gap-2 px-4 py-2 border border-red-400/40 text-red-300 rounded-sm text-sm hover:bg-red-500/10 disabled:opacity-50">
            <Trash2 className="w-4 h-4" /> Supprimer le sandbox
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {accounts.map((a) => {
            const Icon = ROLE_ICON[a.sandbox_slug] || User;
            const inc = incBySlug[a.sandbox_slug];
            return (
              <div key={a.key_id} data-testid={`sandbox-account-${a.sandbox_slug}`} className="border border-white/10 bg-white/[0.03] rounded-sm p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4 text-cyan-300" />
                  <span className="font-bold text-sm">{a.pseudo}</span>
                </div>
                <div className="text-xs text-[#A1A1AA]">
                  Rôle : {a.role}{a.staff_kind ? ` · ${a.staff_kind}` : ''}
                  {a.muted ? ' · muté' : ''}{a.exclude_until ? ' · exclu' : ''}{a.banned ? ' · banni' : ''}
                </div>
                <button
                  onClick={() => inc ? incarnate(inc) : toast.error('Relance « Générer les profils » pour obtenir les clés d\'incarnation.')}
                  data-testid={`sandbox-incarnate-${a.sandbox_slug}`}
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-cyan-500/15 border border-cyan-400/40 text-cyan-200 rounded-sm text-xs hover:bg-cyan-500/25"
                >
                  <LogIn className="w-3.5 h-3.5" /> Incarner ce profil
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
