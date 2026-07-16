/**
 * iter131 — Page « Intégrations Tierces » (Créa-only)
 *
 * Slots UI pour brancher Stripe, Google et ChatGPT. Version gratuite : les
 * clés saisies sont stockées en base et un test syntaxique est disponible ;
 * aucun paiement/appel externe réel n'est déclenché.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Plug, CheckCircle2, XCircle, Loader2, Save, TestTube, ExternalLink, Ban } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_BADGE = {
  connected: { color: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10', Icon: CheckCircle2, label: 'Connecté' },
  configured: { color: 'text-amber-300 border-amber-400/40 bg-amber-400/10', Icon: Plug, label: 'Configuré' },
  disconnected: { color: 'text-red-300 border-red-400/40 bg-red-400/10', Icon: XCircle, label: 'Déconnecté' },
};

const HELP_LINKS = {
  stripe: { label: 'Dashboard Stripe', url: 'https://dashboard.stripe.com/test/apikeys' },
  google: { label: 'Google Cloud Console', url: 'https://console.cloud.google.com/apis/credentials' },
  chatgpt: { label: 'OpenAI API Keys', url: 'https://platform.openai.com/api-keys' },
};

export default function PrivateIntegrations() {
  const navigate = useNavigate();
  const device = useDeviceIdentity();
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState({}); // {integration_id: {field_key: value}}
  const [busy, setBusy] = useState(null);

  const isCreator = device.role === 'creator' && (!device.viewMode || device.viewMode === 'creator');

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/private/integrations/status`, body);
      setIntegrations(r.data?.integrations || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isCreator) loadStatus();
    else setLoading(false);
  }, [isCreator, loadStatus]);

  const setField = (iid, fk, v) => {
    setEditing((s) => ({ ...s, [iid]: { ...(s[iid] || {}), [fk]: v } }));
  };

  const save = async (integration) => {
    setBusy(`save-${integration.id}`);
    try {
      const values = editing[integration.id] || {};
      const body = await withCreatorProof(API, axios, {
        integration_id: integration.id,
        values,
        enabled: integration.enabled,
      });
      await axios.post(`${API}/private/integrations/save`, body);
      toast.success(`${integration.name} sauvegardé.`);
      setEditing((s) => ({ ...s, [integration.id]: {} }));
      await loadStatus();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Sauvegarde impossible.');
    } finally {
      setBusy(null);
    }
  };

  const test = async (integration) => {
    setBusy(`test-${integration.id}`);
    try {
      const body = await withCreatorProof(API, axios, { integration_id: integration.id });
      const r = await axios.post(`${API}/private/integrations/test`, body);
      if (r.data?.ok) toast.success(r.data.message);
      else toast.warning(r.data?.message || 'Test échoué');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Test impossible.');
    } finally {
      setBusy(null);
    }
  };

  const toggleEnabled = async (integration) => {
    setBusy(`toggle-${integration.id}`);
    try {
      const body = await withCreatorProof(API, axios, {
        integration_id: integration.id,
        values: {},
        enabled: !integration.enabled,
      });
      await axios.post(`${API}/private/integrations/save`, body);
      await loadStatus();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Impossible de basculer.');
    } finally {
      setBusy(null);
    }
  };

  if (!isCreator) {
    return (
      <div data-testid="integrations-access-denied" className="min-h-screen bg-[#050505] text-white flex items-center justify-center p-8">
        <div className="max-w-md text-center border border-red-400/30 rounded-sm bg-red-400/5 p-8">
          <Ban className="w-12 h-12 mx-auto mb-4 text-red-400" />
          <h1 className="text-2xl font-['Chivo'] font-bold mb-2">Accès refusé</h1>
          <p className="text-sm text-[#A1A1AA] mb-4">Réservé à la créatrice hors simulation.</p>
          <Button data-testid="integrations-back-btn" onClick={() => navigate('/dashboard')} className="bg-[#E4FF00] text-[#050505] hover:bg-[#C8E000]">Retour</Button>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="integrations-page" className="min-h-screen bg-[#050505] text-white p-4 sm:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <button
            data-testid="integrations-back-dashboard-btn"
            onClick={() => navigate('/dashboard')}
            className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-white mb-2"
          >
            <ArrowLeft className="w-4 h-4" /> Retour dashboard
          </button>
          <h1 className="text-3xl sm:text-4xl font-['Chivo'] font-black tracking-tight">
            Intégrations <span className="text-[#E4FF00]">·</span> Tierces
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-1">
            Branchements optionnels — <strong>version gratuite</strong> : les slots UI sont opérationnels, aucun appel externe payant n&apos;est déclenché.
          </p>
        </div>

        {loading && <div data-testid="integrations-loading" className="text-center py-10"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#E4FF00]" /></div>}
        {error && <div data-testid="integrations-error" className="border border-red-400/30 bg-red-400/5 rounded-sm p-4 text-sm text-red-300">Erreur : {error}</div>}

        {!loading && !error && (
          <div className="space-y-4">
            {integrations.map((intg) => {
              const badge = STATUS_BADGE[intg.status] || STATUS_BADGE.disconnected;
              const help = HELP_LINKS[intg.id];
              return (
                <div key={intg.id} data-testid={`integration-card-${intg.id}`} className="border border-white/10 bg-[#0F0F13] rounded-sm p-5">
                  <div className="flex items-start justify-between mb-3 gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-['Chivo'] font-bold">{intg.name}</h2>
                        <span data-testid={`integration-status-${intg.id}`} className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest border rounded-sm px-1.5 py-0.5 ${badge.color}`}>
                          <badge.Icon className="w-3 h-3" /> {badge.label}
                        </span>
                        {intg.env_present && (
                          <span title={`env ${intg.env_hint} présent`} className="text-[10px] text-emerald-300 border border-emerald-400/40 bg-emerald-400/10 rounded-sm px-1.5 py-0.5">env ✓</span>
                        )}
                      </div>
                      <p className="text-sm text-[#A1A1AA] mt-1">{intg.description}</p>
                    </div>
                    <button
                      data-testid={`integration-toggle-${intg.id}`}
                      onClick={() => toggleEnabled(intg)}
                      disabled={busy === `toggle-${intg.id}`}
                      className={`text-[10px] uppercase tracking-widest px-2 py-1 border rounded-sm ${intg.enabled ? 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' : 'text-white/50 border-white/15'}`}
                    >
                      {intg.enabled ? 'Activé' : 'Désactivé'}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                    {intg.fields.map((f) => {
                      const edited = editing[intg.id]?.[f.key];
                      const value = edited !== undefined ? edited : (f.type === 'password' ? '' : (f.masked || ''));
                      return (
                        <label key={f.key} className="block">
                          <span className="text-[10px] uppercase tracking-widest text-[#71717A]">
                            {f.label}
                            {f.has_value && <span className="ml-1 text-emerald-300">· enregistré{f.type === 'password' ? ` (${f.masked})` : ''}</span>}
                          </span>
                          <input
                            data-testid={`integration-field-${intg.id}-${f.key}`}
                            type={f.type === 'password' ? 'password' : 'text'}
                            value={value}
                            onChange={(e) => setField(intg.id, f.key, e.target.value)}
                            placeholder={f.has_value ? (f.type === 'password' ? '(gardé — remplace pour modifier)' : f.masked) : (f.type === 'password' ? '••••••' : 'Saisir…')}
                            className="w-full mt-1 bg-transparent border border-white/15 focus:border-[#E4FF00]/40 focus:outline-none px-2 py-1.5 rounded-sm text-sm text-white"
                          />
                        </label>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <Button
                      data-testid={`integration-save-${intg.id}`}
                      onClick={() => save(intg)}
                      disabled={busy === `save-${intg.id}` || !editing[intg.id] || Object.keys(editing[intg.id] || {}).length === 0}
                      className="bg-[#E4FF00] text-[#050505] hover:bg-[#C8E000] h-8 text-xs"
                    >
                      {busy === `save-${intg.id}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                      Sauvegarder
                    </Button>
                    <Button
                      data-testid={`integration-test-${intg.id}`}
                      onClick={() => test(intg)}
                      disabled={busy === `test-${intg.id}`}
                      variant="outline"
                      className="h-8 text-xs border-white/15"
                    >
                      {busy === `test-${intg.id}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <TestTube className="w-3 h-3" />}
                      Tester
                    </Button>
                    {help && (
                      <a
                        data-testid={`integration-help-${intg.id}`}
                        href={help.url}
                        target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200"
                      >
                        <ExternalLink className="w-3 h-3" /> {help.label}
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-8 text-xs text-[#71717A] italic">
          Note : Version gratuite = slot UI + validation syntaxique. Pour activer un paiement Stripe réel, un compte marchand vérifié et une clé prod (sk_live_…) sont requis. Le branchement se fera dans une prochaine itération.
        </div>
      </div>
    </div>
  );
}
