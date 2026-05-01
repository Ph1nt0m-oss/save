import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, Code, Smartphone, Monitor, Wand2,
  ArrowRight, ArrowLeft, Lock, MessageCircle, Lightbulb,
  Send, Wifi, Globe as GlobeIcon, Download, Plus, Loader2
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../contexts/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';

// 7 tutorial steps. Each step renders a different mock screen so visitors
// can see EXAMPLES of every page (Dashboard, Wizard, Create, Chat, generated
// app preview, Offline, final CTA). Everything is locked: only the tutorial
// arrows and the top-right "Connexion" button are clickable.
const TOTAL_STEPS = 7;

// ─── Mock screens ────────────────────────────────────────────────────────────

function MockTopBar({ title, subtitle, previewLabel }) {
  return (
    <div className="bg-[#0F0F13] border-b border-white/10 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="font-['Chivo'] font-bold text-xl">{title}</h1>
        {subtitle && <p className="text-xs text-[#A1A1AA] mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2 text-[10px] text-[#A1A1AA]/70 px-2 py-1 border border-white/10 rounded-sm">
        <Lock className="w-3 h-3" /> {previewLabel}
      </div>
    </div>
  );
}

function MockDashboardScreen({ t }) {
  const tiles = [
    { icon: Wand2, color: '#E4FF00', title: t('dashWizard'), desc: t('dashWizardDesc') },
    { icon: Code, color: '#00FF66', title: t('dashCreate'), desc: t('dashCreateDescOn') },
    { icon: MessageCircle, color: '#00D4FF', title: t('dashChat'), desc: t('dashChatDescOn') },
    { icon: Smartphone, color: '#A78BFA', title: t('dashOffline'), desc: t('dashChatDescOff') },
  ];
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={t('dashTitle')} subtitle={t('dashSubtitle')} previewLabel={t('d_preview')} />
      <div className="p-8">
        <h2 className="text-2xl font-['Chivo'] font-black text-white text-center mb-6">{t('dashWhatToDo')}</h2>
        <div className="grid grid-cols-2 gap-4 max-w-3xl mx-auto">
          {tiles.map((tile, i) => (
            <div key={i} className="bg-white/[0.03] border rounded-lg p-5 flex items-start gap-3"
              style={{ borderColor: `${tile.color}33` }}>
              <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ background: tile.color }}>
                <tile.icon className="w-5 h-5 text-[#050505]" />
              </div>
              <div>
                <p className="text-sm font-['Chivo'] font-bold text-white">{tile.title}</p>
                <p className="text-xs text-[#A1A1AA] mt-0.5">{tile.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MockWizardScreen({ t }) {
  const opts = ['🛒 E-Commerce', '📝 Blog/CMS', '💬 Messaging', '🎮 Game', '📊 Dashboard', '🎨 Portfolio'];
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={t('dashWizard')} subtitle={`${t('d_step')} 1/5`} previewLabel={t('d_preview')} />
      <div className="p-8">
        <h2 className="text-xl font-['Chivo'] font-black text-white mb-2">{t('whatTypeApp')}</h2>
        <p className="text-sm text-[#A1A1AA] mb-6">{t('chooseTemplate')}</p>
        <div className="grid grid-cols-3 gap-3 max-w-3xl">
          {opts.map((o, i) => (
            <div key={i} className={`p-4 border rounded-sm text-center text-sm font-['IBM_Plex_Sans'] ${
              i === 0 ? 'border-[#E4FF00] bg-[#E4FF00]/10 text-[#E4FF00]' : 'border-white/10 text-[#A1A1AA]'
            }`}>
              {o}
            </div>
          ))}
        </div>
        <div className="mt-6 flex items-center justify-end gap-2">
          <span className="text-xs text-[#A1A1AA]">{t('d_next')} →</span>
        </div>
      </div>
    </div>
  );
}

function MockCreateScreen({ t }) {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={t('dashCreate')} subtitle={t('dashCreateDescOn')} previewLabel={t('d_preview')} />
      <div className="p-8 grid grid-cols-2 gap-6">
        <div>
          <p className="text-xs text-[#A1A1AA] mb-2">{(t('describeApp') || 'Prompt').toUpperCase()}</p>
          <div className="bg-white/[0.04] border border-[#E4FF00]/30 rounded-sm p-4 text-sm text-white font-['IBM_Plex_Sans']">
            {t('d_b3')}
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs text-[#00FF66]">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>{t('generationInProgress')}</span>
          </div>
        </div>
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm overflow-hidden">
          <div className="bg-[#1a1a1f] px-3 py-1.5 flex items-center gap-1 text-[10px] text-[#A1A1AA]">
            <span className="w-2 h-2 rounded-full bg-red-400" />
            <span className="w-2 h-2 rounded-full bg-yellow-400" />
            <span className="w-2 h-2 rounded-full bg-green-400" />
            <span className="ml-2 truncate">recipes-app.preview</span>
          </div>
          <div className="p-4">
            <p className="text-base font-['Chivo'] font-bold text-[#E4FF00]">🍳 Léa's Recipes</p>
            <p className="text-[10px] text-[#A1A1AA]">Easy &amp; tasty</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {['Apple pie', 'Chicken curry', 'Pasta carbonara', 'Green smoothie'].map((r, i) => (
                <div key={i} className="bg-white/[0.04] border border-white/10 rounded-sm p-2">
                  <p className="text-[11px] text-white truncate">{r}</p>
                  <p className="text-[9px] text-[#E4FF00]">★★★★★</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MockChatScreen({ t }) {
  // Example dialog stays in a neutral conversational form across languages.
  const msgs = [
    { who: 'user', text: '+ share button' },
    { who: 'ai',   text: '✅ Done. Code updated.' },
    { who: 'user', text: '+ dark mode' },
    { who: 'ai',   text: '✅ Dark mode added (WCAG AA contrast).' },
  ];
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={t('dashChat')} subtitle={t('d_b4')} previewLabel={t('d_preview')} />
      <div className="p-6 space-y-3 max-w-2xl mx-auto">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.who === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[75%] p-3 rounded-sm text-sm font-['IBM_Plex_Sans'] ${
              m.who === 'user'
                ? 'bg-[#E4FF00] text-[#050505]'
                : 'bg-white/[0.05] border border-white/10 text-white'
            }`}>
              {m.text}
            </div>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-2 border-t border-white/10 mt-4">
          <div className="flex-1 bg-white/[0.04] border border-white/10 rounded-sm px-3 py-2 text-xs text-[#A1A1AA]/60">
            {t('describeWhatYouWant') || '...'}
          </div>
          <Send className="w-4 h-4 text-[#E4FF00]" />
        </div>
      </div>
    </div>
  );
}

function MockPreviewScreen({ t }) {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={t('preview')} subtitle="Web · PWA · .exe" previewLabel={t('d_preview')} />
      <div className="p-6 grid grid-cols-3 gap-4">
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
          <div className="aspect-video bg-gradient-to-br from-[#E4FF00]/20 to-[#00FF66]/10 rounded-sm flex items-center justify-center">
            <GlobeIcon className="w-10 h-10 text-[#E4FF00]" />
          </div>
          <p className="mt-2 text-xs font-['Chivo'] font-bold text-white">{t('web')}</p>
          <p className="text-[10px] text-[#A1A1AA]">{t('deployVercel')}</p>
        </div>
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
          <div className="aspect-video bg-gradient-to-br from-[#00D4FF]/20 to-[#00FF66]/10 rounded-sm flex items-center justify-center">
            <Smartphone className="w-10 h-10 text-[#00D4FF]" />
          </div>
          <p className="mt-2 text-xs font-['Chivo'] font-bold text-white">PWA {t('mobile')}</p>
          <p className="text-[10px] text-[#A1A1AA]">{t('installOnAndroid')}</p>
        </div>
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-3">
          <div className="aspect-video bg-gradient-to-br from-[#A78BFA]/20 to-[#E4FF00]/10 rounded-sm flex items-center justify-center">
            <Monitor className="w-10 h-10 text-[#A78BFA]" />
          </div>
          <p className="mt-2 text-xs font-['Chivo'] font-bold text-white">{t('desktop')} .exe</p>
          <p className="text-[10px] text-[#A1A1AA]">{t('downloadInstaller')}</p>
        </div>
      </div>
      <div className="px-6 pb-6 flex items-center justify-center gap-3">
        <span className="px-3 py-1.5 text-[10px] font-bold bg-[#E4FF00]/10 text-[#E4FF00] border border-[#E4FF00]/30 rounded-sm inline-flex items-center gap-1">
          <Download className="w-3 h-3" /> ZIP
        </span>
        <span className="px-3 py-1.5 text-[10px] font-bold bg-white/[0.04] text-white border border-white/10 rounded-sm">
          GitHub
        </span>
      </div>
    </div>
  );
}

function MockOfflineScreen({ t }) {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={t('dashOffline')} subtitle="Ollama · 100% local" previewLabel={t('d_preview')} />
      <div className="p-8 grid grid-cols-2 gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs bg-orange-400/20 text-orange-400">
            <Wifi className="w-3 h-3" /> {t('dashOffline')}
          </div>
          <h2 className="mt-3 text-xl font-['Chivo'] font-black text-white">Ollama</h2>
          <p className="mt-2 text-sm text-[#A1A1AA] leading-relaxed">{t('d_b6')}</p>
          <div className="mt-4 bg-black/40 border border-white/10 rounded-sm p-3 font-['IBM_Plex_Mono'] text-xs text-[#00FF66]">
            $ ollama pull deepseek-coder:6.7b<br/>
            $ ollama serve
          </div>
        </div>
        <div className="bg-[#0F0F13] border border-white/10 rounded-sm p-5 space-y-3">
          <p className="text-xs text-[#A1A1AA]">★</p>
          <ul className="text-sm text-white space-y-2">
            <li>✅ {t('l_feat6T')}</li>
            <li>✅ {t('l_feat5T')}</li>
            <li>✅ {t('l_feat6D')}</li>
            <li>✅ {t('l_feat5D')}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function MockFinalScreen({ t }) {
  return (
    <div className="bg-[#050505] rounded-sm overflow-hidden border border-white/10">
      <MockTopBar title={`🎁 ${t('l_ctaTitle')}`} subtitle={t('l_ctaSub')} previewLabel={t('d_preview')} />
      <div className="p-12 text-center max-w-2xl mx-auto">
        <Sparkles className="w-12 h-12 text-[#E4FF00] mx-auto" />
        <h2 className="mt-4 text-3xl font-['Chivo'] font-black text-white">{t('d_t7')}</h2>
        <p className="mt-3 text-sm text-[#A1A1AA]">{t('d_b7')}</p>
        <div className="mt-6 inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
          <Plus className="w-4 h-4 text-[#E4FF00]" />
          {t('d_signup')} ↗
        </div>
      </div>
    </div>
  );
}

const SCREENS = [
  MockDashboardScreen,
  MockWizardScreen,
  MockCreateScreen,
  MockChatScreen,
  MockPreviewScreen,
  MockOfflineScreen,
  MockFinalScreen,
];

// ─── Main component ──────────────────────────────────────────────────────────

export default function Discover() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [step, setStep] = useState(0);
  const wrapperRef = useRef(null);

  const STEP_META = useMemo(() => ([
    { titleKey: 'd_t1', bodyKey: 'd_b1' },
    { titleKey: 'd_t2', bodyKey: 'd_b2' },
    { titleKey: 'd_t3', bodyKey: 'd_b3' },
    { titleKey: 'd_t4', bodyKey: 'd_b4' },
    { titleKey: 'd_t5', bodyKey: 'd_b5' },
    { titleKey: 'd_t6', bodyKey: 'd_b6' },
    { titleKey: 'd_t7', bodyKey: 'd_b7', final: true },
  ]), []);

  const meta = STEP_META[step];
  const ScreenComponent = SCREENS[step];

  useEffect(() => {
    // Block any click that doesn't carry the explicit allow flag.
    const node = wrapperRef.current;
    if (!node) return;
    const blocker = (e) => {
      if (!e.target.closest('[data-discover-allow]')) {
        e.preventDefault();
        e.stopPropagation();
        toast.info(t('d_locked'), { duration: 1800 });
      }
    };
    node.addEventListener('click', blocker, true);
    return () => node.removeEventListener('click', blocker, true);
  }, [t]);

  // Keyboard arrows for navigation (great UX touch).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight') setStep(s => Math.min(TOTAL_STEPS - 1, s + 1));
      else if (e.key === 'ArrowLeft') setStep(s => Math.max(0, s - 1));
      else if (e.key === 'Escape') navigate('/');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const next = () => setStep(s => Math.min(TOTAL_STEPS - 1, s + 1));
  const prev = () => setStep(s => Math.max(0, s - 1));

  return (
    <div ref={wrapperRef} className="min-h-screen bg-[#050505] relative overflow-hidden">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="fixed inset-0 grid-bg opacity-10 pointer-events-none"></div>

      {/* Top bar — [Lang] · [Logo + step counter] · [Connexion] */}
      <header className="relative z-20 grid grid-cols-3 items-center px-6 py-4 border-b border-white/10 bg-black/60 backdrop-blur-md" data-discover-allow>
        <div className="justify-self-start flex items-center gap-3">
          <LanguageToggle placement="bottom" />
          <button
            onClick={() => navigate('/')}
            data-testid="discover-exit-btn"
            className="hidden sm:inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> {t('d_exit')}
          </button>
        </div>

        <div className="justify-self-center flex flex-col items-center gap-0.5">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-[#E4FF00]" />
            <span className="font-['Chivo'] font-black text-white">CodeForge AI</span>
          </div>
          <span className="text-[10px] text-[#A1A1AA] inline-flex items-center gap-1" data-testid="discover-step-counter">
            <Lightbulb className="w-3 h-3 text-[#E4FF00]" /> {t('d_step')} {step + 1} / {TOTAL_STEPS}
          </span>
        </div>

        <div className="justify-self-end">
          <button
            onClick={() => navigate('/login')}
            data-testid="discover-login-btn"
            className="px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
          >
            {t('d_login')}
          </button>
        </div>
      </header>

      {/* Mock screen for the current step */}
      <main className="relative z-10 max-w-6xl mx-auto px-4 py-8 pb-44">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.25 }}
            data-testid={`discover-screen-${step}`}
          >
            <ScreenComponent t={t} />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Floating tutorial card with arrows */}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-30 w-[94%] max-w-2xl" data-discover-allow>
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -10, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="bg-[#0A0A0A] border border-[#E4FF00]/30 rounded-sm p-5 backdrop-blur-2xl shadow-[0_8px_30px_rgba(228,255,0,0.15)]"
            data-testid="discover-tutorial-card"
          >
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-[#E4FF00] flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h2 className="text-base font-['Chivo'] font-bold text-white" data-testid="discover-step-title">{t(meta.titleKey)}</h2>
                <p className="mt-1.5 text-sm text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed">{t(meta.bodyKey)}</p>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-2">
              <button
                type="button" onClick={prev} disabled={step === 0}
                data-testid="discover-prev-btn"
                aria-label={t('d_prev')}
                className="inline-flex items-center gap-1 px-3 py-2 text-xs text-[#A1A1AA] border border-white/10 rounded-sm hover:text-white hover:border-white/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                {t('d_prev')}
              </button>

              <div className="flex items-center gap-1.5">
                {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
                  <span
                    key={i}
                    className={`h-1.5 rounded-full transition-all ${
                      i === step ? 'w-6 bg-[#E4FF00]' : 'w-1.5 bg-white/15'
                    }`}
                  />
                ))}
              </div>

              {step < TOTAL_STEPS - 1 ? (
                <button
                  type="button" onClick={next}
                  data-testid="discover-next-btn"
                  aria-label={t('d_next')}
                  className="inline-flex items-center gap-1 px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
                >
                  {t('d_next')}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button
                  type="button" onClick={() => navigate('/login')}
                  data-testid="discover-final-cta"
                  className="inline-flex items-center gap-1 px-4 py-2 bg-[#E4FF00] text-[#050505] text-xs font-['Chivo'] font-bold rounded-sm hover:-translate-y-0.5 transition-all"
                >
                  {t('d_signup')}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {meta.final && (
              <p className="mt-3 text-[10px] text-[#A1A1AA]/70 text-center">{t('d_kbTip')}</p>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
