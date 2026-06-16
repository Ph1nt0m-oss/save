/**
 * iter128.5 — CreatorChatPersona : barre d'outils créa-only qui se monte
 * au-dessus du champ d'envoi de message dans n'importe quel tchat
 * (privé, public, IA, groupe). Permet à la créatrice de :
 *   - Choisir un **persona d'envoi** : IA / Personne du compte / Créatrice
 *     (pseudo + icône libres).
 *   - Activer/désactiver la **réponse automatique de l'IA** au prochain
 *     message envoyé par la cible.
 *   - Activer/désactiver la **visibilité du message envoyé** (réponse
 *     fantôme — la créa interroge l'IA sans que la cible voie le résultat).
 *
 * Le state est exposé via le hook `useCreatorChatPersona()` ; ce composant
 * n'envoie PAS lui-même les messages — il transmet juste la configuration
 * (persona, ia_reply, visible) que le formulaire d'envoi du tchat doit
 * inclure dans son payload (`persona_override` côté backend).
 *
 * Visible uniquement si `device.role === 'creator'` (signature ECDSA),
 * jamais en simulation.
 */
import React, { useState } from 'react';
import { Bot, User, Crown, Eye, EyeOff, Sparkles, Slash } from 'lucide-react';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const PERSONAS = [
  { id: 'ai',    Icon: Bot,   color: 'text-cyan-300 border-cyan-400/40 bg-cyan-400/10',     label: 'IA' },
  { id: 'owner', Icon: User,  color: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10', label: 'Personne du compte' },
  { id: 'creator', Icon: Crown, color: 'text-[#E4FF00] border-[#E4FF00]/40 bg-[#E4FF00]/10', label: 'Créatrice (pseudo libre)' },
];

/**
 * Hook + composant. Utilisation :
 *
 *   const persona = useCreatorChatPersona();  // { id, customPseudo, customAvatar, aiReplies, visible }
 *   const onSubmit = (text) => sendMessage({ text, persona_override: persona });
 *   return (<><CreatorChatPersonaBar value={persona} onChange={setPersona} /> <ChatInput …/></>);
 *
 * Pour ne pas casser les tchats existants : si non utilisé, aucun impact.
 */
export function useCreatorChatPersona() {
  const [state, setState] = useState({
    id: 'ai',
    customPseudo: '',
    customAvatar: '',
    aiReplies: true,
    visible: true,
  });
  return [state, setState];
}

export default function CreatorChatPersonaBar({ value, onChange, className = '' }) {
  const device = useDeviceIdentity();
  // iter128.5 — Créa physique uniquement (jamais en simulation).
  if (device.role !== 'creator' || (device.viewMode && device.viewMode !== 'creator')) {
    return null;
  }

  const set = (patch) => onChange?.({ ...value, ...patch });

  return (
    <div
      data-testid="creator-chat-persona-bar"
      className={`flex items-center gap-2 flex-wrap px-2 py-1.5 border border-[#E4FF00]/40 bg-[#E4FF00]/5 rounded-sm text-[11px] ${className}`}
    >
      <span className="text-[#E4FF00] font-['Chivo'] font-bold uppercase tracking-widest text-[10px] flex items-center gap-1">
        <Sparkles className="w-3 h-3" /> Persona créa
      </span>
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          type="button"
          data-testid={`persona-${p.id}`}
          onClick={() => set({ id: p.id })}
          className={`inline-flex items-center gap-1 px-2 py-0.5 border rounded-sm transition ${value.id === p.id ? p.color : 'border-white/15 text-[#A1A1AA] hover:text-white'}`}
        >
          <p.Icon className="w-3 h-3" />
          <span>{p.label}</span>
        </button>
      ))}

      {value.id === 'creator' && (
        <>
          <input
            type="text"
            placeholder="Pseudo libre…"
            value={value.customPseudo}
            onChange={(e) => set({ customPseudo: e.target.value })}
            data-testid="persona-custom-pseudo"
            className="bg-transparent border border-white/15 px-2 py-0.5 rounded-sm text-white text-[11px] focus:outline-none focus:border-[#E4FF00]/40"
          />
          <input
            type="url"
            placeholder="URL icône…"
            value={value.customAvatar}
            onChange={(e) => set({ customAvatar: e.target.value })}
            data-testid="persona-custom-avatar"
            className="bg-transparent border border-white/15 px-2 py-0.5 rounded-sm text-white text-[11px] focus:outline-none focus:border-[#E4FF00]/40 w-40"
          />
        </>
      )}

      <button
        type="button"
        data-testid="persona-ai-reply-toggle"
        onClick={() => set({ aiReplies: !value.aiReplies })}
        title="L'IA répond automatiquement au prochain message de la cible"
        className={`inline-flex items-center gap-1 px-2 py-0.5 border rounded-sm transition ${value.aiReplies ? 'border-cyan-400/40 text-cyan-300 bg-cyan-400/10' : 'border-white/15 text-[#A1A1AA] line-through'}`}
      >
        {value.aiReplies ? <Bot className="w-3 h-3" /> : <Slash className="w-3 h-3" />}
        <span>IA répond</span>
      </button>

      <button
        type="button"
        data-testid="persona-visible-toggle"
        onClick={() => set({ visible: !value.visible })}
        title="Message visible par la cible (sinon : interrogation secrète)"
        className={`inline-flex items-center gap-1 px-2 py-0.5 border rounded-sm transition ${value.visible ? 'border-emerald-400/40 text-emerald-300 bg-emerald-400/10' : 'border-violet-400/40 text-violet-300 bg-violet-400/10'}`}
      >
        {value.visible ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        <span>{value.visible ? 'Visible' : 'Fantôme'}</span>
      </button>
    </div>
  );
}
