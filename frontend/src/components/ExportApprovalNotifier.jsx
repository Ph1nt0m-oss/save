import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Eye, X } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Creator-side modal that surfaces pending export requests one at a time,
 * lets the creator open the related account for review, then approve/reject.
 */
export default function ExportApprovalNotifier({ onOpenAccount }) {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const isCreator = device.role === 'creator' && device.viewMode !== 'guest';
  const [pending, setPending] = useState([]);

  useEffect(() => {
    if (!isCreator || !device.keyId) return undefined;
    let cancelled = false;
    const tick = async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/exports/pending`, body);
        if (!cancelled) setPending(r.data?.requests || []);
      } catch (_) {}
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => { cancelled = true; clearInterval(id); };
  }, [isCreator, device.keyId]);

  if (!isCreator || pending.length === 0) return null;
  const req = pending[0];

  const decide = async (decision) => {
    try {
      const body = await withCreatorProof(API, axios, { request_id: req.request_id, decision });
      await axios.post(`${API}/exports/decide`, body);
      setPending((ps) => ps.filter((p) => p.request_id !== req.request_id));
      toast.success(decision === 'approve' ? t('exp_approved_title') : t('exp_rejected_title'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  return (
    <div className="fixed inset-0 z-[88] flex items-center justify-center bg-black/70 p-4" data-testid="export-approval-modal">
      <div className="max-w-md w-full bg-[#0A0A0A] border border-amber-400/40 rounded-sm p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Eye className="w-5 h-5 text-amber-300" />
          <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('exp_review_title')}</h2>
          <button onClick={() => setPending((ps) => ps.slice(1))} className="ml-auto text-[#A1A1AA] hover:text-white" aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <div className="bg-black/30 border border-white/10 rounded-sm p-3 text-xs space-y-1">
          <div><span className="text-[#71717A]">From:</span> <span className="text-white">{req.label || req.key_id.slice(0, 14)}</span></div>
          <div><span className="text-[#71717A]">Project:</span> <code className="text-white">{req.project_id}</code></div>
          <div><span className="text-[#71717A]">Kind:</span> <span className="text-[#E4FF00] uppercase">{req.export_kind}</span></div>
          <div className="text-[10px] text-[#71717A]">{new Date(req.created_at).toLocaleString()}</div>
        </div>
        <button
          type="button"
          onClick={() => { onOpenAccount?.({ key_id: req.key_id, project_id: req.project_id }); }}
          data-testid="exp-review-open"
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/10 rounded-sm font-['Chivo'] font-bold text-xs transition"
        >
          <Eye className="w-3.5 h-3.5" />{t('exp_review_open')}
        </button>
        <div className="flex flex-col gap-2">
          <button onClick={() => decide('approve')} data-testid="exp-approve-btn" className="w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/40 text-emerald-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition">
            <CheckCircle className="w-4 h-4" />{t('exp_review_approve')}
          </button>
          <button onClick={() => decide('reject')} data-testid="exp-reject-btn" className="w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 bg-red-500/15 hover:bg-red-500/25 border border-red-400/40 text-red-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition">
            <XCircle className="w-4 h-4" />{t('exp_review_reject')}
          </button>
        </div>
      </div>
    </div>
  );
}
