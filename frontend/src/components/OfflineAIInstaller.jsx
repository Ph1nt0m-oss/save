import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, X, Terminal, Cpu, ExternalLink, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter90 — Détection du moteur IA local (Ollama) + tutoriel d'installation guidé.
 *
 * Affichage uniquement quand l'utilisateur tente d'utiliser le mode "offline" et
 * qu'Ollama n'est pas détecté. Donne 3 méthodes d'installation par OS et la
 * commande pour télécharger le premier modèle.
 *
 * Props :
 *  - open: bool — afficher le modal
 *  - onClose: () => void
 *  - onInstalled: () => void — appelé quand l'utilisateur clique "Vérifier à nouveau" et qu'Ollama répond.
 */
export default function OfflineAIInstaller({ open, onClose, onInstalled }) {
  const [checking, setChecking] = useState(false);
  const [detected, setDetected] = useState(null); // null = unknown, true/false
  const [os, setOs] = useState('mac'); // 'mac' | 'windows' | 'linux'
  const [copied, setCopied] = useState('');

  useEffect(() => {
    if (!open) return;
    // Auto-detect OS de l'utilisateur
    const ua = navigator.userAgent.toLowerCase();
    if (ua.includes('win')) setOs('windows');
    else if (ua.includes('mac')) setOs('mac');
    else if (ua.includes('linux')) setOs('linux');
    // Premier check
    recheck();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const recheck = async () => {
    setChecking(true);
    try {
      const r = await axios.get(`${API}/system/ollama-status`);
      const ok = !!r.data?.available;
      setDetected(ok);
      if (ok) {
        // Notifier le parent et fermer après 1s
        setTimeout(() => { onInstalled?.(); onClose?.(); }, 1200);
      }
    } catch {
      setDetected(false);
    } finally { setChecking(false); }
  };

  const copyCmd = async (cmd, key) => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(key);
      setTimeout(() => setCopied(''), 2000);
    } catch { /* silent */ }
  };

  if (!open) return null;

  const installCmds = {
    mac: {
      title: 'macOS',
      steps: [
        { label: '1. Télécharger Ollama', kind: 'link', url: 'https://ollama.com/download/mac', text: 'ollama.com/download/mac' },
        { label: '2. Ouvrir le .dmg et glisser Ollama dans Applications', kind: 'note' },
        { label: '3. Lancer Ollama (icône menu bar)', kind: 'note' },
        { label: '4. Télécharger le premier modèle (terminal)', kind: 'cmd', cmd: 'ollama pull gemma3:4b' },
      ],
    },
    windows: {
      title: 'Windows',
      steps: [
        { label: '1. Télécharger Ollama', kind: 'link', url: 'https://ollama.com/download/windows', text: 'ollama.com/download/windows' },
        { label: '2. Exécuter OllamaSetup.exe', kind: 'note' },
        { label: '3. Ollama démarre automatiquement en arrière-plan', kind: 'note' },
        { label: '4. Télécharger le premier modèle (PowerShell ou CMD)', kind: 'cmd', cmd: 'ollama pull gemma3:4b' },
      ],
    },
    linux: {
      title: 'Linux',
      steps: [
        { label: '1. Installer Ollama (terminal)', kind: 'cmd', cmd: 'curl -fsSL https://ollama.com/install.sh | sh' },
        { label: '2. Démarrer le service', kind: 'cmd', cmd: 'sudo systemctl start ollama' },
        { label: '3. Télécharger le premier modèle', kind: 'cmd', cmd: 'ollama pull gemma3:4b' },
      ],
    },
  };

  const cfg = installCmds[os];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
        data-testid="offline-ai-installer"
      >
        <motion.div
          initial={{ scale: 0.94, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.94, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-2xl bg-[#0A0A0A] border border-white/10 rounded-lg shadow-[0_20px_60px_rgba(0,0,0,0.7)] overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-gradient-to-r from-sky-500/10 to-violet-500/10">
            <div className="flex items-center gap-2.5">
              <Cpu className="w-5 h-5 text-sky-400" />
              <h2 className="font-['Chivo'] font-bold text-white text-lg">Installer une IA locale</h2>
            </div>
            <button onClick={onClose} className="text-[#A1A1AA] hover:text-white" data-testid="offline-installer-close">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="px-5 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
            {/* Status banner */}
            <div className={`p-3 rounded-sm border flex items-start gap-2.5 ${
              detected === true ? 'bg-emerald-500/10 border-emerald-400/40' :
              detected === false ? 'bg-amber-500/10 border-amber-400/40' :
              'bg-white/[0.04] border-white/10'
            }`}>
              {detected === true ? <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" /> :
               detected === false ? <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" /> :
               <Loader2 className="w-5 h-5 animate-spin text-[#A1A1AA] flex-shrink-0 mt-0.5" />}
              <div className="flex-1">
                <p className="text-sm font-['Chivo'] font-bold text-white">
                  {detected === true ? 'Moteur IA local détecté !' :
                   detected === false ? 'Aucun moteur IA local détecté' :
                   'Vérification en cours…'}
                </p>
                <p className="text-xs text-[#A1A1AA] mt-1">
                  {detected === true ? 'Ollama répond sur localhost:11434. Tu peux utiliser le mode hors-ligne.' :
                   detected === false ? 'Pour utiliser CodeForge AI hors-ligne (sans Internet), installe Ollama — c\'est gratuit, libre, et tes données ne sortent jamais de ton appareil.' :
                   'On regarde si Ollama tourne déjà sur ta machine…'}
                </p>
              </div>
            </div>

            {detected === false && (
              <>
                {/* OS selector */}
                <div className="flex gap-2" data-testid="offline-installer-os-tabs">
                  {[
                    { id: 'mac', label: 'macOS' },
                    { id: 'windows', label: 'Windows' },
                    { id: 'linux', label: 'Linux' },
                  ].map(o => (
                    <button
                      key={o.id}
                      onClick={() => setOs(o.id)}
                      data-testid={`offline-installer-os-${o.id}`}
                      className={`px-3 py-1.5 text-xs rounded-sm border font-['Chivo'] font-bold transition-colors ${
                        os === o.id ? 'bg-sky-500/20 border-sky-400/60 text-sky-300' : 'bg-white/[0.04] border-white/10 text-[#A1A1AA] hover:text-white'
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>

                {/* Steps */}
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-widest text-[#71717A] font-['Chivo']">
                    Installation pour {cfg.title}
                  </p>
                  {cfg.steps.map((s, i) => (
                    <div key={i} className="bg-[#050505] border border-white/10 rounded-sm p-3" data-testid={`offline-installer-step-${i}`}>
                      <p className="text-sm text-white mb-2">{s.label}</p>
                      {s.kind === 'link' && (
                        <a href={s.url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-sky-300 hover:text-sky-200 underline">
                          <ExternalLink className="w-3.5 h-3.5" />
                          {s.text}
                        </a>
                      )}
                      {s.kind === 'cmd' && (
                        <div className="flex items-center gap-2 bg-[#0F0F13] border border-white/10 rounded-sm px-3 py-2 font-mono text-xs">
                          <Terminal className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                          <code className="flex-1 text-[#D4D4D8] break-all">{s.cmd}</code>
                          <button
                            onClick={() => copyCmd(s.cmd, `s${i}`)}
                            className="text-[#A1A1AA] hover:text-white text-[10px] uppercase tracking-widest font-['Chivo'] font-bold flex-shrink-0"
                            data-testid={`offline-installer-copy-${i}`}
                          >
                            {copied === `s${i}` ? 'Copié !' : 'Copier'}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="text-xs text-[#71717A] bg-white/[0.02] border border-white/10 rounded-sm p-3">
                  <p className="font-['Chivo'] font-bold text-[#A1A1AA] mb-1">💡 Pourquoi installer une IA locale ?</p>
                  <ul className="space-y-0.5 list-disc list-inside">
                    <li>100% gratuit, aucun abonnement</li>
                    <li>Aucune connexion Internet requise après l&apos;installation</li>
                    <li>Tes conversations restent sur ton appareil (privacy max)</li>
                    <li>Modèles disponibles : Gemma 3, Llama 3.2, DeepSeek, Mistral, Qwen…</li>
                  </ul>
                </div>
              </>
            )}
          </div>

          <div className="flex items-center justify-between gap-2 px-5 py-3.5 border-t border-white/10 bg-white/[0.02]">
            <button
              onClick={onClose}
              className="text-xs text-[#A1A1AA] hover:text-white px-3 py-1.5"
              data-testid="offline-installer-cancel"
            >
              Fermer
            </button>
            <button
              onClick={recheck}
              disabled={checking}
              data-testid="offline-installer-recheck"
              className="inline-flex items-center gap-1.5 bg-sky-500 hover:bg-sky-400 text-white font-['Chivo'] font-bold text-xs px-4 py-2 rounded-sm transition-colors disabled:opacity-50"
            >
              {checking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              {checking ? 'Vérification…' : 'Vérifier à nouveau'}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
