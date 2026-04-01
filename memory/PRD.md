# CodeForge AI - Product Requirements Document (FINAL)

## Version Finale - 21 Mars 2026

---

## Description du Projet
**CodeForge AI** est une plateforme de génération d'applications complètes via IA, permettant de créer des apps mobile, web et desktop sans aucune compétence en code.

### Principes Fondamentaux
- **100% Gratuit et Sans Limites** - Aucun crédit, abonnement ou restriction
- **Mode Hors Ligne** - IA locale (Ollama/DeepSeek) fonctionnelle sans internet
- **Multi-plateforme** - Export APK, EXE et Web
- **Bilingue** - Interface Français/Anglais

---

## Fonctionnalités Implémentées

### 1. Authentification Hybride ✅
- **Google OAuth** - Connexion rapide en ligne
- **SMS (Mode Démo)** - Authentification hors ligne
  - Code Twilio préparé (ajouter `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` pour activer)

### 2. Dashboard Principal ✅
- **4 boutons centraux** : Chat/Création en ligne et hors ligne
- **Bouton Assistant Guidé** - Création étape par étape
- **Sélecteur de langue** FR/EN
- **Indicateur de connexion** En ligne/Hors ligne
- **Boutons d'export** APK, EXE, ZIP

### 3. Assistant Guidé (Wizard) ✅
Interface en 5 étapes pour créer une application :
1. **Type d'application** - 12 modèles (E-Commerce, Blog, Social, Chat, Portfolio, Dashboard, Réservation, Média, Maps, Utilitaire, Musique, Personnalisé)
2. **Nom de l'application**
3. **Palette de couleurs** - 6 thèmes prédéfinis
4. **Plateforme cible** - Web, Mobile, Desktop, Toutes
5. **Options avancées** - Auth, Base de données, Langue

### 4. Génération IA ✅
- **Prompts DeepSeek optimisés** pour code complet et fonctionnel
- **Structure de fichiers complète** (HTML, CSS, JS, manifest.json, README)
- **Design moderne** avec palette Cyber Yellow par défaut

### 5. Prévisualisation ✅
- **Boutons toujours visibles** : Web, App, PDF, DOCX
- **Pages de démo** pour chaque format
- **Prévisualisation projet** après génération

### 6. Export Multi-plateforme ✅
- **APK** - Page d'installation Android avec instructions
- **EXE** - Package Electron avec instructions
- **ZIP** - Code source complet

### 7. Mode Hors Ligne ✅
- **Cache local** (localStorage) pour projets et préférences
- **IA locale** via Ollama (DeepSeek Coder)
- **Queue offline** pour actions en attente

### 8. Multilingue ✅
- **Français** - Langue par défaut
- **English** - Traduction complète
- **Sélecteur** dans le dashboard

---

## Architecture Technique

```
/app/
├── backend/
│   ├── server.py              # API FastAPI complète
│   ├── .env                   # Configuration (MONGO_URL, TWILIO_*, etc.)
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.js             # Routes et providers
│   │   ├── contexts/
│   │   │   ├── AuthContext.js      # Authentification
│   │   │   ├── LanguageContext.js  # Multilingue FR/EN
│   │   │   └── CacheContext.js     # Cache local offline
│   │   ├── pages/
│   │   │   ├── Landing.js          # Page d'accueil
│   │   │   ├── Login.js            # Connexion Google + SMS
│   │   │   ├── SMSLogin.js         # Connexion SMS dédiée
│   │   │   ├── Dashboard.js        # Dashboard principal
│   │   │   ├── Create.js           # Création libre
│   │   │   ├── Chat.js             # Chat IA
│   │   │   └── GuidedWizard.js     # Assistant guidé 5 étapes
│   │   └── components/ui/          # Shadcn UI
│   └── .env
│
└── memory/
    └── PRD.md                 # Ce document
```

---

## API Endpoints

### Authentification
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/auth/session` | POST | Session Google OAuth |
| `/api/auth/sms/send` | POST | Envoyer code SMS |
| `/api/auth/sms/verify` | POST | Vérifier code SMS |
| `/api/auth/me` | GET | Utilisateur courant |
| `/api/auth/logout` | POST | Déconnexion |

### Génération IA
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/ai/generate-complete-app` | POST | Générer application complète |
| `/api/ai/generate-code` | POST | Générer code spécifique |
| `/api/chat/message` | POST | Chat avec IA |

### Prévisualisation
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/preview/demo/{type}` | GET | Démo (web, pdf, docx, app, image) |
| `/api/preview/project/{id}` | GET | Prévisualisation projet |
| `/api/preview/{id}` | GET | Prévisualisation par ID |

### Export
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/export/mobile/{id}` | GET | Page installation APK |
| `/api/export/desktop/{id}` | GET | Page téléchargement EXE |
| `/api/export/download` | POST | Télécharger ZIP |

### Projets
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/projects` | GET/POST | Liste/Créer projets |
| `/api/projects/{id}` | GET/PUT/DELETE | CRUD projet |

---

## Configuration Requise

### Variables d'environnement Backend
```env
MONGO_URL=mongodb://...
DB_NAME=codeforge
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-coder:6.7b

# Optionnel - Twilio pour SMS réels
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890
```

### Variables d'environnement Frontend
```env
REACT_APP_BACKEND_URL=https://your-domain.com
```

---

## Tests Effectués

### Iteration 4 - Tous les tests passés ✅
- Backend: 100% (APIs health, preview, SMS, auth)
- Frontend: 100% (Login, Dashboard, Wizard, Create, Chat)

### Fichiers de test
- `/app/backend/tests/test_codeforge_api.py`
- `/app/backend/tests/test_codeforge_v4.py`
- `/app/test_reports/iteration_3.json`
- `/app/test_reports/iteration_4.json`

---

## Notes Importantes

### SMS en Mode Démo
Le code de vérification SMS est retourné dans la réponse API pour les tests. Pour activer l'envoi réel :
1. Créer un compte Twilio
2. Ajouter les variables d'environnement TWILIO_*
3. Le système basculera automatiquement sur Twilio

### Ollama pour Mode Hors Ligne
Pour utiliser l'IA en mode hors ligne :
1. Installer Ollama : `https://ollama.com`
2. Télécharger le modèle : `ollama pull deepseek-coder:6.7b`
3. Lancer Ollama : `ollama serve`

### Export APK/EXE
Les exports génèrent des packages ZIP avec :
- Code source complet
- Instructions de build (Capacitor pour APK, Electron pour EXE)
- manifest.json pour PWA

---

## Statut Final

| Composant | Statut |
|-----------|--------|
| Dashboard avec 4 boutons | ✅ Complet |
| Assistant Guidé (Wizard) | ✅ Complet |
| Authentification Google | ✅ Complet |
| Authentification SMS | ✅ Complet (Mode Démo) |
| Prévisualisation multi-format | ✅ Complet |
| Export APK/EXE/ZIP | ✅ Complet |
| Mode Hors Ligne | ✅ Complet |
| Support Multilingue FR/EN | ✅ Complet |
| Cache Local | ✅ Complet |
| Twilio SMS | ⚠️ Prêt (nécessite clés API) |

---

**Projet terminé et fonctionnel !** 🎉
