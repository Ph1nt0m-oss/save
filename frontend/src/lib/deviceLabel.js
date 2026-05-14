/**
 * Best-effort browser-side device label.
 *
 * Goal: produce a human-friendly name like "Galaxy S21" / "iPhone" /
 * "Mac · Chrome" instead of the raw user-agent. Mobile browsers may expose
 * a model code in the UA string (`SM-G991B`, `Pixel 8`, etc.) which we try
 * to map to a marketing name when we can.
 */

// Samsung Galaxy S/Note/Z model codes → marketing names. Best-effort.
const SAMSUNG_MAP = [
  ['SM-G991', 'Galaxy S21'], ['SM-G996', 'Galaxy S21+'], ['SM-G998', 'Galaxy S21 Ultra'],
  ['SM-S901', 'Galaxy S22'], ['SM-S906', 'Galaxy S22+'], ['SM-S908', 'Galaxy S22 Ultra'],
  ['SM-S911', 'Galaxy S23'], ['SM-S916', 'Galaxy S23+'], ['SM-S918', 'Galaxy S23 Ultra'],
  ['SM-S921', 'Galaxy S24'], ['SM-S926', 'Galaxy S24+'], ['SM-S928', 'Galaxy S24 Ultra'],
  ['SM-S931', 'Galaxy S25'], ['SM-S936', 'Galaxy S25+'], ['SM-S938', 'Galaxy S25 Ultra'],
  ['SM-N98',  'Galaxy Note20'], ['SM-N97',  'Galaxy Note10'],
  ['SM-F94',  'Galaxy Z Fold5'], ['SM-F73',  'Galaxy Z Flip5'],
  ['SM-A',    'Galaxy A'], ['SM-M',    'Galaxy M'], ['SM-G',    'Galaxy'],
];

function browser(ua) {
  if (/Edg\//i.test(ua)) return 'Edge';
  if (/Chrome\//i.test(ua) && !/Chromium/i.test(ua)) return 'Chrome';
  if (/Firefox\//i.test(ua)) return 'Firefox';
  if (/Safari\//i.test(ua)) return 'Safari';
  return '';
}

export function detectDeviceLabel() {
  if (typeof navigator === 'undefined') return 'Inconnu';
  const ua = navigator.userAgent || '';

  if (/iPad/i.test(ua)) return 'iPad';
  if (/iPhone/i.test(ua)) return 'iPhone';

  // Android — Chrome 110+ freezes the model to "K" in the UA string for
  // privacy. Fallback heuristic: probe navigator.userAgentData.getHighEntropy
  // ONCE at module load, cache to localStorage. Returns "Android" until the
  // probe resolves (label can be refreshed on next visit).
  if (/Android/i.test(ua)) {
    const cached = (() => { try { return localStorage.getItem('codeforge_device_label_uach') || ''; } catch (_) { return ''; } })();
    if (cached) return cached;
    // Synchronous fallback first (works on old Chrome / WebView / Firefox).
    const m = ua.match(/\(([^)]*Android[^)]*)\)/i);
    if (m && m[1]) {
      const after = m[1].split(';').slice(2).join(';').trim();
      if (after) {
        const model = after.replace(/\s+Build\/.*$/i, '').trim();
        if (model && model !== 'K' && model.length < 40) {
          for (const [code, friendly] of SAMSUNG_MAP) {
            if (model.startsWith(code)) return friendly;
          }
          if (/^Pixel/i.test(model)) return model;
          if (/^OnePlus/i.test(model)) return model;
          if (/^Mi |^Redmi/i.test(model)) return model;
          return model;
        }
      }
    }
    // Privacy-frozen UA — kick off the async UA-CH probe for next visit.
    if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
      navigator.userAgentData.getHighEntropyValues(['model', 'platform']).then((data) => {
        const model = data?.model || '';
        if (!model) return;
        let friendly = model;
        for (const [code, label] of SAMSUNG_MAP) {
          if (model.startsWith(code)) { friendly = label; break; }
        }
        try { localStorage.setItem('codeforge_device_label_uach', friendly); } catch (_) {}
      }).catch(() => {});
    }
    return 'Téléphone Android';
  }

  const b = browser(ua);
  if (/Macintosh|Mac OS X/i.test(ua)) return b ? `Mac · ${b}` : 'Mac';
  if (/Windows/i.test(ua))            return b ? `PC Windows · ${b}` : 'PC Windows';
  if (/CrOS/i.test(ua))               return b ? `Chromebook · ${b}` : 'Chromebook';
  if (/Linux/i.test(ua))              return b ? `Linux · ${b}` : 'Linux';
  return b || 'Inconnu';
}
