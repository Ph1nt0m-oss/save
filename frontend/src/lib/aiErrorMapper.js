/**
 * iter158.7 — Chantier 4 : AI Error Mapper (frontend).
 *
 * Miroir de `backend/utils/ai_error_mapper.py`. Classifie une erreur axios
 * (ou un objet reçu du backend contenant `error_code`) en une catégorie
 * précise avec une clé i18n.
 *
 * Utilisation :
 *   import { classifyAiError } from '../lib/aiErrorMapper';
 *   const { code, i18nKey, fallback } = classifyAiError(error, { provider: 'ollama' });
 *   toast.error(t(i18nKey) || fallback);
 */

const CF_RE = /cloudflare|<!doctype|<html|cf-ray|bad gateway|gateway time|service unavailable/i;
const OLLAMA_OFFLINE_RE = /ollama.*not.*available|connection refused|11434|no such host|localhost:11434|ollama absent|ollama unreachable/i;
const OLLAMA_MODEL_MISSING_RE = /model.*not found|pull the model|model.*missing|not.*downloaded/i;

const FR_MESSAGES = {
  cloudflare: "Le service IA est momentanément surchargé côté Cloudflare. Réessaie dans quelques instants — ta demande n'a pas été perdue.",
  ollama_offline: "Ollama n'est pas joignable (mode offline). Vérifie que l'application locale Ollama est bien démarrée sur ta machine et que le modèle est installé.",
  ollama_error: "Ollama a répondu avec une erreur. Vérifie que le modèle demandé est disponible (`ollama pull …`).",
  timeout: "La réponse de l'IA a mis trop de temps à arriver (timeout). Réessaie ; si le problème persiste, allège ta demande.",
  json_invalid: "L'IA a renvoyé une réponse dans un format inattendu. Réessaie — le prompt sera re-soumis.",
  auth_error: "Clé d'accès IA absente ou invalide côté serveur. Contacte le créateur — aucune action de ton côté n'est nécessaire.",
  rate_limit: "Trop de requêtes IA récemment (rate limit du fournisseur). Réessaie dans une minute.",
  provider_error: "Le fournisseur IA a répondu avec une erreur temporaire. Réessaie dans quelques instants.",
  network: "Problème de connexion réseau. Vérifie ta connexion et réessaie.",
  unknown: "Une erreur est survenue pendant la génération. Réessaie dans un instant.",
};

function mk(code, extra = {}) {
  return {
    code,
    i18nKey: `ai_err_${code}`,
    fallback: FR_MESSAGES[code] || FR_MESSAGES.unknown,
    ...extra,
  };
}

/**
 * @param {any} error   — axios error, fetch error, ou string
 * @param {object} opts — { provider?, context? }
 */
export function classifyAiError(error, opts = {}) {
  if (!error) return mk('unknown');
  const provider = (opts.provider || '').toLowerCase();

  // 1) Backend a déjà classifié → renvoie directement.
  const backendCode = error?.response?.data?.error_code
    || error?.error_code
    || error?.code;
  if (backendCode && FR_MESSAGES[backendCode]) return mk(backendCode);

  // 2) Axios error décomposition
  const status = error?.response?.status;
  const body = error?.response?.data;
  const raw = typeof body === 'string' ? body
    : (body?.detail ? String(body.detail) : '');
  const msg = String(error?.message || raw || '').slice(0, 800);
  const combined = `${raw} ${msg}`.trim();
  const codeStr = String(error?.code || '').toLowerCase();

  // 3) Timeout — priorité haute
  if (codeStr === 'econnaborted' || /timeout/i.test(codeStr) || /timeout/i.test(msg)) {
    return mk('timeout');
  }
  if (status === 504) return mk('timeout');

  // 4) Cloudflare
  if (combined && CF_RE.test(combined)) return mk('cloudflare');

  // 5) Ollama
  if (provider === 'ollama' && combined) {
    if (OLLAMA_MODEL_MISSING_RE.test(combined)) return mk('ollama_error');
    return mk('ollama_error');
  }
  if (combined && OLLAMA_OFFLINE_RE.test(combined)) return mk('ollama_offline');

  // 6) Auth
  if (status === 401 || status === 403) return mk('auth_error');

  // 7) Rate limit
  if (status === 429) return mk('rate_limit');

  // 8) JSON invalid (SyntaxError / JSON.parse failure)
  if (error instanceof SyntaxError && /JSON/i.test(msg)) return mk('json_invalid');
  if (/unexpected token|json.*parse|jsondecode/i.test(msg)) return mk('json_invalid');

  // 9) Network
  if (codeStr.startsWith('err_network') || /network error/i.test(msg)) return mk('network');
  if (!error?.response && codeStr === 'err_bad_request') return mk('network');

  // 10) Provider error (5xx / 4xx)
  if (status && status >= 500 && status < 600) return mk('provider_error');
  if (status && status >= 400 && status < 500) return mk('provider_error');

  return mk('unknown');
}

export { FR_MESSAGES as AI_ERR_FALLBACK_FR };
