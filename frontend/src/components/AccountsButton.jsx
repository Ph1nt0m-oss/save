import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Users, X, Search, MessageCircle, Edit3, Ban, ShieldCheck, BellOff, Bell, Clock, Skull, ShieldOff, Eye, EyeOff, Crown, History as HistoryIcon, Download, Trash2, Shield, Star } from 'lucide-react';
import { toast } from 'sonner';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EXCLUDE_DURATIONS = [
  { k: 'acc_exclude_5min', minutes: 5 },
  { k: 'acc_exclude_1h', minutes: 60 },
  { k: 'acc_exclude_1d', minutes: 60 * 24 },
  { k: 'acc_exclude_7d', minutes: 60 * 24 * 7 },
  { k: 'acc_exclude_30d', minutes: 60 * 24 * 30 },
];

function downloadText(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Creator-only "Autres comptes" panel: lists every registered account,
 * shows pseudo (auto "#N" for duplicates) + email + state badges and
 * exposes moderation actions (rename, mute, block, exclude, ban, visit).
 * Also hosts the "Remove creator mode" button.
 */
export default function AccountsButton({ onVisitAccount, onMessageAccount }) {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const isCreator = device.role === 'creator' && device.viewMode !== 'guest';
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [excluding, setExcluding] = useState(null); // {target, label}
  const [removing, setRemoving] = useState(false);
  // Local-only "view-cleared" filter (per creator device). Stores the
  // key_ids we want to hide without touching the DB. Restored via Reset.
  const [hidden, setHidden] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('codeforge_accounts_hidden') || '[]')); } catch (_) { return new Set(); }
  });
  const persistHidden = (set) => {
    setHidden(new Set(set));
    try { localStorage.setItem('codeforge_accounts_hidden', JSON.stringify([...set])); } catch (_) {}
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/accounts/list`, body);
      setAccounts(r.data?.accounts || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  if (!isCreator) return null;

  const doAction = async (endpoint, target_key_id, extra = {}) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id, ...extra });
      await axios.post(`${API}${endpoint}`, body);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  const renameContact = async (a) => {
    const next = window.prompt(t('acc_rename_prompt'), a.display || a.pseudo || '');
    if (!next || !next.trim()) return;
    await doAction('/accounts/rename-pseudo', a.key_id, { new_pseudo: next.trim() });
    toast.success(t('pseudo_changed'));
  };

  const exclude = async (target_key_id, minutes) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id, duration_minutes: minutes });
      await axios.post(`${API}/accounts/exclude`, body);
      setExcluding(null);
      toast.success('OK');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  const deleteOne = async (a) => {
    if (!window.confirm(t('acc_delete_confirm').replace('{pseudo}', a.display || a.pseudo || ''))) return;
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: a.key_id });
      await axios.post(`${API}/accounts/delete-one`, body);
      toast.success(t('acc_delete_done'));
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  const deleteAll = async () => {
    if (!window.confirm(t('acc_delete_all_confirm'))) return;
    const pwd = window.prompt(t('acc_delete_all_password_prompt'));
    if (!pwd) return;
    try {
      const body = await withCreatorProof(API, axios, { password: pwd });
      const r = await axios.post(`${API}/accounts/delete-all`, body);
      toast.success(t('acc_delete_done') + ` (${r.data?.deleted || 0})`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    }
  };

  const clearView = () => {
    const next = new Set([...accounts.filter((a) => a.key_id !== device.keyId).map((a) => a.key_id)]);
    persistHidden(next);
    toast.success(t('acc_clear_view_done'));
  };

  const resetView = () => {
    persistHidden(new Set());
    toast.success(t('acc_reset_view_done'));
  };

  const ban = async (a) => {
    if (!window.confirm(t('acc_ban_confirm'))) return;
    await doAction('/accounts/ban', a.key_id);
  };

  const clearHistory = async () => {
    if (!window.confirm(t('hist_clear_confirm') || 'Confirmer ?')) return;
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/accounts/history/clear`, body);
      setHistory([]);
    } catch (_) {}
  };

  const exportHistory = () => {
    const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const lines = history.map((h) => `[${new Date(h.ts).toLocaleString()}]  ${h.event.toUpperCase().padEnd(20)}  ${h.target_label || h.target_key_id || ''}`);
    downloadText(`accounts-history-${ts}.txt`, lines.join('\n') + '\n');
  };

  const setStaffKind = async (a, staff_kind) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: a.key_id, staff_kind });
      await axios.post(`${API}/accounts/set-staff-kind`, body);
      toast.success(staff_kind ? `Promu ${staff_kind}` : 'Badge staff retiré');
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const setForceVisitor = async (a, force) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: a.key_id, force });
      await axios.post(`${API}/accounts/force-visitor`, body);
      toast.success(force ? 'Mode visiteur forcé activé' : 'Mode visiteur retiré');
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Erreur'); }
  };

  const removeCreatorMode = async (target) => {
    // target = null → demote SELF (legacy bottom button). target = row →
    // demote that specific creator device. Both paths take the caller's
    // own password for confirmation.
    const isSelf = !target || target.key_id === device.keyId;
    const promptMsg = isSelf
      ? t('acc_remove_creator_confirm')
      : t('acc_remove_creator_other_confirm').replace('{pseudo}', target.display || target.pseudo || target.key_id.slice(0, 14));
    const pwd = window.prompt(promptMsg);
    if (!pwd) return;
    setRemoving(true);
    try {
      const extra = isSelf ? { password: pwd } : { password: pwd, target_key_id: target.key_id };
      const body = await withCreatorProof(API, axios, extra);
      await axios.post(`${API}/accounts/remove-creator`, body);
      toast.success(t('acc_remove_creator_done'));
      if (isSelf) {
        window.location.reload();
      } else {
        await load();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erreur');
    } finally { setRemoving(false); }
  };

  const filtered = (accounts || []).filter((a) => {
    if (hidden.has(a.key_id)) return false;
    if (!filter) return true;
    const q = filter.toLowerCase();
    return ((a.display || '').toLowerCase().includes(q) ||
            (a.email || '').toLowerCase().includes(q));
  });

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="accounts-btn"
        title={t('acc_title')}
        className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-[#E4FF00] hover:border-[#E4FF00]/40 transition-colors"
      >
        <Users className="w-4 h-4 flex-shrink-0" />
        <span className="text-xs font-['Chivo'] font-bold whitespace-nowrap hidden sm:inline">{t('acc_short')}</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/75 backdrop-blur-sm p-2 sm:p-4" onClick={() => setOpen(false)} data-testid="accounts-panel">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-3xl h-[85vh] bg-[#0A0A0A] border border-white/15 rounded-sm flex flex-col overflow-hidden">
            <header className="px-3 py-3 border-b border-white/10 flex items-center gap-2 flex-shrink-0 flex-wrap">
              <Users className="w-4 h-4 text-[#E4FF00]" />
              <h2 className="text-sm font-['Chivo'] font-bold text-white">{t('acc_title')}</h2>
              <button onClick={() => setOpen(false)} className="ml-auto text-[#A1A1AA] hover:text-white" aria-label="Close">
                <X className="w-4 h-4" />
              </button>
            </header>

            <>
                <div className="px-3 py-2 border-b border-white/10 flex items-center gap-2 flex-shrink-0">
                  <Search className="w-3.5 h-3.5 text-[#71717A]" />
                  <input
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    placeholder={t('acc_search')}
                    data-testid="accounts-search"
                    className="flex-1 bg-transparent text-xs text-white placeholder-[#71717A] focus:outline-none"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                  {loading && <div className="text-xs text-[#A1A1AA] py-4 text-center">…</div>}
                  {!loading && filtered.length === 0 && (
                    <div className="text-xs text-[#A1A1AA] py-4 text-center">{t('acc_empty')}</div>
                  )}
                  {filtered.map((a) => {
                    const isSelf = a.key_id === device.keyId;
                    return (
                    <div key={a.key_id} data-testid={`accounts-row-${a.key_id}`} className="bg-black/30 border border-white/10 rounded-sm p-2.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <div className="min-w-0 flex-1">
                          <div className="text-sm text-white font-['Chivo'] font-bold truncate">{a.display}</div>
                          {a.model && a.model !== a.product && a.model !== a.display && (
                            <div className="text-[10px] text-[#71717A] font-['IBM_Plex_Mono'] truncate" data-testid={`acc-model-${a.key_id}`}>
                              {a.model}
                            </div>
                          )}
                          {/* iter78 — Affiche clé device (préfixe 14 chars) */}
                          <div className="text-[9px] text-[#52525B] font-['IBM_Plex_Mono'] truncate" data-testid={`acc-key-${a.key_id}`}>
                            🔑 {a.key_id.slice(0, 24)}…
                          </div>
                        </div>
                        {isSelf && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-[#E4FF00]/40 text-[#E4FF00] bg-[#E4FF00]/10 rounded-sm">{t('acc_you')}</span>}
                        {a.email && <span className="text-[10px] text-[#71717A] truncate font-['IBM_Plex_Mono']">{a.email}</span>}
                        {a.role === 'creator' && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-[#E4FF00]/40 text-[#E4FF00] bg-[#E4FF00]/10 rounded-sm inline-flex items-center gap-1"><Crown className="w-2.5 h-2.5" />creator</span>}
                        {a.staff_kind === 'admin' && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-cyan-400/40 text-cyan-300 bg-cyan-400/10 rounded-sm inline-flex items-center gap-1"><Shield className="w-2.5 h-2.5" />admin</span>}
                        {a.staff_kind === 'modo' && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-violet-400/40 text-violet-300 bg-violet-400/10 rounded-sm inline-flex items-center gap-1"><Star className="w-2.5 h-2.5" />modo</span>}
                        {a.role === 'approved' && !a.staff_kind && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-emerald-400/40 text-emerald-300 bg-emerald-400/10 rounded-sm">approved</span>}
                        {a.role === 'pending' && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-amber-400/40 text-amber-300 bg-amber-400/10 rounded-sm">pending</span>}
                        {a.role === 'blocked' && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-red-400/40 text-red-300 bg-red-400/10 rounded-sm">blocked</span>}
                        {a.is_inactive && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-zinc-400/40 text-zinc-300 bg-zinc-400/10 rounded-sm">inactif</span>}
                        {a.force_visitor && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-orange-400/40 text-orange-300 bg-orange-400/10 rounded-sm">visiteur forcé</span>}
                        {a.banned && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-red-500/60 text-red-200 bg-red-500/20 rounded-sm">banned</span>}
                        {a.excluded_until && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-orange-400/40 text-orange-300 bg-orange-400/10 rounded-sm">excluded</span>}
                        {a.muted && <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 border border-purple-400/40 text-purple-300 bg-purple-400/10 rounded-sm">muted</span>}
                      </div>
                      <div className="mt-2 flex items-center gap-1 flex-wrap">
                        {!isSelf && (
                          <button title="Visiter le compte" data-testid={`acc-visit-${a.key_id}`} onClick={() => { setOpen(false); onVisitAccount?.(a); }} className="p-1.5 border border-white/15 hover:border-[#E4FF00]/40 text-[#A1A1AA] hover:text-[#E4FF00] rounded-sm transition"><Eye className="w-3.5 h-3.5" /></button>
                        )}
                        {!isSelf && onMessageAccount && (
                          <button title="Message" data-testid={`acc-message-${a.key_id}`} onClick={() => { setOpen(false); onMessageAccount?.(a); }} className="p-1.5 border border-white/15 hover:border-[#00D4FF]/40 text-[#A1A1AA] hover:text-[#00D4FF] rounded-sm transition"><MessageCircle className="w-3.5 h-3.5" /></button>
                        )}
                        <button title={t('acc_action_rename')} onClick={() => renameContact(a)} className="p-1.5 border border-white/15 hover:border-[#E4FF00]/40 text-[#A1A1AA] hover:text-[#E4FF00] rounded-sm transition"><Edit3 className="w-3.5 h-3.5" /></button>
                        {/* iter78 — Promotions staff */}
                        {!isSelf && a.role === 'approved' && (
                          <>
                            <button title={a.staff_kind === 'admin' ? 'Retirer admin' : 'Mettre admin'} data-testid={`acc-admin-${a.key_id}`} onClick={() => setStaffKind(a, a.staff_kind === 'admin' ? null : 'admin')} className={`p-1.5 border rounded-sm transition ${a.staff_kind === 'admin' ? 'border-cyan-400/60 text-cyan-300 bg-cyan-400/10' : 'border-white/15 text-[#A1A1AA] hover:border-cyan-400/40 hover:text-cyan-300'}`}><Shield className="w-3.5 h-3.5" /></button>
                            <button title={a.staff_kind === 'modo' ? 'Retirer modo' : 'Mettre modo'} data-testid={`acc-modo-${a.key_id}`} onClick={() => setStaffKind(a, a.staff_kind === 'modo' ? null : 'modo')} className={`p-1.5 border rounded-sm transition ${a.staff_kind === 'modo' ? 'border-violet-400/60 text-violet-300 bg-violet-400/10' : 'border-white/15 text-[#A1A1AA] hover:border-violet-400/40 hover:text-violet-300'}`}><Star className="w-3.5 h-3.5" /></button>
                          </>
                        )}
                        {/* iter78 — Force visiteur (lecture seule sans déco) */}
                        {!isSelf && a.role !== 'creator' && (
                          <button title={a.force_visitor ? 'Retirer mode visiteur' : 'Forcer mode visiteur'} data-testid={`acc-visitor-${a.key_id}`} onClick={() => setForceVisitor(a, !a.force_visitor)} className={`p-1.5 border rounded-sm transition ${a.force_visitor ? 'border-orange-400/60 text-orange-300 bg-orange-400/10' : 'border-white/15 text-[#A1A1AA] hover:border-orange-400/40 hover:text-orange-300'}`}><EyeOff className="w-3.5 h-3.5" /></button>
                        )}
                        {!isSelf && (a.muted ? (
                          <button title={t('acc_action_unmute')} onClick={() => doAction('/accounts/unmute', a.key_id)} className="p-1.5 border border-purple-400/40 text-purple-300 rounded-sm"><Bell className="w-3.5 h-3.5" /></button>
                        ) : (
                          <button title={t('acc_action_mute')} onClick={() => doAction('/accounts/mute', a.key_id)} className="p-1.5 border border-white/15 hover:border-purple-400/40 text-[#A1A1AA] hover:text-purple-300 rounded-sm transition"><BellOff className="w-3.5 h-3.5" /></button>
                        ))}
                        {!isSelf && (a.role === 'blocked' ? (
                          <button title={t('acc_action_unblock')} onClick={() => doAction('/devices/unblock', a.key_id)} className="p-1.5 border border-emerald-400/40 text-emerald-300 rounded-sm"><ShieldCheck className="w-3.5 h-3.5" /></button>
                        ) : (
                          <button title={t('acc_action_block')} onClick={() => doAction('/devices/block', a.key_id)} className="p-1.5 border border-white/15 hover:border-red-400/40 text-[#A1A1AA] hover:text-red-400 rounded-sm transition"><Ban className="w-3.5 h-3.5" /></button>
                        ))}
                        {!isSelf && (
                          <button title={t('acc_action_exclude')} onClick={() => setExcluding({ a })} data-testid={`acc-exclude-${a.key_id}`} className="p-1.5 border border-white/15 hover:border-orange-400/40 text-[#A1A1AA] hover:text-orange-300 rounded-sm transition"><Clock className="w-3.5 h-3.5" /></button>
                        )}
                        {!isSelf && (a.banned ? (
                          <button title={t('acc_action_unban')} onClick={() => doAction('/accounts/unban', a.key_id)} className="p-1.5 border border-emerald-400/40 text-emerald-300 rounded-sm"><ShieldOff className="w-3.5 h-3.5" /></button>
                        ) : (
                          <button title={t('acc_action_ban')} onClick={() => ban(a)} data-testid={`acc-ban-${a.key_id}`} className="p-1.5 border border-white/15 hover:border-red-500/60 text-[#A1A1AA] hover:text-red-300 rounded-sm transition"><Skull className="w-3.5 h-3.5" /></button>
                        ))}
                        {a.role === 'creator' && (
                          <button
                            title={isSelf ? t('acc_remove_creator_btn') : t('acc_remove_creator_other_btn')}
                            onClick={() => removeCreatorMode(a)}
                            disabled={removing}
                            data-testid={`acc-remove-creator-${a.key_id}`}
                            className="p-1.5 border border-red-400/40 hover:border-red-500 text-red-300 hover:bg-red-500/10 rounded-sm transition disabled:opacity-50"
                          >
                            <ShieldOff className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {!isSelf && (
                          <button
                            title={t('acc_delete_btn')}
                            onClick={() => deleteOne(a)}
                            data-testid={`acc-delete-${a.key_id}`}
                            className="p-1.5 border border-red-500/60 hover:bg-red-500/20 text-red-200 rounded-sm transition"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  )})}
                </div>
                {/* Bottom bar: clear-view (local-only) + delete-all (DB-level) */}
                <div className="border-t border-white/10 px-3 py-2 flex items-center gap-2 flex-wrap flex-shrink-0">
                  {hidden.size > 0 ? (
                    <button onClick={resetView} data-testid="acc-reset-view" className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm transition">
                      {t('acc_reset_view_btn')} ({hidden.size})
                    </button>
                  ) : (
                    <button onClick={clearView} disabled={filtered.length === 0} data-testid="acc-clear-view" className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm transition disabled:opacity-40">
                      {t('acc_clear_view_btn')}
                    </button>
                  )}
                  <button onClick={deleteAll} data-testid="acc-delete-all" className="ml-auto inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-red-500/60 text-red-200 hover:bg-red-500/20 rounded-sm font-['Chivo'] font-bold transition">
                    <Trash2 className="w-3 h-3" />{t('acc_delete_all_btn')}
                  </button>
                </div>
              </>
          </div>
        </div>
      )}

      {excluding && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/80 p-4" onClick={() => setExcluding(null)}>
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-sm bg-[#0A0A0A] border border-orange-400/40 rounded-sm p-4 space-y-3">
            <h3 className="text-sm font-['Chivo'] font-bold text-orange-200">{t('acc_exclude_choose_duration')}</h3>
            <div className="grid grid-cols-2 gap-2">
              {EXCLUDE_DURATIONS.map((d) => (
                <button
                  key={d.k}
                  onClick={() => exclude(excluding.a.key_id, d.minutes)}
                  data-testid={`exclude-${d.minutes}`}
                  className="px-3 py-2 border border-orange-400/40 text-orange-200 hover:bg-orange-400/10 rounded-sm text-xs font-['Chivo'] font-bold transition"
                >
                  {t(d.k)}
                </button>
              ))}
              <button
                onClick={() => {
                  const m = parseInt(window.prompt(t('acc_exclude_custom'), '60') || '0', 10);
                  if (m > 0) exclude(excluding.a.key_id, m);
                }}
                className="col-span-2 px-3 py-2 border border-white/20 text-white hover:bg-white/5 rounded-sm text-xs font-['Chivo'] transition"
              >
                {t('acc_exclude_custom')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
