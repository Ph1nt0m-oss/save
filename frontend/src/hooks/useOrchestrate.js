import { useState, useCallback, useRef } from 'react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter84 — Hook qui lance une session d'orchestration et consomme le SSE
 * /api/chat/orchestrate-stream en temps réel. Chaque événement reçu est
 * ajouté à `events`, ce qui déclenche un re-render du <OrchestrationLog>.
 *
 * Usage :
 *   const { events, running, finalAnswer, run, reset } = useOrchestrate();
 *   run("Comment ajouter un bouton ?");
 */
export default function useOrchestrate() {
  const [events, setEvents] = useState([]);
  const [running, setRunning] = useState(false);
  const [finalAnswer, setFinalAnswer] = useState('');
  const [confidence, setConfidence] = useState(null);
  const abortRef = useRef(null);

  const reset = useCallback(() => {
    setEvents([]);
    setFinalAnswer('');
    setConfidence(null);
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch (_) { /* ignore */ }
      abortRef.current = null;
    }
  }, []);

  const run = useCallback(async (message, { projectId = null, language = 'fr' } = {}) => {
    reset();
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await fetch(`${API}/chat/orchestrate-stream`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, project_id: projectId, language }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE: messages séparés par double newline
        let idx;
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const line = raw.split('\n').find((l) => l.startsWith('data:'));
          if (!line) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            setEvents((prev) => [...prev, evt]);
            if (evt.kind === 'final') {
              setFinalAnswer(evt.content || '');
              setConfidence(evt.confidence ?? null);
            }
          } catch (e) {
            // ignore bad chunk
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setEvents((prev) => [...prev, {
          event_id: `local_err_${Date.now()}`,
          kind: 'error',
          summary: `Erreur réseau : ${e.message || 'unknown'}`,
        }]);
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [reset]);

  const abort = useCallback(() => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch (_) { /* ignore */ }
      abortRef.current = null;
    }
    setRunning(false);
  }, []);

  return { events, running, finalAnswer, confidence, run, reset, abort };
}
