import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Plus, Loader2 } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';
import useViewSpec from '../hooks/useViewSpec';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SEVERITY_COLORS = {
  low: 'text-emerald-300 bg-emerald-500/10 border-emerald-400/30',
  medium: 'text-amber-300 bg-amber-500/10 border-amber-400/30',
  high: 'text-orange-300 bg-orange-500/10 border-orange-400/30',
  critical: 'text-rose-300 bg-rose-500/10 border-rose-400/30',
};
const STATUS_COLORS = {
  open: 'text-rose-300 bg-rose-500/10',
  in_progress: 'text-cyan-300 bg-cyan-500/10',
  resolved: 'text-emerald-300 bg-emerald-500/10',
  wontfix: 'text-[#71717A] bg-white/[0.04]',
};

export default function SiteIssues() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  const { canSeeProgramming } = useViewSpec();
  const isInSimulation = device.viewMode && device.viewMode !== 'creator';
  const allowed = canSeeProgramming && !isInSimulation;

  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ title: '', description: '', severity: 'medium' });
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/site/issues?limit=200`);
      setIssues(r.data?.issues || []);
    } catch { toast.error('Impossible de charger les issues'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const createIssue = async () => {
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      const body = await withCreatorProof(API, axios, form);
      await axios.post(`${API}/site/issues/create`, body);
      toast.success('Issue créée');
      setForm({ title: '', description: '', severity: 'medium' });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec création');
    } finally { setCreating(false); }
  };

  const updateStatus = async (issue_id, status) => {
    try {
      const body = await withCreatorProof(API, axios, { issue_id, status });
      await axios.post(`${API}/site/issues/update`, body);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Échec maj'); }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/dashboard')}
            className="text-[#A1A1AA] hover:text-white text-sm inline-flex items-center gap-1"
            data-testid="issues-back">
            <ArrowLeft className="w-4 h-4" /> {t('back')}
          </button>
          <h1 className="text-2xl font-['Chivo'] font-black inline-flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-rose-400" /> Problèmes du site
          </h1>
        </div>

        {!allowed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-sm p-8 text-center max-w-md mx-auto">
            <h2 className="text-lg font-bold text-red-200 mb-2">{t('prog_access_denied')}</h2>
            <p className="text-sm text-red-100/90">{t('prog_access_body')}</p>
            <p className="text-xs text-amber-200/90 mt-3">{t('prog_access_hint')}</p>
          </div>
        ) : (
          <>
            {/* Création d'issue */}
            <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-4 mb-6 space-y-2" data-testid="issue-create-form">
              <h2 className="font-['Chivo'] font-bold text-sm text-rose-300">Nouvelle issue</h2>
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Titre du problème (ex: SyntaxError dans PrivateProgramming.js)"
                data-testid="issue-title-input"
                className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-1.5 text-xs focus:outline-none focus:border-rose-400"
              />
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={6}
                placeholder="Description, traceback, étapes pour reproduire…"
                data-testid="issue-desc-input"
                className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-rose-400 resize-none"
              />
              <div className="flex items-center gap-2">
                <select
                  value={form.severity}
                  onChange={(e) => setForm({ ...form, severity: e.target.value })}
                  data-testid="issue-severity-select"
                  className="bg-[#050505] border border-white/10 rounded-sm px-2 py-1.5 text-xs">
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
                <button onClick={createIssue} disabled={creating || !form.title.trim()}
                  data-testid="issue-create-btn"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-rose-500 hover:bg-rose-400 disabled:opacity-40 text-white rounded-sm">
                  {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Ajouter
                </button>
              </div>
            </div>

            {/* Liste des issues */}
            <div className="space-y-2" data-testid="issues-list">
              {loading ? (
                <Loader2 className="w-6 h-6 mx-auto mt-12 animate-spin text-rose-400" />
              ) : issues.length === 0 ? (
                <div className="text-center py-12 text-[#71717A] text-sm">Aucune issue. Tout va bien 🎉</div>
              ) : (
                issues.map((iss) => (
                  <div key={iss.issue_id} data-testid={`issue-${iss.issue_id}`}
                    className="bg-[#0A0A0A] border border-white/10 rounded-sm p-3">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h3 className="font-bold text-sm text-white flex-1 break-words">{iss.title}</h3>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-sm border ${SEVERITY_COLORS[iss.severity] || SEVERITY_COLORS.medium}`}>
                        {iss.severity}
                      </span>
                      <select
                        value={iss.status}
                        onChange={(e) => updateStatus(iss.issue_id, e.target.value)}
                        data-testid={`issue-status-${iss.issue_id}`}
                        className={`text-[10px] px-1.5 py-0.5 rounded-sm border-0 ${STATUS_COLORS[iss.status] || STATUS_COLORS.open}`}>
                        <option value="open">Open</option>
                        <option value="in_progress">In progress</option>
                        <option value="resolved">Resolved</option>
                        <option value="wontfix">Won't fix</option>
                      </select>
                    </div>
                    {iss.description && (
                      <pre className="text-[10px] text-[#A1A1AA] whitespace-pre-wrap break-all font-mono max-h-40 overflow-y-auto mt-2">{iss.description}</pre>
                    )}
                    <div className="text-[10px] text-[#71717A] mt-1">
                      {new Date(iss.created_at).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
