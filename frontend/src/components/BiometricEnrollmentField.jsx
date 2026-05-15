/**
 * BiometricEnrollmentField — iter70
 *
 * Mandatory enrollment step shown during signup. Two paths:
 *   1. WebAuthn (fingerprint / Face ID / Windows Hello / hardware key).
 *      This now sends `window.location.origin` to the backend so the
 *      derived RP id matches the browser's current domain (fixes the
 *      "The relying party ID is not a registrable domain suffix" error).
 *   2. Iris via webcam — fullscreen wizard with live liveness checks:
 *        a) face detected & stable
 *        b) "no glasses" heuristic (bright reflective spots above eyes)
 *        c) 3 active head-pose challenges (look LEFT / RIGHT / CENTER)
 *           — pixel diffs between captures must exceed a threshold,
 *           which blocks a still photo held in front of the camera.
 *      The 3 final captures are SHA-256 hashed CLIENT-SIDE and the raw
 *      images NEVER leave the browser.
 *
 * Output via `onChange({ kind, data })`:
 *   - kind = 'webauthn' → data = { credential, options_token }
 *   - kind = 'iris'     → data = { hashes: [b64,b64,b64] }
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';
import axios from 'axios';
import {
  Fingerprint, Eye, Camera, RotateCcw, Check, Loader2, ShieldCheck,
  X, ArrowLeft, ArrowRight, Eye as EyeIcon, Glasses, AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';
import { isWebAuthnSupported, webauthnCreate } from '../lib/webauthnClient';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// 3 randomly-ordered active challenges. The user must complete all of
// them to enrol. The order is shuffled each session so a replay attack
// cannot precompute the sequence.
const POSES = [
  { id: 'left',   label: 'Tourne la tête à gauche', icon: ArrowLeft },
  { id: 'right',  label: 'Tourne la tête à droite', icon: ArrowRight },
  { id: 'center', label: 'Regarde droit devant',    icon: EyeIcon },
];

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function sha256B64(blob) {
  const buf = await blob.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buf);
  const bytes = new Uint8Array(digest);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

/**
 * Compute mean pixel difference between two same-size ImageData buffers.
 * Returns a 0..255 number — higher = more movement between frames.
 * A static photograph held in front of the camera produces ~<3.
 */
function pixelDiff(a, b) {
  if (!a || !b || a.data.length !== b.data.length) return 0;
  let sum = 0;
  let n = 0;
  const stride = 16; // sample one pixel every 4 (RGBA stride)
  for (let i = 0; i < a.data.length; i += stride) {
    sum += Math.abs(a.data[i] - b.data[i])
         + Math.abs(a.data[i + 1] - b.data[i + 1])
         + Math.abs(a.data[i + 2] - b.data[i + 2]);
    n += 3;
  }
  return n === 0 ? 0 : sum / n;
}

/**
 * Heuristic glasses detector: count bright (luminance > 235) pixel
 * clusters in the upper third of the frame (where lenses sit). Lenses
 * reflect ambient light → consistent bright blobs. Returns true if too
 * many such pixels are found (likely glasses).
 */
function looksLikeGlasses(imgData) {
  if (!imgData) return false;
  const { data, width, height } = imgData;
  const yMax = Math.floor(height * 0.5); // upper half — eye region
  let bright = 0;
  const stride = 16;
  for (let y = Math.floor(height * 0.18); y < yMax; y += 2) {
    for (let x = 0; x < width; x += 4) {
      const i = (y * width + x) * 4;
      // luminance approximation (Rec. 709)
      const lum = 0.21 * data[i] + 0.72 * data[i + 1] + 0.07 * data[i + 2];
      if (lum > 235) bright++;
      data; stride;
    }
  }
  // empirical: > ~120 super-bright pixels in the eye row = glasses
  return bright > 120;
}

