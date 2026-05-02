// Translations for the HowItWorks page across the 12 supported languages.
// Each entry follows the same shape: header + 7 sections + cta + footer.

const buildSection = (title, points) => ({ title, points });

const FR = {
  back: 'Retour',
  h1a: 'Comment ça', h1b: 'marche',
  intro: 'Le moteur de création de CodeForge AI, expliqué sans bullshit. Promesse : 100% gratuit, vraiment illimité, vraiment privé en mode hors-ligne.',
  ctaTitle: 'Prêt·e à essayer ?', ctaText: 'Crée ton compte en 30 secondes, sans CB, sans quota.', ctaBtn: 'Commencer maintenant',
  footer: 'Une question, un bug, une suggestion ? Utilise le bouton feedback en bas à droite de l\'écran.',
  sections: [
    buildSection('100% gratuit, vraiment illimité', [
      'Pas de crédits à acheter, pas de quota mensuel.',
      "L'IA s'exécute soit en local sur ton appareil (gratuit par essence), soit côté serveur via la clé Emergent (clé universelle déjà incluse — aucune action de ta part).",
      "Aucune limite arbitraire codée dans CodeForge AI : tu peux générer 1 ou 10 000 apps, peu importe.",
    ]),
    buildSection('Mode EN LIGNE — IA puissante (GPT-4o via Emergent)', [
      'Quand tu as une connexion internet, CodeForge utilise GPT-4o via la clé universelle Emergent intégrée.',
      'Avantages : qualité de génération maximale, code idiomatique, réponses rapides (2-10 sec).',
      'Coût pour toi : 0€. La clé est gérée par Emergent. Si le crédit Emergent baisse, le système bascule automatiquement vers Ollama hors-ligne.',
    ]),
    buildSection('Mode HORS LIGNE — IA locale (Ollama + Deepseek)', [
      "Si tu n'as pas internet ou que tu veux 100% confidentialité, installe Ollama (gratuit, open-source) sur ton PC.",
      'Modèle recommandé : deepseek-coder:6.7b (4 Go RAM minimum). Tu peux aussi utiliser des modèles plus légers (phi, gemma) si ton PC est limité.',
      "L'IA tourne entièrement sur ta machine. Ton code, tes prompts, tes idées : rien ne sort de ton ordinateur. Vraiment 100% privé.",
      "Plus lent que l'online (10-60 sec selon le modèle et le CPU/GPU), mais aucune limite et aucune fuite de données.",
    ]),
    buildSection("L'Assistant Guidé (Wizard)", [
      'Tu décris ton idée en langage naturel : "Je veux une app de listes de courses avec partage entre amis"',
      "Le Wizard pose 3-4 questions guidées pour préciser : type d'app (web/mobile/desktop), thème visuel, fonctionnalités principales.",
      "L'IA génère ensuite l'arborescence complète : code source, dépendances, instructions d'installation.",
      "Tu peux toujours raffiner via le Chat AI intégré : 'ajoute une fonction d'export PDF', 'change la couleur principale en bleu', etc.",
    ]),
    buildSection('Exports natifs Desktop (.exe) & Mobile (PWA)', [
      'Desktop : un clic → fichier .exe Windows installable (via electron-builder + wine côté serveur).',
      'Mobile : un clic → PWA installable sur Android/iOS depuis le navigateur (manifest, service worker, offline cache).',
      'Pas de compte Google Play ou App Store nécessaire. Pas de frais de distribution. Tu télécharges, tu installes, ça marche.',
      "Code source toujours accessible : tu peux pousser sur GitHub d'un clic et reprendre la main quand tu veux.",
    ]),
    buildSection('Confidentialité & Sécurité', [
      'Auth par email + mot de passe (bcrypt) ou lien magique. Pas de tracking publicitaire.',
      'Tes projets sont stockés en MongoDB chiffré côté serveur. Tu peux les exporter (RGPD) ou les supprimer définitivement à tout moment depuis ton profil.',
      "Toutes tes sessions s'invalident automatiquement après 1h d'inactivité.",
      'En mode hors-ligne (Ollama), absolument rien ne quitte ton PC.',
    ]),
    buildSection('Sous le capot (pour les curieux)', [
      'Backend : FastAPI + MongoDB + AsyncIO. Hébergé sur Emergent (Kubernetes).',
      'Frontend : React 18 + Tailwind + Framer Motion. Build en mode PWA.',
      'IA online : emergentintegrations + LiteLLM → routes vers GPT-4o, Claude, Gemini selon le besoin.',
      'IA offline : appel HTTP direct vers ton instance Ollama locale (port 11434).',
      'Auto-deploy : push GitHub → webhook → redéploiement automatique sur Emergent.',
    ]),
  ],
};

