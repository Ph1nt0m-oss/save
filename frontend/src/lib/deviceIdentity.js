/**
 * Device-bound cryptographic identity (browser side).
 *
 * Generates an ECDSA P-256 key pair with `extractable: false`, stores the
 * PRIVATE key in IndexedDB (CryptoKey object — never serialized, never
 * accessible to JS as raw bytes) and the PUBLIC key as a portable JWK
 * (sent to the server on register).
 *
 * Why IndexedDB + non-extractable: it is the closest browser equivalent to
 * a hardware secure element. The private key is exposed only via
 * `crypto.subtle.sign()`, never as raw bytes — even an attacker with XSS
 * cannot exfiltrate it.
 */

const DB_NAME = 'codeforge_device_identity';
const DB_VERSION = 1;
const STORE = 'keys';
const PRIVATE_KEY_HANDLE = 'device_private_key';
const PUBLIC_JWK_HANDLE = 'device_public_jwk';
const KEY_ID_LS = 'codeforge_device_key_id';

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(key) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbSet(key, value) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function sha256Hex(str) {
  const buf = new TextEncoder().encode(str);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function canonicalJwk(jwk) {
  const keep = {};
  for (const k of ['kty', 'crv', 'x', 'y']) if (k in jwk) keep[k] = jwk[k];
  // Manual stable JSON — sorted keys, no whitespace.
  const keys = Object.keys(keep).sort();
  return '{' + keys.map((k) => `"${k}":"${keep[k]}"`).join(',') + '}';
}

export async function computeKeyId(jwk) {
  const hex = await sha256Hex(canonicalJwk(jwk));
  return `dev_${hex.slice(0, 32)}`;
}

function b64urlFromBuf(buf) {
  let bin = '';
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function b64urlToBuf(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  const bin = atob(s);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}

/**
 * Ensure a device key pair exists. Returns the public JWK + key_id.
 * Idempotent — safe to call on every page load. Concurrency-safe:
 * concurrent calls (e.g. React StrictMode double-effect) share a single
 * in-flight promise so only one key pair is ever generated per device.
 */
let _ensurePromise = null;
export async function ensureDeviceKey() {
  if (_ensurePromise) return _ensurePromise;
  _ensurePromise = (async () => {
    let privKey = await idbGet(PRIVATE_KEY_HANDLE);
    let publicJwk = await idbGet(PUBLIC_JWK_HANDLE);

    if (privKey && publicJwk) {
      const keyId = await computeKeyId(publicJwk);
      try { localStorage.setItem(KEY_ID_LS, keyId); } catch (_) {}
      return { keyId, publicJwk };
    }

    // Generate a fresh pair — private key is NON-EXTRACTABLE.
    const pair = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      false, // extractable = false → cannot be exported to raw bytes
      ['sign', 'verify']
    );
    // Public key IS extractable for export to JWK (it's public — safe).
    const publicKey = await crypto.subtle.exportKey('jwk', pair.publicKey);
    publicJwk = { kty: publicKey.kty, crv: publicKey.crv, x: publicKey.x, y: publicKey.y };

    await idbSet(PRIVATE_KEY_HANDLE, pair.privateKey);
    await idbSet(PUBLIC_JWK_HANDLE, publicJwk);

    const keyId = await computeKeyId(publicJwk);
    try { localStorage.setItem(KEY_ID_LS, keyId); } catch (_) {}
    return { keyId, publicJwk };
  })();
  return _ensurePromise;
}

/**
 * Sign a server-issued nonce with the device's private key.
 * Returns the IEEE-P1363 raw signature as base64url (matches what the
 * `cryptography` library expects after our /verify endpoint conversion).
 */
export async function signNonce(nonceB64url) {
  const privKey = await idbGet(PRIVATE_KEY_HANDLE);
  if (!privKey) throw new Error('No device key — call ensureDeviceKey() first.');
  const nonceBuf = b64urlToBuf(nonceB64url);
  const sigBuf = await crypto.subtle.sign(
    { name: 'ECDSA', hash: { name: 'SHA-256' } },
    privKey,
    nonceBuf
  );
  return b64urlFromBuf(sigBuf);
}

export function getCachedKeyId() {
  try { return localStorage.getItem(KEY_ID_LS) || null; } catch (_) { return null; }
}

/**
 * One-shot challenge → sign → verify cycle against the backend.
 * Returns `{ verified, role, can_access, site_mode }` on success.
 * Concurrency-safe — repeated calls share a single in-flight promise.
 */
let _attestPromise = null;
export async function attestDevice(API, axios) {
  if (_attestPromise) return _attestPromise;
  _attestPromise = (async () => {
    try {
      const { keyId, publicJwk } = await ensureDeviceKey();
      const info = (await import('./deviceLabel')).detectDeviceInfo();
      // Register (no-op if already known) — send the rich info so the
      // creator-side accounts panel can display "product / model" two-lined.
      await axios.post(`${API}/devices/register`, {
        public_key_jwk: publicJwk,
        label: info.label,
        product: info.product,
        model: info.model,
      }).catch(() => {});

      const ch = await axios.post(`${API}/devices/challenge`, { key_id: keyId });
      const nonce = ch.data?.nonce;
      if (!nonce) throw new Error('No nonce from server.');
      const signature = await signNonce(nonce);
      const v = await axios.post(`${API}/devices/verify`, { key_id: keyId, nonce, signature });
      return { keyId, publicJwk, ...v.data };
    } finally {
      // Allow refresh() to re-run a fresh attestation after the current one.
      setTimeout(() => { _attestPromise = null; }, 50);
    }
  })();
  return _attestPromise;
}

/**
 * Helper for creator-only endpoints: bundles a fresh challenge+signature
 * proof into a request body to authenticate the caller as the creator.
 */
export async function withCreatorProof(API, axios, body = {}) {
  const keyId = getCachedKeyId();
  if (!keyId) throw new Error('Aucun appareil enregistré.');
  const ch = await axios.post(`${API}/devices/challenge`, { key_id: keyId });
  const nonce = ch.data?.nonce;
  const signature = await signNonce(nonce);
  return { ...body, key_id: keyId, nonce, signature };
}

/**
 * Return the device's public JWK as a base64-url string — used by the
 * "share my device key" feature so a creator can paste it manually.
 */
export async function exportPublicKeyShareCode() {
  const { publicJwk } = await ensureDeviceKey();
  return btoa(JSON.stringify(publicJwk));
}

export function parsePublicKeyShareCode(code) {
  try {
    const jwk = JSON.parse(atob((code || '').trim()));
    if (jwk?.kty === 'EC' && jwk?.crv === 'P-256' && jwk?.x && jwk?.y) {
      return { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y };
    }
  } catch (_) {}
  return null;
}

/** Local-only per-device email memory (NOT password). */
export function rememberEmailForDevice(email) {
  const kid = getCachedKeyId();
  if (!kid || !email) return;
  try { localStorage.setItem(`device_email:${kid}`, email); } catch (_) {}
}

export function recallEmailForDevice() {
  const kid = getCachedKeyId();
  if (!kid) return '';
  try { return localStorage.getItem(`device_email:${kid}`) || ''; } catch (_) { return ''; }
}
