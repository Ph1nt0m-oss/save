import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, MessageCircleQuestion, Bot, Save, Loader2, Sparkles, FileCode, Search as SearchIcon } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';
import useViewSpec from '../hooks/useViewSpec';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter108 — Page de programmation des chatbots (Caly + bots communautaires).
 * iter112 — Split en 2 modes via prop `mode`:
 *   - mode="caly" → Programmation de Caly (chatbot assistant virtuel)
 *   - mode="bots" → Programmations des bots et chatbots (bots communautaires)
 * Permet à la créatrice + admins d'éditer les system prompts et FAQ.
 * Sécurité identique à PrivateProgramming : creator/admin physique + PAS en simulation.
 */
export default function PrivateChatbotProgramming({ mode = 'caly' }) {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  const { canSeeProgramming } = useViewSpec();

  const isInSimulation = device.viewMode && device.viewMode !== 'creator';
  // iter108 — Admins peuvent voir l'onglet aussi (KB + bots communautaires)
  // mais le code source du site reste réservé créa.
  const allowed = canSeeProgramming && !isInSimulation;

  const title = mode === 'caly'
    ? 'Programmation de Caly'
    : 'Programmations des bots et chatbots';
  const subtitle = mode === 'caly'
    ? 'Chatbot assistant virtuel — code & prompt modifiables (admins + créa, masqué en vue simulée)'
    : 'Bots communautaires — code & FAQ modifiables (admins + créa, masqué en vue simulée)';
  const Icon = mode === 'caly' ? MessageCircleQuestion : Bot;
  const iconColor = mode === 'caly' ? 'text-pink-400' : 'text-cyan-400';

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-3 mb-2">
          <button onClick={() => navigate('/dashboard')}
            className="text-[#A1A1AA] hover:text-white text-sm inline-flex items-center gap-1"
            data-testid="chatbot-prog-back">
            <ArrowLeft className="w-4 h-4" /> {t('back')}
          </button>
          <h1 className="text-2xl font-['Chivo'] font-black inline-flex items-center gap-2">
            <Icon className={`w-6 h-6 ${iconColor}`} /> {title}
          </h1>
        </div>
        <p className="text-xs text-[#A1A1AA] mb-6">{subtitle}</p>

        {!allowed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-sm p-8 text-center max-w-md mx-auto" data-testid="private-access-denied">
            <h2 className="text-lg font-bold text-red-200 mb-2">{t('prog_access_denied')}</h2>
            <p className="text-sm text-red-100/90">{t('prog_access_body')}</p>
            <p className="text-xs text-amber-200/90 mt-3">{t('prog_access_hint')}</p>
          </div>
        ) : (
          // iter112 — Plus de tabs : chaque mode rend son éditeur dédié.
          mode === 'caly' ? <CalyPromptEditor /> : <BotsCommunityList />
        )}
      </div>
    </div>
  );
}

