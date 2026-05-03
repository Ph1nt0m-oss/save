# 🧠 AMÉLIORER LES IA — Guide pas-à-pas pour débutants

> **Pour qui ?** Pour toi qui n'as jamais écrit une ligne de code mais qui veut que l'IA de CodeForge devienne **ton assistant sur-mesure**.
>
> **Temps de lecture :** 15 minutes. **Résultat :** une IA qui te comprend 10× mieux.

---

## Sommaire

1. [Comprendre comment une IA « pense »](#1-comprendre)
2. [La recette secrète : un bon prompt](#2-prompt)
3. [Donner une personnalité à l'IA (rôle + ton)](#3-personnalite)
4. [Lui donner de la mémoire (le contexte)](#4-contexte)
5. [Lui donner des connaissances (les pièces jointes)](#5-pieces-jointes)
6. [Lui faire exécuter du code Python (sandbox)](#6-sandbox)
7. [Lui faire fabriquer des fichiers (Word, Excel, PowerPoint, images…)](#7-fichiers)
8. [Les 10 erreurs à éviter](#8-erreurs)
9. [Modèles de prompts prêts à l'emploi](#9-modeles)
10. [Pour aller plus loin](#10-aller-plus-loin)

---

## 1. Comprendre comment une IA « pense » <a id="1-comprendre"></a>

Une IA (comme celle de CodeForge) n'est **pas** un moteur de recherche. C'est plutôt un **écrivain ultra-rapide** qui devine le mot suivant en se basant sur :

- **Ce que tu lui as dit dans ce chat** (son contexte court terme)
- **Ce qu'elle a appris pendant son entraînement** (sa culture générale)
- **Les fichiers que tu lui donnes** (pièces jointes, images)

**Conclusion pratique :** plus tu lui donnes de *matière claire*, meilleure sera sa réponse. Imagine que tu expliques une tâche à un·e nouveau·elle collègue — tu ne dis pas « Fais-moi un truc », tu dis « Voici le contexte, voici ce que je veux, voici les contraintes ».

---

## 2. La recette secrète : un bon prompt <a id="2-prompt"></a>

Un **prompt** = ce que tu tapes à l'IA. Un bon prompt contient **4 ingrédients** :

| Ingrédient | Exemple |
|---|---|
| 🎯 **Le but** | « Je veux un planning de repas pour la semaine. » |
| 📦 **Le contexte** | « Je suis végétarien, je cours 3 fois/semaine, budget 50 €. » |
| 📋 **Le format** | « Fais un tableau avec 7 colonnes (lundi à dimanche) et 3 lignes (midi, soir, collation). » |
| 🚦 **Les contraintes** | « Pas de soja, 2 recettes maximum réutilisées. » |

### Exemple complet

> ❌ **Mauvais :** « Donne-moi un planning. »
>
> ✅ **Bon :** « Fais-moi un **planning de repas pour 1 semaine** (🎯), je suis **végétarienne, sportive, budget 50 €** (📦). **Tableau 7 colonnes × 3 lignes** (📋), **pas de soja**, **2 recettes réutilisées max** (🚦). »

**Règle d'or** : un prompt trop court = une réponse générique. 2–4 phrases valent toujours mieux qu'un mot.

---

## 3. Donner une personnalité à l'IA <a id="3-personnalite"></a>

Tu peux **transformer l'IA en expert** d'un sujet précis en commençant ton message par un **rôle** :

### Formule magique

```
Agis comme un [rôle]. Réponds toujours en [style/ton].
Voici ma demande : [ta question].
```

### Exemples

**Prof bienveillant**
> « Agis comme un prof de maths bienveillant qui explique aux enfants de 12 ans. Réponds en phrases courtes, avec des exemples concrets du quotidien. Explique-moi la règle de trois. »

**Consultant startup**
> « Agis comme un consultant Y Combinator qui a accompagné 200 startups. Réponds par bullet points, sois direct, cite toujours un exemple réel. Voici mon idée de business : […]. »

**Traducteur poétique**
> « Agis comme un traducteur français→anglais spécialiste de poésie. Garde les rimes et le rythme. Voici mon poème : […]. »

💡 **Astuce** : plus le rôle est précis (« prof de maths de 6ème » ≫ « prof »), plus la réponse est adaptée.

---

## 4. Lui donner de la mémoire (le contexte) <a id="4-contexte"></a>

Dans CodeForge AI, **toute la conversation est mémorisée** — aucune limite de messages ! L'IA se souvient de tout ce que tu lui as dit depuis le début.

### Comment en profiter ?

1. **Définis le contexte UNE fois au début** :
   > « Dans toute cette discussion, tu es mon coach nutrition. Je suis un homme de 35 ans, 80 kg, objectif -5 kg en 2 mois. »
2. **Ensuite, pose tes questions normalement** :
   > « Que manger ce midi ? »
   > « Et ce soir ? »
   > « Fais-moi la liste de courses. »

L'IA **garde en tête** toutes tes infos, pas besoin de les répéter à chaque message.

### Réinitialiser le contexte

Si tu changes de sujet, crée un **nouveau chat** (bouton `+ Nouveau projet` dans la sidebar). Chaque chat a son propre contexte isolé.

---

## 5. Lui donner des connaissances (les pièces jointes) <a id="5-pieces-jointes"></a>

Le **trombone 📎** dans la barre du chat accepte **17 formats** :

| Type | Formats | L'IA peut… |
|---|---|---|
| 📄 Documents | `PDF, DOCX, TXT, MD` | Résumer, corriger, traduire |
| 📊 Tableurs | `XLSX` | Analyser les feuilles, faire des stats |
| 🎭 Présentations | `PPTX` | Résumer, restructurer |
| 🗄️ Bases | `SQLite, SQL` | Décrire les tables, écrire des requêtes |
| 🖼️ Images | `PNG, JPG, WEBP` | Décrire, extraire du texte |
| ⚙️ Configs | `YAML, XML, INI, ENV, JSON, TOML` | Valider, expliquer |
| 💻 Code | `PY, JS, TS, JAVA, C++, …` | Expliquer, corriger, optimiser |

### Exemple concret

1. Clique sur 📎, choisis ton `rapport_financier.xlsx`
2. Tape : « **Extrait les 3 tendances principales de cette feuille Excel, puis produis un PowerPoint de 5 slides.** »
3. L'IA analyse, répond en texte, ET génère le fichier `.pptx` prêt à télécharger.

---

## 6. Lui faire exécuter du code Python (sandbox) <a id="6-sandbox"></a>

**Nouveauté 2026 :** l'IA peut **exécuter vraiment** du code Python sur le serveur et te montrer le résultat.

### Comment déclencher le sandbox ?

Utilise des verbes explicites comme :
- « **Exécute** ce code et montre-moi le résultat »
- « **Lance** un petit script qui calcule […] »
- « **Teste** cette fonction Python »
- « **Montre-moi** ce que ça affiche »

### Exemples prêts à copier

**Mathématiques**
> « Exécute du Python pour calculer la dérivée de `3x³ + 2x² − x + 7` et affiche le résultat. »

**Données**
> « Lance un script qui génère 100 nombres aléatoires entre 0 et 50, calcule la moyenne, la médiane et l'écart-type, puis affiche les stats. »

**Web scraping (pédagogique)**
> « Écris et exécute un script qui récupère le titre de la page `https://example.com` avec `requests` et `BeautifulSoup`. »

**Graphique** *(en cours d'ajout)*
> « Dessine-moi le graphique de `sin(x)` entre -π et π avec matplotlib. »

### Librairies disponibles dans le sandbox

`numpy`, `pandas`, `matplotlib`, `sympy`, `requests`, `beautifulsoup4`, `lxml`, `Pillow`, `openpyxl`, `python-docx`, `python-pptx`, `reportlab`, `pypdf`, `httpx`, `yaml`, `python-dateutil`, `pytz` + toute la **bibliothèque standard Python 3.11**.

⏱️ **Timeout** : 10 secondes max par exécution (tu peux dépasser pour un test long, mais le serveur coupe à 30 s).

---

## 7. Lui faire fabriquer des fichiers <a id="7-fichiers"></a>

L'IA peut **produire 17 types de fichiers** directement téléchargeables.

### Les 3 ingrédients d'une demande de fichier

1. **Le verbe** : *« génère », « crée », « fais-moi »*
2. **Le format** : *« un Word », « un Excel », « un PDF », « une image », « un script Python »…*
3. **Le contenu voulu** : plus tu détailles, meilleur sera le fichier.

### Exemples testés ✅

**Word structuré**
> « Génère un **document Word** de 3 pages sur l'impact du réchauffement climatique sur les forêts boréales. Sections : Introduction, Constats, Solutions. »

**Excel avec formules**
> « Crée un **fichier Excel** avec une feuille « Budget » : colonnes Poste / Prévu / Réel / Écart. Ajoute 5 lignes d'exemple + une ligne Total avec `=SUM()`. »

**PowerPoint 10 slides**
> « Fais-moi une **présentation PowerPoint** de 10 slides pour pitcher une app de covoiturage écologique. Ton moderne, une idée clé par slide. »

**Image (Gemini Nano Banana)**
> « Génère une **image** : un chat roux qui lit un livre sur un rebord de fenêtre au crépuscule, style aquarelle. »

**Script Python complet**
> « Écris-moi un **script Python** (.py) qui lit un fichier CSV, filtre les lignes où la colonne « prix » est > 100, et exporte le résultat en JSON. Commenté. »

**PDF élégant**
> « Génère un **PDF** mise en page soignée : CV d'une graphiste 5 ans d'expérience, sections Expérience / Compétences / Formation. »

---

## 8. Les 10 erreurs à éviter <a id="8-erreurs"></a>

1. ❌ **Prompt d'un mot** (« traduis »). ✅ Dis *quoi* traduire, *vers quelle langue*, pour *quel public*.
2. ❌ **Mélanger 5 demandes dans le même message.** ✅ Une demande à la fois, puis enchaîne.
3. ❌ **Pas de format attendu.** ✅ Demande explicitement : tableau, bullet points, JSON, paragraphes…
4. ❌ **Copier-coller 30 pages sans explication.** ✅ Précise : « Résume la partie 2 seulement. »
5. ❌ **Ne jamais corriger l'IA.** ✅ Si la réponse est à côté, dis *pourquoi* : « Non, trop long, fais 3 lignes. »
6. ❌ **Croire que l'IA sait tout.** ✅ Pour des infos très récentes ou ultra-précises, donne-lui une pièce jointe.
7. ❌ **Oublier de dire à qui ça s'adresse.** ✅ « Pour un enfant de 8 ans » vs « Pour un expert du domaine » → résultats totalement différents.
8. ❌ **Ne jamais exécuter le code qu'elle te donne.** ✅ Demande-lui de l'exécuter dans le sandbox → tu vois le résultat direct.
9. ❌ **Vouloir TOUT en un seul message.** ✅ Itère : « Maintenant, ajoute… », « Remplace X par Y… », « Fais plus court. »
10. ❌ **Accepter la première version.** ✅ Demande 2–3 variantes : « Propose-moi 3 versions différentes de ce titre. »

---

## 9. Modèles de prompts prêts à l'emploi <a id="9-modeles"></a>

Copie-colle, remplace les `[crochets]`.

### 📝 Résumer un document
```
Tu es un assistant de synthèse. Résume le document ci-joint en :
- 1 phrase d'accroche
- 5 bullet points clés
- 1 citation forte à retenir
Ton neutre, zéro jargon.
```

### 🧑‍🏫 Expliquer un concept
```
Explique-moi [CONCEPT] comme si j'avais 10 ans.
Utilise une analogie de la vie quotidienne. Maximum 5 phrases.
Finis par une question pour vérifier que j'ai compris.
```

### 🐍 Générer + exécuter un script
```
Écris un script Python qui [TÂCHE], puis EXÉCUTE-le dans le sandbox.
Affiche clairement le résultat avec print().
Ajoute 1–2 lignes de commentaires par étape.
```

### 📊 Analyser un Excel
```
Voici mon fichier Excel en pièce jointe. Fais :
1. Un résumé des feuilles présentes
2. Les 3 tendances principales
3. 2 recommandations concrètes
Ensuite, génère un PowerPoint de 5 slides basé sur cette analyse.
```

### 🎨 Créer une image
```
Génère une image : [SUJET].
Style : [aquarelle / photoréaliste / minimaliste / bande dessinée…].
Ambiance : [chaude / froide / mystérieuse / joyeuse…].
Cadrage : [gros plan / plan large / plongée / …].
Éléments à NE PAS inclure : [liste].
```

### 🌐 Traduire finement
```
Traduis le texte suivant en [LANGUE CIBLE].
Contexte : [marketing / technique / littéraire / juridique].
Conserve le ton [formel / familier / humoristique].
Garde les noms propres en VO.
Texte : """[TEXTE]"""
```

---

## 10. Pour aller plus loin <a id="10-aller-plus-loin"></a>

### Combine les techniques

Le vrai pouvoir vient de **combiner** rôle + contexte + pièce jointe + sandbox + fichier généré :

> « Tu es un data analyst. Voici mon CSV de ventes 2025 (pièce jointe). **Exécute** un script Python qui calcule le chiffre d'affaires mensuel. Ensuite **génère un PowerPoint** de 6 slides avec les constats + un graphique. »

Cette seule phrase déclenche : analyse du fichier → exécution Python → création d'un `.pptx` téléchargeable. **3 minutes de travail manuel économisées.**

### Apprends en observant

Regarde **ce que l'IA te répond** et note ce qui marche pour toi. Chaque personne a son style de prompt préféré. Tiens un petit carnet (ou un chat CodeForge dédié) avec tes meilleurs prompts.

### La règle des 3 passes

Pour un livrable important :
1. **Passe 1** : demande une version rapide.
2. **Passe 2** : demande des améliorations précises (« plus court », « ton plus formel »).
3. **Passe 3** : demande 2 variantes pour choisir.

---

## ✅ Récapitulatif express

| Besoin | Action |
|---|---|
| Meilleure réponse | Prompt en 4 ingrédients (but + contexte + format + contraintes) |
| Expertise ciblée | Commence par « Agis comme un [rôle] » |
| Mémoire longue | Reste dans le même chat (aucune limite !) |
| Connaissances perso | Attache tes fichiers via le trombone 📎 |
| Résultat exécuté | Dis « exécute / lance / teste » pour déclencher le sandbox |
| Fichier livrable | Dis « génère / crée / fais-moi un [format] » |

---

**Dernière chose :** l'IA progresse quand tu progresses. Prends 5 minutes par semaine pour relire tes anciens chats — tu verras exactement où tu peux resserrer ton prompt la fois suivante.

Bon forgeage 🛠️ — *l'équipe CodeForge AI*
