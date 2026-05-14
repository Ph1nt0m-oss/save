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

  // iOS — UA never exposes the iPhone model. Just say "iPhone" or "iPad".
  if (/iPad/i.test(ua)) return 'iPad';
  if (/iPhone/i.test(ua)) return 'iPhone';

  // Android — try to extract the model code from the parenthesised chunk
  //   e.g. "(Linux; Android 13; SM-G991B Build/TP1A...)"
  if (/Android/i.test(ua)) {
    const m = ua.match(/\(([^)]*Android[^)]*)\)/i);
    if (m && m[1]) {
      const inside = m[1];
      // Parts after "Android <ver>;" — typically the model code, then a Build/
      const after = inside.split(';').slice(2).join(';').trim(); // drop "Linux", "Android X"
      if (after) {
        // Strip trailing " Build/..." if present
        const model = after.replace(/\s+Build\/.*$/i, '').trim();
        // Map Samsung codes
        for (const [code, friendly] of SAMSUNG_MAP) {
          if (model.startsWith(code)) return friendly;
        }
        // Pixel, OnePlus, etc. — keep as is, prefixed with brand when obvious
        if (/^Pixel/i.test(model)) return model;
        if (/^OnePlus/i.test(model)) return model;
        if (/^Mi |^Redmi/i.test(model)) return model;
        if (model.length > 0 && model.length < 40) return model;
      }
    }
    return 'Android';
  }

  // Desktop
  const b = browser(ua);
  if (/Macintosh|Mac OS X/i.test(ua)) return b ? `Mac · ${b}` : 'Mac';
  if (/Windows/i.test(ua))            return b ? `PC Windows · ${b}` : 'PC Windows';
  if (/CrOS/i.test(ua))               return b ? `Chromebook · ${b}` : 'Chromebook';
  if (/Linux/i.test(ua))              return b ? `Linux · ${b}` : 'Linux';
  return b || 'Inconnu';
}
