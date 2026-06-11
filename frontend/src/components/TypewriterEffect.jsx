/**
 * iter96 — TypewriterEffect : animation d'écriture mot-par-mot (style "qqun
 * tape sur clavier") pour les réponses IA. Vitesse 1.5x.
 *
 * Si `skip` est true (ex: messages déjà vus, ou modèle Emergent qui rend
 * code par code), affiche le contenu d'un coup.
 *
 * Usage:
 *   <TypewriterEffect text={message.content} skip={message._already_seen} />
 */
import React, { useEffect, useState, useRef } from 'react';

export default function TypewriterEffect({ text = '', skip = false, speed = 12, onDone }) {
  const [displayed, setDisplayed] = useState(skip ? text : '');
  const textRef = useRef(text);
  const indexRef = useRef(0);
  const timerRef = useRef(null);

  useEffect(() => {
    // Si skip → affichage instantané du texte complet
    if (skip) {
      setDisplayed(text);
      if (onDone) onDone();
      return;
    }
    // Si text a changé, reset
    if (textRef.current !== text) {
      textRef.current = text;
      indexRef.current = 0;
      setDisplayed('');
    }
    if (timerRef.current) clearInterval(timerRef.current);
    // speed = ms entre chaque caractère. 12ms = ~83 chars/sec ≈ 1.5x vitesse de frappe humaine rapide
    timerRef.current = setInterval(() => {
      if (indexRef.current >= text.length) {
        clearInterval(timerRef.current);
        timerRef.current = null;
        if (onDone) onDone();
        return;
      }
      // Avance par mot quand possible pour fluidité, sinon char par char
      const chunk = Math.random() < 0.3 ? 2 : 1;
      indexRef.current = Math.min(text.length, indexRef.current + chunk);
      setDisplayed(text.slice(0, indexRef.current));
    }, speed);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, skip]);

  return <>{displayed}{displayed.length < text.length && !skip && <span className="inline-block w-1.5 h-3 bg-current ml-0.5 animate-pulse" aria-hidden="true" />}</>;
}
