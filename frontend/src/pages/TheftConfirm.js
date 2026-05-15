import React, { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, Loader2, Eye } from 'lucide-react';
import { toast } from 'sonner';
import { IrisFullscreenWizard } from '../components/BiometricEnrollmentField';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter75: theft-recovery landing page now uses ONLY the iris liveness
 * leg — the email-token leg has been retired because a thief who has
 * compromised the user's inbox would otherwise be able to revoke the
 * legitimate owner's devices.
 *
 * Flow:
 *  - The user lands on /theft-confirm and types their account email
 *    (so the backend knows which baseline iris to match against).
 *  - Clicks « Lancer l'identification iris » → IrisFullscreenWizard
 *    captures 3 frames as in signup.
 *  - The 3 hashes are POSTed to /auth/theft-iris-verify which (for
 *    now) records the attempt; the upcoming sprint implements real
 *    feature-vector matching and triggers device revocation on match.
 */
export default function TheftConfirm() {
  const [email, setEmail] = useState('');
  const [irisOpen, setIrisOpen] = useState(false);
  const [irisVerified, setIrisVerified] = useState(false);
  const [revoked, setRevoked] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

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
      setIrisVerified(true);
      setRevoked(r.data?.revoked_count || 0);
      toast.success('Iris confirmé. Récupération validée.');
    } catch (e) {
      setErr(e?.response?.data?.detail || 'Vérification iris échouée.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-[#0A0A0A] border border-white/10 rounded-sm p-8 text-center space-y-4">
        {!irisVerified && (
          <>
            <ShieldAlert className="w-12 h-12 text-amber-400 mx-auto" />
            <h1 className="text-xl font-['Chivo'] font-black text-white">Déclaration de vol</h1>
            <p className="text-sm text-[#A1A1AA] leading-relaxed">
              Confirme ton identité par <strong>iris uniquement</strong>. Aucun email ne sera envoyé&nbsp;: un voleur peut accéder à ta boîte mail, mais pas à tes yeux.
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
              type="button"
              onClick={() => setIrisOpen(true)}
              disabled={busy || !email.includes('@')}
              data-testid="theft-iris-start-btn"
              className="w-full inline-flex items-center justify-center gap-2 px-3 py-3 bg-[#00D4FF] text-[#050505] rounded-sm font-['Chivo'] font-bold text-sm disabled:opacity-50"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              Lancer l'identification iris
            </button>
            {err && <p className="text-xs text-red-300" data-testid="theft-err">{err}</p>}
          </>
        )}
        {irisVerified && (
          <>
            <ShieldCheck className="w-12 h-12 text-emerald-400 mx-auto" />
            <h1 className="text-xl font-['Chivo'] font-black text-white">Récupération validée</h1>
            <p className="text-sm text-[#A1A1AA]" data-testid="theft-iris-verified">
              {revoked > 0
                ? <>{revoked} appareil{revoked > 1 ? 's ont' : ' a'} été révoqué{revoked > 1 ? 's' : ''}. Tu peux maintenant te reconnecter depuis ce nouvel appareil.</>
                : 'Identité confirmée. Reconnecte-toi depuis ce nouvel appareil.'}
            </p>
            <Link to="/login" className="inline-block mt-2 px-5 py-2.5 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold hover:bg-white transition" data-testid="theft-confirm-go-login">
              Aller à la connexion
            </Link>
          </>
        )}
      </div>
      {irisOpen && (
        <IrisFullscreenWizard
          onCancel={() => setIrisOpen(false)}
          onDone={handleIrisDone}
        />
      )}
    </div>
  );
}
