# CodeForge AI - Product Requirements Document

## Original Problem Statement
L'utilisateur souhaite créer "CodeForge AI", une plateforme logicielle et mobile permettant de générer des applications complètes via des descriptions textuelles, sans aucune compétence en code.

### Exigences critiques:
- **100% gratuit et sans limites** : Aucun crédit, aucun abonnement, aucune limite d'utilisation
- **Fonctionnement hors ligne/en ligne** : IA locale performante (DeepSeek Coder) en mode hors ligne, IA puissante en ligne
- **Authentification hybride** : Connexion Google (en ligne) et par SMS (hors ligne)
- **Exports multiplateformes** : Boutons pour exporter les applications générées en Mobile (APK), Bureau (EXE) et Web
- **Interface simplifiée** : Thème sombre "Cyber Yellow", 4 boutons centraux (Interaction/Création en ligne/hors ligne)
- **Prévisualisation** : Boutons pour prévisualiser les générations (PDF, DOCX, Web, App)

## User Personas
1. **Développeur débutant** - Veut créer des apps sans coder
2. **Entrepreneur** - Veut prototyper rapidement des idées
3. **Utilisateur hors ligne** - Veut utiliser l'IA sans connexion internet

## Core Requirements
- [x] Interface Dashboard avec 4 boutons centraux
- [x] Thème sombre "Cyber Yellow"
- [x] Authentification Google (en ligne)
- [x] Authentification SMS (hors ligne) - MOCKED
- [x] Génération de code via IA (Ollama/DeepSeek)
- [x] Boutons de Prévisualisation (Web, PDF, DOCX, App)
- [x] Export Mobile (APK) - Page d'installation
- [x] Export Desktop (EXE) - Page de téléchargement
- [x] Export Web (ZIP)

## Technical Stack
- **Frontend**: React, TailwindCSS, Shadcn UI, Framer Motion
- **Backend**: FastAPI, MongoDB
- **IA**: Ollama (DeepSeek Coder 6.7B) pour mode hors ligne
- **Auth**: Google OAuth (Emergent), SMS (custom)

## Architecture
```
/app/
├── backend/
│   ├── server.py          # API endpoints
│   └── .env               # Configuration
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Landing.js
│   │   │   ├── Login.js
│   │   │   ├── SMSLogin.js
│   │   │   ├── Dashboard.js
│   │   │   ├── Create.js
│   │   │   └── Chat.js
│   │   ├── contexts/
│   │   │   └── AuthContext.js
│   │   └── components/ui/
│   └── .env
└── memory/
    └── PRD.md
```

## API Endpoints
- `POST /api/auth/session` - Google OAuth session
- `POST /api/auth/sms/send` - Envoyer code SMS
- `POST /api/auth/sms/verify` - Vérifier code SMS
- `GET /api/auth/me` - Utilisateur courant
- `POST /api/ai/generate-complete-app` - Générer application
- `POST /api/chat/message` - Chat avec IA
- `GET /api/preview/demo/{type}` - Prévisualisations démo (web, pdf, docx, app)
- `GET /api/preview/project/{id}` - Prévisualisation projet
- `GET /api/export/mobile/{id}` - Export APK
- `GET /api/export/desktop/{id}` - Export EXE

## Completed Work (March 21, 2026)

### Session 1
- [x] Initialisation du projet
- [x] Interface Dashboard avec 4 boutons centraux
- [x] Thème sombre "Cyber Yellow"
- [x] Authentification Google intégrée
- [x] Installation Ollama + DeepSeek Coder 6.7B
- [x] Génération de code via IA locale
- [x] Export APK/EXE/ZIP (pages et ZIP)

### Session 2 (Actuelle)
- [x] **Boutons de Prévisualisation** - Web, PDF, DOCX, App sur pages Create et Chat
- [x] **Endpoints de prévisualisation démo** - /api/preview/demo/{type}
- [x] **Authentification SMS** - Pages et API fonctionnelles (MOCKED)
- [x] **Page SMSLogin.js** - Interface complète
- [x] **Suppression CodeEditor.js** - Non utilisé
- [x] **Tests complets** - 100% backend et frontend passés

## Backlog

### P0 (Critical)
- [x] ~~Boutons de prévisualisation~~ DONE
- [x] ~~Auth SMS hors ligne~~ DONE (MOCKED)

### P1 (High)
- [ ] Intégration réelle Twilio pour SMS (actuellement mockée)
- [ ] Build APK réel via Capacitor
- [ ] Build EXE réel via Electron

### P2 (Medium)
- [ ] Améliorer prompts DeepSeek pour meilleure génération
- [ ] Cache local pour mode hors ligne complet
- [ ] Support multi-langue (EN, ES, etc.)

## Known Limitations
- **SMS MOCKED**: Le code est retourné dans la réponse API au lieu d'un vrai SMS
- **APK/EXE**: Téléchargent des ZIP avec instructions, pas de vrais builds
- **Ollama**: Nécessite installation locale pour mode hors ligne

## Test Coverage
- Backend: 16/16 tests passés (100%)
- Frontend: Tous composants validés
- Test Report: `/app/test_reports/iteration_3.json`
