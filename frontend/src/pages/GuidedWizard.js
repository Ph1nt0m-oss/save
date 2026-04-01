import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { 
  ArrowLeft, ArrowRight, Sparkles, Loader2, 
  Smartphone, Monitor, Globe, CheckCircle,
  Palette, Database, Users, ShoppingCart, MessageSquare, Image,
  FileText, Calendar, Music, Video, Map, Bell
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Types d'applications prédéfinis
const APP_TYPES = [
  { id: 'ecommerce', icon: ShoppingCart, label: 'E-Commerce', desc: 'Boutique en ligne avec panier' },
  { id: 'blog', icon: FileText, label: 'Blog/CMS', desc: 'Site de contenu avec gestion' },
  { id: 'social', icon: Users, label: 'Réseau Social', desc: 'Communauté et partage' },
  { id: 'chat', icon: MessageSquare, label: 'Messagerie', desc: 'Chat en temps réel' },
  { id: 'portfolio', icon: Image, label: 'Portfolio', desc: 'Présentation de projets' },
  { id: 'dashboard', icon: Database, label: 'Dashboard', desc: 'Tableau de bord analytique' },
  { id: 'booking', icon: Calendar, label: 'Réservation', desc: 'Système de rendez-vous' },
  { id: 'media', icon: Video, label: 'Média/Streaming', desc: 'Plateforme de contenu' },
  { id: 'maps', icon: Map, label: 'Géolocalisation', desc: 'App basée sur les cartes' },
  { id: 'notifications', icon: Bell, label: 'Utilitaire', desc: 'App de productivité' },
  { id: 'music', icon: Music, label: 'Audio/Musique', desc: 'Lecteur ou streaming' },
  { id: 'custom', icon: Sparkles, label: 'Personnalisé', desc: 'Décrivez votre idée' }
];

// Palettes de couleurs
const COLOR_PALETTES = [
  { id: 'cyber', name: 'Cyber Yellow', primary: '#E4FF00', secondary: '#00FF66', bg: '#050505' },
  { id: 'ocean', name: 'Ocean Blue', primary: '#0EA5E9', secondary: '#06B6D4', bg: '#0F172A' },
  { id: 'sunset', name: 'Sunset', primary: '#F97316', secondary: '#EF4444', bg: '#1C1917' },
  { id: 'forest', name: 'Forest', primary: '#22C55E', secondary: '#10B981', bg: '#052E16' },
  { id: 'purple', name: 'Royal Purple', primary: '#A855F7', secondary: '#EC4899', bg: '#1E1B4B' },
  { id: 'minimal', name: 'Minimal', primary: '#FFFFFF', secondary: '#A1A1AA', bg: '#000000' }
];

// Plateformes cibles
const PLATFORMS = [
  { id: 'web', icon: Globe, label: 'Web', desc: 'Site responsive' },
  { id: 'mobile', icon: Smartphone, label: 'Mobile', desc: 'Android/iOS' },
  { id: 'desktop', icon: Monitor, label: 'Desktop', desc: 'Windows/Mac' },
  { id: 'all', icon: Sparkles, label: 'Toutes', desc: 'Multi-plateforme' }
];

export default function GuidedWizard() {
  const navigate = useNavigate();
  const location = useLocation();
  const mode = location.state?.mode || 'online';
  
  const [step, setStep] = useState(1);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedProject, setGeneratedProject] = useState(null);
  
  // Wizard state
  const [config, setConfig] = useState({
    appType: null,
    customDescription: '',
    colorPalette: 'cyber',
    platform: 'web',
    features: [],
    appName: '',
    hasAuth: true,
    hasDatabase: true,
    language: 'fr'
  });

  const totalSteps = 5;

  const updateConfig = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const canProceed = () => {
    switch (step) {
      case 1: return config.appType !== null;
      case 2: return config.appName.trim().length > 0;
      case 3: return true;
      case 4: return true;
      case 5: return true;
      default: return false;
    }
  };

  const generateApplication = async () => {
    setIsGenerating(true);
    
    const appTypeLabel = APP_TYPES.find(t => t.id === config.appType)?.label || config.appType;
    const paletteInfo = COLOR_PALETTES.find(p => p.id === config.colorPalette);
    
    const fullDescription = `
Créer une application "${config.appName}" de type ${appTypeLabel}.
${config.customDescription ? `Description supplémentaire: ${config.customDescription}` : ''}

Spécifications:
- Plateforme: ${config.platform}
- Palette de couleurs: ${paletteInfo?.name} (Primary: ${paletteInfo?.primary}, Secondary: ${paletteInfo?.secondary}, Background: ${paletteInfo?.bg})
- Authentification: ${config.hasAuth ? 'Oui' : 'Non'}
- Base de données: ${config.hasDatabase ? 'Oui' : 'Non'}
- Fonctionnalités: ${config.features.join(', ') || 'Standard'}
- Langue de l'interface: ${config.language === 'fr' ? 'Français' : 'English'}

Génère une application complète et fonctionnelle avec tous les fichiers nécessaires.
    `.trim();

    try {
      const response = await axios.post(
        `${API}/ai/generate-complete-app`,
        { 
          description: fullDescription,
          mode,
          wizard_config: config
        },
        { withCredentials: true }
      );

      setGeneratedProject(response.data);
      toast.success('Application générée avec succès !');
      setStep(6); // Success step
    } catch (error) {
      console.error('Generation error:', error);
      toast.error('Erreur de génération. Réessayez.');
    } finally {
      setIsGenerating(false);
    }
  };

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div className="space-y-6">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-['Chivo'] font-bold mb-2">Quel type d'application ?</h2>
              <p className="text-[#A1A1AA]">Choisissez le modèle qui correspond le mieux à votre projet</p>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {APP_TYPES.map(type => (
                <motion.button
                  key={type.id}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => updateConfig('appType', type.id)}
                  className={`p-4 rounded-lg border-2 text-left transition-all ${
                    config.appType === type.id
                      ? 'border-[#E4FF00] bg-[#E4FF00]/10'
                      : 'border-white/10 bg-[#0F0F13] hover:border-white/30'
                  }`}
                >
                  <type.icon className={`w-8 h-8 mb-3 ${config.appType === type.id ? 'text-[#E4FF00]' : 'text-[#A1A1AA]'}`} />
                  <h3 className="font-bold mb-1">{type.label}</h3>
                  <p className="text-xs text-[#A1A1AA]">{type.desc}</p>
                </motion.button>
              ))}
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-6 max-w-xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-['Chivo'] font-bold mb-2">Donnez un nom</h2>
              <p className="text-[#A1A1AA]">Comment s'appellera votre application ?</p>
            </div>
            
            <div>
              <input
                type="text"
                value={config.appName}
                onChange={(e) => updateConfig('appName', e.target.value)}
                placeholder="Mon Application"
                className="w-full px-6 py-4 bg-[#0F0F13] border-2 border-white/20 rounded-lg focus:outline-none focus:border-[#E4FF00] text-2xl text-center"
                data-testid="wizard-app-name"
              />
            </div>

            {config.appType === 'custom' && (
              <div className="mt-6">
                <label className="block text-sm font-medium mb-2">Description détaillée</label>
                <textarea
                  value={config.customDescription}
                  onChange={(e) => updateConfig('customDescription', e.target.value)}
                  placeholder="Décrivez votre application en détail..."
                  rows={4}
                  className="w-full px-4 py-3 bg-[#0F0F13] border border-white/20 rounded-lg focus:outline-none focus:border-[#E4FF00]"
                />
              </div>
            )}
          </div>
        );

      case 3:
        return (
          <div className="space-y-6">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-['Chivo'] font-bold mb-2">Choisissez vos couleurs</h2>
              <p className="text-[#A1A1AA]">Sélectionnez une palette de couleurs</p>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
              {COLOR_PALETTES.map(palette => (
                <motion.button
                  key={palette.id}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => updateConfig('colorPalette', palette.id)}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    config.colorPalette === palette.id
                      ? 'border-[#E4FF00]'
                      : 'border-white/10 hover:border-white/30'
                  }`}
                  style={{ backgroundColor: palette.bg }}
                >
                  <div className="flex gap-2 mb-3">
                    <div className="w-8 h-8 rounded-full" style={{ backgroundColor: palette.primary }} />
                    <div className="w-8 h-8 rounded-full" style={{ backgroundColor: palette.secondary }} />
                  </div>
                  <h3 className="font-bold text-sm">{palette.name}</h3>
                </motion.button>
              ))}
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-6">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-['Chivo'] font-bold mb-2">Plateforme cible</h2>
              <p className="text-[#A1A1AA]">Où sera utilisée votre application ?</p>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
              {PLATFORMS.map(platform => (
                <motion.button
                  key={platform.id}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => updateConfig('platform', platform.id)}
                  className={`p-6 rounded-lg border-2 text-center transition-all ${
                    config.platform === platform.id
                      ? 'border-[#E4FF00] bg-[#E4FF00]/10'
                      : 'border-white/10 bg-[#0F0F13] hover:border-white/30'
                  }`}
                >
                  <platform.icon className={`w-12 h-12 mx-auto mb-3 ${config.platform === platform.id ? 'text-[#E4FF00]' : 'text-[#A1A1AA]'}`} />
                  <h3 className="font-bold mb-1">{platform.label}</h3>
                  <p className="text-xs text-[#A1A1AA]">{platform.desc}</p>
                </motion.button>
              ))}
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-6 max-w-2xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-['Chivo'] font-bold mb-2">Options avancées</h2>
              <p className="text-[#A1A1AA]">Personnalisez les fonctionnalités</p>
            </div>
            
            <div className="space-y-4">
              <label className="flex items-center justify-between p-4 bg-[#0F0F13] rounded-lg border border-white/10 cursor-pointer hover:border-white/30">
                <div>
                  <h3 className="font-bold">Authentification</h3>
                  <p className="text-sm text-[#A1A1AA]">Système de login/signup</p>
                </div>
                <input
                  type="checkbox"
                  checked={config.hasAuth}
                  onChange={(e) => updateConfig('hasAuth', e.target.checked)}
                  className="w-6 h-6 accent-[#E4FF00]"
                />
              </label>

              <label className="flex items-center justify-between p-4 bg-[#0F0F13] rounded-lg border border-white/10 cursor-pointer hover:border-white/30">
                <div>
                  <h3 className="font-bold">Base de données</h3>
                  <p className="text-sm text-[#A1A1AA]">Stockage de données persistant</p>
                </div>
                <input
                  type="checkbox"
                  checked={config.hasDatabase}
                  onChange={(e) => updateConfig('hasDatabase', e.target.checked)}
                  className="w-6 h-6 accent-[#E4FF00]"
                />
              </label>

              <div className="p-4 bg-[#0F0F13] rounded-lg border border-white/10">
                <h3 className="font-bold mb-2">Langue de l'interface</h3>
                <div className="flex gap-3">
                  <button
                    onClick={() => updateConfig('language', 'fr')}
                    className={`flex-1 py-2 rounded ${config.language === 'fr' ? 'bg-[#E4FF00] text-[#050505]' : 'bg-white/10'}`}
                  >
                    Français
                  </button>
                  <button
                    onClick={() => updateConfig('language', 'en')}
                    className={`flex-1 py-2 rounded ${config.language === 'en' ? 'bg-[#E4FF00] text-[#050505]' : 'bg-white/10'}`}
                  >
                    English
                  </button>
                </div>
              </div>
            </div>

            {/* Résumé */}
            <div className="mt-8 p-6 bg-[#0F0F13] rounded-lg border border-[#E4FF00]">
              <h3 className="font-bold text-[#E4FF00] mb-4">Résumé de votre application</h3>
              <ul className="space-y-2 text-sm">
                <li><span className="text-[#A1A1AA]">Nom:</span> {config.appName}</li>
                <li><span className="text-[#A1A1AA]">Type:</span> {APP_TYPES.find(t => t.id === config.appType)?.label}</li>
                <li><span className="text-[#A1A1AA]">Couleurs:</span> {COLOR_PALETTES.find(p => p.id === config.colorPalette)?.name}</li>
                <li><span className="text-[#A1A1AA]">Plateforme:</span> {PLATFORMS.find(p => p.id === config.platform)?.label}</li>
                <li><span className="text-[#A1A1AA]">Auth:</span> {config.hasAuth ? 'Oui' : 'Non'}</li>
                <li><span className="text-[#A1A1AA]">Base de données:</span> {config.hasDatabase ? 'Oui' : 'Non'}</li>
              </ul>
            </div>
          </div>
        );

      case 6:
        return (
          <div className="text-center space-y-8 max-w-xl mx-auto">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="w-24 h-24 bg-[#00FF66] rounded-full flex items-center justify-center mx-auto"
            >
              <CheckCircle className="w-12 h-12 text-[#050505]" />
            </motion.div>
            
            <div>
              <h2 className="text-3xl font-['Chivo'] font-bold mb-2">Application Générée !</h2>
              <p className="text-[#A1A1AA]">"{config.appName}" est prête à être exportée</p>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <Button
                onClick={() => window.open(`${API}/export/mobile/${generatedProject?.project?.id}`, '_blank')}
                className="bg-[#E4FF00] text-[#050505] py-6"
                disabled={!generatedProject?.project?.id}
              >
                <Smartphone className="w-5 h-5 mr-2" />
                APK
              </Button>
              <Button
                onClick={() => window.open(`${API}/export/desktop/${generatedProject?.project?.id}`, '_blank')}
                className="bg-[#E4FF00] text-[#050505] py-6"
                disabled={!generatedProject?.project?.id}
              >
                <Monitor className="w-5 h-5 mr-2" />
                EXE
              </Button>
              <Button
                onClick={() => window.open(`${API}/preview/project/${generatedProject?.project?.id}`, '_blank')}
                className="bg-[#00FF66] text-[#050505] py-6"
                disabled={!generatedProject?.project?.id}
              >
                <Globe className="w-5 h-5 mr-2" />
                Web
              </Button>
            </div>

            <Button
              onClick={() => navigate('/dashboard')}
              variant="outline"
              className="border-white/20"
            >
              Retour au Dashboard
            </Button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white">
      {/* Header */}
      <header className="bg-[#0F0F13] border-b border-white/10 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button onClick={() => navigate('/dashboard')} variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Retour
            </Button>
            <div className="flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-[#E4FF00]" />
              <h1 className="font-['Chivo'] font-bold text-xl">Assistant de Création</h1>
            </div>
          </div>
          
          {/* Progress */}
          {step <= totalSteps && (
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map(s => (
                <div
                  key={s}
                  className={`w-3 h-3 rounded-full transition-all ${
                    s === step ? 'bg-[#E4FF00] w-8' : s < step ? 'bg-[#00FF66]' : 'bg-white/20'
                  }`}
                />
              ))}
              <span className="ml-2 text-sm text-[#A1A1AA]">Étape {step}/{totalSteps}</span>
            </div>
          )}
        </div>
      </header>

      {/* Content */}
      <div className="max-w-5xl mx-auto p-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="py-8"
          >
            {renderStep()}
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        {step <= totalSteps && (
          <div className="flex justify-between mt-8 pt-8 border-t border-white/10">
            <Button
              onClick={() => setStep(s => Math.max(1, s - 1))}
              variant="outline"
              disabled={step === 1}
              className="border-white/20"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Précédent
            </Button>

            {step < totalSteps ? (
              <Button
                onClick={() => setStep(s => s + 1)}
                disabled={!canProceed()}
                className="bg-[#E4FF00] text-[#050505]"
              >
                Suivant
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={generateApplication}
                disabled={isGenerating || !canProceed()}
                className="bg-[#00FF66] text-[#050505] px-8"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Génération...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5 mr-2" />
                    Générer l'Application
                  </>
                )}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
