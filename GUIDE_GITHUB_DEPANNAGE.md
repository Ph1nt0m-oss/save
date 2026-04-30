# Guide ULTRA-DÉTAILLÉ — Dépanner CodeForge AI via GitHub

**Audience** : toi-même, demain, sans aucun crédit Emergent, sans Axel, sans agent IA. Tu n'as que ton navigateur et ton compte GitHub.

**Objectif** : si un bug apparaît sur l'authentification email (inscription, connexion, lien magique), tu peux **réparer en 100% autonomie** via le site web de GitHub — **sans installer quoi que ce soit sur ton PC**.

> Chaque étape est numérotée. Ne saute **aucune ligne**. Si une étape échoue, descend à la section "🚨 En cas de problème" tout en bas.

---

## 🔑 Prérequis (à vérifier UNE fois aujourd'hui)

1. Ouvre ton navigateur.
2. Va sur `https://github.com` et connecte-toi avec ton compte.
3. Vérifie que tu accèdes bien au dépôt **`Ph1nt0m-oss/codeforge-ai`** — c'est là que vit CodeForge AI.
4. Tout en haut de la page du dépôt, tu dois voir **"Actions"** dans le menu. Clique dessus et vérifie que tu vois une liste de **"CI / Auto Deploy"** avec des ronds verts ✅.
5. Si tu vois des ronds verts → parfait, **c'est déployé et à jour**. Tu n'as rien à faire aujourd'hui.

C'est tout. Tu es prêt·e pour demain.

---

## 🐛 PROBLÈME 1 : « L'inscription ne fonctionne plus, le lien n'arrive pas »

**Symptôme** : tu cliques sur "Inscription", tu rentres email + mot de passe, et soit tu n'as pas de lien qui s'affiche, soit le lien t'envoie sur une page blanche "403 Forbidden".

### Étape 1 — Vérifier que le mode démo fonctionne
1. Va sur `https://no-code-builder-25.preview.emergentagent.com/login` (ou ton URL Emergent).
2. Clique sur l'onglet **"Inscription"**.
3. Entre `test123@gmail.com` comme email et `monmotdepasse` comme mot de passe.
4. Clique "Créer mon compte".
5. **Un encadré bleu-cyan doit apparaître** avec un lien vers `/verify-email?token=xxx`.

✅ **Si tu vois l'encadré** → le backend fonctionne. Clique sur le lien → tu arrives dans le dashboard. Le bug n'existe pas.

❌ **Si tu ne vois pas l'encadré** → continue à l'étape 2.

### Étape 2 — Lire le dernier log GitHub Actions
1. Sur GitHub, va dans `Ph1nt0m-oss/codeforge-ai` → **Actions**.
2. Clique sur le dernier workflow en haut de la liste.
3. Tu verras plusieurs "jobs" (tests backend, tests frontend, deploy).
4. Si **tous les ronds sont verts** ✅ → le code est bon, le problème vient d'Emergent (crédits épuisés, preview éteint). **Tu n'as rien à faire**, tu dois attendre tes crédits.
5. Si un rond est **rouge** ❌ → clique dessus, lis le message d'erreur en rouge. Note le nom du fichier et le numéro de ligne.

### Étape 3 — Corriger une erreur courante depuis GitHub
Si tu vois une erreur du genre `ImportError: cannot import name X` ou `SyntaxError`, voici comment **éditer directement depuis le site web GitHub** :

