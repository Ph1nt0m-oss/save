import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Fingerprint, X, ShieldAlert, Mail, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { isWebAuthnSupported, webauthnGet } from '../lib/webauthnClient';
import { getCachedKeyId } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Theft recovery dialog — works EVERYWHERE.
 *
 * Two paths:
 *  1. Biometric (WebAuthn) — fast, no email, available when the device
 *     supports it AND a passkey has been enrolled. Calls /webauthn/declare-theft-*.
 *  2. Email fallback — when WebAuthn isn't available or the user has
 *     never enrolled a passkey. Sends a magic link to the account email;
 *     clicking it revokes all creator/approved keys on that account so
 *     the user can re-onboard fresh on the new device.
 */
export default function TheftRecoveryDialog({ open, onClose }) {
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const [hasEnrollment, setHasEnrollment] = useState(true);
  const [supported, setSupported] = useState(true);
  const [email, setEmail] = useState('');
  const [emailSent, setEmailSent] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSupported(isWebAuthnSupported());
    setEmailSent(false);
    axios.get(`${API}/webauthn/has-enrollment`).then((r) => {
      setHasEnrollment(!!r.data?.has_any);
    }).catch(() => setHasEnrollment(false));
  }, [open]);

  const handleVerify = async () => {
    if (!isWebAuthnSupported()) return;
    const keyId = getCachedKeyId();
    if (!keyId) {
      toast.error(t('dm_invalid_code'));
      return;
    }
    setBusy(true);
    try {
      const origin = window.location.origin;
      const optsRes = await axios.post(`${API}/webauthn/declare-theft-options`, { key_id: keyId, origin });
      const credential = await webauthnGet(optsRes.data);
      const verifyRes = await axios.post(`${API}/webauthn/declare-theft-verify`, { key_id: keyId, origin, credential });
      toast.success(t('theft_revoke_success').replace('{n}', String(verifyRes.data?.revoked_count || 0)));
      onClose?.();
      setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e?.message || t('theft_revoke_failed'));
    } finally { setBusy(false); }
  };

  const sendEmailFallback = async () => {
    const e = (email || '').trim().toLowerCase();
    if (!e || !/^\S+@\S+\.\S+$/.test(e)) {
      toast.error(t('theft_email_invalid'));
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/auth/theft-email-request`, { email: e });
      setEmailSent(true);
      toast.success(t('theft_email_sent'));
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('theft_revoke_failed'));
    } finally { setBusy(false); }
  };

  if (!open) return null;
  const canUseBiometric = supported && hasEnrollment;
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4" onClick={onClose} data-testid="theft-dialog">
      <div onClick={(e) => e.stopPropagation()} className="max-w-md w-full bg-[#0A0A0A] border border-red-400/40 rounded-sm p-5 space-y-4">
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

        {/* Biometric path */}
        <div className="space-y-2">
          <button
            onClick={handleVerify}
            disabled={busy || !canUseBiometric}
            data-testid="theft-verify-btn"
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-red-500/15 hover:bg-red-500/25 border border-red-400/40 text-red-200 hover:text-white rounded-sm font-['Chivo'] font-bold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Fingerprint className="w-4 h-4" />
            {busy ? '…' : t('theft_verify')}
          </button>
          {!canUseBiometric && (
            <p className="text-[10px] text-amber-300/80 leading-relaxed">{t('theft_unavailable_use_email')}</p>
          )}
        </div>

        {/* Email fallback — always shown */}
        <div className="pt-3 border-t border-white/10 space-y-2" data-testid="theft-email-fallback">
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-amber-300" />
            <span className="text-xs font-['Chivo'] font-bold text-white">{t('theft_email_title')}</span>
          </div>
          {emailSent ? (
            <p className="text-[11px] text-emerald-300">{t('theft_email_sent')}</p>
          ) : (
            <>
              <input
                type="email"
                inputMode="email"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                placeholder={t('theft_email_placeholder')}
                data-testid="theft-email-input"
                className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-xs text-white placeholder-[#71717A] focus:outline-none focus:border-amber-300"
              />
              <button
                onClick={sendEmailFallback}
                disabled={busy}
                data-testid="theft-email-send"
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 border border-amber-400/40 text-amber-200 hover:bg-amber-400/10 rounded-sm font-['Chivo'] font-bold text-xs transition disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
                {t('theft_email_send_btn')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
