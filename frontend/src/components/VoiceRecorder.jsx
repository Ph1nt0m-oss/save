import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Mic, Loader2, Square } from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Two voice-input buttons sharing the same recorder logic:
 *
 *   • mode="send"     → click → record → click again → transcribe → onResult(text, true)
 *                       Caller sends immediately. Red pulsing dot while recording.
 *   • mode="dictate"  → click → record → click again → transcribe → onResult(text, false)
 *                       Caller fills the input; user reviews & sends manually.
 *
 * Props:
 *   - mode: 'send' | 'dictate'
 *   - onResult(text: string, autoSend: boolean): void
 *   - disabled?: boolean
 *   - language?: string  (ISO-639-1, optional — Whisper auto-detects otherwise)
 *   - testIdSuffix?: string
 */
export default function VoiceRecorder({ mode = 'dictate', onResult, disabled, language, testIdSuffix }) {
  const { t } = useLanguage();
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const tickRef = useRef(null);

  // Cleanup on unmount.
  useEffect(() => () => {
    try { recorderRef.current?.stop?.(); } catch (_) {}
    try { streamRef.current?.getTracks?.().forEach(tr => tr.stop()); } catch (_) {}
    if (tickRef.current) clearInterval(tickRef.current);
  }, []);

  const start = async () => {
    if (recording || busy || disabled) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      toast.error(t('mic_unsupported'));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      // Pick a mime the browser supports + Whisper accepts.
      const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
      const mime = candidates.find(c => window.MediaRecorder?.isTypeSupported?.(c)) || '';
      const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => upload(mr.mimeType || mime || 'audio/webm');
      mr.start();
      recorderRef.current = mr;
      setRecording(true);
      setElapsed(0);
      tickRef.current = setInterval(() => setElapsed(e => {
        const next = e + 1;
        // Hard cap at 60 s to keep payloads small.
        if (next >= 60) {
          try { mr.stop(); } catch (_) {}
        }
        return next;
      }), 1000);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('mic error', err);
      toast.error(t('mic_permission'));
    }
  };

  const stop = () => {
    if (!recording) return;
    try { recorderRef.current?.stop?.(); } catch (_) {}
    try { streamRef.current?.getTracks?.().forEach(tr => tr.stop()); } catch (_) {}
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
    setRecording(false);
    setBusy(true);
  };

  const upload = async (mime) => {
    try {
      const blob = new Blob(chunksRef.current, { type: mime });
      if (blob.size < 200) {
        toast.info(t('mic_too_short'));
        return;
      }
      const ext = (mime.includes('mp4') ? 'm4a' : mime.includes('ogg') ? 'ogg' : 'webm');
      const fd = new FormData();
      fd.append('file', blob, `recording.${ext}`);
      const params = language ? `?language=${encodeURIComponent(language)}` : '';
      const { data } = await axios.post(`${API}/voice/transcribe${params}`, fd, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const text = (data?.text || '').trim();
      if (!text) {
        toast.info(t('mic_no_text'));
        return;
      }
      onResult?.(text, mode === 'send');
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : t('mic_failed'));
    } finally {
      setBusy(false);
      chunksRef.current = [];
    }
  };

  const isSend = mode === 'send';
  const labelKey = isSend ? 'mic_voice_send' : 'mic_voice_text';

  // Visual: dictate = neutral outlined; send = solid white/black (ChatGPT-style "voice send" pill).
  const baseClasses = isSend
    ? 'bg-white text-[#050505] border-white hover:bg-[#E4E4E7]'
    : 'bg-white/[0.04] text-white border-white/15 hover:border-[#E4FF00]/50 hover:text-[#E4FF00]';

  return (
    <button
      type="button"
      disabled={disabled || busy}
      onClick={recording ? stop : start}
      data-testid={`voice-${mode}-btn${testIdSuffix ? `-${testIdSuffix}` : ''}`}
      title={t(labelKey)}
      aria-label={t(labelKey)}
      className={`relative inline-flex items-center justify-center h-11 w-11 rounded-sm border transition-all flex-shrink-0 ${
        recording
          ? 'border-red-500 bg-red-500/10 text-red-400 animate-pulse'
          : baseClasses
      } disabled:opacity-50 disabled:cursor-not-allowed`}
    >
      {busy ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : recording ? (
        <>
          <Square className="w-4 h-4 fill-current" />
          {/* timer + red dot */}
          <span className="absolute -top-2 -right-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-red-500 text-[9px] font-bold text-white">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            {String(Math.floor(elapsed / 60)).padStart(1,'0')}:{String(elapsed % 60).padStart(2,'0')}
          </span>
        </>
      ) : (
        <Mic className="w-4 h-4" />
      )}
    </button>
  );
}
