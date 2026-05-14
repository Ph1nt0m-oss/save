import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Landing page that consumes a theft-email-confirm token. Calls the
 * backend, then displays success/failure. The actual key revocation is
 * server-side; this is just the confirmation step.
 */
export default function TheftConfirm() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const [state, setState] = useState('loading'); // loading | ok | error
  const [revoked, setRevoked] = useState(0);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!token) { setState('error'); setErr('Lien invalide.'); return; }
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
            <Link to="/login" className="inline-block mt-4 px-5 py-2.5 bg-[#E4FF00] text-[#050505] rounded-sm font-['Chivo'] font-bold hover:bg-white transition" data-testid="theft-confirm-go-login">
              Aller à la connexion
            </Link>
          </>
        )}
        {state === 'error' && (
          <>
            <ShieldAlert className="w-12 h-12 text-red-400 mx-auto" />
            <h1 className="text-xl font-['Chivo'] font-black text-white">Lien invalide</h1>
            <p className="text-sm text-[#A1A1AA]">{err}</p>
            <Link to="/login" className="inline-block mt-4 px-5 py-2.5 border border-white/15 text-white rounded-sm font-['Chivo'] font-bold hover:bg-white/5 transition">
              Retour à la connexion
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
