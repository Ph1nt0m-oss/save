import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import {
  ArrowLeft, ArrowRight, Sparkles, Loader2,
  Smartphone, Monitor, Globe, CheckCircle, Wand2,
  Database, Users, ShoppingCart, MessageSquare, Image as ImgIcon,
  FileText, Calendar, Video, Map, Bell, Music, Paintbrush, Cog
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import AttachMenu from '../components/AttachMenu';
import { useLanguage } from '../contexts/LanguageContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PLATFORMS = [
  { id: 'web', icon: Globe, labelKey: 'wizard_plat_web', descKey: 'wizard_plat_web_desc' },
  { id: 'mobile', icon: Smartphone, labelKey: 'wizard_plat_mobile', descKey: 'wizard_plat_mobile_desc' },
  { id: 'desktop', icon: Monitor, labelKey: 'wizard_plat_desktop', descKey: 'wizard_plat_desktop_desc' },
];

const APP_TYPES = [
  { id: 'ecommerce', icon: ShoppingCart, labelKey: 'wizard_type_ecommerce' },
  { id: 'blog', icon: FileText, labelKey: 'wizard_type_blog' },
  { id: 'social', icon: Users, labelKey: 'wizard_type_social' },
  { id: 'chat', icon: MessageSquare, labelKey: 'wizard_type_chat' },
  { id: 'portfolio', icon: ImgIcon, labelKey: 'wizard_type_portfolio' },
  { id: 'dashboard', icon: Database, labelKey: 'wizard_type_dashboard' },
  { id: 'booking', icon: Calendar, labelKey: 'wizard_type_booking' },
  { id: 'media', icon: Video, labelKey: 'wizard_type_media' },
  { id: 'maps', icon: Map, labelKey: 'wizard_type_maps' },
  { id: 'notifications', icon: Bell, labelKey: 'wizard_type_notifications' },
  { id: 'music', icon: Music, labelKey: 'wizard_type_music' },
  { id: 'custom', icon: Sparkles, labelKey: 'wizard_type_custom' },
];

