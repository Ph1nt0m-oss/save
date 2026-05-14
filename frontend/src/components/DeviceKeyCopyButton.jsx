import React, { useEffect, useState } from 'react';
import { Key, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { exportPublicKeyShareCode } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Small icon button that lets any visitor (Login page) copy their own
 * device public key. Required when the creator asks the user to share
 * their key so she can approve it from the device manager.
 */
export default function DeviceKeyCopyButton() {
  const { t } = useLanguage();
  const [code, setCode] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let mounted = true;
    exportPublicKeyShareCode().then((c) => { if (mounted) setCode(c); }).catch(() => {});
    return () => { mounted = false; };
  }, []);

  const copy = async () => {
    if (!code) {
      toast.info(t('dm_no_key_yet') || 'Clé en cours de génération…');
      return;
    }
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      toast.success(t('prof_key_copied') || 'Clé copiée.');
    } catch (_) {
      toast.error(t('dm_copy_failed') || 'Impossible de copier.');
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      data-testid="device-key-copy-btn"
      title={t('prof_my_device_key') || 'Copier ma clé d\'appareil'}
      className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-emerald-300 hover:border-emerald-400/40 transition-colors"
    >
      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Key className="w-4 h-4" />}
    </button>
  );
}
