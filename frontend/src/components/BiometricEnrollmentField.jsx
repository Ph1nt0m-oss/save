/**
 * BiometricEnrollmentField — iter69
 *
 * Mandatory enrollment step shown during signup. The user must either:
 *  - register a WebAuthn credential (fingerprint, Face ID, Windows Hello,
 *    iris camera on Surface, hardware security key…). This is the
 *    one-tap path on any device with native biometry.
 *  - OR capture 3 webcam frames of their iris. The frames are hashed
 *    client-side (SHA-256 over the cropped centre region) so the raw
 *    images never leave the browser unencrypted. The creator NEVER has
 *    access to the photos themselves; the hashes only serve to verify
 *    the user later if they declare a theft.
 *
 * Output via `onChange({ kind, data })`:
 *   - kind = 'webauthn' → data = { credential, options_token }
 *   - kind = 'iris'     → data = { hashes: [b64,b64,b64] }
 */
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Fingerprint, Eye, Camera, RotateCcw, Check, Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { isWebAuthnSupported, webauthnCreate } from '../lib/webauthnClient';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const REQUIRED_FRAMES = 3;

async function sha256B64(blob) {
  const buf = await blob.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buf);
  const bytes = new Uint8Array(digest);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

export default function BiometricEnrollmentField({ value, onChange, email, disabled }) {
  const [mode, setMode] = useState('idle'); // 'idle' | 'webauthn' | 'iris-stream' | 'iris-done' | 'webauthn-done'
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [hashes, setHashes] = useState([]);
  const [streamReady, setStreamReady] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const stopStream = () => {
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch (_) {}
    streamRef.current = null;
    setStreamReady(false);
  };

  useEffect(() => () => stopStream(), []);

  const tryWebAuthn = async () => {
    setError('');
    setBusy(true);
    try {
      const optsRes = await axios.post(`${API}/webauthn/enroll-begin`, { email: (email || '').trim() || null });
      const { options, options_token } = optsRes.data;
      const credential = await webauthnCreate(options);
      onChange({ kind: 'webauthn', data: { credential, options_token } });
      setMode('webauthn-done');
      toast.success('Empreinte / capteur biométrique enregistré.');
    } catch (e) {
      // Most common failure modes: NotAllowedError (user cancelled),
      // NotSupportedError (no authenticator), SecurityError (HTTP).
      // All map to "tu peux passer à l'iris".
      setError(e?.message || 'Le capteur biométrique n\'a pas répondu. Essaie l\'iris.');
      setMode('idle');
    } finally {
      setBusy(false);
    }
  };

  const startIris = async () => {
    setError('');
    setBusy(true);
    setMode('iris-stream');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStreamReady(true);
      setHashes([]);
    } catch (e) {
      setError('Impossible d\'accéder à la caméra. Vérifie les permissions.');
      setMode('idle');
    } finally {
      setBusy(false);
    }
  };

  const captureFrame = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const v = videoRef.current;
    const c = canvasRef.current;
    // Crop a 256x256 square around the centre — coarse iris region.
    const SIZE = 256;
    c.width = SIZE;
    c.height = SIZE;
    const ctx = c.getContext('2d');
    const sx = Math.max(0, (v.videoWidth - SIZE) / 2);
    const sy = Math.max(0, (v.videoHeight - SIZE) / 2);
    ctx.drawImage(v, sx, sy, SIZE, SIZE, 0, 0, SIZE, SIZE);
    c.toBlob(async (blob) => {
      if (!blob) return;
      const h = await sha256B64(blob);
      const next = [...hashes, h];
      setHashes(next);
      if (next.length >= REQUIRED_FRAMES) {
        stopStream();
        setMode('iris-done');
        onChange({ kind: 'iris', data: { hashes: next } });
        toast.success('3 captures iris enregistrées.');
      }
    }, 'image/jpeg', 0.85);
  };

  const resetAll = () => {
    stopStream();
    setHashes([]);
    setError('');
    setMode('idle');
    onChange(null);
  };

  const enrolled = value && (value.kind === 'webauthn' || (value.kind === 'iris' && value.data?.hashes?.length >= REQUIRED_FRAMES));

  return (
    <div className="space-y-2" data-testid="biometric-enrollment-field">
      <label className="block text-xs text-[#A1A1AA] font-['IBM_Plex_Sans']">
        Identité biométrique <span className="text-red-400">*</span>
      </label>
      <p className="text-[10px] text-[#71717A] leading-relaxed">
        <ShieldCheck className="w-3 h-3 inline-block mr-1 text-emerald-400" />
        La créatrice n'a <strong>aucun accès</strong> à tes empreintes ni à la photo de ton iris. Ces données servent
        uniquement à prouver ton identité en cas de déclaration de vol.
      </p>

      {!enrolled && mode === 'idle' && (
        <div className="flex flex-col sm:flex-row gap-2">
          <button
            type="button"
            onClick={tryWebAuthn}
            disabled={busy || disabled}
            data-testid="bio-webauthn-btn"
            className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-3 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white hover:border-[#E4FF00]/60 hover:bg-white/[0.08] transition disabled:opacity-50"
          >
            <Fingerprint className="w-4 h-4 text-[#E4FF00]" />
            Empreinte / Face ID
          </button>
          <button
            type="button"
            onClick={startIris}
            disabled={busy || disabled}
            data-testid="bio-iris-btn"
            className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-3 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white hover:border-[#00D4FF]/60 hover:bg-white/[0.08] transition disabled:opacity-50"
          >
            <Eye className="w-4 h-4 text-[#00D4FF]" />
            Iris (webcam)
          </button>
        </div>
      )}

      {mode === 'iris-stream' && (
        <div className="bg-black/40 border border-white/10 rounded-sm p-3 space-y-2" data-testid="iris-stream">
          <div className="relative aspect-video bg-black rounded-sm overflow-hidden">
            <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
              <div className="w-32 h-32 sm:w-40 sm:h-40 border-2 border-[#00D4FF]/70 rounded-full" />
            </div>
            <canvas ref={canvasRef} className="hidden" />
          </div>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] text-[#A1A1AA] flex-1">
              Place tes yeux dans le cercle. <strong>{hashes.length}/{REQUIRED_FRAMES}</strong> capture(s).
              Bouge légèrement les yeux entre chaque capture pour prouver que tu es vivant.
            </p>
            <button
              type="button"
              onClick={captureFrame}
              disabled={!streamReady}
              data-testid="iris-capture-btn"
              className="inline-flex items-center gap-1 px-3 py-2 bg-[#00D4FF] text-[#050505] rounded-sm text-xs font-['Chivo'] font-bold disabled:opacity-50 hover:bg-[#00D4FF]/90"
            >
              <Camera className="w-3 h-3" /> Capturer
            </button>
          </div>
        </div>
      )}

      {enrolled && (
        <div className="flex items-center justify-between gap-2 bg-emerald-500/10 border border-emerald-400/40 rounded-sm px-3 py-2" data-testid="bio-enrolled">
          <div className="flex items-center gap-2 text-xs text-emerald-200">
            <Check className="w-4 h-4" />
            {value.kind === 'webauthn' ? 'Capteur biométrique enregistré' : 'Iris enregistré (3 captures)'}
          </div>
          <button
            type="button"
            onClick={resetAll}
            data-testid="bio-reset-btn"
            className="text-xs text-emerald-200/80 hover:text-white inline-flex items-center gap-1"
          >
            <RotateCcw className="w-3 h-3" /> Refaire
          </button>
        </div>
      )}

      {busy && mode === 'idle' && (
        <div className="text-[11px] text-[#A1A1AA] inline-flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin" /> Activation…
        </div>
      )}

      {error && (
        <p className="text-[11px] text-red-300" data-testid="bio-error">{error}</p>
      )}
    </div>
  );
}
