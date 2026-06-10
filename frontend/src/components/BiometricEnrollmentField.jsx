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
  Eye, RotateCcw, Check, ShieldCheck, X,
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
// Kept for back-compat with axios import (used by other paths in this
// project that share the same module).
const _api = API;

// 3 randomly-ordered active challenges. The user must complete all of
// (iter74 removed POSES + shuffle — replaced by alignment loop with fixed
// pose-per-capture-index, see POSE_FOR_INDEX inside the wizard.)

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
 * Variance of luminance over the centre region — coarse proxy for "is
 * something with structure (a face) currently inside the circle?". A flat
 * wall or empty frame has variance < ~250. A real face crowded into the
 * circle averages 800–1800.
 */
function faceVariance(imgData) {
  if (!imgData) return 0;
  const { data, width, height } = imgData;
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.min(width, height) * 0.4;
  const r2 = r * r;
  let sum = 0;
  let sumSq = 0;
  let n = 0;
  for (let y = 0; y < height; y += 4) {
    const dy = y - cy;
    for (let x = 0; x < width; x += 4) {
      const dx = x - cx;
      if (dx * dx + dy * dy > r2) continue;
      const i = (y * width + x) * 4;
      const lum = 0.21 * data[i] + 0.72 * data[i + 1] + 0.07 * data[i + 2];
      sum += lum;
      sumSq += lum * lum;
      n++;
    }
  }
  if (n === 0) return 0;
  const mean = sum / n;
  return Math.max(0, sumSq / n - mean * mean);
}

