/**
 * iter141 — Bulle de message groupe.
 *
 * Design (spec utilisateur) :
 *  - Bordure blanche (1px)
 *  - Fond gris identique au fond du tchat (transparent avec léger noir)
 *  - Texte coloré selon le rôle de l'expéditeur (accessibilité daltoniens)
 *  - En-tête : label du rôle (Créa/Admin/Modo/Privé/Utilisateur/Anonyme)
 *    puis pseudo, puis identité publique unique (@handle)
 *
 * Couleurs par rôle :
 *   Créa      → noir (#050505 sur fond gris)
 *   Admin     → orange (#FB923C)
 *   Modo      → bleu (#60A5FA)
 *   Privé (approved) — clés validées → violet (#C084FC)
 *   Utilisateur (pending) / non-validé → vert (#4ADE80)
 *   Anonyme   → gris (#9CA3AF)
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Crown, Shield, Lock, User, EyeOff, Sparkles, Pencil, Check as CheckIcon } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function roleMeta(msg) {
  const role = msg?.from_role;
  const sk = msg?.from_staff_kind;
  if (role === 'anon') {
    return { label: 'Anonyme', color: '#9CA3AF', Icon: EyeOff };
  }
  if (role === 'creator') {
    return { label: 'Créa', color: '#050505', Icon: Crown };
  }
  if (sk === 'admin') {
    return { label: 'Admin', color: '#FB923C', Icon: Shield };
  }
  if (sk === 'modo') {
    return { label: 'Modo', color: '#60A5FA', Icon: Shield };
  }
  if (role === 'approved') {
    return { label: 'Privé', color: '#C084FC', Icon: Lock };
  }
  if (role === 'pending') {
    return { label: 'Utilisateur', color: '#4ADE80', Icon: User };
  }
  return { label: 'Utilisateur', color: '#4ADE80', Icon: User };
}

export default function MessageBubble({ message, revealAnonymous = false }) {
  // iter146 — Alias local (renommage personnel). Hooks AVANT early return
  // pour respecter les rules-of-hooks React.
  const [alias, setAlias] = useState('');
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const canRename = !!message?.from_key_id && message?.from_role !== 'anon' && message?.from_role !== 'bot';

  useEffect(() => {
    if (!canRename) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/rename/local/list`, body);
        if (cancelled) return;
        const match = (r.data?.aliases || []).find((a) => a.target_key_id === message.from_key_id);
        setAlias(match?.alias || '');
      } catch (_e) { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, [message?.from_key_id, canRename]);

  if (!message) return null;
  const { label, color, Icon } = roleMeta(message);
  const pseudo = message.from_pseudo || (message.from_key_id || '').slice(0, 10);
  const handle = message.from_public_handle || '';
  const ts = message.ts ? new Date(message.ts) : null;

  const saveAlias = async () => {
    try {
      const body = await withCreatorProof(API, axios, {
        target_key_id: message.from_key_id,
        alias: draft.trim() || null,
      });
      await axios.post(`${API}/rename/local/set`, body);
      setAlias(draft.trim());
      setEditing(false);
    } catch (_e) { /* silent */ }
  };

  const displayPseudo = alias || pseudo;

  return (
    <div
      className="rounded-md px-3 py-2 bg-[#111114]/70 border border-white/95"
      data-testid={`msg-bubble-${message.message_id}`}
      style={{ borderWidth: '1px' }}
    >
      {/* Header row : icon + role label + pseudo + @handle + timestamp */}
      <div className="flex items-center gap-2 flex-wrap text-[11px] mb-1">
        <Icon className="w-3 h-3" style={{ color }} />
        <span
          className="font-bold uppercase tracking-wide"
          style={{ color }}
          data-testid="msg-role-label"
        >
          {label}
        </span>
        <span className="text-white/70">·</span>
        <span
          className="font-bold text-white"
          data-testid="msg-pseudo"
          title={alias ? `Pseudo officiel : ${pseudo}` : undefined}
        >
          {displayPseudo}
          {alias && <span className="ml-1 text-[10px] text-white/50">(alias)</span>}
        </span>
        {handle ? (
          <span
            className="text-white/50 text-[10px] font-mono"
            data-testid="msg-public-handle"
          >
            @{handle}
          </span>
        ) : null}
        {canRename && !editing && (
          <button
            type="button"
            onClick={() => { setDraft(alias || ''); setEditing(true); }}
            data-testid={`msg-rename-local-${message.message_id}`}
            title="Renommer localement (visible que par toi)"
            className="text-white/30 hover:text-[#E4FF00] transition p-0.5"
          >
            <Pencil className="w-3 h-3" />
          </button>
        )}
        {editing && (
          <span className="inline-flex items-center gap-1">
            <input
              autoFocus
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') saveAlias(); if (e.key === 'Escape') setEditing(false); }}
              maxLength={30}
              placeholder="alias"
              data-testid={`msg-rename-input-${message.message_id}`}
              className="bg-black/40 border border-white/20 rounded-sm px-1.5 py-0.5 text-[11px] text-white w-24"
            />
            <button
              type="button"
              onClick={saveAlias}
              data-testid={`msg-rename-save-${message.message_id}`}
              className="text-emerald-300 hover:text-emerald-200"
            >
              <CheckIcon className="w-3 h-3" />
            </button>
          </span>
        )}
        {message._revealed_from_anonymous && revealAnonymous ? (
          <span className="text-[10px] text-amber-300 inline-flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> révélé (Soleil)
          </span>
        ) : null}
        {ts && (
          <span className="text-white/40 text-[10px] ml-auto">
            {ts.toLocaleString()}
          </span>
        )}
      </div>
      {/* Message body : text color follows the role. Mentions @handle
          rendered with highlight. */}
      <div
        className="text-sm whitespace-pre-wrap break-words"
        style={{ color }}
        data-testid="msg-body"
      >
        {renderWithMentions(message.content, color)}
      </div>
    </div>
  );
}

/**
 * iter142 — Découpe le texte pour styler @handle en surbrillance.
 * Un handle vaut : @ suivi de 3-24 caractères [A-Za-z0-9_.-].
 */
function renderWithMentions(text, roleColor) {
  if (!text) return null;
  const parts = [];
  const re = /@([A-Za-z0-9_.-]{3,24})/g;
  let last = 0;
  let m;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(
      <span
        key={`m-${i}`}
        data-testid="msg-mention"
        className="px-1 py-0.5 rounded-sm bg-white/10 font-mono text-[13px]"
        style={{ color: '#E4FF00' }}
      >
        @{m[1]}
      </span>,
    );
    last = m.index + m[0].length;
    i += 1;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
