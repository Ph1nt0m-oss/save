/**
 * iter92 — Hook + helper pour traduire dynamiquement les noms de tchats/projets
 * selon la langue UI active. Cache localStorage par (project_id × langue) pour
 * éviter les re-traductions inutiles, et appelle `/api/projects/translate-name`
 * (cache backend MongoDB côté serveur) en fallback.
 *
 * Usage :
 *   const translatedName = useTranslatedProjectName(project);
 *   <span>{translatedName}</span>  // affiche le nom dans la langue courante
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STORAGE_KEY = 'codeforge_chat_name_translations';

// Cache structure: { [project_id]: { [lang]: translated } }
const readCache = () => {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
  catch { return {}; }
};
const writeCache = (obj) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(obj)); } catch { /* silent */ }
};

const inflightCalls = {};  // dedup concurrent requests for same (pid, lang)

export function useTranslatedProjectName(project) {
  const { language } = useLanguage();
  const [name, setName] = useState(project?.name || '');

  useEffect(() => {
    if (!project?.project_id) { setName(project?.name || ''); return; }
    const original = project.name || '';
    if (!original) { setName(''); return; }
    // Si la langue UI est celle d'origine probable (heuristique fr default),
    // on ne traduit pas — affiche tel quel.
    // L'utilisatrice peut aussi forcer la traduction via le contexte.
    const pid = project.project_id;
    const cache = readCache();
    const cached = cache[pid]?.[language];
    if (cached) { setName(cached); return; }

    let cancelled = false;
    const key = `${pid}__${language}`;
    if (inflightCalls[key]) {
      inflightCalls[key].then(v => { if (!cancelled && v) setName(v); });
      return () => { cancelled = true; };
    }
    inflightCalls[key] = (async () => {
      try {
        const r = await axios.post(`${API}/projects/translate-name`, {
          project_id: pid, target_lang: language, name: original,
        }, { withCredentials: true });
        const t = r?.data?.translated || original;
        // Persist
        const c = readCache();
        c[pid] = { ...(c[pid] || {}), [language]: t };
        writeCache(c);
        return t;
      } catch {
        return original;
      } finally {
        setTimeout(() => { delete inflightCalls[key]; }, 100);
      }
    })();
    inflightCalls[key].then(v => { if (!cancelled) setName(v || original); });
    // Set fallback immediately to avoid blank UI
    setName(original);
    return () => { cancelled = true; };
  }, [project?.project_id, project?.name, language]);

  return name;
}

// Helper standalone pour code impératif (hors hooks)
export async function translateProjectNameOnce(projectId, name, targetLang) {
  if (!projectId || !name) return name;
  const cache = readCache();
  if (cache[projectId]?.[targetLang]) return cache[projectId][targetLang];
  try {
    const r = await axios.post(`${API}/projects/translate-name`, {
      project_id: projectId, target_lang: targetLang, name,
    }, { withCredentials: true });
    const t = r?.data?.translated || name;
    const c = readCache();
    c[projectId] = { ...(c[projectId] || {}), [targetLang]: t };
    writeCache(c);
    return t;
  } catch { return name; }
}

// Invalide le cache localStorage pour un projet (ex: après rename)
export function invalidateLocalNameCache(projectId) {
  const c = readCache();
  if (c[projectId]) {
    delete c[projectId];
    writeCache(c);
  }
}
