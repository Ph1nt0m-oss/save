# 🚀 CodeForge AI - Plateforme de Création Sans Limites

**Créez des applications complètes sans écrire de code !**

<div align="center">

![CodeForge AI](https://img.shields.io/badge/CodeForge-AI-E4FF00?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production-00FF66?style=for-the-badge)
![Gratuit](https://img.shields.io/badge/100%25-Gratuit-E4FF00?style=for-the-badge)

</div>

---

## ✨ Fonctionnalités

### 🎯 Création Intelligente
- **Mode Chat (GPT)** : Discutez avec l'IA pour des questions simples
- **Mode Création (Emergent)** : Interface de codage complète pour créer des applications
- **Génération automatique** : Décrivez votre idée, l'IA génère tout le code

### 📱 Export Mobile (APK)
- **App Store Privé** : Page d'installation style Play Store
- **Installation directe** : Téléchargez et installez sur Android
- **PWA Support** : Fonctionne aussi comme Progressive Web App

### 💻 Export Desktop (EXE)
- **Application Windows** : Créez des logiciels installables
- **Package complet** : Electron + instructions de build
- **Multi-plateforme** : Windows, macOS, Linux

### 🌐 Déploiement Web
- **Guide complet** : Instructions pour Vercel, Netlify, etc.
- **Gratuit à 100%** : Hébergement permanent sans frais
- **HTTPS automatique** : Sécurisé par défaut

### 🔋 Mode Hors Ligne
- **Service Worker** : Fonctionne sans connexion
- **Cache intelligent** : Toutes les ressources en local
- **Synchronisation** : Mise à jour automatique quand en ligne

---

## 🎨 Design

**Thème Cyber Yellow**
- Couleur principale: `#E4FF00` (Cyber Yellow)
- Couleur secondaire: `#00FF66` (Neon Green)
- Background: `#050505` (Void Black)
- Police: Chivo (headings) + IBM Plex Sans (body)

---

## 🚀 Démarrage Rapide

### 1. Accéder à l'Application

**URL actuelle:** https://deepseek-forge.preview.emergentagent.com

> ⚠️ **Important**: Cette URL est temporaire. Suivez le [Guide de Déploiement](/DEPLOYMENT_GUIDE.md) pour un hébergement permanent.

### 2. Se Connecter

1. Cliquez sur **"Connexion"**
2. Connectez-vous avec **Google**
3. Accédez au **Dashboard**

### 3. Créer un Projet

1. Cliquez sur **"+ Nouveau Projet"**
2. Choisissez le type : **Web**, **Mobile**, ou **Desktop**
3. Décrivez votre application

### 4. Générer le Code

**Option A: Mode Chat**
- Posez des questions
- Obtenez des réponses et conseils

**Option B: Mode Création**
- Cliquez sur **"Mode Création"** (bouton vert)
- Ouvre Emergent pour un développement complet
- Créez l'application de A à Z

### 5. Exporter

**📱 Mobile (APK)**
- Cliquez sur l'icône 📱
- Page d'installation s'ouvre
- Téléchargez et installez sur Android

**💻 Desktop (EXE)**
- Cliquez sur l'icône 💻  
- Page de téléchargement s'ouvre
- Installez sur Windows

**📦 Code Source (ZIP)**
- Cliquez sur l'icône 📥
- Téléchargez le ZIP complet
- Modifiez et déployez où vous voulez

---

## 📂 Structure du Projet

```
/app/
├── backend/                 # API FastAPI
│   ├── server.py           # Serveur principal
│   ├── requirements.txt    # Dépendances Python
│   └── .env               # Variables d'environnement
│
├── frontend/               # Application React
│   ├── src/
│   │   ├── pages/         # Pages de l'app
│   │   │   ├── Landing.js
│   │   │   ├── Login.js
│   │   │   ├── Dashboard.js
│   │   │   └── AuthCallback.js
│   │   ├── contexts/      # React Context
│   │   └── components/    # Composants UI
│   ├── package.json
│   └── .env
│
├── DEPLOYMENT_GUIDE.md     # Guide de déploiement complet
└── README_CODEFORGE.md    # Ce fichier
```

---

## 🌐 Déploiement Production

**Lisez le guide complet:** [`DEPLOYMENT_GUIDE.md`](/DEPLOYMENT_GUIDE.md)

### Méthode Rapide (Vercel + Railway)

**Frontend (Vercel)**
```bash
cd frontend
vercel --prod
```

**Backend (Railway)**
```bash
cd backend
railway login
railway up
```

**Base de données (MongoDB Atlas)**
- Gratuit : 512MB
- https://www.mongodb.com/cloud/atlas

### Coût Total: **0€ / mois** 🎉

---

## 📱 Installer sur Mobile

### Méthode 1: PWA (La plus simple)

1. Ouvrir le site sur Chrome Android
2. Menu → **"Ajouter à l'écran d'accueil"**
3. ✅ Application installée !

### Méthode 2: APK

1. Créer un projet dans CodeForge
2. Générer le code
3. Cliquer sur 📱 **Export Mobile**
4. Télécharger et installer l'APK

### Méthode 3: PWA Builder

1. Aller sur https://www.pwabuilder.com/
2. Entrer l'URL de votre site
3. Générer le package Android
4. Installer l'APK

---

## 💻 Installer sur Desktop

### Méthode 1: PWA Desktop

1. Ouvrir le site sur Chrome/Edge
2. Icône d'installation dans la barre d'adresse
3. Cliquer pour installer
4. ✅ Application sur le bureau !

### Méthode 2: Electron

1. Créer un projet dans CodeForge
2. Générer le code
3. Cliquer sur 💻 **Export Desktop**
4. Suivre les instructions de build

---

## 🆓 Pourquoi "Sans Limites" ?

### Aucune restriction de :
- ❌ **Crédits** : Pas de système de crédits
- ❌ **Utilisation** : Générez autant d'apps que vous voulez
- ❌ **Politique** : Pas de censure excessive
- ❌ **Coûts** : 100% gratuit avec hébergement gratuit

### Accès complet à :
- ✅ **Mode Chat** (GPT) pour discuter
- ✅ **Mode Création** (Emergent) pour coder
- ✅ **Exports** illimités (APK, EXE, ZIP)
- ✅ **Déploiement** gratuit permanent

---

## 📞 Support

### Documentation
- Guide de déploiement : [`DEPLOYMENT_GUIDE.md`](/DEPLOYMENT_GUIDE.md)
- Tests d'authentification : [`auth_testing.md`](/auth_testing.md)

### Problèmes Communs

**Le chat ne répond pas**
- Mode Chat utilise des réponses simulées (pas de coût API)
- Utilisez **Mode Création** pour un développement complet

**Export ne fonctionne pas**
- Assurez-vous d'avoir généré le code d'abord
- Vérifiez que le projet a du contenu

**Authentification échoue**
- Vérifiez les cookies (doivent être autorisés)
- Essayez en navigation privée

---

<div align="center">

**🚀 CodeForge AI - Création Sans Limites 🚀**

*Développé sur [Emergent AI](https://emergent.sh)*

![Made with Emergent](https://img.shields.io/badge/Made%20with-Emergent%20AI-E4FF00?style=for-the-badge)

</div>
