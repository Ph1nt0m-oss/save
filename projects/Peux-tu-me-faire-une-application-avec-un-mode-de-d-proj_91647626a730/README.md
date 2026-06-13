# CoachFit Pro - Application de Coaching Sportif

## 🎯 Description

CoachFit Pro est une application web progressive (PWA) de coaching sportif personnel avec deux modes principaux :

1. **Mode Défis Quotidiens** : Un programme d'exercices généré automatiquement chaque jour
2. **Mode Coach en Direct** : Correction et feedback en temps réel pendant vos exercices

## ✨ Fonctionnalités

### Défis Quotidiens
- Génération automatique d'un défi personnalisé chaque jour
- 3-4 exercices variés avec nombre de répétitions et séries
- Suivi de progression en temps réel
- Système de points pour motiver
- Validation des exercices complétés

### Coach en Direct
- 8 exercices disponibles (Pompes, Squats, Planche, Burpees, etc.)
- Compteur de répétitions interactif
- Feedback en temps réel avec conseils de forme
- Chronomètre intégré
- Système de séries (3 séries par défaut)
- Conseils techniques affichables pendant l'exercice

### Statistiques & Historique
- Suivi de votre série de jours consécutifs
- Nombre total de sessions effectuées
- Total de répétitions accomplies
- Historique détaillé de toutes vos sessions
- Score de performance pour chaque session

### Fonctionnalités Techniques
- **PWA** : Installable sur mobile et bureau
- **Mode Offline** : Fonctionne sans connexion internet
- **LocalStorage** : Sauvegarde automatique de toutes vos données
- **Responsive** : Design adaptatif mobile-first
- **Animations fluides** : Interface moderne et réactive

## 🚀 Installation

### Méthode 1 : Utilisation directe
1. Téléchargez tous les fichiers dans un même dossier
2. Ouvrez `index.html` dans votre navigateur
3. L'application fonctionne immédiatement !

### Méthode 2 : Installation comme PWA
1. Ouvrez l'application dans Chrome/Edge/Safari
2. Cliquez sur l'icône d'installation dans la barre d'adresse
3. Ou Menu → "Installer CoachFit Pro"
4. L'application s'installe sur votre écran d'accueil

### Méthode 3 : Serveur local (optionnel)
```bash
# Avec Python 3
python -m http.server 8000

# Avec Node.js
npx serve

# Accédez ensuite à http://localhost:8000
```

## 📱 Utilisation

### Démarrer un Défi Quotidien
1. Sur l'écran d'accueil, cliquez sur "🎯 Défi Quotidien"
2. Consultez la liste des exercices du jour
3. Effectuez chaque exercice selon les répétitions et séries indiquées
4. Cliquez sur "Marquer comme terminé" après chaque exercice
5. Complétez tous les exercices pour gagner vos points !

### Utiliser le Coach en Direct
1. Cliquez sur "🤖 Coach en Direct"
2. Sélectionnez l'exercice que vous voulez faire
3. Cliquez sur "💡 Voir les conseils" pour afficher les consignes de forme
4. Appuyez sur "✓ Répétition" à chaque répétition effectuée
5. Le coach vous donne du feedback en temps réel
6. Complétez les 3 séries de 20 répétitions

### Consulter l'Historique
1. Cliquez sur "📊 Historique des sessions"
2. Visualisez toutes vos sessions passées
3. Consultez vos performances et durées

## 🎨 Design

L'application utilise un design moderne type "cyber" avec :
- Fond noir profond (#050505)
- Jaune fluo (#E4FF00) pour les éléments principaux
- Vert néon (#00FF66) pour les succès
- Cyan (#00D4FF) pour le mode coach
- Effets de glow et animations fluides

## 💾 Stockage des Données

Toutes vos données sont stockées localement dans votre navigateur :
- Statistiques (série, sessions, répétitions)
- Historique des sessions
- Défi quotidien actuel
- Date de dernière activité

Les données persistent même après fermeture du navigateur.

## 🔧 Structure des Fichiers

```
coachfit-pro/
├── index.html          # Point d'entrée de l'application
├── App.jsx             # Composant React principal (logique complète)
├── styles.css          # Styles et animations personnalisées
├── manifest.json       # Configuration PWA
├── sw.js              # Service Worker pour mode offline
└── README.md          # Cette documentation
```

## 📊 Exercices Disponibles

| Exercice | Difficulté | Muscles ciblés |
|----------|-----------|----------------|
| Pompes | Facile | Pectoraux, Triceps |
| Squats | Facile | Quadriceps, Fessiers |
| Planche | Moyen | Abdominaux, Dos |
| Burpees | Difficile | Corps entier |
| Fentes | Moyen | Jambes, Fessiers |
| Mountain Climbers | Moyen | Cardio, Abdos |
| Dips | Moyen | Triceps, Épaules |
| Jumping Jacks | Facile | Cardio |

## 🛠️ Technologies Utilisées

- **React 18** : Framework JavaScript
- **TailwindCSS** : Framework CSS utility-first
- **LocalStorage API** : Persistance des données
- **Service Worker** : Mode offline
- **PWA** : Progressive Web App

## 🔒 Sécurité & Vie Privée

- ✅ Aucune donnée envoyée à un serveur
- ✅ Toutes les données restent sur votre appareil
- ✅ Pas de tracking, pas de cookies
- ✅ Pas de connexion internet requise après installation
- ✅ Code source ouvert et auditable

## 🐛 Dépannage

### L'application ne s'affiche pas correctement
- Videz le cache du navigateur (Ctrl+Shift+Delete)
- Vérifiez que JavaScript est activé
- Utilisez un navigateur moderne (Chrome, Firefox, Safari, Edge)

### Les données ont disparu
- Vérifiez que vous n'avez pas vidé le LocalStorage
- Ne naviguez pas en mode incognito (les données ne persistent pas)

### Le Service Worker ne fonctionne pas
- Servez l'application via HTTPS ou localhost
- Les Service Workers nécessitent un contexte sécurisé

## 📈 Améliorations Futures Possibles

- Ajout de nouveaux exercices
- Programmes d'entraînement sur plusieurs semaines
- Export des données en CSV
- Graphiques de progression
- Minuteur de repos entre séries
- Sons de motivation
- Partage de performances sur réseaux sociaux

## 📄 Licence

Ce projet est libre d'utilisation pour usage personnel et éducatif.

## 🤝 Contribution

N'hésitez pas à suggérer des améliorations ou signaler des bugs !

---

**Version:** 1.0.0  
**Dernière mise à jour:** 2024  
**Compatibilité:** Chrome 90+, Firefox 88+, Safari 14+, Edge 90+