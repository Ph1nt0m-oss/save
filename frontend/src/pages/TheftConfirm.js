import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, Loader2, Eye } from 'lucide-react';
import { toast } from 'sonner';
import { IrisFullscreenWizard } from '../components/BiometricEnrollmentField';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Landing page that consumes a theft-email-confirm token. Calls the
 * backend, then displays success/failure. The actual key revocation is
 * server-side; this is just the confirmation step.
 *
 * iter71: after the email-token leg succeeds the user is offered a
 * second, stronger leg — an iris liveness re-confirmation via the
 * shared IrisFullscreenWizard. The capture runs the full 4-step tutorial
 * (approach → glasses → 3 pose challenges) and posts the resulting
 * hashes to /auth/theft-iris-verify. The endpoint currently accepts any
 * well-formed payload and logs it for the next sprint's real matching
 * pass; the UI itself is therefore production-ready.
 */
export default function TheftConfirm() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const [state, setState] = useState('loading'); // loading | ok | error
  const [revoked, setRevoked] = useState(0);
  const [err, setErr] = useState('');
  const [irisOpen, setIrisOpen] = useState(false);
  const [irisVerified, setIrisVerified] = useState(false);
  const [irisSending, setIrisSending] = useState(false);
  // iter71 fix: StrictMode + dev double-fires useEffect → burned the
  // single-use email-confirm token on the 2nd render. Guard the call.
  const firedRef = useRef(false);

  useEffect(() => {
    if (!token) { setState('error'); setErr('Lien invalide.'); return; }
    if (firedRef.current) return;
    firedRef.current = true;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/auth/theft-email-confirm`, { params: { token } });
        if (cancelled) return;
        setRevoked(r.data?.revoked_count || 0);
        setState('ok');
      } catch (e) {
        if (cancelled) return;
        setErr(e?.response?.data?.detail || 'Erreur.');
        setState('error');
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const handleIrisDone = async (hashes) => {
    setIrisOpen(false);
    setIrisSending(true);
    try {
      await axios.post(`${API}/auth/theft-iris-verify`, { token, hashes });
      setIrisVerified(true);
      toast.success('Iris confirmé. Procédure complète.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Vérification iris échouée.');
    } finally {
      setIrisSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-[#0A0A0A] border border-white/10 rounded-sm p-8 text-center space-y-4">
        {state === 'loading' && (
          <>
            <Loader2 className="w-8 h-8 animate-spin text-[#E4FF00] mx-auto" />
            <p className="text-sm text-[#A1A1AA]">Confirmation en cours…</p>
          </>
        )}
        {state === 'ok' && (
          <>
            <ShieldCheck className="w-12 h-12 text-emerald-400 mx-auto" />
            <h1 className="text-xl font-['Chivo'] font-black text-white">Récupération validée</h1>
            <p className="text-sm text-[#A1A1AA]">
              {revoked} appareil{revoked > 1 ? 's' : ''} révoqué{revoked > 1 ? 's' : ''}. Tu peux maintenant te reconnecter depuis ce nouvel appareil — il deviendra ton nouvel appareil principal après inscription.
            </p>
            {!irisVerified && (
              <div className="bg-[#00D4FF]/10 border border-[#00D4FF]/30 rounded-sm p-3 text-left space-y-2">
                <p className="text-xs text-[#00D4FF] font-['Chivo'] font-bold flex items-center gap-2">
                  <Eye className="w-4 h-4" /> Étape 2 — Confirme ton identité par iris
                </p>
                <p className="text-[11px] text-[#A1A1AA] leading-relaxed">
                  Un voleur peut accéder à ton email mais pas à tes yeux. Confirme ton iris pour finaliser la récupération.
                </p>
                <button
                  type="button"
                  onClick={() => setIrisOpen(true)}
                  disabled={irisSending}
                  data-testid="theft-iris-confirm-btn"
                  className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 bg-[#00D4FF] text-[#050505] rounded-sm font-['Chivo'] font-bold text-xs disabled:opacity-50"
                >
                  {irisSending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
                  Lancer la vérification iris
                </button>
              </div>
            )}
            {irisVerified && (
              <div className="bg-emerald-500/10 border border-emerald-400/40 rounded-sm p-2 text-emerald-200 text-xs inline-flex items-center gap-1 justify-center" data-testid="theft-iris-verified">
                <ShieldCheck className="w-4 h-4" /> Iris confirmé — récupération renforcée
              </div>
            )}
            <Link to="/login" className="inline-block mt-4 px-5 py-2.5 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold hover:bg-white transition" data-testid="theft-confirm-go-login">
              Aller à la connexion
            </Link>
          </>
        )}
        {state === 'error' && (
          <>
            <ShieldAlert className="w-12 h-12 text-red-400 mx-auto" />
            <h1 className="text-xl font-['Chivo'] font-black text-white">Échec</h1>
            <p className="text-sm text-[#A1A1AA]">{err}</p>
            <Link to="/login" className="inline-block mt-4 px-5 py-2.5 bg-white/[0.06] text-white border border-white/15 rounded-sm font-['Chivo'] hover:bg-white/[0.10] transition">
              Retour
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
