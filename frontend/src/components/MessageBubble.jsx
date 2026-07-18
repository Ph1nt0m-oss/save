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
import React from 'react';
import { Crown, Shield, Lock, User, EyeOff, Sparkles } from 'lucide-react';

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
  if (!message) return null;
  const { label, color, Icon } = roleMeta(message);
  const pseudo = message.from_pseudo || (message.from_key_id || '').slice(0, 10);
  const handle = message.from_public_handle || '';
  const ts = message.ts ? new Date(message.ts) : null;

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
        >
          {pseudo}
        </span>
        {handle ? (
          <span
            className="text-white/50 text-[10px] font-mono"
            data-testid="msg-public-handle"
          >
            @{handle}
          </span>
        ) : null}
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
