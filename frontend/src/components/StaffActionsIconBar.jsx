/**
 * iter144 — Barre d'actions staff UNIFORME.
 *
 * Affiche exactement le même nombre d'icônes pour chaque compte staff
 * selon le rôle de l'acteur (viewer). Les icônes non-autorisées sont
 * grisées (disabled) mais VISIBLES pour conserver la cohérence de mise
 * en page (spec utilisateur : "mêmes nombres d'icones dont il est
 * responsable").
 *
 * Icônes (ordre stable) :
 *   1. Eye        → visite compte (créa only)
 *   2. Pencil     → renommer (rename_global : admin+/créa)
 *   3. Shield     → promote modo
 *   4. Star       → promote admin  (bouclier étoile)
 *   5. Crown      → promote créa   (créa réelle only)
 *   6. VolumeX    → mute persistant
 *   7. Ban        → block persistant
 *   8. Clock      → exclude temporaire
 *   9. UserMinus  → force visiteur temporaire
 *  10. LogOut     → déconnexion temporaire
 *  11. XCircle    → ban définitif (admin+/créa)
 *  12. Trash2     → supprimer (créa only)
 *
 * Les fondatrices (isFounder) affichent aussi toutes les icônes mais
 * TOUTES désactivées (aucune action possible).
 */
import React, { useState } from 'react';
import axios from 'axios';
import {
  Eye, Pencil, Shield, Star, Crown, VolumeX, Ban, Clock,
  UserMinus, LogOut, XCircle, Trash2, Lock,
} from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ICONS = [
  { key: 'visit',           Icon: Eye,        label: 'Visite compte',  min: 'creator' },
  { key: 'rename_global',   Icon: Pencil,     label: 'Renommer',       min: 'admin' },
  { key: 'promote_modo',    Icon: Shield,     label: 'Promouvoir modo', min: 'admin' },
  { key: 'promote_admin',   Icon: Star,       label: 'Promouvoir admin', min: 'admin' },
  { key: 'promote_creator', Icon: Crown,      label: 'Promouvoir créa', min: 'creator' },
  { key: 'mute',            Icon: VolumeX,    label: 'Rendre muet',    min: 'modo' },
  { key: 'block',           Icon: Ban,        label: 'Bloquer',        min: 'modo' },
  { key: 'exclude',         Icon: Clock,      label: 'Exclure temp.',  min: 'modo' },
  { key: 'force_visitor',   Icon: UserMinus,  label: 'Forcer vue invité', min: 'modo' },
  { key: 'disconnect',      Icon: LogOut,     label: 'Déconnecter',    min: 'modo' },
  { key: 'ban',             Icon: XCircle,    label: 'Bannir (définitif)', min: 'admin' },
  { key: 'delete',          Icon: Trash2,     label: 'Supprimer',      min: 'creator' },
];

function rankOf(role, staffKind) {
  if (role === 'creator') return 3;
  if (staffKind === 'admin') return 2;
  if (staffKind === 'modo') return 1;
  return 0;
}
const MIN_RANK = { modo: 1, admin: 2, creator: 3 };

export default function StaffActionsIconBar({
  target,                // { key_id, pseudo, role, staff_kind, is_founder }
  viewerRole,            // effective role
  viewerStaffKind,
  onDeleteRequested,     // optional callback (parent handles the delete flow)
  onVisit,               // optional callback
  onRename,              // optional callback
  onAfterAction,         // called after successful staff action
}) {
  const [busy, setBusy] = useState(null);
  const viewerRank = rankOf(viewerRole, viewerStaffKind);
  const targetIsFounder = !!target?.is_founder;

  const call = async (action) => {
    if (!target?.key_id) return;
    if (action === 'visit') { onVisit?.(target); return; }
    if (action === 'rename_global') { onRename?.(target); return; }
    if (action === 'delete') { onDeleteRequested?.(target); return; }
    if (['ban', 'block', 'promote_creator'].includes(action) &&
        !window.confirm(`Confirmer : ${action} ${target.pseudo || 'ce compte'} ?`)) return;
    setBusy(action);
    try {
      const body = await withCreatorProof(API, axios, {
        target_key_id: target.key_id, action,
      });
      await axios.post(`${API}/staff/action`, body);
      onAfterAction?.(action, target);
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${action} impossible`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      className="flex flex-wrap items-center gap-1"
      data-testid={`staff-icon-bar-${target?.key_id}`}
    >
      {ICONS.map(({ key, Icon, label, min }) => {
        const allowed = viewerRank >= MIN_RANK[min] && !targetIsFounder;
        const isBusy = busy === key;
        return (
          <button
            key={key}
            type="button"
            title={targetIsFounder ? 'Créa fondatrice — action interdite' : label}
            onClick={() => allowed && !isBusy && call(key)}
            disabled={!allowed || isBusy}
            data-testid={`staff-action-${key}-${target?.key_id}`}
            className={`w-7 h-7 rounded-sm border inline-flex items-center justify-center transition ${
              allowed && !isBusy
                ? 'border-white/15 text-white/80 hover:border-[#E4FF00]/60 hover:text-[#E4FF00]'
                : 'border-white/5 text-white/20 cursor-not-allowed opacity-40'
            } ${targetIsFounder ? 'bg-red-500/[0.03]' : ''}`}
          >
            {targetIsFounder ? <Lock className="w-3 h-3" /> : <Icon className="w-3.5 h-3.5" />}
          </button>
        );
      })}
    </div>
  );
}
