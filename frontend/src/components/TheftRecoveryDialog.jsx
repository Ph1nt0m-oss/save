import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Fingerprint, X, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { isWebAuthnSupported, webauthnGet } from '../lib/webauthnClient';
import { getCachedKeyId } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Modal triggered from the login page — confirms the user's biometric and,
 * on success, revokes all other creator devices and promotes the calling
 * device to creator. After success, the page is reloaded so the new role
 * is picked up by useDeviceIdentity.
 */
export default function TheftRecoveryDialog({ open, onClose }) {
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const [hasEnrollment, setHasEnrollment] = useState(true);

  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/webauthn/has-enrollment`).then((r) => {
      setHasEnrollment(!!r.data?.has_any);
    }).catch(() => setHasEnrollment(false));
  }, [open]);

  const handleVerify = async () => {
    if (!isWebAuthnSupported()) {
      toast.error(t('theft_unavailable'));
      return;
    }
    const keyId = getCachedKeyId();
    if (!keyId) {
      toast.error(t('dm_invalid_code'));
      return;
    }
    setBusy(true);
    try {
      const origin = window.location.origin;
      const optsRes = await axios.post(`${API}/webauthn/declare-theft-options`, {
        key_id: keyId, origin,
      });
      const credential = await webauthnGet(optsRes.data);
      const verifyRes = await axios.post(`${API}/webauthn/declare-theft-verify`, {
        key_id: keyId, origin, credential,
      });
      toast.success(t('theft_revoke_success').replace('{n}', String(verifyRes.data?.revoked_count || 0)));
      onClose?.();
      // Hard reload so role + canWrite refresh everywhere.
      setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e?.message || t('theft_revoke_failed'));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      onClick={onClose}
      data-testid="theft-dialog"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-w-md w-full bg-[#0A0A0A] border border-red-400/40 rounded-sm p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-400" />
            <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('theft_title')}</h2>
          </div>
          <button onClick={onClose} className="text-[#A1A1AA] hover:text-white" data-testid="theft-close">
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-xs text-[#A1A1AA] leading-relaxed">{t('theft_body')}</p>
        {!hasEnrollment && (
          <div className="text-[11px] text-amber-300 border border-amber-400/40 bg-amber-400/10 rounded-sm p-2.5">
            {t('theft_unavailable')}
          </div>
        )}
        <button
          onClick={handleVerify}
          disabled={busy || !hasEnrollment || !isWebAuthnSupported()}
          data-testid="theft-verify-btn"
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-red-500/15 hover:bg-red-500/25 border border-red-400/40 text-red-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Fingerprint className="w-4 h-4" />
          {busy ? '…' : t('theft_verify')}
        </button>
      </div>
    </div>
  );
}
