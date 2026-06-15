# TEST_iter53 — Calculatrice React (PWA)

Application de calculatrice moderne (style sombre « cyber ») en **React 18** avec **TailwindCSS**, animations, support clavier, historique et **persistance LocalStorage**. Compatible **PWA** avec **Service Worker** pour un mode hors-ligne.

## Lancer l’application

### Option 1 — Ouverture directe
1. Placez tous les fichiers dans le même dossier : `index.html`, `App.jsx`, `styles.css`, `manifest.json`, `sw.js`.
2. Ouvrez `index.html` dans votre navigateur.

> Note : certaines fonctionnalités PWA (installation + service worker) peuvent être limitées si vous ouvrez le fichier via `file://`. Pour une expérience PWA complète, utilisez un petit serveur local.

### Option 2 — Serveur local (recommandé pour PWA)
- Avec Python :
  - `python -m http.server 5173`
  - Ouvrez `http://localhost:5173`

- Avec Node (si vous avez `npx`) :
  - `npx serve .`

## Installation PWA (mobile)
1. Ouvrez l’app via `http(s)://...` (serveur local ou hébergement).
2. Sur Chrome/Android : menu ⋮ → **Ajouter à l’écran d’accueil**.
3. Sur Safari/iOS : bouton Partager → **Sur l’écran d’accueil**.

## Fonctionnalités
- Opérations : addition, soustraction, multiplication, division
- Gestion des décimales avec **virgule** côté UI
- Pourcentage `%` (comportement type calculatrice)
- Boutons **AC**, **CE**, **⌫**
- **±** pour inverser le signe
- **Historique** cliquable (recharge un résultat)
- **Copie** du résultat
- Gestion d’erreurs (division par zéro, NaN, Infinity)
- **Persistance** : état + historique via LocalStorage
- **Mode hors-ligne** : mise en cache via service worker

## Raccourcis clavier
- Chiffres : `0-9`
- Décimal : `.` ou `,`
- Opérateurs : `+`, `-`, `*` (ou `x`), `/`
- Calcul : `Entrée` ou `=`
- Effacer tout : `Échap`
- Retour arrière : `Backspace`
- Pourcentage : `%`

## Structure des fichiers
- `index.html` : point d’entrée (CDN React/ReactDOM/Babel/Tailwind)
- `App.jsx` : composant principal (logique calculatrice + UI)
- `styles.css` : styles additionnels + animations
- `manifest.json` : paramètres PWA + icônes embarquées (SVG en data URI)
- `sw.js` : service worker (cache-first pour assets locaux)

## Notes techniques
- Aucun `eval()` : calculs effectués via fonctions sécurisées.
- Limitation raisonnable de la longueur des nombres pour éviter les débordements.
- Le service worker met en cache les fichiers locaux et fournit `index.html` en fallback pour les navigations.
