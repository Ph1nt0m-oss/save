/**
 * iter158.9 — P0.2 : Cloche des notifications secrètes du propriétaire.
 *
 * Visible UNIQUEMENT sur un appareil propriétaire réel (is_owner=true).
 * Affiche les notifications générées par le backend quand :
 *   - une action est prise contre le propriétaire alors qu'il est en mode OFF
 *     (voir `ownership_guard.assert_not_owner_target` + `log_owner_notification`)
 *   - un autre propriétaire effectue une action administrative
 *     (transparence inter-propriétaires — spec CDC)
 *
 * Sécurité : le backend applique `_require_owner` sur `/ownership/notifications`
 * et `/mark-read`. Le frontend n'est jamais l'unique protection. Un délégué,
 * admin ou modo ne verra rien (endpoint retourne 403).
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Bell, BellDot, X, Check, User, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_LABEL = {
  ban: 'Bannissement',
  block: 'Blocage',
  mute: 'Mute',
  exclude: 'Exclusion',
  force_visitor: 'Mode visiteur forcé',
  disconnect: 'Déconnexion',
  rename: 'Renommage global',
  delete: 'Suppression',
  remove_creator: 'Retrait statut créa',
  promote_admin: 'Promotion admin',
  promote_modo: 'Promotion modo',
  demote: 'Rétrogradation',
};

const ROLE_BADGE = {
  creator: { label: 'Créa', cls: 'border-[#E4FF00]/60 text-[#E4FF00] bg-[#E4FF00]/10' },
  approved: { label: 'Validé', cls: 'border-white/20 text-white/70' },
  pending: { label: 'Pending', cls: 'border-white/15 text-[#71717A]' },
};

const STAFF_BADGE = {
  admin: { label: 'Admin', cls: 'border-cyan-400/60 text-cyan-300 bg-cyan-400/10' },
  modo: { label: 'Modo', cls: 'border-violet-400/60 text-violet-300 bg-violet-400/10' },
};

function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
  } catch (_) { return iso; }
}

export default function OwnerNotificationsBell() {
  const device = useDeviceIdentity();
  const [isOwner, setIsOwner] = useState(false);
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);

  // Vérifie is_owner via /ownership/status (une seule fois par device).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (device.role !== 'creator') { setIsOwner(false); return; }
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/ownership/status`, body);
        if (!cancelled) setIsOwner(!!r.data?.is_owner);
      } catch (_) { if (!cancelled) setIsOwner(false); }
    })();
    return () => { cancelled = true; };
  }, [device.role, device.keyId]);

  const refresh = useCallback(async () => {
    if (!isOwner) return;
    setLoading(true);
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/ownership/notifications`, body);
      setRows(r.data?.notifications || []);
      setUnread(r.data?.unread_count || 0);
    } catch (e) {
      // Silencieux : si backend refuse (non-owner), on masque simplement.
      setRows([]); setUnread(0);
    } finally { setLoading(false); }
  }, [isOwner]);

  // Poll ~30 s tant que la cloche est montée (léger, owner-only donc rare).
  useEffect(() => {
    if (!isOwner) return;
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, [isOwner, refresh]);

  const markAllRead = async () => {
    try {
      const body = await withCreatorProof(API, axios, {});
      await axios.post(`${API}/ownership/notifications/mark-read`, body);
      toast.success('Notifications marquées lues');
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec mark-read');
    }
  };

  if (!isOwner) return null;

  return (
    <>
      <button
        onClick={() => { setOpen(true); refresh(); }}
        data-testid="owner-notifications-bell"
        title="Notifications propriétaire (secrètes)"
        aria-label="Notifications propriétaire"
        className="relative z-[5] text-[#A1A1AA] hover:text-[#E4FF00] transition-colors p-1.5 rounded-sm hover:bg-white/[0.04] ml-1 flex-shrink-0"
      >
        {unread > 0 ? <BellDot className="w-4 h-4 text-[#E4FF00]" /> : <Bell className="w-4 h-4" />}
        {unread > 0 && (
          <span
            data-testid="owner-notifications-unread-badge"
            className="absolute -top-1 -right-1 bg-[#E4FF00] text-black text-[9px] font-bold rounded-sm px-1 leading-tight min-w-[14px] text-center"
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[86] bg-black/80 flex items-start justify-center p-3 overflow-y-auto"
          onClick={() => setOpen(false)}
          data-testid="owner-notifications-panel"
        >
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-2xl bg-[#0A0A0A] border border-[#E4FF00]/40 rounded-sm p-4 space-y-3 mt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BellDot className="w-4 h-4 text-[#E4FF00]" />
                <h3 className="text-sm font-['Chivo'] font-bold uppercase tracking-widest text-white">
                  Notifications propriétaire
                </h3>
                {unread > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 border border-[#E4FF00]/60 text-[#E4FF00] bg-[#E4FF00]/10 rounded-sm">
                    {unread} non lue{unread > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={markAllRead}
                  disabled={unread === 0}
                  data-testid="owner-notifications-mark-read"
                  className="inline-flex items-center gap-1 text-[11px] px-2 py-1.5 border border-emerald-400/60 text-emerald-300 hover:bg-emerald-400/10 rounded-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Check className="w-3 h-3" />
                  Tout marquer lu
                </button>
                <button onClick={() => setOpen(false)} data-testid="owner-notifications-close" className="text-[#A1A1AA] hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="text-[10px] text-[#71717A] italic px-1">
              Ces notifications sont visibles UNIQUEMENT par les appareils propriétaires
              (transparence inter-propriétaires). Un délégué, un admin ou un modo ne peut y accéder.
            </div>

            <div className="space-y-1 max-h-[60vh] overflow-y-auto">
              {loading && <div className="text-xs text-[#A1A1AA] py-2 text-center">Chargement…</div>}
              {!loading && rows.length === 0 && (
                <div className="text-xs text-[#A1A1AA] py-6 text-center" data-testid="owner-notifications-empty">
                  Aucune notification pour le moment.
                </div>
              )}
              {rows.map((r, i) => {
                const rb = ROLE_BADGE[r.actor_role] || null;
                const sb = STAFF_BADGE[r.actor_staff_kind] || null;
                const isSelfTarget = r.target_key_id === r.owner_key_id;
                return (
                  <div
                    key={i}
                    data-testid={`owner-notification-row-${i}`}
                    className={`bg-black/30 border rounded-sm p-2 space-y-1 ${
                      r.read ? 'border-white/10 opacity-70' : 'border-[#E4FF00]/30'
                    }`}
                  >
                    <div className="flex items-center gap-2 flex-wrap text-[11px]">
                      <span className="uppercase tracking-widest px-1.5 py-0.5 border border-white/15 rounded-sm text-white/80">
                        {ACTION_LABEL[r.action] || r.action}
                      </span>
                      {isSelfTarget && (
                        <span className="text-[9px] uppercase tracking-widest px-1 py-0.5 border border-orange-400/60 text-orange-300 bg-orange-400/10 rounded-sm">
                          contre toi (OFF)
                        </span>
                      )}
                      <div className="flex-1" />
                      {!r.read && <span className="w-1.5 h-1.5 bg-[#E4FF00] rounded-full" title="Non lu" />}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap text-[11px]">
                      <User className="w-3 h-3 text-[#71717A]" />
                      <span className="text-white/80 font-['IBM_Plex_Mono']">
                        {r.actor_public_handle ? `@${r.actor_public_handle}` : (r.actor_key_id?.slice(0, 16) || 'inconnu')}
                      </span>
                      {rb && (
                        <span className={`text-[9px] uppercase tracking-widest px-1 py-0.5 border rounded-sm ${rb.cls}`}>
                          {rb.label}
                        </span>
                      )}
                      {sb && (
                        <span className={`text-[9px] uppercase tracking-widest px-1 py-0.5 border rounded-sm ${sb.cls}`}>
                          {sb.label}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-[#71717A]">
                      <Clock className="w-2.5 h-2.5" />
                      {fmtDate(r.ts)}
                    </div>
                    {r.detail && Object.keys(r.detail).length > 0 && (
                      <div className="text-[10px] text-[#52525B] font-['IBM_Plex_Mono']">
                        {JSON.stringify(r.detail)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
