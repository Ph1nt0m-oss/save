/**
 * Best-effort browser-side device label.
 *
 * Goal: produce a human-friendly name like "Galaxy S21 5G" + model code
 * "SM-G991U1" (two-line display when both available) instead of the raw
 * user-agent. Mobile browsers may expose a model code via Sec-CH-UA-Model
 * or User-Agent Client Hints API; we map it to a marketing name when we
 * can.
 *
 * iter61: returns an object { product, model, label } so the caller can
 * choose to display product + model on two lines instead of a single
 * concatenated string.
 *  - product = marketing name ("Galaxy S21 5G", "iPhone 15 Pro", "Pixel 8 Pro")
 *  - model   = the raw code ("SM-G991U1", "iPhone15,2", …) when known
 *  - label   = a single-line concatenation suitable for legacy callers
 */

// Samsung Galaxy model code → marketing name. Best effort and pragmatic:
// the LONGEST prefix wins so we get "Galaxy S21 5G" (SM-G991U1) instead
// of being captured by the shorter "SM-G991" entry.
const SAMSUNG_MAP = [
  // S25 / S24 / S23 / S22 / S21 series — explicit "5G" variants come first
  ['SM-G991U1', 'Galaxy S21 5G'], ['SM-G991U', 'Galaxy S21 5G'], ['SM-G991N', 'Galaxy S21 5G'],
  ['SM-G991B', 'Galaxy S21 5G'], ['SM-G991W', 'Galaxy S21 5G'], ['SM-G991', 'Galaxy S21'],
  ['SM-G996U1', 'Galaxy S21+ 5G'], ['SM-G996B', 'Galaxy S21+ 5G'], ['SM-G996', 'Galaxy S21+'],
  ['SM-G998U1', 'Galaxy S21 Ultra 5G'], ['SM-G998B', 'Galaxy S21 Ultra 5G'], ['SM-G998', 'Galaxy S21 Ultra'],
  ['SM-S908', 'Galaxy S22 Ultra 5G'], ['SM-S906', 'Galaxy S22+ 5G'], ['SM-S901', 'Galaxy S22 5G'],
  ['SM-S918', 'Galaxy S23 Ultra 5G'], ['SM-S916', 'Galaxy S23+ 5G'], ['SM-S911', 'Galaxy S23 5G'],
  ['SM-S928', 'Galaxy S24 Ultra 5G'], ['SM-S926', 'Galaxy S24+ 5G'], ['SM-S921', 'Galaxy S24 5G'],
  ['SM-S938', 'Galaxy S25 Ultra 5G'], ['SM-S936', 'Galaxy S25+ 5G'], ['SM-S931', 'Galaxy S25 5G'],
  ['SM-N98',  'Galaxy Note20'], ['SM-N97', 'Galaxy Note10'],
  ['SM-F94',  'Galaxy Z Fold5'], ['SM-F95', 'Galaxy Z Fold6'],
  ['SM-F73',  'Galaxy Z Flip5'], ['SM-F74', 'Galaxy Z Flip6'],
  ['SM-A',    'Galaxy A'], ['SM-M',    'Galaxy M'], ['SM-G',    'Galaxy'],
];

const PIXEL_MAP = [
  ['Pixel 9 Pro XL', 'Pixel 9 Pro XL'], ['Pixel 9 Pro', 'Pixel 9 Pro'], ['Pixel 9', 'Pixel 9'],
  ['Pixel 8 Pro', 'Pixel 8 Pro'], ['Pixel 8a', 'Pixel 8a'], ['Pixel 8', 'Pixel 8'],
  ['Pixel 7 Pro', 'Pixel 7 Pro'], ['Pixel 7a', 'Pixel 7a'], ['Pixel 7', 'Pixel 7'],
  ['Pixel 6 Pro', 'Pixel 6 Pro'], ['Pixel 6a', 'Pixel 6a'], ['Pixel 6', 'Pixel 6'],
];

const IPHONE_MAP = [
  ['iPhone15,', 'iPhone 15 / 14 Pro'], ['iPhone16,', 'iPhone 15 Pro'],
  ['iPhone17,', 'iPhone 16'], ['iPhone18,', 'iPhone 17'],
  ['iPhone14,', 'iPhone 13 / 14'], ['iPhone13,', 'iPhone 12'],
  ['iPhone12,', 'iPhone 11'], ['iPhone11,', 'iPhone XS / XR'],
];

