# 💃 DanceFlow - Coach de Danse Personnel

Application web progressive (PWA) de coaching de danse avec défis quotidiens et corrections en temps réel.

## ✨ Fonctionnalités

### 🎯 Défis Quotidiens
- Un nouveau défi chaque jour adapté à votre niveau
- Progression automatique et suivi de vos performances
- Système de points et récompenses
- Série de jours consécutifs (streak)

### 👨‍🏫 Coaching en Direct
- Instructions étape par étape avec timer
- Corrections automatiques pendant l'exercice
- Navigation libre entre les étapes
- Pause et reprise de la session

### 💎 Styles de Danse Inclus
- **Hip-Hop** 🎤 - Isolations, groove, style urbain
- **Salsa** 💃 - Pas de base, mouvements de hanches
- **Breakdance** 🕺 - Freezes, power moves, footwork
- **Contemporain** 🩰 - Expression corporelle, fluidité

### 📊 Suivi de Progression
- Statistiques personnelles (streak, sessions, défis complétés)
- Historique des performances
- Système de points cumulatifs
- Badges et accomplissements

## 🚀 Installation

### Utilisation Simple
1. Téléchargez tous les fichiers dans un même dossier
2. Ouvrez `index.html` dans votre navigateur
3. L'application fonctionne immédiatement !

### Installation PWA (Mobile/Desktop)
1. Ouvrez l'application dans Chrome/Safari/Edge
2. Cliquez sur "Installer" ou "Ajouter à l'écran d'accueil"
3. L'application fonctionne maintenant comme une app native
4. Mode hors-ligne automatique après la première visite

## 📱 Compatibilité

- ✅ Chrome/Edge (Desktop & Mobile)
- ✅ Safari (iOS & macOS)
- ✅ Firefox (Desktop & Mobile)
- ✅ Samsung Internet
- ✅ Mode hors-ligne complet
- ✅ Installation PWA sur tous supports

## 🎮 Comment Utiliser

### Démarrer un Défi
1. Sur l'écran d'accueil, consultez le **Défi du jour**
2. Cliquez sur le défi pour voir les détails
3. Lisez les étapes et conseils du coach
4. Appuyez sur **"Démarrer le coaching en direct"**

### Mode Coaching
- Suivez les instructions affichées
- Respectez le timer (15 secondes par étape)
- Lisez les corrections automatiques du coach
- Naviguez avec **Précédent/Suivant** si besoin
- Terminez pour gagner vos points !

### Parcourir les Défis
- Section **"Tous les défis"** pour voir les exercices disponibles
- Filtrez par style de danse
- Les défis complétés sont marqués ✓
- Répétez les défis autant que vous voulez

## 🏗️ Structure Technique

### Architecture
```
danceflow/
├── index.html          # Point d'entrée, CDN React
├── App.jsx            # Application React complète
├── styles.css         # Animations et styles custom
├── manifest.json      # Configuration PWA
├── sw.js             # Service Worker (cache offline)
└── README.md         # Documentation
```

### Stack Technologique
- **React 18** - Framework UI (via CDN)
- **TailwindCSS** - Styling responsive (via CDN)
- **LocalStorage** - Persistance des données
- **Service Worker** - Mode hors-ligne
- **PWA** - Installation native

### Données Stockées Localement
- Défis complétés
- Points totaux
- Série de jours (streak)
- Nombre de sessions
- Historique de progression

## 🎨 Design System

### Palette de Couleurs
- **Background**: `#050505` (noir profond)
- **Cards**: `#0F0F13` (gris foncé)
- **Primary**: `#E4FF00` (jaune cyber)
- **Secondary**: `#00FF66` (vert néon)
- **Accent**: `#00D4FF` (cyan)
- **Text**: `#FFFFFF` / `#A1A1AA`

### Animations
- Fade-in progressif au chargement
- Slide-up pour les cartes
- Pulse sur les boutons d'action
- Transitions fluides (0.2s ease)

## ⚡ Performances

- ✅ Chargement instantané (fichier unique)
- ✅ 0 dépendances externes (tout en CDN)
- ✅ Cache intelligent (offline-first)
- ✅ Animations optimisées GPU
- ✅ Images SVG légères
- ✅ LocalStorage pour persistance rapide

## 🔒 Sécurité

- Pas d'évaluation de code dynamique
- Données stockées localement uniquement
- Pas de collecte de données personnelles
- HTTPS recommandé pour PWA complète

## 🐛 Dépannage

### L'application ne se charge pas
- Vérifiez votre connexion internet (pour les CDN)
- Essayez de vider le cache du navigateur
- Assurez-vous que JavaScript est activé

### Les données ne se sauvent pas
- Vérifiez que LocalStorage est autorisé
- Ne pas utiliser le mode navigation privée
- Vérifiez l'espace de stockage disponible

### Le mode hors-ligne ne fonctionne pas
- Visitez l'app une première fois en ligne
- Attendez que le Service Worker s'installe
- Rechargez la page une fois

## 🔮 Évolutions Futures

- [ ] Vidéos de démonstration intégrées
- [ ] Détection de mouvement via webcam
- [ ] Partage de progression sur réseaux sociaux
- [ ] Mode multijoueur avec défis entre amis
- [ ] Playlist musicale synchronisée
- [ ] Programmes d'entraînement personnalisés
- [ ] Statistiques avancées avec graphiques

## 📄 Licence

Ce projet est libre d'utilisation pour un usage personnel et éducatif.

## 🤝 Contribution

Pour améliorer l'application :
1. Ajoutez de nouveaux défis dans `DAILY_CHALLENGES`
2. Créez de nouveaux styles de danse dans `DANCE_STYLES`
3. Personnalisez les couleurs dans le design system
4. Ajoutez vos propres animations CSS

---

**Développé avec ❤️ pour les passionnés de danse**

Profitez de vos sessions et dansez avec style ! 💃🕺