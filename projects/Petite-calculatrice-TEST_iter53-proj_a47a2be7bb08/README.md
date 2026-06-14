# TEST_iter53 — Petite calculatrice (React + Tailwind via CDN)

Application de calculatrice moderne, responsive, avec historique et mémoire, persistée via LocalStorage et installable en PWA.

## Lancer l’application

### Option A — Ouverture directe (rapide)
1. Ouvrez `index.html` dans votre navigateur.
2. L’application fonctionne immédiatement.

> Note : l’installation PWA et le mode offline via Service Worker fonctionnent le mieux via HTTPS ou `http://localhost`.

### Option B — Recommandé (PWA + offline fiables)
Utilisez un petit serveur statique.

#### Avec Python
```bash
python -m http.server 5173
```
Puis ouvrez : `http://localhost:5173`

#### Avec Node (serve)
```bash
npx serve -l 5173
```
Puis ouvrez : `http://localhost:5173`

## Fonctionnalités
- Opérations : `+`, `-`, `×`, `÷`, `%` (modulo via l’opérateur dédié), et conversion `%` (bouton % sous forme “÷100”).
- Mémoire : `MC`, `MR`, `M+`, `M-`.
- Fonctions : `√` (racine carrée), `1/x` (inverse).
- Historique (jusqu’à 30 entrées), cliquable pour recopier un résultat.
- Persistance : état (affichage, mémoire, historique) sauvegardé automatiquement dans LocalStorage.
- UX : animations/transition, design sombre type “Emergent”, mobile-first.
- Accessibilité : focus visible, `aria-label`, support clavier.

## Raccourcis clavier
- Chiffres : `0–9`
- Opérateurs : `+`, `-`, `*`, `/`, `%`
- Virgule/point : `,` ou `.`
- Calculer : `Entrée` ou `=`
- Retour arrière : `Backspace`
- Tout effacer : `Échap`

## Structure
- `index.html` : point d’entrée, CDNs React/ReactDOM/Babel + Tailwind
- `App.jsx` : application React (composants fonctionnels + hooks)
- `styles.css` : styles additionnels (scrollbar, effets, transitions)
- `manifest.json` : manifeste PWA
- `sw.js` : service worker (cache des assets, support offline)

## Données (LocalStorage)
Clé : `test_iter53_calc_state_v1`
- `current` (string)
- `tokens` (tableau)
- `justEvaluated` (bool)
- `memory` (number)
- `history` (tableau max 30)

Vous pouvez effacer les données via le bouton **Effacer** dans l’en-tête.

## Dépannage
- Si le Service Worker ne se met pas à jour : faites un “hard refresh” (Ctrl+F5) ou supprimez les données de site (Application → Service Workers / Storage).
- PWA : l’option “Ajouter à l’écran d’accueil” apparaît surtout sur mobile (Chrome/Edge) lorsque le site est servi en HTTPS ou sur `localhost`.
