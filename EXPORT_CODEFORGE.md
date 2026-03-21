# 📦 Exporter CodeForge Complète

Ce guide explique comment exporter **CodeForge elle-même** (l'application complète) pour la distribuer.

---

## 🎯 Options d'Export

### 1. 📱 Application Mobile (APK)

Exporter CodeForge comme application Android installable.

**Méthode 1 : PWA (Progressive Web App)**

```bash
# 1. Build le frontend
cd /app/frontend
npm run build

# 2. Créer manifest.json (déjà présent)
# Vérifier que manifest.json contient:
{
  "name": "CodeForge AI",
  "short_name": "CodeForge",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#050505",
  "theme_color": "#E4FF00",
  "icons": [...]
}

# 3. Ajouter service worker pour offline
# Créer public/sw.js (voir ci-dessous)

# 4. Héberger sur HTTPS (Vercel/Netlify)
vercel --prod

# 5. Installer sur Android:
# - Ouvrir Chrome Android
# - Aller sur https://votre-codeforge.vercel.app
# - Menu → "Ajouter à l'écran d'accueil"
# ✅ CodeForge installée comme app native!
```

**Méthode 2 : Capacitor (APK natif)**

```bash
cd /app/frontend

# Installer Capacitor
npm install @capacitor/core @capacitor/cli
npx cap init

# Ajouter Android
npx cap add android

# Build
npm run build
npx cap copy
npx cap open android

# Dans Android Studio:
# Build → Generate Signed Bundle / APK
# ✅ APK dans android/app/build/outputs/apk/
```

**Méthode 3 : PWA Builder**

1. Déployer CodeForge sur Vercel/Netlify
2. Aller sur https://www.pwabuilder.com/
3. Entrer l'URL de votre CodeForge
4. Télécharger le package Android
5. ✅ APK prêt à distribuer!

---

### 2. 💻 Application Desktop (EXE)

Exporter CodeForge comme application Windows.

**Méthode : Electron**

```bash
# 1. Créer dossier Electron
mkdir codeforge-desktop && cd codeforge-desktop

# 2. Init
npm init -y
npm install electron electron-builder

# 3. Créer main.js
cat > main.js << 'EOF'
const { app, BrowserWindow } = require('electron');

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    icon: 'icon.png'
  });

  // Charger CodeForge
  win.loadURL('https://votre-codeforge.vercel.app');
  
  // Ou charger en local:
  // win.loadFile('../frontend/build/index.html');
}

app.whenReady().then(createWindow);
EOF

# 4. package.json
cat > package.json << 'EOF'
{
  "name": "codeforge-desktop",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "build": "electron-builder"
  },
  "build": {
    "appId": "com.codeforge.app",
    "productName": "CodeForge AI",
    "win": {
      "target": "nsis",
      "icon": "icon.ico"
    }
  }
}
EOF

# 5. Build
npm run build

# ✅ EXE dans dist/CodeForge AI Setup 1.0.0.exe
```

---

### 3. 🌐 Site Web Public

Déployer CodeForge sur une page web accessible.

**Option A : Vercel (Recommandé)**

```bash
# Frontend
cd /app/frontend
vercel --prod
# ✅ Obtenir URL: https://codeforge.vercel.app

# Backend  
cd /app/backend
vercel --prod
# ✅ Obtenir URL: https://codeforge-api.vercel.app

# Mettre à jour frontend/.env
REACT_APP_BACKEND_URL=https://codeforge-api.vercel.app

# Redeploy frontend
vercel --prod
```

**Option B : Netlify**

```bash
cd /app/frontend
npm run build
netlify deploy --prod --dir=build

# Backend sur Railway/Render
cd /app/backend
railway up
```

**Option C : Self-Hosted**

```bash
# Créer docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
  
  backend:
    build: ./backend
    ports:
      - "8001:8001"
    environment:
      - MONGO_URL=mongodb://mongo:27017
  
  mongo:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
EOF

# Lancer
docker-compose up -d

# ✅ CodeForge sur http://votre-serveur:3000
```

---

## 🔄 Service Worker (Mode Offline)

Pour que CodeForge fonctionne hors ligne :

```javascript
// /app/frontend/public/sw.js
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

Enregistrer dans `/app/frontend/src/index.js` :

```javascript
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('SW registered:', reg))
      .catch(err => console.log('SW error:', err));
  });
}
```

---

## 📦 Package Complet (Tout-en-Un)

Créer un package qui contient TOUT :

```bash
#!/bin/bash
# export-codeforge.sh

echo "🚀 Export CodeForge Complet"

# 1. Build frontend
cd /app/frontend
npm run build

# 2. Créer archive
cd /app
mkdir -p exports
tar -czf exports/codeforge-complete.tar.gz \
  frontend/build \
  backend \
  DEPLOYMENT_GUIDE.md \
  OLLAMA_SETUP.md \
  README_CODEFORGE.md

echo "✅ Export créé: exports/codeforge-complete.tar.gz"
echo "📦 Taille: $(du -h exports/codeforge-complete.tar.gz | cut -f1)"
```

---

## 🎯 Distribution

### Partager CodeForge

**Option 1 : GitHub Release**
```bash
# Créer release
gh release create v1.0.0 \
  exports/codeforge-complete.tar.gz \
  --title "CodeForge AI v1.0.0" \
  --notes "Plateforme de création d'apps par IA sans limites"
```

**Option 2 : Site de Téléchargement**
```bash
# Héberger sur Netlify Drop
drag & drop: exports/codeforge-complete.tar.gz
# ✅ Obtenir lien de téléchargement
```

**Option 3 : NPM Package**
```bash
npm publish codeforge-ai
# Installation: npx codeforge-ai
```

---

## ✅ Checklist Export

- [ ] Frontend build (`npm run build`)
- [ ] Backend testé et fonctionnel
- [ ] MongoDB configuré (Atlas ou local)
- [ ] Variables d'environnement définies
- [ ] Service Worker ajouté (offline)
- [ ] Manifest.json configuré (PWA)
- [ ] Icons générés (192x192, 512x512)
- [ ] APK généré (Capacitor/PWABuilder)
- [ ] EXE généré (Electron)
- [ ] Documentation incluse
- [ ] Tests sur mobile/desktop

---

## 🎉 Résultat

Vous avez maintenant :
- ✅ APK CodeForge installable sur Android
- ✅ EXE CodeForge installable sur Windows
- ✅ Site web CodeForge accessible publiquement
- ✅ Package complet téléchargeable
- ✅ Mode offline fonctionnel

**CodeForge est prête à être partagée avec le monde ! 🚀**
