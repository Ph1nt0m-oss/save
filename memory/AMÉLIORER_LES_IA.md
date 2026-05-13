# 🧠 BIEN UTILISER LES IA DE CODEFORGE — Guide utilisateur

> Ce guide explique comment **tirer le maximum** de chaque modèle d'IA disponible
> dans CodeForge AI, sans aucune compétence technique.

---

## 1. Choisir la bonne IA pour la bonne tâche

### Dans le **Chat** (en haut à droite, clique sur le sélecteur de modèle)

| IA | Quand l'utiliser | Exemple concret |
|---|---|---|
| 🟡 **Caly (GPT-5.2)** | Discussion généraliste, brainstorm, écriture, analyse | « Aide-moi à rédiger un email de relance commercial » |
| 🟠 **Claude Opus 4.5** *(Thinking)* | Problèmes complexes nécessitant un raisonnement pas-à-pas | « J'ai 3 offres d'emploi, aide-moi à choisir en pesant les pour/contre » |
| 🟠 **Claude Sonnet 4.5** *(Code)* | Snippets de code, refactor, debug ligne par ligne | « Écris-moi une fonction Python qui... » + bouton ▶ pour exécuter |
| 🔵 **Gemini 3 Pro** *(Multimodal)* | Analyser une image jointe (OCR, schéma, photo) | Joindre une photo → « De quoi parle ce ticket de caisse ? » |
| 🔵 **Gemini 3 Flash** *(Ultra-rapide)* | Questions courtes, ping-pong, vérification express | « Capitale du Pérou ? », « Convertis 32°F en °C » |

**Règle d'or** : commence avec **Caly** par défaut, et bascule vers Claude Opus dès que la question devient complexe (analyse, décision, projet long).

### Dans la **Création** (page Create)

| IA | Quand l'utiliser | Type de projet |
|---|---|---|
| 🟠 **Claude Sonnet 4.5** | Par défaut — le plus rapide et propre | App standard, site marketing, outil CRUD |
| 🟠 **Claude Opus 4.5** | Projets multi-modules, logique métier complexe | Backend avec règles, App SaaS, dashboard |
| 🟡 **Caly (GPT-5.2)** | Bon équilibre, hypothèses intelligentes | App complète, projet équilibré |
| 🔵 **Gemini 3 Pro** | Quand tu veux une UI plus créative | Landing page, portfolio, identité visuelle |
| 🔵 **Gemini 3 Flash** | Prototype rapide, MVP simple | Page unique, démo express |

**Workflow type** :
1. **Décris ton idée** en quelques phrases.
2. Choisis **Claude Sonnet** (recommandé par défaut).
3. Clique **Créer** → l'IA génère le code complet.
4. Le système lance automatiquement un **Build & Test** :
   - ✅ vert = preview fonctionnel, tu peux cliquer "Aperçu Live"
   - ⚠️ orange = code généré mais aperçu KO → ouvre manuellement
5. **Itère** dans le chat si tu veux ajuster.

---

## 2. Changer de modèle au milieu d'une conversation

Tu peux **basculer** entre Caly, Claude, Gemini à tout moment. L'IA suivante
sait que la précédente a parlé et **reprend le fil naturellement** — pas besoin
de tout réexpliquer.

**Astuce** : commence avec **Gemini 3 Flash** pour brainstormer rapidement,
puis bascule vers **Claude Opus** quand tu veux approfondir une piste.

---

## 3. Modes Hors-ligne (Ollama)

Si tu as installé **Ollama** sur ta machine, tu peux discuter avec un modèle
**100% local et privé** — rien ne sort de chez toi.

### Modèles recommandés

| Modèle | RAM mini | Recommandé pour |
|---|---|---|
| 🔵 **Gemma 3 (4B)** | 8 Go | Vieux laptop, tâches simples |
| 🟢 **Gemma 3 (12B)** | 16 Go | Polyvalent, multilingue, recommandé |
| 🟣 **Gemma 3 (27B)** | 24 Go+ | Qualité GPT-3.5 hors-ligne |
| 💎 **DeepSeek R1 (7B)** | 12 Go | Code et maths |
| 🌐 **Qwen 2.5 (7B)** | 12 Go | Multilangue (chinois inclus) |
| 🇫🇷 **Mistral 7B** | 12 Go | Français natif, RGPD |

### Installation rapide

```bash
# Installer Ollama (une fois)
curl -fsSL https://ollama.com/install.sh | sh

# Récupérer un modèle (à faire une fois par modèle)
ollama pull gemma3:12b
ollama pull deepseek-r1:7b

# Le serveur démarre automatiquement sur localhost:11434
```

Dans CodeForge, sélectionne **mode Hors-ligne** dans le menu, puis choisis ton modèle.

---

## 4. Les 12 langues supportées

CodeForge parle (et te répond) dans :

🇫🇷 Français · 🇬🇧 English · 🇪🇸 Español · 🇵🇹 Português · 🇩🇪 Deutsch ·
🇳🇱 Nederlands · 🇷🇺 Русский · 🇨🇳 中文 · 🇮🇳 हिन्दी · 🇧🇩 বাংলা ·
🇵🇰 اردو · 🇯🇵 日本語 · 🇭🇷 Hrvatski · 🇩🇰 Dansk

**Astuce** : tu peux écrire en français et demander à l'IA de te répondre en
japonais (ou inverse), elle s'adapte. Pour basculer toute l'interface,
utilise le sélecteur de langue dans Profil.

---

## 5. Sandbox Python — Le chat devient un mini Jupyter

Quand Claude Sonnet (ou n'importe quel modèle) te donne un bloc de code Python,
tu peux **cliquer ▶ Exécuter** dans le bloc — le serveur exécute le code et te
montre le résultat directement dans le chat (avec graphiques matplotlib si
demandé).

**Variables persistantes** : si tu définis `x = 42` dans un bloc, le bloc
suivant peut faire `print(x)` — les variables sont gardées (mode REPL).
Reset via le bouton 🔄 du header.

**Upload de fichiers** : clique 📎 dans un bloc de code pour joindre un CSV /
JSON / image → ton code peut le lire avec `pandas.read_csv("data.csv")`.

---

## 6. 5 erreurs à éviter

1. ❌ Toujours utiliser le même modèle → ✅ choisis selon la tâche
2. ❌ Donner un prompt vague (« écris un truc ») → ✅ contexte + format attendu
3. ❌ Demander 5 choses à la fois → ✅ une demande, puis itère
4. ❌ Oublier de cliquer ▶ Exécuter sur les blocs Python → ✅ tu rates 50% des capacités
5. ❌ Rester en mode online quand tu n'as plus de budget → ✅ bascule hors-ligne avec Gemma

---

*Document interne CodeForge AI — Ne pas partager publiquement.*