function CalyPromptEditor() {
  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [isDefault, setIsDefault] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // iter109 — Code source Caly côté backend (read + write + search)
  const [codeContent, setCodeContent] = useState('');
  const [codeBuffer, setCodeBuffer] = useState('');
  const [codeDirty, setCodeDirty] = useState(false);
  const [codeLoading, setCodeLoading] = useState(true);
  const [codeSaving, setCodeSaving] = useState(false);
  const [searchPattern, setSearchPattern] = useState('');
  const [searchResults, setSearchResults] = useState(null);

  useEffect(() => {
    // Prompt système Caly
    axios.get(`${API}/caly/config`).then((r) => {
      setPrompt(r.data?.prompt || '');
      setOriginalPrompt(r.data?.prompt || '');
      setIsDefault(r.data?.is_default !== false);
    }).catch(() => toast.error('Impossible de charger le prompt Caly'))
      .finally(() => setLoading(false));
    // Code source Caly (chunk de server.py contenant les endpoints /caly/*)
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, { path: 'backend/server.py' });
        const r = await axios.post(`${API}/private/code/read-file`, body);
        const full = r.data?.content || '';
        // Extraire la section Caly (CALY_DEFAULT_SYSTEM_PROMPT → fin de caly_config_set)
        const start = full.indexOf('# iter106 — CALY CHATBOT');
        const end = full.indexOf('# ==========================================================================', start + 80);
        const slice = (start >= 0 && end > start)
          ? full.slice(start, end + 80)
          : full;  // fallback : tout le fichier
        setCodeContent(slice);
        setCodeBuffer(slice);
      } catch (e) {
        toast.error('Impossible de charger le code Caly');
      } finally { setCodeLoading(false); }
    })();
  }, []);

  const savePrompt = async () => {
    if (!prompt.trim()) return;
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, { prompt: prompt.trim() });
      await axios.post(`${API}/caly/config`, body);
      setOriginalPrompt(prompt.trim());
      setIsDefault(false);
      toast.success('Prompt Caly sauvegardé ✓');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec sauvegarde');
    } finally { setSaving(false); }
  };

  const saveCode = async () => {
    if (!codeDirty) return;
    setCodeSaving(true);
    try {
      // Réécrit la section Caly dans server.py
      const bodyRead = await withCreatorProof(API, axios, { path: 'backend/server.py' });
      const r = await axios.post(`${API}/private/code/read-file`, bodyRead);
      const full = r.data?.content || '';
      const start = full.indexOf('# iter106 — CALY CHATBOT');
      const end = full.indexOf('# ==========================================================================', start + 80);
      if (start < 0 || end < start) throw new Error('Marqueurs introuvables dans server.py');
      const newContent = full.slice(0, start) + codeBuffer + full.slice(end + 80);
      const bodyWrite = await withCreatorProof(API, axios, { path: 'backend/server.py', content: newContent });
      await axios.post(`${API}/private/code/write-file`, bodyWrite);
      setCodeContent(codeBuffer);
      setCodeDirty(false);
      toast.success('Code Caly sauvegardé (backup .bak créé)');
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || 'Échec sauvegarde code');
    } finally { setCodeSaving(false); }
  };

  const doSearch = async () => {
    if (!searchPattern.trim()) return;
    try {
      const body = await withCreatorProof(API, axios, { pattern: searchPattern.trim() });
      const r = await axios.post(`${API}/private/code/grep`, body);
      setSearchResults(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Recherche impossible'); }
  };

  const dirty = prompt !== originalPrompt;
  if (loading) return <Loader2 className="w-6 h-6 mx-auto mt-12 animate-spin text-pink-400" />;

  return (
    <div className="space-y-4" data-testid="caly-prompt-editor">
      {/* Section 1 : Prompt système */}
      <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="font-['Chivo'] font-bold text-sm text-pink-300 inline-flex items-center gap-2">
              <Sparkles className="w-4 h-4" /> Prompt système de Caly
            </h2>
            <p className="text-[11px] text-[#A1A1AA] mt-0.5">
              {isDefault ? 'Prompt par défaut (jamais modifié)' : 'Prompt personnalisé actif'}
              {' — Modifie le comportement de Caly. Visible immédiatement par tous les utilisateurs.'}
            </p>
          </div>
          <button onClick={savePrompt} disabled={!dirty || saving}
            data-testid="caly-prompt-save"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-pink-500 hover:bg-pink-400 disabled:opacity-40 text-white rounded-sm">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Sauvegarder
          </button>
        </div>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          spellCheck="false"
          rows={14}
          data-testid="caly-prompt-textarea"
          className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-pink-400 resize-none"
        />
        <div className="flex items-center justify-between text-[10px] text-[#71717A]">
          <span>{prompt.length} / 8000 caractères</span>
          {dirty && <span className="text-amber-300">● Modifications non sauvegardées</span>}
        </div>
      </div>

      {/* Section 2 : Code source Caly (édition directe backend) */}
      <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-4 space-y-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div>
            <h2 className="font-['Chivo'] font-bold text-sm text-pink-300 inline-flex items-center gap-2">
              <FileCode className="w-4 h-4" /> Code source Caly (compétences, endpoints)
            </h2>
            <p className="text-[11px] text-[#A1A1AA] mt-0.5">
              Extrait de <span className="font-mono text-cyan-300">backend/server.py</span> contenant les endpoints
              <span className="font-mono"> /caly/ask</span> et <span className="font-mono">/caly/config</span>. Backup .bak auto.
            </p>
          </div>
          <button onClick={saveCode} disabled={!codeDirty || codeSaving}
            data-testid="caly-code-save"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-pink-500 hover:bg-pink-400 disabled:opacity-40 text-white rounded-sm">
            {codeSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Sauvegarder le code
          </button>
        </div>
        {codeLoading ? (
          <Loader2 className="w-5 h-5 animate-spin text-pink-400" />
        ) : (
          <textarea
            value={codeBuffer}
            onChange={(e) => { setCodeBuffer(e.target.value); setCodeDirty(e.target.value !== codeContent); }}
            spellCheck="false"
            rows={20}
            data-testid="caly-code-textarea"
            className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-[10px] font-mono text-white focus:outline-none focus:border-pink-400 resize-none"
          />
        )}
        {codeDirty && <div className="text-[10px] text-amber-300">● Modifications non sauvegardées</div>}
      </div>

      {/* Section 3 : Recherche dans le code */}
      <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-4 space-y-2">
        <h2 className="font-['Chivo'] font-bold text-sm text-pink-300 inline-flex items-center gap-2">
          <SearchIcon className="w-4 h-4" /> Recherche dans le code
        </h2>
        <div className="flex gap-2">
          <input
            value={searchPattern}
            onChange={(e) => setSearchPattern(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') doSearch(); }}
            placeholder="Pattern à chercher…"
            data-testid="caly-search-input"
            className="flex-1 bg-[#050505] border border-white/15 rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none focus:border-pink-400"
          />
          <button onClick={doSearch} data-testid="caly-search-btn"
            className="px-3 py-1.5 bg-pink-500 hover:bg-pink-400 text-white font-bold text-xs rounded-sm">
            Grep
          </button>
        </div>
        {searchResults && (
          <div className="text-[10px] text-[#A1A1AA] mt-1 max-h-40 overflow-y-auto">
            <div>{searchResults.total} ligne(s) trouvée(s)</div>
            {(searchResults.matches || []).slice(0, 30).map((line, i) => (
              <div key={i} className="text-[10px] font-mono text-white py-0.5 truncate">{line}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BotsCommunityList() {
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    axios.get(`${API}/community-bots`)
      .then((r) => setBots(r.data?.bots || []))
      .catch(() => toast.error('Impossible de charger les bots'))
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <Loader2 className="w-6 h-6 mx-auto mt-12 animate-spin text-cyan-400" />;
  return (
    <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-4" data-testid="bots-community-list">
      <h2 className="font-['Chivo'] font-bold text-sm text-cyan-300 mb-3 inline-flex items-center gap-2">
        <Bot className="w-4 h-4" /> Bots communautaires ({bots.length})
      </h2>
      <p className="text-[11px] text-[#A1A1AA] mb-3">
        Pour modifier le prompt d'un bot ou enrichir sa base de connaissances, utilise
        le bouton « Bots » dans la top-bar (accessible aux admins).
      </p>
      {bots.length === 0 ? (
        <div className="text-[11px] text-[#71717A] text-center py-6">
          Aucun bot communautaire créé pour le moment.
        </div>
      ) : (
        <div className="space-y-2">
          {bots.map((b) => (
            <div key={b.bot_id} data-testid={`prog-bot-${b.bot_id}`}
              className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-sm text-white truncate">{b.name}</h3>
                  <p className="text-[11px] text-[#A1A1AA] mt-0.5 line-clamp-2">{b.description || '(pas de description)'}</p>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-sm flex-shrink-0 ${
                  b.is_published ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'
                }`}>
                  {b.is_published ? 'Publié' : 'Brouillon'}
                </span>
              </div>
              <div className="text-[10px] text-[#71717A] mt-2 font-mono truncate">
                Kind: {b.kind || 'assistance'} · Bot ID: {b.bot_id}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
