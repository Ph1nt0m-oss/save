/**
 * iter143 — Input avec autocomplete @mentions par identité publique unique.
 *
 *  - Détecte le pattern `@xxx` dans le texte
 *  - Fetch /api/social/handle-search (compact) pour proposer 5 candidats
 *  - Respecte les permissions du groupe : seuls les membres visibles au
 *    caller peuvent être mentionnés (règle anti-scan des identités).
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { AtSign, Send } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function extractCurrentToken(value, cursorPos) {
  // Trouve le @xxx en cours (à gauche du curseur, jusqu'à espace ou début).
  const left = value.slice(0, cursorPos);
  const match = left.match(/@([A-Za-z0-9_.-]{0,24})$/);
  if (!match) return null;
  return { query: match[1], startIndex: match.index, endIndex: cursorPos };
}

export default function MentionInput({
  value, onChange, onSend, disabled, groupType, viewMode, placeholder = 'Message…',
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [showSug, setShowSug] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const inputRef = useRef(null);
  const cursorRef = useRef(0);

  const token = useMemo(() => extractCurrentToken(value, cursorRef.current), [value]);

  useEffect(() => {
    if (!token || !groupType) { setSuggestions([]); setShowSug(false); return; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const body = await withCreatorProof(API, axios, {
          group_type: groupType, view_mode: viewMode,
        });
        const r = await axios.post(`${API}/groups/members`, body);
        if (cancelled) return;
        const q = token.query.toLowerCase();
        const filtered = (r.data?.members || []).filter((m) => {
          if (!m.public_handle) return false;
          if (!q) return true;
          return m.public_handle.toLowerCase().includes(q)
            || (m.pseudo || '').toLowerCase().includes(q);
        }).slice(0, 6);
        setSuggestions(filtered);
        setShowSug(filtered.length > 0);
        setHighlightIdx(0);
      } catch (_e) {
        setSuggestions([]); setShowSug(false);
      }
    }, 120);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [token?.query, groupType, viewMode]); // eslint-disable-line

  const acceptSuggestion = (m) => {
    if (!token) return;
    const before = value.slice(0, token.startIndex);
    const after = value.slice(token.endIndex);
    const replacement = `@${m.public_handle} `;
    const next = `${before}${replacement}${after}`;
    onChange(next);
    setShowSug(false);
    setTimeout(() => {
      const pos = before.length + replacement.length;
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(pos, pos);
      cursorRef.current = pos;
    }, 0);
  };

  const onKeyDown = (e) => {
    if (showSug && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIdx((i) => (i + 1) % suggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIdx((i) => (i - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        acceptSuggestion(suggestions[highlightIdx]);
        return;
      }
      if (e.key === 'Escape') { setShowSug(false); return; }
    }
    if (e.key === 'Enter') { e.preventDefault(); onSend?.(); }
  };

  const onSelect = (e) => { cursorRef.current = e.target.selectionStart || 0; };

  return (
    <div className="relative flex-1">
      {showSug && (
        <div
          className="absolute bottom-full mb-1 left-0 right-0 bg-[#0A0A0A] border border-white/20 rounded-sm shadow-2xl max-h-56 overflow-y-auto"
          data-testid="mention-suggestions"
        >
          {suggestions.map((m, i) => (
            <button
              key={m.key_id}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); acceptSuggestion(m); }}
              data-testid={`mention-opt-${m.public_handle}`}
              className={`w-full text-left px-2 py-1.5 flex items-center gap-2 border-b border-white/5 last:border-b-0 ${
                i === highlightIdx ? 'bg-[#E4FF00]/15' : 'hover:bg-white/[0.04]'
              }`}
            >
              <AtSign className="w-3 h-3 text-[#E4FF00]" />
              <span className="text-xs text-white font-mono">@{m.public_handle}</span>
              <span className="text-[10px] text-white/50 truncate">{m.pseudo}</span>
            </button>
          ))}
        </div>
      )}
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => { cursorRef.current = e.target.selectionStart || e.target.value.length; onChange(e.target.value); }}
        onKeyDown={onKeyDown}
        onKeyUp={onSelect}
        onClick={onSelect}
        placeholder={placeholder}
        data-testid="group-input"
        disabled={disabled}
        className="w-full px-3 py-2 bg-[#0F0F13] border border-white/15 rounded-sm text-sm focus:outline-none focus:border-[#E4FF00]"
      />
    </div>
  );
}

export function MentionInputWithSend({ value, onChange, onSend, disabled, groupType, viewMode }) {
  return (
    <div className="border-t border-white/10 p-2 flex gap-2">
      <MentionInput
        value={value}
        onChange={onChange}
        onSend={onSend}
        disabled={disabled}
        groupType={groupType}
        viewMode={viewMode}
      />
      <button
        onClick={onSend}
        disabled={disabled || !value.trim()}
        data-testid="group-send"
        className="px-3 py-2 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90 disabled:opacity-40"
      >
        <Send className="w-4 h-4" />
      </button>
    </div>
  );
}
