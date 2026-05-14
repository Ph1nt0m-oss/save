import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Smartphone, MapPin, Check, X, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Modal that pops up whenever an authenticated user has pending session
 * requests on their account (from another device). Polls every 3s. Once
 * shown, the connected user can Approve (allow the new device) or Deny
 * (which the spec frames as "report violation").
 */
export default function SessionRequestNotifier() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [requests, setRequests] = useState([]);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    const fetchPending = async () => {
      try {
        const r = await axios.get(`${API}/auth/session-pending`, { withCredentials: true });
        if (cancelled) return;
        setRequests(r.data?.requests || []);
      } catch (_) { /* not logged in or network */ }
    };
    fetchPending();
    const id = setInterval(fetchPending, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, [user]);

  const decide = async (request_id, decision) => {
    setBusyId(request_id);
    try {
      await axios.post(`${API}/auth/session-decide`, { request_id, decision }, { withCredentials: true });
      setRequests((rs) => rs.filter((r) => r.request_id !== request_id));
      toast.success(decision === 'approve' ? t('sess_approved') : t('sess_denied'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    } finally {
      setBusyId(null);
    }
  };

  if (!user || requests.length === 0) return null;
  const req = requests[0];

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      data-testid="session-request-modal"
    >
      <div className="max-w-md w-full bg-[#0A0A0A] border border-amber-400/40 rounded-sm p-5 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-amber-300" />
          <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('sess_request_title')}</h2>
        </div>
        <p className="text-xs text-[#A1A1AA] leading-relaxed">
          {t('sess_request_body').replace('{email}', req.email || user.email || '')}
        </p>

        <div className="bg-black/40 border border-white/10 rounded-sm p-3 space-y-2 text-sm">
          <div className="flex items-start gap-2">
            <Smartphone className="w-4 h-4 text-[#E4FF00] mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-widest text-[#71717A]">{t('sess_device_label')}</div>
              <div className="text-white text-xs truncate" data-testid="sess-device-label">
                {req.requesting_label || req.requesting_key_id?.slice(0, 16) + '…'}
              </div>
            </div>
          </div>
          {req.is_gmail && (
            <div className="flex items-start gap-2">
              <MapPin className="w-4 h-4 text-amber-300 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest text-[#71717A]">{t('sess_loc_label')}</div>
                <div className="text-white text-xs truncate" data-testid="sess-location">
                  {req.location || t('sess_loc_unknown')}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => decide(req.request_id, 'approve')}
            disabled={busyId === req.request_id}
            data-testid="sess-approve-btn"
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/40 text-emerald-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            {t('sess_approve_btn')}
          </button>
          <button
            type="button"
            onClick={() => decide(req.request_id, 'deny')}
            disabled={busyId === req.request_id}
            data-testid="sess-deny-btn"
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-red-500/15 hover:bg-red-500/25 border border-red-400/40 text-red-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            {t('sess_deny_btn')}
          </button>
        </div>
      </div>
    </div>
  );
}
