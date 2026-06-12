import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, MessageCircleQuestion, Bot, Save, Loader2, Sparkles } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';
import useViewSpec from '../hooks/useViewSpec';
import useDeviceIdentity from '../hooks/useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter108 — Page de programmation des chatbots (Caly + bots communautaires).
 * Permet à la créatrice + admins d'éditer les system prompts et FAQ.
 * Sécurité identique à PrivateProgramming : creator physique + PAS en simulation.
 */
export default function PrivateChatbotProgramming() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const device = useDeviceIdentity();
  const { canSeeProgramming } = useViewSpec();
  const [tab, setTab] = useState('caly');  // 'caly' | 'bots'

  const isInSimulation = device.viewMode && device.viewMode !== 'creator';
  // iter108 — Admins peuvent voir l'onglet aussi (KB + bots communautaires)
  // mais le code source du site reste réservé créa.
  const allowed = canSeeProgramming && !isInSimulation;

  return (
    <div className="min-h-screen bg-[#050505] text-white p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/dashboard')}
            className="text-[#A1A1AA] hover:text-white text-sm inline-flex items-center gap-1"
            data-testid="chatbot-prog-back">
            <ArrowLeft className="w-4 h-4" /> {t('back')}
          </button>
          <h1 className="text-2xl font-['Chivo'] font-black inline-flex items-center gap-2">
            <Bot className="w-6 h-6 text-pink-400" /> Programmation des chatbots
          </h1>
        </div>

        {!allowed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-sm p-8 text-center max-w-md mx-auto">
            <h2 className="text-lg font-bold text-red-200 mb-2">{t('prog_access_denied')}</h2>
            <p className="text-sm text-red-100/90">{t('prog_access_body')}</p>
            <p className="text-xs text-amber-200/90 mt-3">{t('prog_access_hint')}</p>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div className="flex gap-2 mb-4 border-b border-white/10">
              <button
                onClick={() => setTab('caly')}
                data-testid="chatbot-prog-tab-caly"
                className={`px-4 py-2 text-sm font-bold rounded-t-sm transition-colors ${
                  tab === 'caly' ? 'bg-pink-500/15 text-pink-300 border-b-2 border-pink-400' : 'text-[#A1A1AA] hover:text-white'
                }`}
              >
                <MessageCircleQuestion className="w-4 h-4 inline mr-1" /> Caly (chatbot d'aide)
              </button>
              <button
                onClick={() => setTab('bots')}
                data-testid="chatbot-prog-tab-bots"
                className={`px-4 py-2 text-sm font-bold rounded-t-sm transition-colors ${
                  tab === 'bots' ? 'bg-cyan-500/15 text-cyan-300 border-b-2 border-cyan-400' : 'text-[#A1A1AA] hover:text-white'
                }`}
              >
                <Bot className="w-4 h-4 inline mr-1" /> Bots communautaires
              </button>
            </div>

            {tab === 'caly' ? <CalyPromptEditor /> : <BotsCommunityList />}
          </>
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

  useEffect(() => {
    axios.get(`${API}/caly/config`).then((r) => {
      setPrompt(r.data?.prompt || '');
      setOriginalPrompt(r.data?.prompt || '');
      setIsDefault(r.data?.is_default !== false);
    }).catch(() => toast.error('Impossible de charger le prompt Caly'))
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
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

  const dirty = prompt !== originalPrompt;
  if (loading) return <Loader2 className="w-6 h-6 mx-auto mt-12 animate-spin text-pink-400" />;

  return (
    <div className="bg-[#0A0A0A] border border-white/10 rounded-sm p-4 space-y-3" data-testid="caly-prompt-editor">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-['Chivo'] font-bold text-sm text-pink-300 inline-flex items-center gap-2">
            <Sparkles className="w-4 h-4" /> Prompt système de Caly
          </h2>
          <p className="text-[11px] text-[#A1A1AA] mt-0.5">
            {isDefault ? 'Prompt par défaut (jamais modifié)' : 'Prompt personnalisé actif'}
            {' — Modifie le comportement de Caly. Visible immédiatement par tous les utilisateurs.'}
          </p>
        </div>
        <button onClick={save} disabled={!dirty || saving}
          data-testid="caly-prompt-save"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-pink-500 hover:bg-pink-400 disabled:opacity-40 text-white rounded-sm">
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Sauvegarder
        </button>
      </div>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        spellCheck="false"
        rows={24}
        data-testid="caly-prompt-textarea"
        className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-pink-400 resize-none"
      />
      <div className="flex items-center justify-between text-[10px] text-[#71717A]">
        <span>{prompt.length} / 8000 caractères</span>
        {dirty && <span className="text-amber-300">● Modifications non sauvegardées</span>}
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
