import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { X, User as UserIcon, Lock, Loader2, Plus, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KNOWN_ACCOUNTS_KEY = 'codeforge_known_accounts';

function loadAccounts() {
  try {
    const raw = localStorage.getItem(KNOWN_ACCOUNTS_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch (_) { return []; }
}

function rememberAccount(user) {
  if (!user || !user.email) return;
  try {
    const list = loadAccounts().filter(a => a.email !== user.email);
    list.unshift({
      email: user.email,
      name: user.name || user.email.split('@')[0],
      picture: user.picture || null,
      last_used: new Date().toISOString(),
    });
    localStorage.setItem(KNOWN_ACCOUNTS_KEY, JSON.stringify(list.slice(0, 6)));
  } catch (_) {}
}

function removeAccount(email) {
  try {
    const list = loadAccounts().filter(a => a.email !== email);
    localStorage.setItem(KNOWN_ACCOUNTS_KEY, JSON.stringify(list));
  } catch (_) {}
}

export default function SwitchAccountModal({ open, onClose }) {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [pickedEmail, setPickedEmail] = useState('');
  const [pwd, setPwd] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setAccounts(loadAccounts());
      setPickedEmail('');
      setPwd('');
    }
  }, [open]);

  if (!open) return null;

  const otherAccounts = accounts.filter(a => !user || a.email !== user.email);

  const submit = async (e) => {
    e.preventDefault();
    if (!pickedEmail || !pwd) return;
    if (submitting) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/auth/login`, {
        email: pickedEmail,
        password: pwd,
      });
      // Success: persist new session token, replace current user
      try {
        if (data.session_token) localStorage.setItem('session_token', data.session_token);
        localStorage.setItem('codeforge_last_email', pickedEmail);
      } catch (_) {}
      rememberAccount(data);
      setUser(data);
      toast.success(`Compte changé : ${data.name || data.email}`);
      onClose?.();
      // Force a full reload of the dashboard so any user-scoped data
      // (projects, chats, …) is refetched cleanly.
      navigate('/dashboard', { replace: true, state: { user: data } });
    } catch (err) {
      // Fail-safe: keep the current session active. We never log the
      // user out on switch failure.
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : "Impossible de changer de compte. Tu restes connecté avec le compte actuel.";
      toast.error(msg, { duration: 5000 });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 20, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 280, damping: 25 }}
          onClick={(e) => e.stopPropagation()}
          data-testid="switch-account-modal"
          className="w-full max-w-md bg-[#0A0A0A] border border-white/15 rounded-sm p-6 backdrop-blur-2xl"
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-lg font-['Chivo'] font-black text-white">Changer de compte</h2>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Choisis un compte enregistré sur cet appareil. Tu restes connecté avec le compte actuel si la connexion échoue.
              </p>
            </div>
            <button onClick={onClose} data-testid="switch-account-close" className="text-[#A1A1AA] hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          {!pickedEmail && (
            <div className="space-y-2" data-testid="switch-account-list">
              {otherAccounts.length === 0 && (
                <p className="text-sm text-[#A1A1AA] text-center py-4">
                  Aucun autre compte enregistré sur cet appareil.
                </p>
              )}
              {otherAccounts.map((a) => (
                <button
                  key={a.email}
                  type="button"
                  onClick={() => setPickedEmail(a.email)}
                  data-testid={`switch-account-pick-${a.email}`}
                  className="w-full flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-sm hover:border-[#E4FF00]/40 hover:bg-white/[0.06] transition-all text-left"
                >
                  <div className="w-9 h-9 rounded-full bg-[#E4FF00]/20 flex items-center justify-center flex-shrink-0">
                    {a.picture
                      ? <img src={a.picture} alt="" className="w-9 h-9 rounded-full object-cover" />
                      : <UserIcon className="w-4 h-4 text-[#E4FF00]" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-['Chivo'] font-bold truncate">{a.name}</p>
                    <p className="text-xs text-[#A1A1AA] truncate">{a.email}</p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); removeAccount(a.email); setAccounts(loadAccounts()); }}
                    data-testid={`switch-account-remove-${a.email}`}
                    aria-label="Retirer ce compte"
                    className="text-[#A1A1AA] hover:text-red-400 px-2 py-1 text-[10px]"
                  >
                    ✕
                  </button>
                </button>
              ))}

              <button
                type="button"
                onClick={() => { onClose?.(); navigate('/login'); }}
                data-testid="switch-account-add-new"
                className="w-full flex items-center gap-3 p-3 bg-white/[0.02] border border-dashed border-white/15 rounded-sm hover:border-[#E4FF00]/40 transition-all text-left"
              >
                <div className="w-9 h-9 rounded-full bg-white/[0.04] flex items-center justify-center">
                  <Plus className="w-4 h-4 text-[#E4FF00]" />
                </div>
                <div>
                  <p className="text-sm text-white font-['Chivo'] font-bold">Ajouter un autre compte</p>
                  <p className="text-xs text-[#A1A1AA]">Connecte-toi avec une autre adresse</p>
                </div>
              </button>
            </div>
          )}

          {pickedEmail && (
            <form onSubmit={submit} className="space-y-3" data-testid="switch-account-form">
              <button type="button" onClick={() => setPickedEmail('')} className="text-xs text-[#A1A1AA] hover:text-white inline-flex items-center gap-1">
                <ArrowLeft className="w-3 h-3" /> Choisir un autre compte
              </button>
              <div className="p-3 bg-white/[0.04] border border-white/10 rounded-sm">
                <p className="text-xs text-[#A1A1AA]">Compte sélectionné</p>
                <p className="text-sm text-white font-['Chivo'] font-bold mt-0.5">{pickedEmail}</p>
              </div>
              <div>
                <label className="block text-xs text-[#A1A1AA] mb-1">Mot de passe</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A1AA]" />
                  <input
                    type="password" value={pwd} onChange={(e) => setPwd(e.target.value)}
                    required minLength={6} autoFocus
                    data-testid="switch-account-password"
                    className="w-full bg-white/[0.04] border border-white/10 rounded-sm pl-10 pr-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none"
                    placeholder="••••••••"
                  />
                </div>
              </div>
              <button
                type="submit" disabled={submitting}
                data-testid="switch-account-submit"
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all disabled:opacity-60"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {submitting ? 'Connexion…' : 'Basculer sur ce compte'}
              </button>
              <p className="text-[10px] text-[#A1A1AA]/70 text-center">
                Si la connexion échoue, tu resteras connecté avec ton compte actuel.
              </p>
            </form>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
