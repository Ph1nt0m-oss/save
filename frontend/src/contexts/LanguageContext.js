import React, { createContext, useContext, useState, useEffect } from 'react';

// Traductions
const translations = {
  fr: {
    // Common
    back: 'Retour',
    next: 'Suivant',
    previous: 'Précédent',
    generate: 'Générer',
    loading: 'Chargement...',
    error: 'Erreur',
    success: 'Succès',
    cancel: 'Annuler',
    save: 'Enregistrer',
    delete: 'Supprimer',
    edit: 'Modifier',
    close: 'Fermer',
    yes: 'Oui',
    no: 'Non',
    
    // Auth
    login: 'Connexion',
    logout: 'Déconnexion',
    loginWithGoogle: 'Continuer avec Google',
    loginWithSMS: 'Connexion SMS (Hors Ligne)',
    phoneNumber: 'Numéro de téléphone',
    sendCode: 'Envoyer le code',
    verifyCode: 'Vérifier le code',
    invalidCode: 'Code invalide',
    codeSent: 'Code envoyé !',
    
    // Dashboard
    dashboard: 'Tableau de bord',
    projects: 'Projets',
    newProject: 'Nouveau Projet',
    whatToDo: 'Que souhaitez-vous faire ?',
    chooseWorkMode: 'Choisissez votre mode de travail',
    
    // Modes
    online: 'En ligne',
    offline: 'Hors ligne',
    onlineChat: 'Interaction IA en ligne',
    offlineChat: 'Interaction IA hors ligne',
    onlineCreate: 'Création en ligne',
    offlineCreate: 'Création hors ligne',
    
    // Create
    createTitle: 'Création IA Sans Limites',
    describeApp: 'Décrivez votre application',
    aiGeneratesAll: "L'IA génère tout automatiquement",
    unlimitedCreation: 'Création Illimitée',
    describeWhatYouWant: 'Décrivez ce que vous voulez créer',
    generationInProgress: 'Génération en cours...',
    appGenerated: 'Application générée !',
    codeReadyExport: 'Code généré et prêt à exporter',
    
    // Preview
    preview: 'Prévisualisation',
    previewWeb: 'Prévisualiser Web',
    previewApp: 'Prévisualiser App',
    previewPDF: 'Prévisualiser PDF',
    previewDOCX: 'Prévisualiser DOCX',
    
    // Export
    export: 'Export',
    exportAPK: 'Export Mobile (APK)',
    exportEXE: 'Export Desktop (EXE)',
    exportWeb: 'Déploiement Web',
    downloadSource: 'Télécharger le code source',
    installOnAndroid: 'Installez sur Android directement',
    downloadInstaller: "Téléchargez l'installateur Windows",
    deployVercel: 'Déployez sur Vercel, Netlify ou votre hébergeur',
    
    // Wizard
    wizardTitle: 'Assistant de Création',
    step: 'Étape',
    whatTypeApp: "Quel type d'application ?",
    chooseTemplate: 'Choisissez le modèle qui correspond le mieux',
    giveName: 'Donnez un nom',
    whatWillBeCalled: "Comment s'appellera votre application ?",
    chooseColors: 'Choisissez vos couleurs',
    selectPalette: 'Sélectionnez une palette de couleurs',
    targetPlatform: 'Plateforme cible',
    whereUsed: 'Où sera utilisée votre application ?',
    advancedOptions: 'Options avancées',
    customizeFeatures: 'Personnalisez les fonctionnalités',
    authentication: 'Authentification',
    loginSignupSystem: 'Système de login/signup',
    database: 'Base de données',
    persistentStorage: 'Stockage de données persistant',
    interfaceLanguage: "Langue de l'interface",
    summary: 'Résumé de votre application',
    generateApp: "Générer l'Application",
    appReady: 'Application prête à être exportée',
    
    // App Types
    ecommerce: 'E-Commerce',
    blog: 'Blog/CMS',
    social: 'Réseau Social',
    chat: 'Messagerie',
    portfolio: 'Portfolio',
    dashboardType: 'Dashboard',
    booking: 'Réservation',
    media: 'Média/Streaming',
    maps: 'Géolocalisation',
    utility: 'Utilitaire',
    music: 'Audio/Musique',
    custom: 'Personnalisé',
    
    // Platforms
    web: 'Web',
    mobile: 'Mobile',
    desktop: 'Desktop',
    allPlatforms: 'Toutes'
  },
  
  en: {
    // Common
    back: 'Back',
    next: 'Next',
    previous: 'Previous',
    generate: 'Generate',
    loading: 'Loading...',
    error: 'Error',
    success: 'Success',
    cancel: 'Cancel',
    save: 'Save',
    delete: 'Delete',
    edit: 'Edit',
    close: 'Close',
    yes: 'Yes',
    no: 'No',
    
    // Auth
    login: 'Login',
    logout: 'Logout',
    loginWithGoogle: 'Continue with Google',
    loginWithSMS: 'SMS Login (Offline)',
    phoneNumber: 'Phone number',
    sendCode: 'Send code',
    verifyCode: 'Verify code',
    invalidCode: 'Invalid code',
    codeSent: 'Code sent!',
    
    // Dashboard
    dashboard: 'Dashboard',
    projects: 'Projects',
    newProject: 'New Project',
    whatToDo: 'What would you like to do?',
    chooseWorkMode: 'Choose your work mode',
    
    // Modes
    online: 'Online',
    offline: 'Offline',
    onlineChat: 'Online AI Chat',
    offlineChat: 'Offline AI Chat',
    onlineCreate: 'Online Creation',
    offlineCreate: 'Offline Creation',
    
    // Create
    createTitle: 'Unlimited AI Creation',
    describeApp: 'Describe your application',
    aiGeneratesAll: 'AI generates everything automatically',
    unlimitedCreation: 'Unlimited Creation',
    describeWhatYouWant: 'Describe what you want to create',
    generationInProgress: 'Generation in progress...',
    appGenerated: 'Application generated!',
    codeReadyExport: 'Code generated and ready to export',
    
    // Preview
    preview: 'Preview',
    previewWeb: 'Preview Web',
    previewApp: 'Preview App',
    previewPDF: 'Preview PDF',
    previewDOCX: 'Preview DOCX',
    
    // Export
    export: 'Export',
    exportAPK: 'Mobile Export (APK)',
    exportEXE: 'Desktop Export (EXE)',
    exportWeb: 'Web Deployment',
    downloadSource: 'Download source code',
    installOnAndroid: 'Install on Android directly',
    downloadInstaller: 'Download Windows installer',
    deployVercel: 'Deploy on Vercel, Netlify or your host',
    
    // Wizard
    wizardTitle: 'Creation Wizard',
    step: 'Step',
    whatTypeApp: 'What type of application?',
    chooseTemplate: 'Choose the template that fits best',
    giveName: 'Give it a name',
    whatWillBeCalled: 'What will your application be called?',
    chooseColors: 'Choose your colors',
    selectPalette: 'Select a color palette',
    targetPlatform: 'Target platform',
    whereUsed: 'Where will your application be used?',
    advancedOptions: 'Advanced options',
    customizeFeatures: 'Customize features',
    authentication: 'Authentication',
    loginSignupSystem: 'Login/signup system',
    database: 'Database',
    persistentStorage: 'Persistent data storage',
    interfaceLanguage: 'Interface language',
    summary: 'Your application summary',
    generateApp: 'Generate Application',
    appReady: 'Application ready to export',
    
    // App Types
    ecommerce: 'E-Commerce',
    blog: 'Blog/CMS',
    social: 'Social Network',
    chat: 'Messaging',
    portfolio: 'Portfolio',
    dashboardType: 'Dashboard',
    booking: 'Booking',
    media: 'Media/Streaming',
    maps: 'Geolocation',
    utility: 'Utility',
    music: 'Audio/Music',
    custom: 'Custom',
    
    // Platforms
    web: 'Web',
    mobile: 'Mobile',
    desktop: 'Desktop',
    allPlatforms: 'All'
  }
};

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(() => {
    // Récupérer depuis localStorage ou utiliser le navigateur
    const saved = localStorage.getItem('codeforge_language');
    if (saved) return saved;
    
    const browserLang = navigator.language.split('-')[0];
    return browserLang === 'fr' ? 'fr' : 'en';
  });

  useEffect(() => {
    localStorage.setItem('codeforge_language', language);
  }, [language]);

  const t = (key) => {
    return translations[language]?.[key] || translations['en']?.[key] || key;
  };

  const toggleLanguage = () => {
    setLanguage(prev => prev === 'fr' ? 'en' : 'fr');
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}

export default LanguageContext;