export default function BiometricEnrollmentField({ value, onChange, email, disabled }) {
  const [mode, setMode] = useState('idle'); // 'idle' | 'webauthn-busy' | 'iris-fullscreen' | 'done'
  const [error, setError] = useState('');

  // Persist last enrolled summary for the compact "Done" pill.
  const enrolled = value && (
    value.kind === 'webauthn'
    || (value.kind === 'iris' && (value.data?.hashes?.length || 0) >= 3)
  );

  const tryWebAuthn = async () => {
    setError('');
    setMode('webauthn-busy');
    try {
      if (!isWebAuthnSupported()) {
        throw new Error('Ce navigateur ne supporte pas WebAuthn.');
      }
      const optsRes = await axios.post(`${API}/webauthn/enroll-begin`, {
        email: (email || '').trim() || null,
        origin: window.location.origin,
      });
      const { options, options_token } = optsRes.data;
      const credential = await webauthnCreate(options);
      onChange({ kind: 'webauthn', data: { credential, options_token } });
      setMode('done');
      toast.success('Capteur biométrique enregistré.');
    } catch (e) {
      const msg = e?.message || '';
      // Friendlier French copy for the most common WebAuthn failure modes
      let pretty = 'Le capteur biométrique a refusé. Essaie l\'iris ci-dessous.';
      if (/relying party ID/i.test(msg)) {
        pretty = 'Configuration WebAuthn invalide pour ce domaine. Essaie l\'iris ci-dessous.';
      } else if (/NotAllowedError|denied|cancel/i.test(msg)) {
        pretty = 'Demande annulée. Recommence ou utilise l\'iris.';
      } else if (/NotSupportedError|no.*authenticator/i.test(msg)) {
        pretty = 'Aucun capteur biométrique détecté sur cet appareil. Utilise l\'iris.';
      }
      setError(pretty);
      setMode('idle');
    }
  };

  const handleIrisDone = (hashes) => {
    onChange({ kind: 'iris', data: { hashes } });
    setMode('done');
    toast.success('Iris enregistré ✓');
  };

  const resetAll = () => {
    setError('');
    setMode('idle');
    onChange(null);
  };

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
            disabled={disabled}
            data-testid="bio-webauthn-btn"
            className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-3 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white hover:border-[#E4FF00]/60 hover:bg-white/[0.08] transition disabled:opacity-50"
          >
            <Fingerprint className="w-4 h-4 text-[#E4FF00]" />
            Empreinte / Face ID
          </button>
          <button
            type="button"
            onClick={() => { setError(''); setMode('iris-fullscreen'); }}
            disabled={disabled}
            data-testid="bio-iris-btn"
            className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-3 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white hover:border-[#00D4FF]/60 hover:bg-white/[0.08] transition disabled:opacity-50"
          >
            <Eye className="w-4 h-4 text-[#00D4FF]" />
            Iris (webcam)
          </button>
        </div>
      )}

      {mode === 'webauthn-busy' && (
        <div className="text-[11px] text-[#A1A1AA] inline-flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin" /> En attente du capteur…
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

      {error && (
        <p className="text-[11px] text-red-300" data-testid="bio-error">{error}</p>
      )}

      {mode === 'iris-fullscreen' && (
        <IrisFullscreenWizard
          onCancel={() => setMode('idle')}
          onDone={handleIrisDone}
        />
      )}
    </div>
  );
}

/**
 * Fullscreen iris wizard. Lives outside the normal flex flow so the user
 * can read every prompt clearly even on small phones. Uses requestAnimationFrame
 * to compute live movement deltas — a still photograph held in front of the
 * camera fails the liveness checks because the per-frame diff stays near 0.
 */
function IrisFullscreenWizard({ onCancel, onDone }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const rafRef = useRef(null);
  const lastFrameRef = useRef(null);
  const movementHistoryRef = useRef([]); // sliding window of last ~30 diffs
  const recentSamplesRef = useRef([]); // (frame timestamp, diff) for the active pose

  const [streamReady, setStreamReady] = useState(false);
  const [step, setStep] = useState(0); // 0 = warm-up & glasses check, 1..3 = pose challenges, 4 = done
  const [poses] = useState(() => shuffle(POSES));
  const [glassesAlert, setGlassesAlert] = useState(false);
  const [statusMsg, setStatusMsg] = useState('Initialisation de la caméra…');
  const [hashes, setHashes] = useState([]);
  const [activePoseProgress, setActivePoseProgress] = useState(0); // 0..100

  const stopStream = useCallback(() => {
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch (_) {}
    streamRef.current = null;
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
  }, []);

  useEffect(() => () => stopStream(), [stopStream]);

  // Start camera
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
        if (!mounted) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setStreamReady(true);
        setStatusMsg('Vérification des lunettes…');
      } catch (e) {
        setStatusMsg('Impossible d\'accéder à la caméra. Vérifie les permissions et recommence.');
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Continuous frame analysis loop
  useEffect(() => {
    if (!streamReady) return;
    const v = videoRef.current;
    const c = canvasRef.current;
    if (!v || !c) return;

    const SIZE = 256;
    c.width = SIZE;
    c.height = SIZE;
    const ctx = c.getContext('2d', { willReadFrequently: true });

    const loop = () => {
      try {
        const sx = Math.max(0, (v.videoWidth - SIZE) / 2);
        const sy = Math.max(0, (v.videoHeight - SIZE) / 2);
        if (v.videoWidth > 0) {
          ctx.drawImage(v, sx, sy, SIZE, SIZE, 0, 0, SIZE, SIZE);
          const img = ctx.getImageData(0, 0, SIZE, SIZE);
          const diff = pixelDiff(lastFrameRef.current, img);
          lastFrameRef.current = img;
          // Maintain a sliding window of last 30 diffs
          const hist = movementHistoryRef.current;
          hist.push(diff);
          if (hist.length > 30) hist.shift();
          recentSamplesRef.current.push(diff);
          if (recentSamplesRef.current.length > 60) recentSamplesRef.current.shift();
        }
      } catch (_) { /* video not yet ready */ }
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [streamReady]);

  // Step 0: glasses pre-check + warm-up
  useEffect(() => {
    if (!streamReady || step !== 0) return;
    const t = setTimeout(() => {
      try {
        const last = lastFrameRef.current;
        if (looksLikeGlasses(last)) {
          setGlassesAlert(true);
          setStatusMsg('Veuillez enlever vos lunettes pour une identification infaillible.');
        } else {
          setGlassesAlert(false);
          setStep(1);
          recentSamplesRef.current = [];
          setActivePoseProgress(0);
          setStatusMsg(poses[0].label);
        }
      } catch (_) {}
    }, 1500); // give 1.5s for camera autoexposure + face placement
    return () => clearTimeout(t);
  }, [streamReady, step, poses]);

  // Steps 1..3: pose challenges. We need a sustained burst of movement
  // (avg diff > MOVE_MIN over the last ~1.5s) to consider the pose "done".
  // A static photo held in front of the camera produces near-zero diff
  // because the only varying pixels are background noise — it will never
  // reach the threshold required to advance through the 3 challenges.
  useEffect(() => {
    if (step < 1 || step > 3) return;
    recentSamplesRef.current = [];
    setActivePoseProgress(0);
    const MOVE_MIN = 4.0;     // ~3-5 = empirical floor for genuine motion
    const REQUIRED_HITS = 12; // about 0.4s at 30fps of active motion
    let hits = 0;
    const id = setInterval(() => {
      const samples = recentSamplesRef.current;
      if (samples.length === 0) return;
      const avg = samples.reduce((s, d) => s + d, 0) / samples.length;
      const pct = Math.min(100, Math.round((avg / MOVE_MIN) * 50 + (hits / REQUIRED_HITS) * 50));
      setActivePoseProgress(pct);
      if (avg > MOVE_MIN) hits++;
      else hits = Math.max(0, hits - 1);
      if (hits >= REQUIRED_HITS) {
        clearInterval(id);
        // Capture the final frame for this pose and hash it
        const c = canvasRef.current;
        if (c) {
          c.toBlob(async (blob) => {
            if (!blob) return;
            const h = await sha256B64(blob);
            const next = [...hashes, h];
            setHashes(next);
            if (step < 3) {
              setStep(step + 1);
              setStatusMsg(poses[step].label);
            } else {
              setStatusMsg('Iris enregistré !');
              setStep(4);
              setTimeout(() => { stopStream(); onDone(next); }, 600);
            }
          }, 'image/jpeg', 0.85);
        }
      }
    }, 100);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, poses]);

  const dismiss = () => { stopStream(); onCancel(); };

  const CurrentPose = step >= 1 && step <= 3 ? poses[step - 1] : null;
  const CurrentIcon = CurrentPose?.icon;

  // iter70: render through a Portal so the parent Login card's
  // `backdrop-filter: blur(...)` does NOT trap our `position: fixed` to
  // its 446px containing block. Direct child of <body> = true viewport.
  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-[110] bg-black flex flex-col"
      data-testid="iris-fullscreen-wizard"
    >
      {/* Header */}
      <header className="flex items-center justify-between gap-2 px-4 py-3 border-b border-white/10 bg-black/80">
        <div className="flex items-center gap-2">
          <Eye className="w-5 h-5 text-[#00D4FF]" />
          <h2 className="text-sm sm:text-base font-['Chivo'] font-bold text-white">
            Identification iris {step >= 1 && step <= 3 && (<span className="text-[#A1A1AA] font-normal ml-2">{step}/3</span>)}
          </h2>
        </div>
        <button
          type="button"
          onClick={dismiss}
          data-testid="iris-cancel"
          aria-label="Fermer"
          className="text-[#A1A1AA] hover:text-white p-1"
        >
          <X className="w-5 h-5" />
        </button>
      </header>

      {/* Live video — fills available space */}
      <div className="flex-1 relative bg-black flex items-center justify-center overflow-hidden">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full h-full object-cover"
          // Mirror horizontally so the user's movement feels natural
          style={{ transform: 'scaleX(-1)' }}
        />
        <canvas ref={canvasRef} className="hidden" />

        {/* Centre face mask */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="w-[60vmin] h-[60vmin] max-w-[420px] max-h-[420px] rounded-full border-2 border-[#00D4FF]/70 shadow-[0_0_120px_rgba(0,212,255,0.4)]" />
        </div>

        {/* Active pose arrow / icon */}
        {CurrentIcon && (
          <div className="pointer-events-none absolute top-1/2 -translate-y-1/2 right-4 sm:right-12 text-[#00D4FF] animate-pulse">
            <CurrentIcon className="w-16 h-16 sm:w-24 sm:h-24" />
          </div>
        )}

        {/* Glasses alert overlay */}
        {glassesAlert && (
          <div className="absolute inset-x-0 top-1/3 mx-4 sm:mx-auto sm:max-w-md bg-amber-500/95 text-[#050505] rounded-sm p-4 shadow-2xl" data-testid="iris-glasses-alert">
            <div className="flex items-start gap-2">
              <Glasses className="w-6 h-6 flex-shrink-0" />
              <div className="flex-1">
                <p className="font-['Chivo'] font-bold text-sm mb-1">Lunettes détectées</p>
                <p className="text-xs leading-relaxed">Veuillez enlever vos lunettes pour une identification infaillible.</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => { setGlassesAlert(false); setStep(1); setStatusMsg(poses[0].label); recentSamplesRef.current = []; }}
              data-testid="iris-glasses-ack"
              className="mt-3 w-full inline-flex items-center justify-center gap-1 px-3 py-2 bg-[#050505] text-amber-300 rounded-sm font-['Chivo'] font-bold text-xs"
            >
              C'est fait — continuer
            </button>
          </div>
        )}
      </div>

      {/* Status footer */}
      <footer className="px-4 py-4 bg-[#0A0A0A] border-t border-white/10 space-y-2">
        <p className="text-center text-sm sm:text-base text-white font-['Chivo'] font-bold" data-testid="iris-status">{statusMsg}</p>
        {step >= 1 && step <= 3 && (
          <>
            <p className="text-center text-[11px] text-[#A1A1AA]">
              <AlertTriangle className="w-3 h-3 inline-block mr-1 text-amber-400" />
              Bouge réellement ta tête — une photo statique ne sera pas acceptée.
            </p>
            <div className="w-full max-w-md mx-auto h-1.5 bg-white/[0.08] rounded-full overflow-hidden" data-testid="iris-progress">
              <div
                className="h-full bg-[#00D4FF] transition-[width] duration-100"
                style={{ width: `${activePoseProgress}%` }}
              />
            </div>
          </>
        )}
        {step === 4 && (
          <p className="text-center text-xs text-emerald-300 inline-flex items-center justify-center gap-1">
            <Check className="w-4 h-4" /> 3/3 captures réussies
          </p>
        )}
      </footer>
    </div>,
    document.body
  );
}
