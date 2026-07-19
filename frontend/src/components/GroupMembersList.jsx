/**
 * iter146 Sprint 2 — Liste des membres du groupe avec filtres par rôle.
 *
 * Filtres (barre en tête de liste) : Tous · Staff · Amis · Anonymes.
 * Respecte les règles de visibilité :
 *  - Créa masquée sauf dans 'staff' ou pour les Admins (backend applique).
 *  - Anonymes montrés comme "Anonyme" sauf en Sun mode staff.
 *
 * Data-testids : gm-filter-all|staff|friends|anon, gm-member-<key_id>.
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Users, Shield, ShieldCheck, EyeOff, Crown, Heart } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function GroupMembersList({ groupType, viewMode, friendsKeyIds = [] }) {
  const [members, setMembers] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!groupType) return undefined;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, { group_type: groupType, view_mode: viewMode });
        const r = await axios.post(`${API}/groups/members`, body);
        if (!cancelled) setMembers(r.data?.members || []);
      } catch (_e) {
        if (!cancelled) setMembers([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [groupType, viewMode]);

  const filtered = useMemo(() => {
    if (filter === 'staff') return members.filter((m) => m.role === 'creator' || ['admin', 'modo'].includes(m.staff_kind));
    if (filter === 'friends') return members.filter((m) => friendsKeyIds.includes(m.key_id));
    if (filter === 'anon') return members.filter((m) => m.anonymous === true);
    return members;
  }, [members, filter, friendsKeyIds]);

  const counts = useMemo(() => ({
    all: members.length,
    staff: members.filter((m) => m.role === 'creator' || ['admin', 'modo'].includes(m.staff_kind)).length,
    friends: members.filter((m) => friendsKeyIds.includes(m.key_id)).length,
    anon: members.filter((m) => m.anonymous === true).length,
  }), [members, friendsKeyIds]);

  const FILTERS = [
    { k: 'all',     label: 'Tous',     Icon: Users,       badge: counts.all },
    { k: 'staff',   label: 'Staff',    Icon: ShieldCheck, badge: counts.staff },
    { k: 'friends', label: 'Amis',     Icon: Heart,       badge: counts.friends },
    { k: 'anon',    label: 'Anonymes', Icon: EyeOff,      badge: counts.anon },
  ];

  return (
    <div className="border-t border-white/10" data-testid="group-members-panel">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-white/5 overflow-x-auto">
        {FILTERS.map(({ k, label, Icon, badge }) => (
          <button
            key={k}
            type="button"
            onClick={() => setFilter(k)}
            data-testid={`gm-filter-${k}`}
            className={`inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-sm border whitespace-nowrap transition ${
              filter === k
                ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00]'
                : 'text-[#A1A1AA] border-white/15 hover:border-white/30'
            }`}
          >
            <Icon className="w-3 h-3" /> {label}
            <span className={`text-[9px] px-1 rounded-sm ${filter === k ? 'bg-[#050505]/20' : 'bg-white/10'}`}>
              {badge}
            </span>
          </button>
        ))}
      </div>
      <div className="max-h-40 overflow-y-auto" tabIndex={0}>
        {loading && <div className="text-[11px] text-[#71717A] p-2">Chargement…</div>}
        {!loading && filtered.length === 0 && (
          <div className="text-[11px] text-[#71717A] p-2 text-center">Aucun membre.</div>
        )}
        {filtered.map((m) => (
          <div
            key={m.key_id}
            data-testid={`gm-member-${m.key_id}`}
            className="flex items-center gap-2 px-2 py-1 hover:bg-white/[0.03] text-[11px]"
          >
            {m.role === 'creator' && <Crown className="w-3 h-3 text-[#E4FF00]" />}
            {m.staff_kind === 'admin' && <ShieldCheck className="w-3 h-3 text-orange-300" />}
            {m.staff_kind === 'modo' && <Shield className="w-3 h-3 text-cyan-300" />}
            {m.anonymous && <EyeOff className="w-3 h-3 text-white/40" />}
            <span className="text-white truncate max-w-[120px]">{m.pseudo || '—'}</span>
            {m.public_handle && (
              <span className="text-white/40 font-mono text-[10px] truncate">@{m.public_handle}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