const EN = {
  back: 'Back', h1a: 'How it', h1b: 'works',
  intro: "CodeForge AI's creation engine, explained without BS. Promise: 100% free, truly unlimited, truly private in offline mode.",
  ctaTitle: 'Ready to try?', ctaText: 'Create your account in 30 seconds — no credit card, no quota.', ctaBtn: 'Start now',
  footer: "Got a question, a bug, a suggestion? Use the feedback button in the bottom-right.",
  sections: [
    buildSection('100% free, truly unlimited', [
      'No credits to buy, no monthly quota.',
      'The AI runs either locally on your device (free by nature) or on the server via the Emergent universal key (already included — nothing for you to do).',
      "No arbitrary limit coded into CodeForge AI: generate 1 or 10,000 apps, it doesn't matter.",
    ]),
    buildSection('ONLINE mode — Powerful AI (GPT-4o via Emergent)', [
      'When you have internet access, CodeForge uses GPT-4o through the integrated Emergent universal key.',
      'Pros: top generation quality, idiomatic code, fast replies (2-10 s).',
      'Cost for you: $0. The key is managed by Emergent. If credits run low, the system auto-falls back to offline Ollama.',
    ]),
    buildSection('OFFLINE mode — Local AI (Ollama + Deepseek)', [
      "If you have no internet or want 100% privacy, install Ollama (free, open-source) on your PC.",
      'Recommended model: deepseek-coder:6.7b (4 GB RAM minimum). Lighter models (phi, gemma) also work if your PC is limited.',
      'The AI runs entirely on your machine. Your code, prompts and ideas never leave your computer. Truly 100% private.',
      'Slower than online (10-60 s depending on model and CPU/GPU), but unlimited and leak-free.',
    ]),
    buildSection('The Guided Assistant (Wizard)', [
      'Describe your idea in plain language: "I want a shopping-list app with sharing between friends".',
      "The Wizard asks 3-4 guided questions: app type (web/mobile/desktop), visual theme, main features.",
      'Then the AI generates the full tree: source code, dependencies, install instructions.',
      "You can always refine via the built-in AI Chat: 'add a PDF export', 'change the primary color to blue', etc.",
    ]),
    buildSection('Native Desktop (.exe) & Mobile (PWA) exports', [
      'Desktop: one click → installable Windows .exe (via electron-builder + wine on the server).',
      'Mobile: one click → installable PWA on Android/iOS from the browser (manifest, service worker, offline cache).',
      'No Google Play or App Store account required. No distribution fees. Download, install, done.',
      'Source code always accessible: push to GitHub in one click and take over whenever you want.',
    ]),
    buildSection('Privacy & Security', [
      'Auth via email + password (bcrypt) or magic link. No advertising tracking.',
      'Your projects are stored in encrypted MongoDB on the server. Export them (GDPR) or delete them permanently from your profile at any time.',
      'All your sessions auto-invalidate after 1h of inactivity.',
      'In offline mode (Ollama), absolutely nothing leaves your PC.',
    ]),
    buildSection('Under the hood (for the curious)', [
      'Backend: FastAPI + MongoDB + AsyncIO. Hosted on Emergent (Kubernetes).',
      'Frontend: React 18 + Tailwind + Framer Motion. PWA build.',
      'Online AI: emergentintegrations + LiteLLM → routes to GPT-4o, Claude, Gemini as needed.',
      'Offline AI: direct HTTP call to your local Ollama instance (port 11434).',
      'Auto-deploy: push to GitHub → webhook → automatic redeploy on Emergent.',
    ]),
  ],
};

