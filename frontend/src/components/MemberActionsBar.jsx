/**
 * iter140 Phase 2 — Barre d'actions par membre (6 boutons)
 *
 * Utilisée dans les tchats de groupe ET les messages privés. 6 icônes :
 *   🔇 Mute       (impossible sur supérieur hiérarchique)
 *   🔕 Notif OFF  (fonctionne sur tous, y compris supérieurs)
 *   🚫 Bloquer    (empêche demandes clé / messages entrants)
 *   ⚠️  Signaler
 *   👥 Demande d'ami (envoi clé en ami)
 *   🗑  Supprimer  (supprime le message dans le contexte fourni)
 */
import React, { useState } from 'react';
import axios from 'axios';
import { VolumeX, BellOff, Ban, AlertTriangle, UserPlus, Trash2 } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Ordre hiérarchique côté client (miroir du backend).
const TIER = { users: 1, private: 2, modo: 3, admin: 4, creator: 5 };

function tierOf(target) {
  if (!target) return 0;
  if (target.role === 'creator') return TIER.creator;
  if (target.staff_kind === 'admin') return TIER.admin;
  if (target.staff_kind === 'modo') return TIER.modo;
  if (target.role === 'approved') return TIER.private;
  if (target.role === 'pending') return TIER.users;
  return 0;
}

export default function MemberActionsBar({
  me, target, prefs = {}, onDelete, className = '',
}) {
  const [busy, setBusy] = useState(null);
  if (!target?.key_id) return null;
  const isSelf = me?.key_id === target.key_id;
  if (isSelf) return null; // Auto-actions interdites

  const call = async (action, extra = {}) => {
    setBusy(action);
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: target.key_id, action, ...extra });
      await axios.post(`${API}/social/member/action`, body);
      toast.success(`${action} appliqué`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${action} impossible`);
    } finally {
      setBusy(null);
    }
  };

  const canMute = tierOf(target) <= tierOf(me);
  const isMuted = (prefs.mutes || []).includes(target.key_id);
  const isNotifOff = (prefs.notif_off || []).includes(target.key_id);
  const isBlocked = (prefs.blocks || []).includes(target.key_id);

  const Btn = ({ id, Icon, label, onClick, active, disabled, testId, cls = '' }) => (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy === id}
      title={label + (disabled ? ' (non autorisé)' : '')}
      data-testid={testId}
      className={`w-6 h-6 flex items-center justify-center rounded-sm border transition ${
        active ? 'bg-[#E4FF00]/20 border-[#E4FF00]/50 text-[#E4FF00]' : 'border-white/15 text-white/70 hover:text-white hover:border-white/30'
      } ${disabled ? 'opacity-40 cursor-not-allowed' : ''} ${cls}`}
    >
      <Icon className="w-3 h-3" />
    </button>
  );

  return (
    <div className={`inline-flex items-center gap-1 ${className}`} data-testid={`member-actions-${target.key_id}`}>
      <Btn id="mute" Icon={VolumeX}
        label={canMute ? (isMuted ? 'Démute' : 'Mute') : 'Impossible sur un supérieur'}
        onClick={() => call(isMuted ? 'unmute' : 'mute')}
        active={isMuted} disabled={!canMute}
        testId={`member-mute-${target.key_id}`}
      />
      <Btn id="notif" Icon={BellOff}
        label={isNotifOff ? 'Réactive notifs' : 'Coupe notifs (autorisé sur tous)'}
        onClick={() => call(isNotifOff ? 'notif_on' : 'notif_off')}
        active={isNotifOff}
        testId={`member-notif-${target.key_id}`}
      />
      <Btn id="block" Icon={Ban}
        label={isBlocked ? 'Débloque' : 'Bloque'}
        onClick={() => call(isBlocked ? 'unblock' : 'block')}
        active={isBlocked}
        testId={`member-block-${target.key_id}`}
      />
      <Btn id="report" Icon={AlertTriangle}
        label="Signaler"
        onClick={() => { const r = window.prompt('Motif du signalement ?', ''); if (r !== null) call('report', { reason: r }); }}
        testId={`member-report-${target.key_id}`}
      />
      <Btn id="friend" Icon={UserPlus}
        label="Demander en ami (clé)"
        onClick={() => call('friend_req')}
        testId={`member-friend-${target.key_id}`}
      />
      <Btn id="delete" Icon={Trash2}
        label="Supprimer message"
        onClick={() => onDelete?.(target)}
        cls="hover:!text-red-300 hover:!border-red-400/40"
        disabled={!onDelete}
        testId={`member-delete-${target.key_id}`}
      />
    </div>
  );
}