function browser(ua) {
  if (/Edg\//i.test(ua)) return 'Edge';
  if (/Chrome\//i.test(ua) && !/Chromium/i.test(ua)) return 'Chrome';
  if (/Firefox\//i.test(ua)) return 'Firefox';
  if (/Safari\//i.test(ua)) return 'Safari';
  return '';
}

function mapAndroidModel(model) {
  if (!model) return null;
  for (const [code, friendly] of SAMSUNG_MAP) {
    if (model.startsWith(code)) return friendly;
  }
  for (const [prefix, friendly] of PIXEL_MAP) {
    if (model === prefix || model.startsWith(prefix)) return friendly;
  }
  if (/^OnePlus/i.test(model)) return model;
  if (/^Mi |^Redmi/i.test(model)) return model;
  return model;
}

function mapIphoneModel(model) {
  for (const [code, friendly] of IPHONE_MAP) {
    if (model.startsWith(code)) return friendly;
  }
  return null;
}

/**
 * Synchronous best-effort detection. Returns { product, model, label }.
 * Every field may be empty if the browser hides everything (e.g., Chrome
 * 110+ freezes Android UA to "K" without high-entropy hints permission).
 */
export function detectDeviceInfo() {
  if (typeof navigator === 'undefined') return { product: '', model: '', label: 'Inconnu' };
  const ua = navigator.userAgent || '';

  // iPhone / iPad — Apple does NOT expose the precise model code in any
  // browser API. We can only state the family.
  if (/iPad/i.test(ua)) return { product: 'iPad', model: '', label: 'iPad' };
  if (/iPhone/i.test(ua)) {
    const cachedModel = (() => { try { return localStorage.getItem('codeforge_ios_model') || ''; } catch (_) { return ''; } })();
    return { product: 'iPhone', model: cachedModel, label: cachedModel ? `iPhone · ${cachedModel}` : 'iPhone' };
  }

  // Android — try synchronous UA parse first.
  if (/Android/i.test(ua)) {
    const cached = (() => {
      try { return JSON.parse(localStorage.getItem('codeforge_device_info_uach') || 'null'); } catch (_) { return null; }
    })();
    if (cached && (cached.product || cached.model)) {
      return { product: cached.product || '', model: cached.model || '', label: makeLabel(cached.product, cached.model) };
    }
    const m = ua.match(/\(([^)]*Android[^)]*)\)/i);
    if (m && m[1]) {
      const after = m[1].split(';').slice(2).join(';').trim();
      if (after) {
        const model = after.replace(/\s+Build\/.*$/i, '').trim();
        if (model && model !== 'K' && model.length < 40) {
          const product = mapAndroidModel(model) || 'Téléphone Android';
          // Fire-and-forget the high-entropy probe so the next visit gets
          // a sharper "model" code we can show on a second line.
          probeUACH();
          return { product, model, label: makeLabel(product, model) };
        }
      }
    }
    probeUACH();
    return { product: 'Téléphone Android', model: '', label: 'Téléphone Android' };
  }

  const b = browser(ua);
  // Desktop hostname (DESKTOP-52KO8J1) is NOT exposed to browsers — it's
  // a privacy boundary every modern browser enforces. Best we can do is
  // platform + browser. Users can manually rename via the AccountsButton.
  if (/Macintosh|Mac OS X/i.test(ua)) return { product: 'Mac', model: '', label: b ? `Mac · ${b}` : 'Mac' };
  if (/Windows/i.test(ua))            return { product: 'PC Windows', model: '', label: b ? `PC Windows · ${b}` : 'PC Windows' };
  if (/CrOS/i.test(ua))               return { product: 'Chromebook', model: '', label: b ? `Chromebook · ${b}` : 'Chromebook' };
  if (/Linux/i.test(ua))              return { product: 'Linux', model: '', label: b ? `Linux · ${b}` : 'Linux' };
  return { product: '', model: '', label: b || 'Inconnu' };
}

function probeUACH() {
  if (!(navigator.userAgentData && navigator.userAgentData.getHighEntropyValues)) return;
  navigator.userAgentData.getHighEntropyValues(['model', 'platform', 'platformVersion'])
    .then((data) => {
      const model = (data?.model || '').trim();
      if (!model) return;
      const product = mapAndroidModel(model) || model;
      try {
        localStorage.setItem('codeforge_device_info_uach', JSON.stringify({ product, model }));
      } catch (_) {}
    }).catch(() => {});
}

function makeLabel(product, model) {
  if (product && model && product !== model) return `${product} · ${model}`;
  return product || model || 'Inconnu';
}

// Legacy helper for callers that still expect a single string.
export function detectDeviceLabel() {
  return detectDeviceInfo().label;
}
