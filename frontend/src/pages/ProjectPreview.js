import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Smartphone, Monitor, Tablet, RefreshCw, ExternalLink, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Live Preview — rend le projet courant dans une iframe isolée.
 * Trois tailles (Desktop / Tablette / Mobile) + recharge + ouverture nouvelle fenêtre.
 */
export default function ProjectPreview() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [device, setDevice] = useState('desktop'); // desktop | tablet | mobile
  const [iframeKey, setIframeKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [projectName, setProjectName] = useState('');

  useEffect(() => {
    // Fetch minimal project metadata (just the name) for the header.
    (async () => {
      try {
        const res = await fetch(`${API}/projects`, { credentials: 'include' });
        if (!res.ok) return;
        const list = await res.json();
        const p = (list || []).find((x) => x.project_id === projectId);
        if (p) setProjectName(p.name || projectId);
      } catch { /* ignore */ }
    })();
  }, [projectId]);

  const previewUrl = `${API}/preview/project/${projectId}`;

  const sizes = {
    desktop: { width: '100%', maxWidth: '100%', height: '100%' },
    tablet: { width: '820px', maxWidth: '100%', height: '1100px' },
    mobile: { width: '390px', maxWidth: '100%', height: '844px' },
  };
  const size = sizes[device];

  return (
    <div data-testid="project-preview-page" className="min-h-screen bg-[#050505] text-white flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-black/60 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            data-testid="preview-back-btn"
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-sm bg-white/[0.04] hover:bg-white/[0.08] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Retour
          </button>
          <div>
            <div className="text-xs text-[#A1A1AA] font-['IBM_Plex_Sans']">Aperçu Live</div>
            <div className="text-sm font-['Chivo'] font-bold truncate max-w-[50vw]">{projectName || projectId}</div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {[
            { id: 'desktop', icon: Monitor, label: 'Ordi' },
            { id: 'tablet', icon: Tablet, label: 'Tablette' },
            { id: 'mobile', icon: Smartphone, label: 'Mobile' },
          ].map((b) => (
            <button
              key={b.id}
              data-testid={`preview-device-${b.id}`}
              onClick={() => setDevice(b.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs border transition-all ${
                device === b.id
                  ? 'bg-[#E4FF00] text-[#050505] border-[#E4FF00] font-bold'
                  : 'bg-white/[0.04] border-white/10 hover:bg-white/[0.08]'
              }`}
            >
              <b.icon className="w-3.5 h-3.5" />
              {b.label}
            </button>
          ))}
          <button
            data-testid="preview-refresh-btn"
            onClick={() => { setLoading(true); setIframeKey((k) => k + 1); }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs bg-white/[0.04] border border-white/10 hover:bg-white/[0.08] transition-colors ml-1"
            title="Recharger"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <a
            data-testid="preview-open-new-btn"
            href={previewUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs bg-white/[0.04] border border-white/10 hover:bg-white/[0.08] transition-colors"
            title="Ouvrir dans un onglet"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* Preview area */}
      <main className="flex-1 flex items-start justify-center p-4 overflow-auto bg-[radial-gradient(ellipse_at_top,rgba(228,255,0,0.04),transparent_60%)]">
        <div
          className={`relative bg-white/5 border border-white/10 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.5)] overflow-hidden transition-all`}
          style={{ width: size.width, maxWidth: size.maxWidth, height: size.height }}
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#050505]/90 z-10">
              <Loader2 className="w-6 h-6 animate-spin text-[#E4FF00]" />
            </div>
          )}
          <iframe
            key={iframeKey}
            data-testid="preview-iframe"
            src={previewUrl}
            title="Aperçu du projet"
            sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
            onLoad={() => setLoading(false)}
            className="w-full h-full bg-white"
            style={{ border: 0 }}
          />
        </div>
      </main>
    </div>
  );
}