export default function GuidedWizard() {
  const navigate = useNavigate();
  const location = useLocation();
  const { language, t } = useLanguage();
  const mode = location.state?.mode || 'online';

  const [step, setStep] = useState(1);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedProject, setGeneratedProject] = useState(null);

  const [platforms, setPlatforms] = useState([]);            // multi-select
  const [appTypes, setAppTypes] = useState([]);              // multi-select
  const [appName, setAppName] = useState('');
  const [nameSuggestions, setNameSuggestions] = useState([]);
  const [magicLoading, setMagicLoading] = useState({ name: false, design: false, func: false });
  const [designText, setDesignText] = useState('');          // visuel
  const [funcText, setFuncText] = useState('');              // fonctionnement
  const [attachments, setAttachments] = useState([]);        // [{kind, name?, text?, url?}]

  const totalSteps = 4;

  const togglePlatform = (id) => setPlatforms(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  const toggleType = (id) => setAppTypes(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);

  const canProceed = () => {
    if (step === 1) return platforms.length > 0 && appTypes.length > 0;
    if (step === 2) return appName.trim().length > 1;
    if (step === 3) return designText.trim().length > 0 || funcText.trim().length > 0;
    return true;
  };

  const askMagicName = async () => {
    setMagicLoading(s => ({ ...s, name: true }));
    try {
      const r = await axios.post(`${API}/ai/wizard-suggest`,
        { kind: 'name', platforms, app_type: appTypes[0] || null, description: funcText, language, seed: Math.random() },
        { withCredentials: true });
      const list = Array.isArray(r.data?.suggestions) ? r.data.suggestions.slice(0, 3) : [];
      setNameSuggestions(list);
      // iter79 — Toujours écraser le nom existant à chaque clic de la baguette
      // pour proposer un nouveau pseudo, même si l'utilisateur a déjà saisi/choisi.
      if (list[0]) {
        setAppName(list[0]);
        toast.success('🪄 ' + list.join(' · '));
      }
    } catch (_) {
      toast.error('Suggestion impossible');
    } finally {
      setMagicLoading(s => ({ ...s, name: false }));
    }
  };

  const askMagicDesign = async () => {
    setMagicLoading(s => ({ ...s, design: true }));
    try {
      const r = await axios.post(`${API}/ai/wizard-suggest`,
        { kind: 'design', platforms, app_type: appTypes[0] || null, description: funcText || appName, language, seed: Math.random() },
        { withCredentials: true });
      const text = (r.data?.design || '').trim();
      if (text) {
        setDesignText(prev => prev ? `${prev}\n\n${text}` : text);
        toast.success('🪄 Design ajouté');
      }
    } catch (_) {
      toast.error('Suggestion impossible');
    } finally {
      setMagicLoading(s => ({ ...s, design: false }));
    }
  };

  // iter80 C2 — Suggestion IA pour le bloc Fonctionnement.
  const askMagicFunc = async () => {
    setMagicLoading(s => ({ ...s, func: true }));
    try {
      const r = await axios.post(`${API}/ai/wizard-suggest`,
        { kind: 'function', platforms, app_type: appTypes[0] || null, description: designText || appName, language, seed: Math.random() },
        { withCredentials: true });
      const text = (r.data?.func || r.data?.design || '').trim();
      if (text) {
        setFuncText(prev => prev ? `${prev}\n\n${text}` : text);
        toast.success('🪄 Fonctionnement ajouté');
      }
    } catch (_) {
      toast.error('Suggestion impossible');
    } finally {
      setMagicLoading(s => ({ ...s, func: false }));
    }
  };

  const handleAttach = (att) => {
    setAttachments(a => [...a, att]);
    if (att.kind === 'text') {
      setFuncText(prev => prev ? `${prev}\n${att.text}` : att.text);
      toast.success('📋 Presse-papier ajouté');
    } else if (att.kind === 'url') {
      setFuncText(prev => prev ? `${prev}\nRéférence : ${att.url}` : `Référence : ${att.url}`);
      toast.success('🔗 ' + att.url);
    } else if (att.kind === 'file') {
      toast.success('📎 ' + att.name);
    }
  };

  const removeAttachment = (idx) => setAttachments(a => a.filter((_, i) => i !== idx));

  const summaryDescription = () => {
    const platLabel = platforms.map(p => PLATFORMS.find(x => x.id === p)?.label).filter(Boolean).join(', ');
    const typeLabel = appTypes.map(t => APP_TYPES.find(x => x.id === t)?.label).filter(Boolean).join(', ');
    return [
      `Application "${appName}" — type ${typeLabel}.`,
      `Plateformes cibles : ${platLabel}.`,
      designText ? `Direction visuelle : ${designText}` : '',
      funcText ? `Fonctionnement attendu : ${funcText}` : '',
      attachments.length ? `Pièces jointes : ${attachments.map(a => a.name || a.url || 'extrait').join(', ')}` : '',
    ].filter(Boolean).join('\n\n');
  };

  const generateApplication = async () => {
    setIsGenerating(true);
    try {
      const r = await axios.post(
        `${API}/ai/generate-complete-app`,
        {
          description: summaryDescription(),
          mode,
          wizard_config: { platforms, appTypes, appName, designText, funcText, language },
        },
        { withCredentials: true }
      );
      setGeneratedProject(r.data);
      toast.success(t('wizard_success_toast'));
      setStep(5);
    } catch (e) {
      toast.error(t('wizard_error_toast'));
    } finally {
      setIsGenerating(false);
    }
  };

  const renderStep = () => {
    if (step === 1) {
      return (
        <div className="space-y-10">
          <header className="text-center">
            <h2 className="text-3xl sm:text-4xl font-['Chivo'] font-black mb-2">{t('wizard_q1_title')}</h2>
            <p className="text-[#A1A1AA]">{t('wizard_q1_subtitle')}</p>
          </header>

          <section>
            <h3 className="text-xs uppercase tracking-widest text-[#A1A1AA] mb-3">{t('wizard_platform_label')}</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="wizard-platforms">
              {PLATFORMS.map(p => {
                const active = platforms.includes(p.id);
                return (
                  <motion.button
                    key={p.id} whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}
                    onClick={() => togglePlatform(p.id)}
                    data-testid={`wizard-platform-${p.id}`}
                    className={`p-5 rounded-sm border-2 text-left transition-all ${
                      active ? 'border-[#E4FF00] bg-[#E4FF00]/10' : 'border-white/10 bg-[#0F0F13] hover:border-white/30'
                    }`}
                  >
                    <p.icon className={`w-7 h-7 mb-3 ${active ? 'text-[#E4FF00]' : 'text-[#A1A1AA]'}`} />
                    <h4 className="font-['Chivo'] font-bold">{t(p.labelKey)}</h4>
                    <p className="text-xs text-[#A1A1AA] mt-1">{t(p.descKey)}</p>
                  </motion.button>
                );
              })}
            </div>
          </section>

          <section>
            <h3 className="text-xs uppercase tracking-widest text-[#A1A1AA] mb-3">{t('wizard_apptype_label')}</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="wizard-types">
              {APP_TYPES.map(tp => {
                const active = appTypes.includes(tp.id);
                return (
                  <motion.button
                    key={tp.id} whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}
                    onClick={() => toggleType(tp.id)}
                    data-testid={`wizard-type-${tp.id}`}
                    className={`p-3 rounded-sm border text-left transition-all ${
                      active ? 'border-[#E4FF00] bg-[#E4FF00]/10' : 'border-white/10 bg-[#0F0F13] hover:border-white/30'
                    }`}
                  >
                    <tp.icon className={`w-5 h-5 mb-2 ${active ? 'text-[#E4FF00]' : 'text-[#A1A1AA]'}`} />
                    <h4 className="text-sm font-['Chivo'] font-bold">{t(tp.labelKey)}</h4>
                  </motion.button>
                );
              })}
            </div>
          </section>
        </div>
      );
    }

    if (step === 2) {
      return (
        <div className="space-y-8 max-w-xl mx-auto">
          <header className="text-center">
            <h2 className="text-3xl sm:text-4xl font-['Chivo'] font-black mb-2">{t('wizard_q2_title')}</h2>
            <p className="text-[#A1A1AA]">{t('wizard_q2_subtitle')}</p>
          </header>

          <div className="relative">
            <input
              type="text" value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder={t('wizard_name_placeholder')}
              data-testid="wizard-app-name"
              className="w-full px-6 py-5 pr-16 bg-[#0F0F13] border-2 border-white/15 rounded-sm focus:outline-none focus:border-[#E4FF00] text-2xl text-center font-['Chivo']"
            />
            <button
              type="button" onClick={askMagicName}
              data-testid="wizard-magic-name-btn"
              disabled={magicLoading.name || platforms.length === 0}
              title={t('wizard_magic_name_tip')}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-sm bg-[#E4FF00] text-[#050505] hover:scale-105 transition-transform disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {magicLoading.name ? <Loader2 className="w-5 h-5 animate-spin" /> : <Wand2 className="w-5 h-5" />}
            </button>
          </div>

          {nameSuggestions.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-center" data-testid="wizard-name-suggestions">
              {nameSuggestions.map((n) => (
                <button key={n} onClick={() => setAppName(n)}
                  className="px-3 py-1.5 text-sm border border-white/15 rounded-sm hover:border-[#E4FF00] hover:text-[#E4FF00] transition-colors">
                  {n}
                </button>
              ))}
            </div>
          )}

          <p className="text-xs text-[#A1A1AA] text-center">
            {t('wizard_magic_name_hint')}
          </p>
        </div>
      );
    }

    if (step === 3) {
      return (
        <div className="space-y-8 max-w-3xl mx-auto">
          <header className="text-center">
            <h2 className="text-3xl sm:text-4xl font-['Chivo'] font-black mb-2">{t('wizard_q3_title')}</h2>
            <p className="text-[#A1A1AA]">{t('wizard_q3_subtitle')}</p>
          </header>

          <div className="grid md:grid-cols-2 gap-5">
            <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-['Chivo'] font-bold flex items-center gap-2"><Paintbrush className="w-4 h-4 text-[#E4FF00]" /> {t('wizard_design_label')}</h3>
                <div className="flex items-center gap-1.5">
                  <button onClick={askMagicDesign}
                    data-testid="wizard-magic-design-btn"
                    disabled={magicLoading.design}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:scale-105 transition-transform disabled:opacity-40">
                    {magicLoading.design ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                    {t('wizard_ai_suggestion')}
                  </button>
                  {/* iter80 C2 — Pièces jointes possibles aussi dans Design */}
                  <AttachMenu onResult={handleAttach} />
                </div>
              </div>
              <textarea
                value={designText} onChange={(e) => setDesignText(e.target.value)}
                rows={8} placeholder={t('wizard_design_placeholder')}
                data-testid="wizard-design-textarea"
                className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-[#E4FF00]"
              />
            </div>

            <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-['Chivo'] font-bold flex items-center gap-2"><Cog className="w-4 h-4 text-[#00FF66]" /> {t('wizard_func_label')}</h3>
                <div className="flex items-center gap-1.5">
                  {/* iter80 C2 — Suggestion IA possible aussi dans Fonctionnement */}
                  <button onClick={askMagicFunc}
                    data-testid="wizard-magic-func-btn"
                    disabled={magicLoading.func}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs bg-[#00FF66] text-[#050505] font-bold rounded-sm hover:scale-105 transition-transform disabled:opacity-40">
                    {magicLoading.func ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                    {t('wizard_ai_suggestion')}
                  </button>
                  <AttachMenu onResult={handleAttach} />
                </div>
              </div>
              <textarea
                value={funcText} onChange={(e) => setFuncText(e.target.value)}
                rows={8} placeholder={t('wizard_func_placeholder')}
                data-testid="wizard-func-textarea"
                className="w-full bg-[#050505] border border-white/10 rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-[#00FF66]"
              />
            </div>
          </div>

          {attachments.length > 0 && (
            <div data-testid="wizard-attachments" className="flex flex-wrap gap-2">
              {attachments.map((a, i) => (
                <span key={i} className="inline-flex items-center gap-2 px-2.5 py-1 text-xs bg-white/5 border border-white/10 rounded-sm">
                  📎 {a.name || a.url || 'extrait'}
                  <button onClick={() => removeAttachment(i)} className="text-[#A1A1AA] hover:text-red-400">×</button>
                </span>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (step === 4) {
      return (
        <div className="max-w-2xl mx-auto space-y-6" data-testid="wizard-recap">
          <header className="text-center">
            <h2 className="text-3xl sm:text-4xl font-['Chivo'] font-black mb-2">{t('wizard_recap_title')}</h2>
            <p className="text-[#A1A1AA]">{t('wizard_recap_subtitle')}</p>
          </header>

          <div className="bg-[#0F0F13] border-2 border-[#E4FF00] rounded-sm p-6 space-y-4 text-sm">
            <Row label={t('wizard_recap_name')} value={appName || '—'} />
            <Row label={t('wizard_recap_platforms')} value={platforms.map(p => t(PLATFORMS.find(x => x.id === p)?.labelKey)).filter(Boolean).join(', ') || '—'} />
            <Row label={t('wizard_recap_types')} value={appTypes.map(tp => t(APP_TYPES.find(x => x.id === tp)?.labelKey)).filter(Boolean).join(', ') || '—'} />
            <Row label={t('wizard_recap_design')} value={designText || '—'} multiline />
            <Row label={t('wizard_recap_func')} value={funcText || '—'} multiline />
            {attachments.length > 0 && (
              <Row label={t('wizard_recap_attachments')} value={attachments.map(a => a.name || a.url || 'extrait').join(', ')} />
            )}
          </div>
        </div>
      );
    }

    if (step === 5) {
      return (
        <div className="text-center space-y-8 max-w-xl mx-auto">
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}
            className="w-24 h-24 bg-[#00FF66] rounded-full flex items-center justify-center mx-auto">
            <CheckCircle className="w-12 h-12 text-[#050505]" />
          </motion.div>
          <div>
            <h2 className="text-3xl font-['Chivo'] font-black mb-2">{t('wizard_generated_title')}</h2>
            <p className="text-[#A1A1AA]">&quot;{appName}&quot; {t('wizard_generated_ready')}</p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Button onClick={() => window.open(`${API}/export/mobile/${generatedProject?.project?.id}`, '_blank')}
              className="bg-[#E4FF00] text-[#050505] py-6" disabled={!generatedProject?.project?.id}>
              <Smartphone className="w-5 h-5 mr-2" /> APK
            </Button>
            <Button onClick={() => window.open(`${API}/export/desktop/${generatedProject?.project?.id}`, '_blank')}
              className="bg-[#E4FF00] text-[#050505] py-6" disabled={!generatedProject?.project?.id}>
              <Monitor className="w-5 h-5 mr-2" /> EXE
            </Button>
            <Button onClick={() => window.open(`${API}/preview/project/${generatedProject?.project?.id}`, '_blank')}
              className="bg-[#00FF66] text-[#050505] py-6" disabled={!generatedProject?.project?.id}>
              <Globe className="w-5 h-5 mr-2" /> Web
            </Button>
          </div>
          <Button onClick={() => navigate('/dashboard')} variant="outline" className="border-white/20">
            {t('wizard_back_dashboard')}
          </Button>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      <header className="bg-[#0F0F13] border-b border-white/10 px-3 sm:px-6 py-3 sm:py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <Button onClick={() => navigate('/dashboard')} variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{t('back')}</span>
            </Button>
            <Sparkles className="w-5 h-5 text-[#E4FF00] flex-shrink-0" />
            <h1 className="font-['Chivo'] font-bold text-base sm:text-xl truncate">{t('wizard_assistant_title')}</h1>
          </div>
          {step <= totalSteps && (
            <div className="flex items-center gap-1.5">
              {Array.from({ length: totalSteps }, (_, i) => i + 1).map(s => (
                <div key={s} data-testid={`wizard-step-dot-${s}`}
                  className={`h-2 rounded-full transition-all ${
                    s === step ? 'bg-[#E4FF00] w-6' : s < step ? 'bg-[#00FF66] w-2' : 'bg-white/20 w-2'
                  }`}
                />
              ))}
              <span className="ml-2 text-xs text-[#A1A1AA] hidden sm:inline">{t('wizard_step_label')} {step}/{totalSteps}</span>
            </div>
          )}
        </div>
      </header>

      <div className="max-w-5xl mx-auto p-4 sm:p-6">
        <AnimatePresence mode="wait">
          <motion.div key={step}
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
            className="py-6 sm:py-10">
            {renderStep()}
          </motion.div>
        </AnimatePresence>

        {step <= totalSteps && (
          <div className="flex justify-between mt-6 pt-6 border-t border-white/10 gap-3">
            <Button onClick={() => setStep(s => Math.max(1, s - 1))} variant="outline"
              disabled={step === 1} className="border-white/20" data-testid="wizard-back-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> {t('wizard_back_btn')}
            </Button>

            {step < totalSteps ? (
              <Button onClick={() => setStep(s => s + 1)} disabled={!canProceed()}
                data-testid="wizard-next-btn"
                className="bg-[#E4FF00] text-[#050505] font-['Chivo'] font-bold">
                {t('wizard_next_btn')} <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            ) : (
              <Button onClick={generateApplication} disabled={isGenerating || !canProceed()}
                data-testid="wizard-generate-btn"
                className="bg-[#00FF66] text-[#050505] px-6 sm:px-8 font-['Chivo'] font-bold">
                {isGenerating ? <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> {t('wizard_generating')}</>
                  : <><Sparkles className="w-5 h-5 mr-2" /> {t('wizard_generate_btn')}</>}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const Row = ({ label, value, multiline }) => (
  <div className="grid grid-cols-1 sm:grid-cols-[140px_1fr] gap-1 sm:gap-3">
    <div className="text-xs uppercase tracking-widest text-[#A1A1AA]">{label}</div>
    <div className={multiline ? 'whitespace-pre-wrap' : ''}>{value}</div>
  </div>
);