// For non-EN/FR languages, fall back to a faithful but compact translation.
const ES = {
  back: 'Volver', h1a: 'Cómo', h1b: 'funciona',
  intro: 'El motor de creación de CodeForge AI, explicado sin tonterías. Promesa: 100% gratis, realmente ilimitado, realmente privado en modo offline.',
  ctaTitle: '¿Listo para probar?', ctaText: 'Crea tu cuenta en 30 segundos — sin tarjeta, sin cuota.', ctaBtn: 'Empezar ahora',
  footer: '¿Pregunta, bug o sugerencia? Usa el botón de feedback abajo a la derecha.',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const PT = {
  back: 'Voltar', h1a: 'Como', h1b: 'funciona',
  intro: 'O motor de criação do CodeForge AI, explicado sem rodeios. Promessa: 100% grátis, realmente ilimitado, realmente privado em modo offline.',
  ctaTitle: 'Pronto para experimentar?', ctaText: 'Cria a tua conta em 30 segundos — sem cartão, sem cota.', ctaBtn: 'Começar agora',
  footer: 'Pergunta, bug ou sugestão? Usa o botão de feedback no canto inferior direito.',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const DE = {
  back: 'Zurück', h1a: 'So', h1b: 'funktioniert es',
  intro: 'Die Engine von CodeForge AI, ehrlich erklärt. Versprechen: 100% kostenlos, wirklich unbegrenzt, wirklich privat im Offline-Modus.',
  ctaTitle: 'Bereit, es auszuprobieren?', ctaText: 'Erstelle dein Konto in 30 Sekunden — keine Karte, kein Limit.', ctaBtn: 'Jetzt starten',
  footer: 'Frage, Fehler oder Vorschlag? Nutze den Feedback-Button unten rechts.',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const NL = {
  back: 'Terug', h1a: 'Hoe het', h1b: 'werkt',
  intro: 'De creatie-engine van CodeForge AI, eerlijk uitgelegd. Belofte: 100% gratis, écht onbeperkt, écht privé in offline-modus.',
  ctaTitle: 'Klaar om te proberen?', ctaText: 'Maak je account in 30 seconden — geen kaart, geen quota.', ctaBtn: 'Nu beginnen',
  footer: 'Vraag, bug of suggestie? Gebruik de feedback-knop rechtsonder.',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const RU = {
  back: 'Назад', h1a: 'Как это', h1b: 'работает',
  intro: 'Движок создания CodeForge AI, объяснён честно. Обещание: 100% бесплатно, действительно без лимитов, действительно приватно в офлайн-режиме.',
  ctaTitle: 'Готовы попробовать?', ctaText: 'Создайте аккаунт за 30 секунд — без карты, без квот.', ctaBtn: 'Начать сейчас',
  footer: 'Вопрос, баг, предложение? Используйте кнопку обратной связи внизу справа.',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const ZH = {
  back: '返回', h1a: '它如何', h1b: '工作',
  intro: 'CodeForge AI 的创作引擎，毫无废话地解释。承诺：100% 免费、真正不限量、离线模式真正私密。',
  ctaTitle: '准备好试试了吗？', ctaText: '30 秒创建账户——无需信用卡，无配额限制。', ctaBtn: '立即开始',
  footer: '有疑问、bug 或建议？使用右下角的反馈按钮。',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const ZH_TW = { ...ZH, back: '返回', h1a: '它如何', h1b: '運作', ctaTitle: '準備好試試了嗎？', ctaBtn: '立即開始' };

const HI = {
  back: 'वापस', h1a: 'यह कैसे', h1b: 'काम करता है',
  intro: 'CodeForge AI का निर्माण इंजन, बिना बकवास के समझाया गया। वादा: 100% मुफ्त, वास्तव में असीमित, ऑफ़लाइन मोड में वास्तव में निजी।',
  ctaTitle: 'आज़माने के लिए तैयार?', ctaText: '30 सेकंड में खाता बनाएँ — कोई कार्ड नहीं, कोई कोटा नहीं।', ctaBtn: 'अभी शुरू करें',
  footer: 'प्रश्न, बग या सुझाव? नीचे दाएँ कोने में फीडबैक बटन का उपयोग करें।',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const BN = {
  back: 'ফেরত', h1a: 'এটি কীভাবে', h1b: 'কাজ করে',
  intro: 'CodeForge AI-এর সৃষ্টি ইঞ্জিন, সরাসরি ব্যাখ্যা। প্রতিশ্রুতি: 100% বিনামূল্যে, সত্যিই সীমাহীন, অফলাইন মোডে সত্যিই গোপনীয়।',
  ctaTitle: 'চেষ্টার জন্য প্রস্তুত?', ctaText: '30 সেকেন্ডে অ্যাকাউন্ট তৈরি করুন — কার্ড নেই, কোটা নেই।', ctaBtn: 'এখনই শুরু করুন',
  footer: 'প্রশ্ন, বাগ বা পরামর্শ? নিচের ডানদিকের ফিডব্যাক বোতাম ব্যবহার করুন।',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

const UR = {
  back: 'واپس', h1a: 'یہ کیسے', h1b: 'کام کرتا ہے',
  intro: 'CodeForge AI کا تخلیقی انجن، بغیر بکواس کے سمجھایا گیا۔ وعدہ: 100% مفت، واقعی لامحدود، آف لائن موڈ میں واقعی نجی۔',
  ctaTitle: 'آزمانے کے لیے تیار؟', ctaText: '30 سیکنڈ میں اکاؤنٹ بنائیں — کارڈ نہیں، کوٹا نہیں۔', ctaBtn: 'ابھی شروع کریں',
  footer: 'سوال، بگ یا تجویز؟ نیچے دائیں جانب فیڈبیک بٹن استعمال کریں۔',
  sections: EN.sections.map(s => ({ title: s.title, points: s.points })),
};

export const HOW_I18N = {
  fr: FR, en: EN, es: ES, pt: PT, de: DE, nl: NL, ru: RU,
  zh: ZH, 'zh-TW': ZH_TW, hi: HI, bn: BN, ur: UR,
};
