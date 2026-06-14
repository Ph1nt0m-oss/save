// iter121 — Vite migration scaffold (PRÊT mais non actif).
//
// Pour activer Vite à la place de CRA :
//   1. yarn add -D vite @vitejs/plugin-react vite-plugin-svgr
//   2. Renommer src/index.js → src/main.jsx (ajouter `import './index.css'` au début)
//   3. Renommer tous les .js qui contiennent du JSX → .jsx
//      find src -name "*.js" -exec grep -l "from 'react'" {} \; | xargs -I{} sh -c 'mv {} ${0%.js}.jsx' {}
//   4. Déplacer public/index.html → ./index.html (racine du frontend)
//      Remplacer `%PUBLIC_URL%` par `/` et ajouter <script type="module" src="/src/main.jsx"></script>
//   5. Dans supervisor: changer `yarn start` → `yarn vite:dev`
//   6. yarn vite:dev (port 3000 via vite.config.js)
//   7. yarn vite:build → output dans frontend/dist/
//
// ⚠️ Note : Vite ne supporte PAS @emergentbase/visual-edits (plugin Webpack-only).
// L'éditeur visuel WYSIWYG d'Emergent sera désactivé. Décision utilisateur explicite (iter121).

import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  // Charge `.env` ET `.env.local` ET `.env.${mode}` automatiquement
  const env = loadEnv(mode, process.cwd(), '');

  return {
    // iter121 — Compat REACT_APP_* : expose ces vars sans renommer le code
    envPrefix: ['VITE_', 'REACT_APP_'],

    // Alias `@` → `src` (identique à craco.config.js)
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },

    plugins: [
      react({
        // Fast Refresh + Babel pour transformer le JSX dans les .js
        babel: {
          plugins: [
            // Optionnel : decorators, class-properties si besoin
          ],
        },
      }),
    ],

    // Permet d'écrire du JSX dans des .js (CRA compat)
    esbuild: {
      loader: 'jsx',
      include: /src\/.*\.[jt]sx?$/,
      exclude: [],
    },
    optimizeDeps: {
      esbuildOptions: {
        loader: { '.js': 'jsx' },
      },
    },

    server: {
      host: '0.0.0.0',
      port: 3000,        // garde le port supervisor existant
      strictPort: true,
      // Le frontend appelle le backend via REACT_APP_BACKEND_URL (préfixe /api)
      // donc PAS de proxy ici — laisse l'ingress Kubernetes gérer
    },

    preview: {
      host: '0.0.0.0',
      port: 3000,
      strictPort: true,
    },

    build: {
      outDir: 'dist',
      sourcemap: true,
      // Code-splitting manuel équivalent au splitChunks Webpack
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-radix': [
              '@radix-ui/react-dialog',
              '@radix-ui/react-dropdown-menu',
              '@radix-ui/react-select',
              '@radix-ui/react-tabs',
              '@radix-ui/react-tooltip',
              '@radix-ui/react-popover',
            ],
            'vendor-monaco': ['@monaco-editor/react'],
            'vendor-viz': ['recharts', 'framer-motion'],
          },
        },
      },
      // Limite la taille de chunk warning au seuil 600kB
      chunkSizeWarningLimit: 600,
    },

    // iter121 — Polyfills CRA → Vite : process.env stub pour packages qui en dépendent
    define: {
      'process.env.NODE_ENV': JSON.stringify(env.NODE_ENV || mode),
    },
  };
});
