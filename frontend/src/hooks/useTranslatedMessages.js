/**
 * iter94 — Hook pour traduire dynamiquement le contenu des messages de chat
 * selon la langue UI courante. Batch + cache localStorage + dedup.
 *
 * Usage :
 *   const translated = useTranslatedMessages(messages);
 *   // translated[i] = { ...messages[i], displayed_content: '...' }
 */
import { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STORAGE_KEY = 'codeforge_chat_message_translations';

const readCache = () => {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
  catch { return {}; }
};
const writeCache = (obj) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(obj)); } catch { /* silent */ }
};

export function useTranslatedMessages(messages, options = {}) {
  const { language } = useLanguage();
  const { enabled = true, defaultLang = 'fr' } = options;
  const [translatedMap, setTranslatedMap] = useState({});  // {message_id: translated_content}
  const inflightRef = useRef(false);

  useEffect(() => {
    // Si traduction désactivée OU langue UI == langue par défaut, ne traduit pas.
    if (!enabled || !language || language === defaultLang || !Array.isArray(messages) || messages.length === 0) {
      setTranslatedMap({});
      return;
    }
    if (inflightRef.current) return;

    // Lecture cache localStorage
    const cache = readCache();
    const cacheBucket = cache[language] || {};
    const map = {};
    const needBackend = [];
    for (const m of messages) {
      const mid = m.message_id || m.id;
      const content = m.content || '';
      if (!mid || !content) continue;
      if (cacheBucket[mid]) {
        map[mid] = cacheBucket[mid];
      } else {
        needBackend.push({ message_id: mid, content });
      }
    }
    setTranslatedMap(map);

    if (needBackend.length === 0) return;

    // Appel backend batch
    inflightRef.current = true;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.post(`${API}/chat/translate-messages`, {
          messages: needBackend,
          target_lang: language,
        }, { withCredentials: true });
        if (cancelled) return;
        const newTrans = r?.data?.translations || {};
        // Merge + persist
        const updated = { ...map, ...newTrans };
        setTranslatedMap(updated);
        const cache2 = readCache();
        cache2[language] = { ...(cache2[language] || {}), ...newTrans };
        writeCache(cache2);
      } catch { /* silent */ }
      finally { inflightRef.current = false; }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language, messages?.length, messages?.[messages?.length - 1]?.message_id]);

  // Retourne les messages avec un `displayed_content` éventuellement traduit
  if (!enabled || !language || language === defaultLang) {
    return messages;
  }
  return (messages || []).map((m) => {
    const mid = m.message_id || m.id;
    const t = mid && translatedMap[mid];
    return t ? { ...m, displayed_content: t, _is_translated: true } : { ...m, displayed_content: m.content };
  });
}
