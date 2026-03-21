# 🚀 Guide de Déploiement CodeForge AI

Ce guide vous explique comment déployer **CodeForge AI** de manière permanente, accessible au public et gratuite.

## 📋 Table des Matières

1. [Déploiement Web (Gratuit)](#déploiement-web)
2. [Application Mobile (APK)](#application-mobile)
3. [Application Desktop (EXE)](#application-desktop)
4. [Mode Hors Ligne](#mode-hors-ligne)

---

## 🌐 Déploiement Web

### Option 1: Vercel (Recommandé) ✨

**Gratuit, rapide, HTTPS automatique**

```bash
# 1. Installer Vercel CLI
npm install -g vercel

# 2. Se connecter
vercel login

# 3. Déployer le frontend
cd /app/frontend
vercel

# 4. Déployer le backend
cd /app/backend
vercel

# 5. Configurer les variables d'environnement dans Vercel Dashboard
# - MONGO_URL (MongoDB Atlas gratuit: https://www.mongodb.com/cloud/atlas)
# - EMERGENT_LLM_KEY
# - CORS_ORIGINS
```

### Option 2: Netlify

```bash
# 1. Installer Netlify CLI
npm install -g netlify-cli

# 2. Build le frontend
cd /app/frontend
npm run build

# 3. Déployer
netlify deploy --prod --dir=build
```

### Option 3: Hébergement Gratuit

**Frontend:**
- [Vercel](https://vercel.com) - Illimité, HTTPS auto
- [Netlify](https://netlify.com) - 100GB/mois
- [GitHub Pages](https://pages.github.com) - Gratuit
- [Cloudflare Pages](https://pages.cloudflare.com) - Illimité

**Backend:**
- [Railway](https://railway.app) - 5$/mois gratuit
- [Render](https://render.com) - Gratuit (sleep après inactivité)
- [Fly.io](https://fly.io) - 5$/mois gratuit
- [Heroku](https://heroku.com) - Gratuit avec limitations

**Base de Données:**
- [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) - 512MB gratuit
- [Supabase](https://supabase.com) - 500MB gratuit

---

## 📱 Application Mobile (APK)

### Méthode 1: PWA (Progressive Web App) - Le Plus Simple

**Aucun code nécessaire, installation directe !**

1. **Ajouter un manifest.json** (déjà généré)
2. **Ajouter un service worker** pour le mode offline
3. **Héberger sur HTTPS** (Vercel/Netlify le font auto)
4. **Installer sur Android:**
   - Ouvrir Chrome sur Android
   - Aller sur votre site
   - Menu → "Ajouter à l'écran d'accueil"
   - ✅ L'app est installée !

### Méthode 2: Capacitor (APK Natif)

```bash
# 1. Installer Capacitor
npm install -g @capacitor/cli
cd /app/frontend

# 2. Initialiser
npx cap init

# 3. Ajouter Android
npx cap add android

# 4. Build
npm run build
npx cap copy
npx cap open android

# 5. Dans Android Studio:
# Build → Generate Signed Bundle / APK
```

### Méthode 3: PWA Builder (Sans Code)

1. Aller sur [https://www.pwabuilder.com/](https://www.pwabuilder.com/)
2. Entrer l'URL de votre site
3. Cliquer "Package For Stores"
4. Télécharger le package Android
5. ✅ APK prêt !

### Méthode 4: AppGyver / Thunkable

Outils no-code pour convertir web → mobile gratuitement.

---

## 💻 Application Desktop (EXE)

### Méthode 1: Electron (Recommandé)

```bash
# 1. Créer dossier Electron
mkdir electron-app && cd electron-app

# 2. Initialiser
npm init -y
npm install electron electron-builder

# 3. Créer main.js (voir /app/backend/server.py pour le code)

# 4. Build
npm run build

# ✅ L'exe sera dans dist/
```

### Méthode 2: Tauri (Plus Léger)

```bash
# Tauri crée des .exe de 3-5MB (vs 150MB pour Electron)
npm create tauri-app
cd tauri-app
npm install
npm run tauri build
```

### Méthode 3: PWA Desktop

Les PWA peuvent aussi s'installer sur Windows/Mac/Linux:
- Chrome: Menu → Installer CodeForge AI
- Edge: Même chose
- ✅ Icône sur le bureau !

---

## 🔌 Mode Hors Ligne

### Service Worker (PWA)

Créer `/app/frontend/public/service-worker.js`:

```javascript
const CACHE_NAME = 'codeforge-v1';
const urlsToCache = [
  '/',
  '/static/css/main.css',
  '/static/js/main.js',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
```

Enregistrer dans `/app/frontend/src/index.js`:

```javascript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js');
}
```

---

## 🎯 Configuration Complète (Tout-en-Un)

### 1. Frontend sur Vercel

```bash
cd /app/frontend
echo "REACT_APP_BACKEND_URL=https://votre-backend.vercel.app" > .env.production
vercel --prod
```

### 2. Backend sur Railway

```bash
cd /app/backend
# Créer railway.json
echo '{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn server:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE"
  }
}' > railway.json

# Déployer
railway login
railway up
```

### 3. MongoDB Atlas (Gratuit)

1. [Créer compte](https://www.mongodb.com/cloud/atlas/register)
2. Créer cluster gratuit (512MB)
3. Obtenir connection string
4. Ajouter dans variables d'environnement

---

## ✅ Checklist Déploiement

- [ ] Frontend déployé et accessible
- [ ] Backend déployé avec HTTPS
- [ ] MongoDB configuré
- [ ] Variables d'environnement définies
- [ ] CORS configuré correctement
- [ ] PWA manifest.json présent
- [ ] Service Worker activé (mode offline)
- [ ] APK généré ou PWA installable
- [ ] Desktop app créée (optionnel)
- [ ] Tests sur mobile/desktop

---

## 🆓 Coût Total: 0€

Avec cette stack:
- Vercel (Frontend): **Gratuit**
- Railway (Backend): **5$ gratuit/mois**
- MongoDB Atlas: **Gratuit**
- GitHub: **Gratuit**
- APK (PWA): **Gratuit**
- Desktop (Electron): **Gratuit**

✅ **100% gratuit, sans limites !**

---

## 📞 Support

En cas de problème:
1. Vérifier les logs (Vercel/Railway dashboard)
2. Tester les endpoints API
3. Vérifier les CORS
4. S'assurer que MongoDB est accessible

---

## 🚀 Prochaines Étapes

1. **Déployer** en suivant ce guide
2. **Tester** sur tous les appareils
3. **Partager** le lien avec d'autres
4. **Améliorer** avec de nouvelles fonctionnalités

**CodeForge AI - Création Sans Limites !** 🎉
