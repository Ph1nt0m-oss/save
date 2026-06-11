/**
 * iter93 — Preview live à la Emergent : panneau iframe qui affiche le site
 * en direct (hot reload du frontend), sans rebuild. L'utilisatrice peut
 * naviguer dans son app pendant qu'elle modifie le code → changements
 * visibles en temps réel (grâce au hot reload Webpack du frontend dev).
 *
 * Différence avec `on_preview_real` (iter88) :
 *   - on_preview_real → lance `yarn build` (20s) → URL statique
 *   - LivePreviewPanel → iframe directe sur REACT_APP_BACKEND_URL → 0ms
 *
 * Pas besoin de Docker dédié — le hot reload Webpack du frontend est déjà actif.
 */
import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, X, RefreshCw, ExternalLink, Maximize2, Minimize2 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function LivePreviewPanel({ open, onClose, defaultPath = '/' }) {
  const [path, setPath] = useState(defaultPath);
  const [maximized, setMaximized] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const iframeRef = useRef(null);

  const previewUrl = `${BACKEND_URL}${path}`;

  const handleReload = () => setReloadKey((k) => k + 1);

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className={`fixed z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center ${
          maximized ? 'inset-0 p-0' : 'inset-0 p-4'
        }`}
        onClick={onClose}
        data-testid="live-preview-panel"
      >
        <motion.div
          initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className={`bg-[#0A0A0A] border border-white/10 rounded-lg shadow-[0_20px_60px_rgba(0,0,0,0.7)] overflow-hidden flex flex-col ${
            maximized ? 'w-full h-full rounded-none' : 'w-full max-w-6xl h-[85vh]'
          }`}
        >
          <header className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-gradient-to-r from-emerald-500/10 to-cyan-500/10">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <Eye className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span className="text-xs font-['Chivo'] font-bold text-white flex-shrink-0">Aperçu live</span>
              <input
                value={path}
                onChange={(e) => setPath(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleReload(); }}
                placeholder="/dashboard"
                data-testid="live-preview-path"
                className="flex-1 min-w-0 bg-[#0F0F13] border border-white/10 rounded-sm px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-emerald-400"
              />
              <span className="text-[10px] text-[#71717A] hidden md:inline truncate">{previewUrl}</span>
            </div>
            <div className="flex items-center gap-1 ml-2">
              <button onClick={handleReload} title="Recharger" data-testid="live-preview-reload"
                className="p-1.5 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-sm">
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
              <a href={previewUrl} target="_blank" rel="noopener noreferrer" title="Ouvrir dans un nouvel onglet"
                data-testid="live-preview-open-tab"
                className="p-1.5 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-sm">
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
              <button onClick={() => setMaximized((m) => !m)} title={maximized ? 'Restaurer' : 'Plein écran'}
                data-testid="live-preview-maximize"
                className="p-1.5 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-sm">
                {maximized ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              </button>
              <button onClick={onClose} title="Fermer" data-testid="live-preview-close"
                className="p-1.5 text-[#A1A1AA] hover:text-red-400 hover:bg-white/5 rounded-sm">
                <X className="w-4 h-4" />
              </button>
            </div>
          </header>
          <div className="flex-1 bg-white relative">
            <iframe
              ref={iframeRef}
              key={`${previewUrl}-${reloadKey}`}
              src={previewUrl}
              title="Live Preview"
              data-testid="live-preview-iframe"
              className="w-full h-full border-0"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            />
          </div>
          <footer className="px-3 py-1.5 border-t border-white/10 bg-black/30 flex items-center justify-between gap-2">
            <span className="text-[10px] text-[#71717A]">
              ⚡ Hot reload actif — les changements apparaissent instantanément.
            </span>
            <span className="text-[10px] text-[#71717A]">
              iter93 · Live Preview
            </span>
          </footer>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
