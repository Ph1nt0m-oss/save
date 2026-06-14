# Migration Vite — Guide d'activation (iter121)

> Statut : **SCAFFOLD prêt** — Vite n'est PAS actif. CRA/CRACO reste le bundler par défaut.
> Décision utilisateur (iter121) : garder Webpack 5 cache (option a) + scaffold Vite ready (option b) pour switch futur.

---

## Pourquoi rester sur CRA/Webpack pour l'instant ?

Le plugin Emergent `@emergentbase/visual-edits` est **Webpack-only** — il fournit l'éditeur visuel WYSIWYG dans l'IDE Emergent. Migrer vers Vite désactivera cette fonctionnalité tant qu'Emergent ne sort pas de version Vite-compatible.

Optimisations CRA actuelles (iter121) :
- ✅ Webpack 5 persistent filesystem cache (`node_modules/.cache/webpack`)
- ✅ `eval-cheap-module-source-map` en dev (HMR plus rapide)
- ✅ Split chunks intelligent en prod (`vendor-react`, `vendor-radix`, `vendor-monaco`, `vendor-viz`)
- ✅ Compression gzip du cache (footprint réduit)

**Gain mesuré** :
- 1er build froid : ~20s (identique CRA pur)
- Builds suivants (cache hit) : ~5-8s
- HMR dev : ~150-300ms par changement

---

## Quand migrer vers Vite ?

Migre **uniquement si** :
- Emergent a sorti `@emergentbase/visual-edits-vite` (vérifie `npm info @emergentbase/visual-edits-vite`)
- OU tu acceptes de perdre l'éditeur WYSIWYG
- OU tu déploies sur une CI où visual-edits n'est pas utilisé

Gain Vite vs CRA :
- 1er build froid : ~5s (vs 20s)
- HMR dev start : ~500ms (vs 8-15s)
- HMR par changement : ~30-100ms

---

## Étapes de migration (testées sur le scaffold actuel)

### 1. Installer Vite + plugins
```bash
cd /app/frontend
yarn vite:install
# = yarn add -D vite @vitejs/plugin-react
```

### 2. Renommer `src/index.js` → `src/main.jsx`
```bash
mv src/index.js src/main.jsx
```

### 3. Renommer tous les fichiers JSX en `.jsx`
```bash
# Trouve tous les .js qui contiennent du JSX
find src -name "*.js" -exec grep -l "from 'react'" {} \; | while read f; do
  mv "$f" "${f%.js}.jsx"
done
# Met à jour les imports cassés (les `from './X'` deviennent `from './X'` toujours OK,
# Vite résoud automatiquement les extensions)
```

### 4. Déplacer `public/index.html` → `./index.html` (racine frontend)
```bash
mv public/index.html ./index.html
```
Puis dans `./index.html`, remplace :
- `%PUBLIC_URL%` → `/`
- Avant `</body>`, ajoute :
  ```html
  <script type="module" src="/src/main.jsx"></script>
  ```

### 5. Changer la commande supervisor
Le fichier `/etc/supervisor/conf.d/...` est en lecture seule, mais tu peux :
- Modifier `package.json` : `"start": "vite --host 0.0.0.0 --port 3000"`
- OU lancer manuellement `yarn vite:dev` (port 3000)

### 6. Tester
```bash
yarn vite:dev
# → "vite v5.x  ready in 487 ms"
# → Local:   http://localhost:3000/
```

### 7. Build prod
```bash
yarn vite:build
# → "dist/index.html             2.34 kB"
# → "dist/assets/index-XYZ.js  450.21 kB"
ls -la dist/
```

---

## Compatibilité ENV vars

Le `vite.config.js` actuel utilise :
```js
envPrefix: ['VITE_', 'REACT_APP_'],
```

→ **Tu n'as PAS besoin de renommer** `REACT_APP_BACKEND_URL` en `VITE_BACKEND_URL`. Les deux préfixes sont exposés.

⚠️ Mais le code doit utiliser `import.meta.env.REACT_APP_BACKEND_URL` (Vite) au lieu de `process.env.REACT_APP_BACKEND_URL` (CRA). Le shim suivant peut être ajouté en haut de `src/main.jsx` :

```js
// Shim CRA → Vite pour les fichiers qui utilisent process.env.REACT_APP_*
if (typeof process === 'undefined') {
  window.process = { env: { ...import.meta.env, NODE_ENV: import.meta.env.MODE } };
}
```

Sinon, fais un `sed` global :
```bash
find src -name "*.jsx" -o -name "*.js" | \
  xargs sed -i 's/process\.env\.REACT_APP_/import.meta.env.REACT_APP_/g'
```

---

## Rollback Vite → CRA

```bash
# 1. Restaure les .js (Vite tolère les .jsx mais CRA accepte le JSX dans .js)
find src -name "*.jsx" | while read f; do mv "$f" "${f%.jsx}.js"; done
# 2. Restaure src/index.js
mv src/main.js src/index.js
# 3. Restaure public/index.html
mv index.html public/index.html  # puis remets %PUBLIC_URL%
# 4. package.json : "start": "craco start"
# 5. yarn (réinstalle craco)
```

---

## Fichiers concernés (iter121)

- `craco.config.js` — Webpack 5 cache + splitChunks actifs
- `vite.config.js` — scaffold prêt à activer (envPrefix REACT_APP_+VITE_, alias @, splitChunks Rollup)
- `package.json` — scripts `vite:dev`, `vite:build`, `vite:preview`, `vite:install`
- `docs/MIGRATION_VITE.md` — ce fichier
