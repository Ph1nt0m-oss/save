import React, { useState } from 'react';
import axios from 'axios';
import { ShieldAlert, X, Eye, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../contexts/LanguageContext';
import { IrisFullscreenWizard } from './BiometricEnrollmentField';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter77 — Theft recovery via Iris EXACTEMENT comme l'inscription.
 *
 * Plus de WebAuthn / Email Gmail. La personne tape l'email de son compte volé,
 * lance le wizard iris (anti-photo, plein écran) et le backend révoque toutes
 * les sessions de l'email. Aucun email envoyé (un voleur pourrait y accéder).
 */
export default function TheftRecoveryDialog({ open, onClose }) {
  const { t } = useLanguage();
  const [email, setEmail] = useState('');
  const [irisOpen, setIrisOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [doneCount, setDoneCount] = useState(null);

  if (!open) return null;

  const launchIris = () => {
    setErr('');
    if (!email.includes('@')) { setErr('Email invalide.'); return; }
    setIrisOpen(true);
  };

  const handleIrisDone = async (hashes) => {
    setIrisOpen(false);
    setBusy(true);
    setErr('');
    try {
      const r = await axios.post(`${API}/auth/theft-iris-verify`, {
        token: null,
        email: email.trim(),
        hashes,
      });
      setDoneCount(r.data?.revoked_count || 0);
      toast.success('Iris confirmé.');
      setTimeout(() => { onClose?.(); window.location.reload(); }, 1500);
    } catch (e) {
      setErr(e?.response?.data?.detail || 'Vérification iris échouée.');
    } finally {
      setBusy(false);
    }
  };

  if (irisOpen) {
    return (
      <IrisFullscreenWizard
        onCancel={() => setIrisOpen(false)}
        onDone={handleIrisDone}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4" onClick={onClose} data-testid="theft-dialog">
      <div onClick={(e) => e.stopPropagation()} className="max-w-md w-full bg-[#0A0A0A] border border-red-400/40 rounded-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-400" />
            <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('theft_title') || 'Déclarer un vol'}</h2>
          </div>
          <button onClick={onClose} className="text-[#A1A1AA] hover:text-white" data-testid="theft-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {doneCount === null ? (
          <>
            <p className="text-xs text-[#A1A1AA] leading-relaxed">
              Confirme ton identité par <strong>iris uniquement</strong>. Aucun email ne sera envoyé — un voleur peut accéder à ta boîte mail, pas à tes yeux.
            </p>
            <div className="text-left">
              <label className="block text-xs text-[#A1A1AA] mb-1">Email du compte volé</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ton@email.com"
                data-testid="theft-email-input"
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white placeholder:text-[#71717A] focus:outline-none focus:border-[#00D4FF]"
                disabled={busy}
              />
            </div>
            <button
              onClick={launchIris}
              disabled={busy || !email.includes('@')}
              data-testid="theft-iris-launch"
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-[#00D4FF] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm disabled:opacity-50"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              Lancer l'identification iris
            </button>
            {err && <p className="text-xs text-red-300" data-testid="theft-err">{err}</p>}
          </>
        ) : (
          <p className="text-sm text-emerald-300 text-center" data-testid="theft-done">
            {doneCount > 0
              ? `${doneCount} appareil${doneCount > 1 ? 's' : ''} révoqué${doneCount > 1 ? 's' : ''}. Tu peux te reconnecter.`
              : 'Iris vérifié. Redirection…'}
          </p>
        )}
      </div>
    </div>
  );
}
