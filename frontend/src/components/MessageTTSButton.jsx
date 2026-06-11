/**
 * iter95 — Bouton TTS qui lit à voix haute un message IA via OpenAI TTS.
 * Appelle /api/chat/tts, reçoit audio MP3 base64, joue via <audio>.
 *
 * Usage :
 *   <MessageTTSButton text={msg.content} />
 */
import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Volume2, Loader2, Square } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function MessageTTSButton({ text, voice = 'alloy', className = '' }) {
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  const stop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setPlaying(false);
  };

  const playTTS = async (e) => {
    e?.stopPropagation();
    if (playing) { stop(); return; }
    if (!text || !text.trim()) return;
    setLoading(true);
    try {
      const r = await axios.post(`${API}/chat/tts`, {
        text: text.slice(0, 4000),
        voice,
      }, { withCredentials: true });
      const audioB64 = r?.data?.audio_base64;
      const mime = r?.data?.mime_type || 'audio/mpeg';
      if (!audioB64) throw new Error('Pas d\'audio');
      const audio = new Audio(`data:${mime};base64,${audioB64}`);
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      audio.onerror = () => setPlaying(false);
      await audio.play();
      setPlaying(true);
    } catch (err) {
      console.warn('TTS failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={playTTS}
      disabled={loading}
      data-testid="message-tts-btn"
      title={playing ? 'Arrêter la lecture' : 'Écouter à voix haute'}
      className={`inline-flex items-center justify-center w-6 h-6 rounded-sm text-[#A1A1AA] hover:text-[#E4FF00] hover:bg-white/5 transition-colors ${className}`}
    >
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : playing ? (
        <Square className="w-3.5 h-3.5 fill-current" />
      ) : (
        <Volume2 className="w-3.5 h-3.5" />
      )}
    </button>
  );
}
