/**
 * WebAuthn client helpers.
 *
 * Spec: navigator.credentials.create / get returns ArrayBuffers that must be
 * encoded to base64url before posting to the server, and the server returns
 * options where some fields (challenge, user.id, allowCredentials[].id) are
 * base64url-encoded strings that must be decoded back to ArrayBuffers.
 */

function b64urlToBuf(s) {
  const norm = s.replace(/-/g, '+').replace(/_/g, '/');
  const padded = norm + '==='.slice((norm.length + 3) % 4);
  const bin = atob(padded);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}

function bufToB64url(buf) {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

export function isWebAuthnSupported() {
  return typeof window !== 'undefined'
    && !!window.PublicKeyCredential
    && typeof navigator.credentials?.create === 'function'
    && typeof navigator.credentials?.get === 'function';
}

/**
 * Convert the server's registration options (with base64url strings) to the
 * shape WebAuthn expects (ArrayBuffers).
 */
function prepareRegisterOptions(opts) {
  return {
    ...opts,
    challenge: b64urlToBuf(opts.challenge),
    user: { ...opts.user, id: b64urlToBuf(opts.user.id) },
    excludeCredentials: (opts.excludeCredentials || []).map((c) => ({ ...c, id: b64urlToBuf(c.id) })),
  };
}

function prepareAuthOptions(opts) {
  return {
    ...opts,
    challenge: b64urlToBuf(opts.challenge),
    allowCredentials: (opts.allowCredentials || []).map((c) => ({ ...c, id: b64urlToBuf(c.id) })),
  };
}

/** Run navigator.credentials.create and serialize the result for the server. */
export async function webauthnCreate(opts) {
  const cred = await navigator.credentials.create({ publicKey: prepareRegisterOptions(opts) });
  if (!cred) throw new Error('Aucun credential renvoyé par le navigateur.');
  return {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    response: {
      attestationObject: bufToB64url(cred.response.attestationObject),
      clientDataJSON: bufToB64url(cred.response.clientDataJSON),
    },
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
  };
}

/** Run navigator.credentials.get and serialize the result for the server. */
export async function webauthnGet(opts) {
  const cred = await navigator.credentials.get({ publicKey: prepareAuthOptions(opts) });
  if (!cred) throw new Error('Aucun credential renvoyé par le navigateur.');
  return {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    response: {
      authenticatorData: bufToB64url(cred.response.authenticatorData),
      clientDataJSON: bufToB64url(cred.response.clientDataJSON),
      signature: bufToB64url(cred.response.signature),
      userHandle: cred.response.userHandle ? bufToB64url(cred.response.userHandle) : null,
    },
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
  };
}