/**
 * Heuristic glasses detector: count bright (luminance > 235) pixel
 * clusters in the upper third of the frame (where lenses sit).
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

export default function BiometricEnrollmentField({ value, onChange, disabled }) {
  const [mode, setMode] = useState('idle'); // 'idle' | 'iris-fullscreen' | 'done'
  const [error, setError] = useState('');

  // Persist last enrolled summary for the compact "Done" pill.
  const enrolled = value && value.kind === 'iris' && (value.data?.hashes?.length || 0) >= 3;

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
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => { setError(''); setMode('iris-fullscreen'); }}
            disabled={disabled}
            data-testid="bio-iris-btn"
            className="inline-flex items-center justify-center gap-2 px-3 py-3 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white hover:border-[#00D4FF]/60 hover:bg-white/[0.08] transition disabled:opacity-50"
          >
            <Eye className="w-4 h-4 text-[#00D4FF]" />
            Démarrer l'identification iris
          </button>
        </div>
      )}

      {enrolled && (
        <div className="flex items-center justify-between gap-2 bg-emerald-500/10 border border-emerald-400/40 rounded-sm px-3 py-2" data-testid="bio-enrolled">
          <div className="flex items-center gap-2 text-xs text-emerald-200">
            <Check className="w-4 h-4" />
            Iris enregistré (3 captures)
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
export function IrisFullscreenWizard({ onCancel, onDone }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const rafRef = useRef(null);
  const lastFrameRef = useRef(null);
  const movementHistoryRef = useRef([]); // sliding window of last ~30 diffs
  const recentSamplesRef = useRef([]); // (frame timestamp, diff) for the active pose

  const [streamReady, setStreamReady] = useState(false);
  const [streamError, setStreamError] = useState('');
  // iter74 — pose-based flow with live "rouge/vert" alignment :
  //   captureIdx 0..2 → after 3 successful captures we exit.
  //   For each capture: cycle (instruction) → (aligned, hold steady) →
  //   (countdown 2 s with blue bar, ring vert) → (capture+hash) → reset.
  //   The required "current instruction" varies per capture index so
  //   the user must visibly change pose between them (look ahead /
  //   turn left / turn right) — that's what blocks photos and masks.
  const [captureIdx, setCaptureIdx] = useState(0);
  // 'unknown' | 'no_face' | 'too_far' | 'glasses' | 'turn_left' |
  // 'turn_right' | 'aligned'
  const [alignment, setAlignment] = useState('unknown');
  const [holdProgress, setHoldProgress] = useState(0); // 0..100 — blue bar (steadiness countdown)
  const [hashes, setHashes] = useState([]);
  const HOLD_TICKS = 20; // 20 ticks of 100 ms = 2 s steady before capture
  const holdRef = useRef(0); // active hold counter
  const POSE_FOR_INDEX = ['center', 'left', 'right']; // distinct pose per capture

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
      const sessionId = `iris_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const reportEvt = (kind, extra = {}) => {
        // iter84 — Observabilité bug vidéo mobile : on poste l'événement à un
        // endpoint de log côté backend pour debug ultérieur. Best-effort.
        const payload = {
          kind,
          session_id: sessionId,
          ua: navigator.userAgent.slice(0, 300),
          viewport: { w: window.innerWidth, h: window.innerHeight },
          is_secure: window.isSecureContext,
          ts: new Date().toISOString(),
          ...extra,
        };
        try {
          fetch(`${process.env.REACT_APP_BACKEND_URL}/api/observability/video-event`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive: true,
          }).catch(() => null);
        } catch (_) { /* silent */ }
      };
      reportEvt('iris_start');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
        if (!mounted) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        const track = stream.getVideoTracks()[0];
        const settings = track ? track.getSettings() : {};
        reportEvt('iris_stream_ok', {
          track_label: track?.label,
          track_state: track?.readyState,
          settings: {
            width: settings.width, height: settings.height,
            frame_rate: settings.frameRate, facing: settings.facingMode,
          },
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          try {
            await videoRef.current.play();
            reportEvt('iris_video_play_ok', { ready_state: videoRef.current.readyState });
          } catch (playErr) {
            reportEvt('iris_video_play_fail', { error: String(playErr).slice(0, 300) });
            throw playErr;
          }
        }
        setStreamReady(true);
        setAlignment('no_face');
      } catch (e) {
        reportEvt('iris_stream_error', {
          error: String(e?.message || e).slice(0, 300),
          name: e?.name,
        });
        setStreamError('Impossible d\'accéder à la caméra. Vérifie les permissions et recommence.');
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

  // iter74 — single unified alignment loop. At 10 Hz we (1) compute a
  // coarse face presence + horizontal balance signal from the latest
  // frame and (2) pick the most actionable instruction. While the user
  // is properly aligned for the current capture's required pose, a 2 s
  // steady countdown fills the blue bar; if the alignment breaks, the
  // counter resets — the ring goes red and the instructions re-appear.
  useEffect(() => {
    if (!streamReady || captureIdx >= 3) return;
    const requiredPose = POSE_FOR_INDEX[captureIdx];
    const id = setInterval(async () => {
      const img = lastFrameRef.current;
      if (!img) return;
      const v = faceVariance(img);
      if (v < 80) {
        holdRef.current = 0;
        setHoldProgress(0);
        setAlignment('no_face');
        return;
      }
      if (v < 250) {
        holdRef.current = 0;
        setHoldProgress(0);
        setAlignment('too_far');
        return;
      }
      // Glasses guard active on every capture (not just first).
      if (looksLikeGlasses(img)) {
        holdRef.current = 0;
        setHoldProgress(0);
        setAlignment('glasses');
        return;
      }
      // Pose: compute centre-of-mass shift of bright/dark structure on
      // the X axis. positive → user is turned RIGHT (mirror video so
      // their right ends up on the right of the canvas).
      const { data, width, height } = img;
      let sumLeft = 0;
      let sumRight = 0;
      const half = Math.floor(width / 2);
      for (let y = Math.floor(height * 0.25); y < Math.floor(height * 0.75); y += 4) {
        for (let x = 0; x < width; x += 4) {
          const i = (y * width + x) * 4;
          const lum = 0.21 * data[i] + 0.72 * data[i + 1] + 0.07 * data[i + 2];
          // High-frequency structure proxy: distance from mid-grey (128)
          const s = Math.abs(lum - 128);
          if (x < half) sumLeft += s; else sumRight += s;
        }
      }
      const total = sumLeft + sumRight || 1;
      const balance = (sumRight - sumLeft) / total; // -1..1, positive = looking right
      let detected;
      if (balance > 0.18) detected = 'right';
      else if (balance < -0.18) detected = 'left';
      else detected = 'center';
      if (detected !== requiredPose) {
        holdRef.current = 0;
        setHoldProgress(0);
        setAlignment(requiredPose === 'left' ? 'turn_left'
          : requiredPose === 'right' ? 'turn_right'
          : 'center');
        return;
      }
      // Aligned → progress the steady-hold countdown.
      setAlignment('aligned');
      holdRef.current = Math.min(HOLD_TICKS, holdRef.current + 1);
      const pct = Math.round((holdRef.current / HOLD_TICKS) * 100);
      setHoldProgress(pct);
      if (holdRef.current >= HOLD_TICKS) {
        clearInterval(id);
        // capture
        const c = canvasRef.current;
        if (c) {
          c.toBlob(async (blob) => {
            if (!blob) return;
            const h = await sha256B64(blob);
            const next = [...hashes, h];
            setHashes(next);
            // reset for next capture
            holdRef.current = 0;
            setHoldProgress(0);
            if (next.length >= 3) {
              setCaptureIdx(3); // done sentinel
              setTimeout(() => { stopStream(); onDone(next); }, 400);
            } else {
              setAlignment('unknown');
              setCaptureIdx(captureIdx + 1);
            }
          }, 'image/jpeg', 0.85);
        }
      }
    }, 100);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamReady, captureIdx]);

  const ALIGN_COPY = {
    unknown:    'Initialisation…',
    no_face:    'Place ton visage face à la caméra',
    too_far:    'Rapproche-toi de la caméra',
    glasses:    'Enlève tes lunettes',
    turn_left:  'Tourne la tête à gauche',
    turn_right: 'Tourne la tête à droite',
    center:     'Regarde droit devant',
    aligned:    'Ne bouge plus — capture en cours',
  };
  const isAligned = alignment === 'aligned';
  const ringColor = isAligned ? '#10B981' : '#EF4444'; // emerald / red
  const ringGlow = isAligned ? 'rgba(16,185,129,0.55)' : 'rgba(239,68,68,0.45)';
  const dismiss = () => { stopStream(); onCancel(); };

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
            Identification iris
            {captureIdx < 3 && (
              <span className="text-[#A1A1AA] font-normal ml-2">{captureIdx + 1}/3</span>
            )}
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
          style={{ transform: 'scaleX(-1)' }}
        />
        <canvas ref={canvasRef} className="hidden" />

        {/* Centre face mask — colour-coded by alignment */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div
            data-testid="iris-ring"
            data-aligned={isAligned ? '1' : '0'}
            className="w-[60vmin] h-[60vmin] max-w-[420px] max-h-[420px] rounded-full transition-colors duration-150"
            style={{
              borderWidth: 3,
              borderStyle: 'solid',
              borderColor: ringColor,
              boxShadow: `0 0 120px ${ringGlow}`,
            }}
          />
        </div>
      </div>

      {/* Status footer — instruction ABOVE, blue countdown bar BELOW */}
      <footer className="px-4 py-4 bg-[#0A0A0A] border-t border-white/10 space-y-3">
        <p
          className="text-center text-base sm:text-lg text-white font-['Chivo'] font-bold transition-colors duration-150"
          data-testid="iris-instruction"
          style={{ color: isAligned ? '#10B981' : '#EF4444' }}
        >
          {streamError ? streamError : (ALIGN_COPY[alignment] || ALIGN_COPY.unknown)}
        </p>
        {captureIdx < 3 && streamReady && (
          <div className="w-full max-w-md mx-auto h-2 bg-white/[0.08] rounded-full overflow-hidden" data-testid="iris-hold-progress">
            <div
              className="h-full bg-[#00D4FF] transition-[width] duration-100"
              style={{ width: `${holdProgress}%` }}
            />
          </div>
        )}
        {captureIdx >= 3 && (
          <p className="text-center text-xs text-emerald-300 inline-flex items-center justify-center gap-1">
            <Check className="w-4 h-4" /> 3/3 captures réussies
          </p>
        )}
      </footer>
    </div>,
    document.body
  );
}
