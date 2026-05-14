import React, { useState } from 'react';
import axios from 'axios';
import { Fingerprint } from 'lucide-react';
import { toast } from 'sonner';
import { isWebAuthnSupported, webauthnCreate } from '../lib/webauthnClient';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Creator-only button — enrolls a platform biometric (Touch ID / Face ID /
 * Windows Hello / Android fingerprint) that can later be used to recover
 * access via the "Declare theft" flow on the login page.
 */
export default function BiometricEnrollButton() {
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);

  const handleEnroll = async () => {
    if (!isWebAuthnSupported()) {
      toast.error(t('theft_unavailable'));
      return;
    }
    setBusy(true);
    try {
      const origin = window.location.origin;
      const body = await withCreatorProof(API, axios, { origin });
      const optsRes = await axios.post(`${API}/webauthn/register-options`, body);
      const credential = await webauthnCreate(optsRes.data);
      const verifyBody = await withCreatorProof(API, axios, { origin, credential });
      await axios.post(`${API}/webauthn/register-verify`, verifyBody);
      toast.success(t('theft_enroll_success'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || e?.message || t('theft_enroll_failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleEnroll}
      disabled={busy}
      data-testid="biometric-enroll-btn"
      className="inline-flex items-center gap-2 px-3 py-1.5 bg-[#E4FF00]/10 border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20 rounded-sm text-xs font-['Chivo'] font-bold transition disabled:opacity-60"
    >
      <Fingerprint className="w-3.5 h-3.5" />
      {busy ? '…' : t('theft_enroll')}
    </button>
  );
}
