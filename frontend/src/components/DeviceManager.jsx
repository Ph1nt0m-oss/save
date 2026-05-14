import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { X, Crown, Check, Trash2, Power, KeyRound, Copy, ShieldCheck, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof, exportPublicKeyShareCode, parsePublicKeyShareCode } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROLE_META = {
  creator:  { tk: 'role_creator',  color: 'text-[#E4FF00] border-[#E4FF00]/40 bg-[#E4FF00]/10', icon: Crown },
  approved: { tk: 'role_approved', color: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10', icon: ShieldCheck },
  pending:  { tk: 'role_pending',  color: 'text-amber-300 border-amber-400/40 bg-amber-400/10', icon: ShieldAlert },
  revoked:  { tk: 'role_revoked',  color: 'text-red-300 border-red-400/40 bg-red-400/10', icon: ShieldAlert },
};

/**
 * Modal accessible from UserMenu.
 *  - Creator view: list, approve, revoke, disconnect, promote-to-creator,
 *    add-by-key (paste another device's public key).
 *  - Non-creator view: just shows their own share-code with copy button.
 */
export default function DeviceManager({ open, onClose, role, currentKeyId }) {
  const { t } = useLanguage();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [myShareCode, setMyShareCode] = useState('');
  const [pasteCode, setPasteCode] = useState('');
  const [promotePwd, setPromotePwd] = useState('');
  const [promoteTarget, setPromoteTarget] = useState(null);
  const isCreator = role === 'creator';

  useEffect(() => {
    if (!open) return;
    exportPublicKeyShareCode().then(setMyShareCode).catch(() => {});
    if (isCreator) refreshList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const refreshList = async () => {
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/devices/list`, body);
      setDevices(r.data?.devices || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_list_unavailable'));
    } finally { setLoading(false); }
  };

  const callTarget = async (path, target_key_id, extra = {}) => {
    try {
      const body = await withCreatorProof(API, axios, { target_key_id, ...extra });
      await axios.post(`${API}${path}`, body);
      toast.success(t('dm_op_done'));
      refreshList();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_op_failed'));
    }
  };

  const handleAddByKey = async () => {
    const jwk = parsePublicKeyShareCode(pasteCode);
    if (!jwk) { toast.error(t('dm_invalid_code')); return; }
    try {
      const body = await withCreatorProof(API, axios, { public_key_jwk: jwk, role: 'approved' });
      const r = await axios.post(`${API}/devices/add-by-key`, body);
      toast.success(`${t('dm_added')} (${r.data?.key_id?.slice(0, 12)}…)`);
      setPasteCode('');
      refreshList();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_add_failed'));
    }
  };

  const handlePromote = async () => {
    if (!promoteTarget || !promotePwd) return;
    try {
      const body = await withCreatorProof(API, axios, {
        target_key_id: promoteTarget,
        password: promotePwd,
      });
      await axios.post(`${API}/devices/promote-creator`, body);
      toast.success(t('dm_promoted'));
      setPromoteTarget(null);
      setPromotePwd('');
      refreshList();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('dm_promote_failed'));
    }
  };

  const copyShareCode = async () => {
    try {
      await navigator.clipboard.writeText(myShareCode);
      toast.success(t('dm_copied'));
    } catch { toast.error(t('dm_copy_failed')); }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
      data-testid="device-manager-modal"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-w-2xl w-full max-h-[85vh] overflow-y-auto bg-[#0A0A0A] border border-white/15 rounded-sm p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-[#E4FF00]" />
            <h2 className="text-lg font-['Chivo'] font-bold text-white">{t('dm_title')}</h2>
          </div>
          <button onClick={onClose} data-testid="device-manager-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Always: my share code (so user can give it to creator offline) */}
        <section className="bg-white/[0.03] border border-white/10 rounded-sm p-3 space-y-2">
          <div className="text-xs uppercase tracking-widest text-[#71717A]">Ma clé d'appareil (à partager hors-ligne)</div>
          <div className="flex items-center gap-2">
            <code
              className="flex-1 text-[11px] text-emerald-300 bg-black/40 px-2 py-1.5 rounded-sm overflow-x-auto whitespace-nowrap"
              data-testid="my-share-code"
            >
              {myShareCode || '…'}
            </code>
            <button
              onClick={copyShareCode}
              data-testid="copy-share-code"
              className="flex-shrink-0 px-2 py-1.5 border border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] rounded-sm text-xs transition"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>
          <p className="text-[11px] text-[#A1A1AA]">
            {t('dm_my_key_hint')}
          </p>
        </section>

        {/* Creator panel */}
        {isCreator && (
          <>
            <section className="bg-white/[0.03] border border-white/10 rounded-sm p-3 space-y-2">
              <div className="text-xs uppercase tracking-widest text-[#71717A]">{t('dm_add_by_key_title')}</div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder={t('dm_add_placeholder')}
                  value={pasteCode}
                  onChange={(e) => setPasteCode(e.target.value)}
                  data-testid="paste-share-code"
                  className="flex-1 bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
                />
                <button
                  onClick={handleAddByKey}
                  data-testid="add-by-key-btn"
                  className="px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold text-xs rounded-sm hover:bg-white transition"
                >
                  {t('dm_add_btn')}
                </button>
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-['Chivo'] font-bold text-white">{t('dm_registered_devices')}</h3>
                <button onClick={refreshList} className="text-xs text-[#A1A1AA] hover:text-white">{t('dm_refresh')}</button>
              </div>
              {loading && <div className="text-xs text-[#A1A1AA]">{t('dm_loading')}</div>}
              <div className="space-y-2">
                {devices.map((d) => {
                  const meta = ROLE_META[d.role] || ROLE_META.pending;
                  const Mi = meta.icon;
                  const isMe = d.key_id === currentKeyId;
                  return (
                    <div
                      key={d.key_id}
                      data-testid={`device-row-${d.key_id}`}
                      className="bg-black/30 border border-white/10 rounded-sm p-3 flex items-start gap-3"
                    >
                      <Mi className="w-4 h-4 text-[#A1A1AA] mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-1.5 py-0.5 border rounded-sm ${meta.color}`}>
                            {t(meta.tk)}
                          </span>
                          {isMe && (
                            <span className="text-[10px] uppercase tracking-widest text-[#E4FF00]">{t('dm_me')}</span>
                          )}
                          {d.label && <span className="text-xs text-white truncate">{d.label}</span>}
                        </div>
                        <code className="block text-[10px] text-[#71717A] truncate mt-1">{d.key_id}</code>
                        <div className="text-[10px] text-[#71717A] mt-0.5">
                          {d.last_seen_at ? t('dm_seen').replace('{when}', new Date(d.last_seen_at).toLocaleString()) : t('dm_never_seen')}
                        </div>
                      </div>
                      <div className="flex flex-col gap-1 flex-shrink-0">
                        {d.role === 'pending' && (
                          <button
                            onClick={() => callTarget('/devices/approve', d.key_id)}
                            data-testid={`approve-${d.key_id}`}
                            className="px-2 py-1 text-[11px] border border-emerald-400 text-emerald-300 hover:bg-emerald-400 hover:text-[#050505] rounded-sm transition"
                          >
                            <Check className="w-3 h-3 inline mr-1" />{t('dm_approve')}
                          </button>
                        )}
                        {!isMe && d.role !== 'creator' && (
                          <button
                            onClick={() => setPromoteTarget(d.key_id)}
                            data-testid={`promote-${d.key_id}`}
                            className="px-2 py-1 text-[11px] border border-[#E4FF00] text-[#E4FF00] hover:bg-[#E4FF00] hover:text-[#050505] rounded-sm transition"
                          >
                            <Crown className="w-3 h-3 inline mr-1" />{t('dm_promote')}
                          </button>
                        )}
                        {!isMe && (
                          <>
                            <button
                              onClick={() => callTarget('/devices/disconnect', d.key_id)}
                              data-testid={`disconnect-${d.key_id}`}
                              className="px-2 py-1 text-[11px] border border-amber-400 text-amber-300 hover:bg-amber-400 hover:text-[#050505] rounded-sm transition"
                            >
                              <Power className="w-3 h-3 inline mr-1" />{t('dm_disconnect')}
                            </button>
                            <button
                              onClick={() => callTarget('/devices/revoke', d.key_id)}
                              data-testid={`revoke-${d.key_id}`}
                              className="px-2 py-1 text-[11px] border border-red-400 text-red-300 hover:bg-red-400 hover:text-white rounded-sm transition"
                            >
                              <Trash2 className="w-3 h-3 inline mr-1" />{t('dm_revoke')}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
                {!loading && devices.length === 0 && (
                  <div className="text-xs text-[#A1A1AA]">{t('dm_no_devices')}</div>
                )}
              </div>
            </section>
          </>
        )}

        {/* Promote confirmation */}
        {promoteTarget && (
          <div
            className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4"
            onClick={() => setPromoteTarget(null)}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className="max-w-sm w-full bg-[#0A0A0A] border border-[#E4FF00]/40 rounded-sm p-5 space-y-3"
            >
              <div className="flex items-center gap-2">
                <Crown className="w-5 h-5 text-[#E4FF00]" />
                <h3 className="font-['Chivo'] font-bold text-white">{t('dm_promote_title')}</h3>
              </div>
              <p className="text-xs text-[#A1A1AA]">
                {t('dm_promote_hint')}
              </p>
              <input
                type="password"
                value={promotePwd}
                onChange={(e) => setPromotePwd(e.target.value)}
                data-testid="promote-password"
                placeholder={t('dm_password')}
                className="w-full bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#E4FF00]"
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => { setPromoteTarget(null); setPromotePwd(''); }}
                  className="px-3 py-1.5 text-xs text-[#A1A1AA] hover:text-white"
                >{t('dm_cancel')}</button>
                <button
                  onClick={handlePromote}
                  data-testid="promote-confirm"
                  className="px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold text-xs rounded-sm hover:bg-white transition"
                >{t('dm_confirm')}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