1. Va sur `Ph1nt0m-oss/codeforge-ai` (page d'accueil du dépôt).
2. Clique sur le dossier **`backend/`** puis sur le fichier **`server.py`**.
3. En haut à droite du code, clique sur l'icône **crayon ✏️** ("Edit this file").
4. GitHub ouvre un éditeur dans ton navigateur.
5. Utilise `Ctrl+F` (ou `Cmd+F`) pour chercher la ligne en erreur.
6. Corrige, puis descends en bas de la page.
7. Dans la section **"Commit changes"** :
   - Titre du commit : `Fix: <décris ton changement>`
   - Description : laisse vide ou explique.
   - **Coche "Commit directly to the main branch"**.
8. Clique sur le bouton vert **"Commit changes"**.
9. Retourne dans l'onglet **Actions** de GitHub → un nouveau workflow démarre automatiquement.
10. **Attends 2-3 minutes**. Quand le rond devient vert ✅ → ton code est déployé en live. Retourne sur la page `/login` d'Emergent et re-teste.

---

## 🐛 PROBLÈME 2 : « La connexion dit "Email ou mot de passe incorrect" même avec le bon mot de passe »

### Cause probable
- Ton compte n'est **pas encore vérifié**. Tu dois cliquer sur le lien reçu lors de l'inscription (mode démo : le lien s'affiche sur la page d'inscription).

### Solution rapide
1. Va sur `/login` → onglet **"Inscription"**.
2. Réinscris-toi avec le **même** email que la fois précédente.
3. Le backend détecte que ce compte existe mais n'est pas vérifié → il te redonne un **nouveau lien magique**.
4. Clique sur le lien → tu es vérifié·e → connexion OK.

### Si ça ne marche toujours pas (bug plus profond)
1. Va dans GitHub → `Ph1nt0m-oss/codeforge-ai/actions`.
2. Regarde le dernier workflow.
3. Si vert ✅ → redémarrer le backend Emergent (bouton "Restart" dans l'interface Emergent, pas via GitHub).
4. Si rouge ❌ → suit l'étape 3 du PROBLÈME 1.

---

## 🐛 PROBLÈME 3 : « La page est complètement blanche / "403 Forbidden" »

### Cause probable
- L'URL de preview Emergent a changé (ça arrive si on est resté trop longtemps sans rafraîchir).

### Solution
1. Retourne sur le chat Emergent.
2. Regarde le panneau de droite — l'URL actuelle du preview est affichée.
3. Utilise **cette URL-là**, pas une ancienne.

Si l'URL est correcte mais la page reste blanche :
1. Ouvre la console du navigateur (`F12` → onglet "Console").
2. Cherche un message rouge commençant par `Failed to load` ou `CORS`.
3. Note le message et va sur GitHub → **Issues** (onglet en haut du dépôt) → **New Issue** → colle le message. Tu pourras revenir le lire plus tard.

---

## 🐛 PROBLÈME 4 : « Je veux rollback complet à la version qui marchait avant »

### Solution via GitHub (sans rien installer)
1. Va sur `https://github.com/Ph1nt0m-oss/codeforge-ai/commits/main`.
2. Tu vois la liste de tous les commits (les plus récents en haut).
3. Trouve le commit qui correspond à l'**état qui fonctionnait** (regarde les dates et les messages).
4. Clique sur le bouton `<>` à droite du commit → ça ouvre le code à ce moment-là.
5. En haut de la page, clique sur le bouton **"Revert"** — si disponible.
6. Sinon : crée un nouveau commit qui remet les fichiers tels qu'ils étaient :
   - Note le "SHA" (hash) du commit qui marchait — ex: `a1b2c3d`.
   - Va sur la page Actions et utilise le workflow "Rollback" s'il existe, ou crée une issue en notant le SHA.

---

## 🐛 PROBLÈME 5 : « Rien ne marche plus, je suis complètement perdu·e »

**Procédure de secours ultime** :

1. Va sur GitHub → `Ph1nt0m-oss/codeforge-ai/settings` (onglet tout à droite si tu es propriétaire).
2. **NE TOUCHE À RIEN** dans Settings. C'est dangereux.
3. À la place, retourne sur la page d'accueil du dépôt et clique sur l'onglet **"Actions"**.
4. Dans la colonne de gauche, cherche **"CI / Auto Deploy"**.
5. Clique sur le bouton **"Run workflow"** (en haut à droite).
6. Sélectionne la branche `main` → clique **"Run workflow"** (bouton vert).
7. **Attends 5 minutes** que le workflow passe au vert.
8. Re-teste l'app.

Si ça ne marche toujours pas :
- Ouvre un ticket sur `github.com/Ph1nt0m-oss/codeforge-ai/issues/new`.
- Colle ce guide dans le ticket avec ta description du problème.
- Attends le retour des crédits Emergent pour relancer un agent IA.

---

## 📁 Fichiers importants à connaître

| Fichier | Rôle | Quand le toucher |
|---|---|---|
| `backend/server.py` | Toute la logique auth email/password | En dernier recours |
| `backend/.env` | Clés secrètes (NE JAMAIS PUSH) | Jamais via GitHub |
| `frontend/src/pages/Login.js` | Page connexion/inscription | Si tu veux changer un texte |
| `frontend/src/pages/VerifyEmail.js` | Page de confirmation du lien | Jamais, ça marche |
| `frontend/.env` | URL du backend (NE JAMAIS PUSH) | Jamais via GitHub |
| `.github/workflows/ci.yml` | Auto-déploiement CI/CD | Jamais |

---

## 🚨 En cas de problème absolu

1. **NE PANIQUE PAS**. Le code est sauvegardé sur GitHub.
2. Va sur `github.com/Ph1nt0m-oss/codeforge-ai/commits/main`.
3. Regarde le dernier commit vert ✅ — il contient du code fonctionnel.
4. Note sa date et son message.
5. Si tu dois attendre que tes crédits reviennent, au moins tu sais que **rien n'est perdu**.
6. L'agent IA pourra reprendre à partir de ce commit.

---

## 📞 Contacts d'urgence
- Support Emergent : via le chat de la plateforme
- Documentation FastAPI : `https://fastapi.tiangolo.com`
- Tests backend : `backend/tests/test_email_auth.py` — tu peux voir ce qui est testé

---

## ✅ Résumé ultra-court (à coller sur ton frigo)

1. **L'inscription ne marche pas** → retourne sur `/login`, onglet Inscription, re-teste. Si rond rouge sur GitHub Actions → clique sur le commit rouge pour voir l'erreur.
2. **La connexion dit "incorrect"** → ton compte n'est pas vérifié. Réinscris-toi avec le même email pour obtenir un nouveau lien.
3. **Page blanche** → vérifie que l'URL du preview Emergent n'a pas changé.
4. **Rien ne marche** → va dans GitHub Actions → "Run workflow" → attends 5 min.

Bon courage 💪
