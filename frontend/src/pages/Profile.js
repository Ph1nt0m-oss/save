import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { ArrowLeft, Lock, Mail, Download, Trash2, Loader2, AlertTriangle, User as UserIcon, Settings as SettingsIcon, Users as UsersIcon, Plus, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KNOWN_ACCOUNTS_KEY = 'codeforge_known_accounts';
const DEVICE_ID_KEY = 'codeforge_device_id';
const PREFS_KEY = 'codeforge_prefs';

function getOrCreateDeviceId() {
  try {
    let id = localStorage.getItem(DEVICE_ID_KEY);
    if (!id) {
      id = 'dev_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(DEVICE_ID_KEY, id);
    }
    return id;
  } catch (_) { return 'dev_unknown'; }
}

function readKnownAccounts() {
  try {
    const raw = localStorage.getItem(KNOWN_ACCOUNTS_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch (_) { return []; }
}

function writeKnownAccounts(list) {
  try { localStorage.setItem(KNOWN_ACCOUNTS_KEY, JSON.stringify(list.slice(0, 6))); } catch (_) {}
}

function applyPreferences(prefs) {
  // Apply theme + accent on the document root.
  const root = document.documentElement;
  const theme = prefs.theme === 'auto'
    ? (window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : (prefs.theme || 'dark');
  root.dataset.theme = theme;
  root.dataset.contrast = prefs.contrast || 'normal';
  if (prefs.accent) root.style.setProperty('--cf-accent', prefs.accent);
}

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' }); }
  catch (_) { return iso; }
}

export default function Profile() {
  const navigate = useNavigate();
  const { user, setUser, logout } = useAuth();

  const [tab, setTab] = useState('info'); // 'info' | 'password' | 'email' | 'prefs' | 'accounts' | 'danger'
  const [submitting, setSubmitting] = useState(false);

  // Change password
  const [curPwd, setCurPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');

  // Change email
  const [newEmail, setNewEmail] = useState('');
  const [pwdForEmail, setPwdForEmail] = useState('');

  // Delete account
  const [pwdForDelete, setPwdForDelete] = useState('');
  const [confirmDelete, setConfirmDelete] = useState('');

  // Preferences
  const [prefs, setPrefs] = useState(() => {
    try {
      const cached = JSON.parse(localStorage.getItem(PREFS_KEY) || 'null');
      return cached || { theme: 'dark', contrast: 'normal', accent: '#E4FF00', notifications_email: true, notifications_push: false };
    } catch (_) { return { theme: 'dark', contrast: 'normal', accent: '#E4FF00', notifications_email: true, notifications_push: false }; }
  });
  const [prefsSaving, setPrefsSaving] = useState(false);
  const deviceId = getOrCreateDeviceId();
  const [deviceCopied, setDeviceCopied] = useState(false);

  // Linked accounts (multi-account, client side)
  const [accounts, setAccounts] = useState(() => readKnownAccounts());
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [addEmail, setAddEmail] = useState('');
  const [addPassword, setAddPassword] = useState('');
  const [addBusy, setAddBusy] = useState(false);
  const [pendingRemove, setPendingRemove] = useState(null); // {email}
  const [removePwd, setRemovePwd] = useState('');

  // Load server-side preferences once on mount, fallback silently.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/auth/preferences`, { withCredentials: true });
        if (!cancelled && r.data) {
          setPrefs(p => ({ ...p, ...r.data }));
          applyPreferences({ ...prefs, ...r.data });
          try { localStorage.setItem(PREFS_KEY, JSON.stringify({ ...prefs, ...r.data })); } catch (_) {}
        }
      } catch (_) { /* anonymous fallback to local */ }
    })();
    applyPreferences(prefs);
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updatePref = (key, value) => {
    const next = { ...prefs, [key]: value };
    setPrefs(next);
    applyPreferences(next);
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(next)); } catch (_) {}
  };

  const savePreferences = async () => {
    setPrefsSaving(true);
    try {
      await axios.put(`${API}/auth/preferences`, prefs, { withCredentials: true });
      toast.success('Préférences enregistrées');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur');
    } finally { setPrefsSaving(false); }
  };

  const copyDeviceId = async () => {
    try {
      await navigator.clipboard.writeText(deviceId);
      setDeviceCopied(true);
      toast.success('Identifiant copié');
      setTimeout(() => setDeviceCopied(false), 1500);
    } catch (_) { toast.error('Copie impossible'); }
  };

  const submitAddAccount = async (e) => {
    e.preventDefault();
    if (!addEmail.trim() || !addPassword) return;
    setAddBusy(true);
    try {
      // Verify credentials by hitting /auth/login (does NOT switch the active session here).
      const r = await axios.post(`${API}/auth/login`, { email: addEmail.trim(), password: addPassword });
      // Trigger a confirmation magic-link to the added address (best-effort).
      try {
        await axios.post(`${API}/auth/magic-link`, {
          email: addEmail.trim(),
          frontend_url: window.location.origin,
        });
      } catch (_) { /* non-blocker */ }

      const list = readKnownAccounts();
      const filtered = list.filter(a => a.email !== addEmail.trim());
      const entry = {
        email: addEmail.trim(),
        name: r.data?.name || addEmail.split('@')[0],
        picture: r.data?.picture || null,
        last_used: new Date().toISOString(),
      };
      const updated = [entry, ...filtered].slice(0, 6);
      writeKnownAccounts(updated);
      setAccounts(updated);
      setAddEmail(''); setAddPassword(''); setShowAddAccount(false);
      toast.success('Compte ajouté. Un email de confirmation a été envoyé.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Identifiants invalides');
    } finally { setAddBusy(false); }
  };

  const requestRemove = (acc) => { setPendingRemove(acc); setRemovePwd(''); };
  const cancelRemove = () => { setPendingRemove(null); setRemovePwd(''); };
  const confirmRemove = async (e) => {
    e.preventDefault();
    if (!pendingRemove || !removePwd) return;
    try {
      await axios.post(`${API}/auth/login`, { email: user.email, password: removePwd });
      const updated = readKnownAccounts().filter(a => a.email !== pendingRemove.email);
      writeKnownAccounts(updated);
      setAccounts(updated);
      cancelRemove();
      toast.success('Compte retiré de la liste');
    } catch (err) {
      toast.error('Mot de passe incorrect');
    }
  };

  if (!user) {
    // ProtectedRoute already handles this, but defensive
    navigate('/login');
    return null;
  }

  const submitPasswordChange = async (e) => {
    e.preventDefault();
    if (newPwd.length < 6) return toast.error('6 caractères minimum');
    if (newPwd !== confirmPwd) return toast.error('Les mots de passe ne correspondent pas');
    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/change-password`, {
        current_password: curPwd,
        new_password: newPwd,
      });
      toast.success('Mot de passe mis à jour. Tes autres sessions ont été déconnectées.');
      setCurPwd(''); setNewPwd(''); setConfirmPwd('');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur');
    } finally { setSubmitting(false); }
  };

  const submitEmailChange = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/auth/change-email`, {
        new_email: newEmail.trim(),
        current_password: pwdForEmail,
        frontend_url: window.location.origin,
      });
      if (data.email_sent) {
        toast.success(`Email de confirmation envoyé à ${newEmail}. Clique le lien pour finaliser.`);
      } else if (data.verification_link) {
        toast.info('Mode démo — lien ouvert dans un nouvel onglet.');
        window.open(data.verification_link, '_blank', 'noopener,noreferrer');
      }
      setNewEmail(''); setPwdForEmail('');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur');
    } finally { setSubmitting(false); }
  };

  const exportMyData = async () => {
    try {
      const resp = await axios.get(`${API}/auth/export`, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([resp.data], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url; a.download = 'codeforge-mes-donnees.json';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Tes données ont été téléchargées.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur export');
    }
  };

  const submitDelete = async (e) => {
    e.preventDefault();
    if (confirmDelete !== 'SUPPRIMER') {
      return toast.error("Tape SUPPRIMER en majuscules pour confirmer.");
    }
    if (!window.confirm("Cette action est IRRÉVERSIBLE. Continuer ?")) return;
    setSubmitting(true);
    try {
      await axios.delete(`${API}/auth/me`, { data: { current_password: pwdForDelete } });
      toast.success('Compte supprimé. À bientôt.');
      try { localStorage.removeItem('session_token'); } catch (_) {}
      try { localStorage.removeItem('codeforge_last_email'); } catch (_) {}
      setUser(null);
      setTimeout(() => navigate('/', { replace: true }), 800);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur suppression');
    } finally { setSubmitting(false); }
  };

  return (
    <div className="min-h-screen bg-[#050505] relative overflow-hidden">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="fixed inset-0 grid-bg opacity-10 pointer-events-none"></div>

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-8">
        <button
          onClick={() => navigate('/dashboard')}
          data-testid="profile-back-btn"
          className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Retour au dashboard
        </button>

        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-3xl sm:text-4xl font-['Chivo'] font-black text-white">
            Mon profil
          </h1>
          <p className="text-sm text-[#A1A1AA] font-['IBM_Plex_Sans'] mt-1">
            Gère ton compte, tes accès et tes données.
          </p>
        </motion.div>

        {/* Tabs */}
        <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10">
          {[
            ['info', 'Informations', UserIcon],
            ['password', 'Mot de passe', Lock],
            ['email', 'Email', Mail],
            ['prefs', 'Préférences', SettingsIcon],
            ['accounts', 'Comptes', UsersIcon],
            ['danger', 'Zone dangereuse', AlertTriangle],
          ].map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              data-testid={`profile-tab-${key}`}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-['Chivo'] font-bold border-b-2 -mb-px transition-colors ${
                tab === key
                  ? (key === 'danger' ? 'text-red-400 border-red-400' : 'text-[#E4FF00] border-[#E4FF00]')
                  : 'text-[#A1A1AA] border-transparent hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        {/* Panels */}
        <div className="mt-6">
          {tab === 'info' && (
            <div data-testid="profile-info" className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl">
              <div className="grid sm:grid-cols-2 gap-4 text-sm">
                <Field label="Nom" value={user.name || '—'} />
                <Field label="Email" value={user.email || '—'} />
                <Field label="Type d'auth" value={user.auth_type || 'email'} />
                <Field label="Email vérifié" value={user.verified ? 'Oui' : 'Non'} />
                <Field label="Membre depuis" value={fmtDate(user.created_at)} />
                <Field label="Dernière connexion" value={fmtDate(user.last_login)} />
              </div>
              <div className="mt-6 pt-6 border-t border-white/10">
                <h3 className="font-['Chivo'] font-bold text-white mb-2">Tes données (RGPD)</h3>
                <p className="text-xs text-[#A1A1AA] mb-3">
                  Télécharge un export complet de toutes les données qu'on stocke sur toi (compte, projets, sessions, chats).
                </p>
                <button
                  onClick={exportMyData}
                  data-testid="profile-export-btn"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-400/20 hover:bg-cyan-400/30 border border-cyan-400/30 text-cyan-300 text-sm font-['Chivo'] font-bold rounded-sm transition-all"
                >
                  <Download className="w-4 h-4" /> Télécharger mes données (JSON)
                </button>
              </div>
            </div>
          )}

          {tab === 'password' && (
            <form onSubmit={submitPasswordChange} data-testid="profile-password-form" className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl space-y-4">
              <h3 className="font-['Chivo'] font-bold text-white">Changer le mot de passe</h3>
              <PwdInput value={curPwd} onChange={setCurPwd} label="Mot de passe actuel" testId="profile-current-pwd" />
              <PwdInput value={newPwd} onChange={setNewPwd} label="Nouveau mot de passe" testId="profile-new-pwd" hint="6 caractères minimum" />
              <PwdInput value={confirmPwd} onChange={setConfirmPwd} label="Confirme le nouveau mot de passe" testId="profile-confirm-pwd" />
              <button
                type="submit" disabled={submitting}
                data-testid="profile-password-submit"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(228,255,0,0.3)] transition-all disabled:opacity-60"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                Mettre à jour
              </button>
              <p className="text-[11px] text-[#A1A1AA]">Toutes tes autres sessions seront déconnectées par sécurité.</p>
            </form>
          )}

          {tab === 'email' && (
            <form onSubmit={submitEmailChange} data-testid="profile-email-form" className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl space-y-4">
              <h3 className="font-['Chivo'] font-bold text-white">Changer l'email</h3>
              <p className="text-xs text-[#A1A1AA]">Email actuel : <span className="text-white">{user.email}</span></p>
              <div>
                <label className="block text-xs text-[#A1A1AA] mb-1">Nouvel email</label>
                <input
                  type="email" value={newEmail} required onChange={(e) => setNewEmail(e.target.value)}
                  data-testid="profile-new-email"
                  className="w-full bg-white/[0.04] border border-white/10 rounded-sm px-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none"
                  placeholder="nouveau@gmail.com"
                />
              </div>
              <PwdInput value={pwdForEmail} onChange={setPwdForEmail} label="Mot de passe actuel" testId="profile-email-pwd" />
              <button
                type="submit" disabled={submitting}
                data-testid="profile-email-submit"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all disabled:opacity-60"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                Envoyer le lien de confirmation
              </button>
              <p className="text-[11px] text-[#A1A1AA]">Le changement n'est appliqué qu'après que tu cliques sur le lien envoyé au nouvel email.</p>
            </form>
          )}

          {tab === 'prefs' && (
            <div data-testid="profile-prefs" className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl space-y-6">
              <h3 className="font-['Chivo'] font-bold text-white">Apparence et notifications</h3>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs uppercase tracking-widest text-[#A1A1AA] mb-2">Thème</label>
                  <div className="flex gap-2" data-testid="prefs-theme">
                    {['dark', 'light', 'auto'].map(v => (
                      <button key={v} onClick={() => updatePref('theme', v)}
                        data-testid={`prefs-theme-${v}`}
                        className={`flex-1 py-2 text-sm rounded-sm border transition-all ${
                          prefs.theme === v ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00]' : 'border-white/15 hover:border-white/40'
                        }`}>
                        {v === 'dark' ? 'Sombre' : v === 'light' ? 'Clair' : 'Auto'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs uppercase tracking-widest text-[#A1A1AA] mb-2">Contraste</label>
                  <div className="flex gap-2" data-testid="prefs-contrast">
                    {['normal', 'high'].map(v => (
                      <button key={v} onClick={() => updatePref('contrast', v)}
                        data-testid={`prefs-contrast-${v}`}
                        className={`flex-1 py-2 text-sm rounded-sm border transition-all ${
                          prefs.contrast === v ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00]' : 'border-white/15 hover:border-white/40'
                        }`}>
                        {v === 'normal' ? 'Normal' : 'Élevé'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-[#A1A1AA] mb-2">Couleur d'accent</label>
                <div className="flex flex-wrap gap-2" data-testid="prefs-accent">
                  {['#E4FF00', '#00FF66', '#0EA5E9', '#A855F7', '#F97316', '#EF4444'].map(c => (
                    <button key={c} onClick={() => updatePref('accent', c)}
                      data-testid={`prefs-accent-${c.replace('#', '')}`}
                      style={{ backgroundColor: c }}
                      className={`w-9 h-9 rounded-sm border-2 transition-transform hover:scale-110 ${
                        prefs.accent === c ? 'border-white' : 'border-transparent'
                      }`}
                    />
                  ))}
                  <input type="color" value={prefs.accent} onChange={(e) => updatePref('accent', e.target.value)}
                    data-testid="prefs-accent-custom"
                    className="w-9 h-9 rounded-sm border border-white/20 bg-transparent cursor-pointer" />
                </div>
              </div>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 bg-[#0F0F13] rounded-sm border border-white/10 cursor-pointer">
                  <div>
                    <div className="font-['Chivo'] font-bold">Notifications email</div>
                    <p className="text-xs text-[#A1A1AA]">Mises à jour de projets, sécurité, factures.</p>
                  </div>
                  <input type="checkbox" checked={!!prefs.notifications_email}
                    onChange={(e) => updatePref('notifications_email', e.target.checked)}
                    data-testid="prefs-notif-email"
                    className="w-5 h-5 accent-[#E4FF00]" />
                </label>
                <label className="flex items-center justify-between p-3 bg-[#0F0F13] rounded-sm border border-white/10 cursor-pointer">
                  <div>
                    <div className="font-['Chivo'] font-bold">Notifications push</div>
                    <p className="text-xs text-[#A1A1AA]">Alertes navigateur lorsque l'app est ouverte.</p>
                  </div>
                  <input type="checkbox" checked={!!prefs.notifications_push}
                    onChange={(e) => updatePref('notifications_push', e.target.checked)}
                    data-testid="prefs-notif-push"
                    className="w-5 h-5 accent-[#E4FF00]" />
                </label>
              </div>

              <div className="pt-4 border-t border-white/10">
                <label className="block text-xs uppercase tracking-widest text-[#A1A1AA] mb-2">Identifiant de cet appareil</label>
                <p className="text-[11px] text-[#A1A1AA] mb-2">Sert à associer plusieurs comptes au même appareil.</p>
                <div className="flex items-center gap-2">
                  <code data-testid="prefs-device-id" className="flex-1 px-3 py-2 bg-[#050505] border border-white/10 rounded-sm text-xs font-mono text-[#E4FF00] truncate">
                    {deviceId}
                  </code>
                  <button onClick={copyDeviceId} data-testid="prefs-device-copy"
                    className="inline-flex items-center gap-1 px-3 py-2 border border-white/15 rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-colors text-xs">
                    {deviceCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {deviceCopied ? 'Copié' : 'Copier'}
                  </button>
                </div>
              </div>

              <div>
                <button onClick={savePreferences} disabled={prefsSaving}
                  data-testid="prefs-save-btn"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all disabled:opacity-60">
                  {prefsSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <SettingsIcon className="w-4 h-4" />}
                  Enregistrer
                </button>
              </div>
            </div>
          )}

          {tab === 'accounts' && (
            <div data-testid="profile-accounts" className="bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl space-y-5">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <h3 className="font-['Chivo'] font-bold text-white">Comptes associés à cet appareil</h3>
                  <p className="text-xs text-[#A1A1AA] mt-1">Bascule rapidement entre plusieurs comptes sans te reconnecter à chaque fois.</p>
                </div>
                <button onClick={() => setShowAddAccount(s => !s)}
                  data-testid="accounts-add-toggle"
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm">
                  <Plus className="w-4 h-4" /> Ajouter un compte
                </button>
              </div>

              {showAddAccount && (
                <form onSubmit={submitAddAccount} data-testid="accounts-add-form"
                  className="grid sm:grid-cols-[1fr_1fr_auto] gap-2 items-end p-3 border border-[#E4FF00]/30 rounded-sm bg-[#E4FF00]/5">
                  <div>
                    <label className="block text-xs text-[#A1A1AA] mb-1">Email</label>
                    <input type="email" required value={addEmail}
                      onChange={(e) => setAddEmail(e.target.value)}
                      data-testid="accounts-add-email"
                      placeholder="autre@email.com"
                      className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-[#E4FF00]" />
                  </div>
                  <div>
                    <label className="block text-xs text-[#A1A1AA] mb-1">Mot de passe</label>
                    <input type="password" required minLength={6} value={addPassword}
                      onChange={(e) => setAddPassword(e.target.value)}
                      data-testid="accounts-add-password"
                      placeholder="••••••••"
                      className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-[#E4FF00]" />
                  </div>
                  <button type="submit" disabled={addBusy}
                    data-testid="accounts-add-submit"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm disabled:opacity-60">
                    {addBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                    Confirmer par email
                  </button>
                </form>
              )}

              {accounts.length === 0 ? (
                <p className="text-sm text-[#A1A1AA] py-6 text-center" data-testid="accounts-empty">
                  Aucun compte associé pour l'instant.
                </p>
              ) : (
                <ul className="divide-y divide-white/5 border border-white/10 rounded-sm bg-[#0F0F13]">
                  {accounts.map(acc => (
                    <li key={acc.email} className="flex items-center justify-between gap-3 px-4 py-3"
                      data-testid={`accounts-row-${acc.email}`}>
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-full bg-[#E4FF00]/15 border border-[#E4FF00]/30 flex items-center justify-center text-[#E4FF00] font-['Chivo'] font-bold flex-shrink-0">
                          {(acc.name || acc.email)[0].toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm truncate">{acc.name || acc.email.split('@')[0]}</div>
                          <div className="text-xs text-[#A1A1AA] truncate">{acc.email}</div>
                        </div>
                      </div>
                      <button onClick={() => requestRemove(acc)}
                        data-testid={`accounts-remove-${acc.email}`}
                        disabled={acc.email === user.email}
                        title={acc.email === user.email ? 'Tu ne peux pas retirer ton compte actif' : 'Retirer'}
                        className="text-xs text-red-400 hover:text-red-300 disabled:opacity-30 disabled:cursor-not-allowed inline-flex items-center gap-1">
                        <Trash2 className="w-3.5 h-3.5" /> Retirer
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {pendingRemove && (
                <form onSubmit={confirmRemove} data-testid="accounts-remove-modal"
                  className="p-4 border border-red-500/30 bg-red-500/5 rounded-sm space-y-3">
                  <p className="text-sm text-red-200">
                    Confirme avec ton mot de passe pour retirer <b>{pendingRemove.email}</b>.
                  </p>
                  <input type="password" autoFocus minLength={6} required value={removePwd}
                    onChange={(e) => setRemovePwd(e.target.value)}
                    data-testid="accounts-remove-password"
                    placeholder="Ton mot de passe"
                    className="w-full bg-[#050505] border border-red-500/30 rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-red-500" />
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={cancelRemove}
                      data-testid="accounts-remove-cancel"
                      className="px-3 py-2 text-sm border border-white/15 rounded-sm hover:border-white/40">
                      Annuler
                    </button>
                    <button type="submit"
                      data-testid="accounts-remove-confirm"
                      className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-red-500 hover:bg-red-600 text-white font-['Chivo'] font-bold rounded-sm">
                      <Trash2 className="w-3.5 h-3.5" /> Retirer
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          {tab === 'danger' && (
            <form onSubmit={submitDelete} data-testid="profile-danger-form" className="bg-red-500/5 border border-red-500/30 rounded-sm p-6 backdrop-blur-xl space-y-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5" />
                <div>
                  <h3 className="font-['Chivo'] font-bold text-red-300">Supprimer mon compte</h3>
                  <p className="text-xs text-red-200/80 mt-1">
                    Action irréversible. Tous tes projets, sessions et chats seront effacés définitivement.
                  </p>
                </div>
              </div>
              <PwdInput value={pwdForDelete} onChange={setPwdForDelete} label="Mot de passe pour confirmer" testId="profile-delete-pwd" />
              <div>
                <label className="block text-xs text-red-200/80 mb-1">Tape <code className="bg-red-500/20 px-1 rounded">SUPPRIMER</code> pour confirmer</label>
                <input
                  type="text" value={confirmDelete} required
                  onChange={(e) => setConfirmDelete(e.target.value)}
                  data-testid="profile-delete-confirm"
                  className="w-full bg-white/[0.04] border border-red-500/30 rounded-sm px-3 py-3 text-sm text-white focus:border-red-500 focus:outline-none"
                  placeholder="SUPPRIMER"
                />
              </div>
              <button
                type="submit" disabled={submitting || confirmDelete !== 'SUPPRIMER'}
                data-testid="profile-delete-submit"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-600 text-white font-['Chivo'] font-bold rounded-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Supprimer définitivement mon compte
              </button>
            </form>
          )}
        </div>

        <div className="mt-8 text-center">
          <button
            onClick={() => logout()}
            data-testid="profile-logout-btn"
            className="text-xs text-[#A1A1AA] hover:text-[#E4FF00] underline transition-colors"
          >
            Me déconnecter
          </button>
        </div>
      </div>
    </div>
  );
}

const Field = ({ label, value }) => (
  <div>
    <p className="text-[10px] uppercase tracking-wider text-[#A1A1AA]">{label}</p>
    <p className="text-white font-['IBM_Plex_Sans']">{value}</p>
  </div>
);

const PwdInput = ({ label, value, onChange, testId, hint }) => (
  <div>
    <label className="block text-xs text-[#A1A1AA] mb-1">{label}</label>
    <input
      type="password" value={value} required minLength={6}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testId}
      className="w-full bg-white/[0.04] border border-white/10 rounded-sm px-3 py-3 text-sm text-white placeholder-[#A1A1AA]/60 focus:border-[#E4FF00] focus:outline-none"
      placeholder="••••••••"
    />
    {hint && <p className="text-[10px] text-[#A1A1AA]/70 mt-1">{hint}</p>}
  </div>
);
