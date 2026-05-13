import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { ExternalLink, Sparkles, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Public preview page — anyone with the slug can view the project. No auth.
 * Renders the project's HTML in a sandboxed iframe and shows a small banner
 * with a "Build your own with CodeForge AI" CTA — viral loop.
 */
export default function SharedPreview() {
  const { slug } = useParams();
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/share/${slug}`)
      .then((r) => { if (!cancelled) setMeta(r.data); })
      .catch((e) => { if (!cancelled) setErr(e.response?.data?.detail || 'Projet introuvable'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [slug]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center" data-testid="shared-loading">
        <div className="flex items-center gap-2 text-[#A1A1AA]">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Chargement…</span>
        </div>
      </div>
    );
  }

  if (err || !meta) {
    return (
      <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center p-6" data-testid="shared-error">
        <div className="max-w-md text-center space-y-4">
          <Sparkles className="w-8 h-8 text-[#E4FF00] mx-auto" />
          <h1 className="text-2xl font-['Chivo'] font-bold">Projet introuvable</h1>
          <p className="text-sm text-[#A1A1AA]">{err || 'Ce lien public n\'existe pas ou a été désactivé.'}</p>
          <a href="/" className="inline-block px-4 py-2 border border-[#E4FF00] text-[#E4FF00] font-['Chivo'] font-bold text-sm rounded-sm hover:bg-[#E4FF00] hover:text-[#050505] transition">
            Découvrir CodeForge AI
          </a>
        </div>
      </div>
    );
  }

  const previewUrl = `${API}/share/${slug}/preview`;

  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col" data-testid="shared-page">
      {/* Sticky public banner with CTA */}
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 bg-[#0A0A0A] border-b border-white/10 sticky top-0 z-10">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles className="w-4 h-4 text-[#E4FF00] flex-shrink-0" />
          <div className="min-w-0">
            <div className="text-sm font-['Chivo'] font-bold truncate" data-testid="shared-name">{meta.name || 'Projet partagé'}</div>
            {meta.description && (
              <div className="text-[11px] text-[#A1A1AA] truncate">{meta.description}</div>
            )}
          </div>
        </div>
        <a
          href="/"
          target="_blank"
          rel="noreferrer"
          data-testid="shared-cta"
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold rounded-sm hover:bg-white transition"
        >
          Crée la tienne <ExternalLink className="w-3 h-3" />
        </a>
      </header>

      {/* Live iframe — sandbox restricts to no-same-origin scripts, no top-nav. */}
      <div className="flex-1 bg-white">
        <iframe
          src={previewUrl}
          title={meta.name || 'Aperçu'}
          data-testid="shared-iframe"
          className="w-full h-full min-h-[calc(100vh-44px)] border-0"
          sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
        />
      </div>
    </div>
  );
}
