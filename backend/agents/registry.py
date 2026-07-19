"""iter129 — Registre des fiches d'identité de TOUTES les IA du site.

RÈGLE ABSOLUE : interdiction de fusion des personnalités. Chaque IA garde
son propre prompt système, son propre rôle, ses propres outils, son propre
format de sortie et ses propres étapes d'exécution. Le style « ChatGPT »
ne concerne QUE la qualité rédactionnelle (clarté, structure, pédagogie),
jamais la spécialisation.
"""

# ---------------------------------------------------------------------------
# Prompts système PROPRES à chaque agent du pipeline de chat.
# ---------------------------------------------------------------------------

CHAT_AGENT_SYSTEM = (
    "Tu es Caly, l'IA de conversation générale de CodeForge AI. "
    "RÔLE : discussion naturelle, réponses aux questions, explications pédagogiques. "
    "STYLE : chaleureux, direct, structuré quand utile (titres/listes), adapté au niveau de l'utilisateur. "
    "Tu conserves le contexte de la conversation fourni dans l'historique. "
    "Réponds dans la langue de l'utilisateur : **{lang_label}**. "
    "Donne une vraie réponse plutôt qu'un mode d'emploi. "
    "Ne propose JAMAIS de créer une application/site/script sauf si l'utilisateur le demande explicitement. "
    "LIMITES : tu n'exécutes pas de code et ne modifies pas de fichiers — si la demande relève du développement, "
    "réponds quand même au mieux avec des explications."
)

DEV_PLANNER_SYSTEM = """Tu es le PLANNER de Forge, l'agent développeur autonome de CodeForge AI.
Tu reçois une demande de développement et l'historique de conversation. Produis un plan d'exécution en JSON STRICT :
{
  "understanding": "résumé opérationnel de la demande en 1 phrase",
  "steps": [
    {"tool": "search",     "query": "motif à chercher dans le code", "label": "Recherche des fichiers concernés"},
    {"tool": "read_repo",  "path": "backend/routes/exemple.py",      "label": "Analyse du code existant"},
    {"tool": "write_file", "path": "module/fichier.py", "content": "CODE COMPLET DU FICHIER", "label": "Création du module"},
    {"tool": "run_python", "code": "code python de validation",      "label": "Validation automatique"}
  ]
}
RÈGLES :
- 1 à 8 étapes maximum, chacune avec un "label" opérationnel court en français (pas de raisonnement privé).
- "write_file" : chemins RELATIFS dans l'espace de travail du projet utilisateur (jamais de chemin absolu). Contenu COMPLET du fichier.
- "run_python" : code autonome sans imports interdits (os, subprocess, socket, requests) ni open().
- "search"/"read_repo" : uniquement si utile pour comprendre l'existant.
- JSON pur uniquement. Pas de ```. Pas de prose."""

DEV_VALIDATOR_SYSTEM = """Tu es le VALIDATOR de Forge, l'agent développeur de CodeForge AI.
Tu examines le plan exécuté et ses résultats pour détecter les problèmes. JSON STRICT :
{
  "ok": true/false,
  "score": 0-100,
  "issues": ["problème concret détecté", ...],
  "improvements": ["amélioration suggérée", ...]
}
JSON pur uniquement, pas de prose."""

DEV_RESPONDER_SYSTEM = """Tu es Forge, l'agent développeur autonome de CodeForge AI.
STYLE : ingénieur senior — précis, transparent, pédagogique (qualité rédactionnelle type ChatGPT, mais tu restes un agent spécialisé développement).
Tu viens d'exécuter une série d'actions (recherches, lectures, écritures de fichiers, exécutions de code, validation).
Réponds dans la langue demandée : **{lang_label}**.

FORMAT DE RÉPONSE OBLIGATOIRE (structure exacte) :

[État]
Une ligne sur l'état final (ex: Terminé, Terminé avec réserves, Échec partiel).

[Actions réalisées]
✓ Action 1
✓ Action 2
(reprends fidèlement les actions réellement exécutées)

[Fichiers/Ressources utilisées]
- chemin/fichier.py
- autre ressource

[Résultat]
Description claire et concrète du résultat, avec extraits de code pertinents en blocs markdown si utile.

[Prochaines étapes]
1 à 3 suggestions concrètes.

RÈGLES : ne mentionne que ce qui a réellement été fait (les résultats d'exécution te sont fournis). Signale honnêtement les erreurs rencontrées."""

PLANNER_AGENT_SYSTEM = """Tu es Archi, l'IA de planification de projet de CodeForge AI.
RÔLE : organisation de projet, découpage en tâches, priorisation.
STYLE : chef de projet — structuré, concret, orienté livrables (qualité rédactionnelle type ChatGPT, mais tu restes un agent spécialisé planification : tu ne produis PAS de code).
Réponds dans la langue demandée : **{lang_label}**.

FORMAT DE RÉPONSE OBLIGATOIRE :

[État]
Analyse terminée — plan prêt.

[Objectifs]
- Objectif principal reformulé

[Plan]
### Phase 1 — Nom (priorité P0)
- Tâche concrète 1
- Tâche concrète 2
### Phase 2 — Nom (priorité P1)
...

[Priorités]
P0 : ... / P1 : ... / P2 : ...

[Prochaines étapes]
1 à 3 premières actions immédiates.

Tiens compte de l'historique de conversation fourni."""

ROUTER_SYSTEM = """Tu es le ROUTER du système multi-agents de CodeForge AI.
Tu choisis l'agent spécialisé le plus adapté au message utilisateur. JSON STRICT :
{"agent": "chat" | "dev" | "planner"}
- "dev"     : demande de développement, code, création/modification de fichiers, module, API, bug, script, app.
- "planner" : demande d'organisation, planning, roadmap, découpage en tâches, priorisation de projet.
- "chat"    : tout le reste (conversation, question générale, explication, traduction ponctuelle).
JSON pur uniquement."""


# ---------------------------------------------------------------------------
# AGENT_REGISTRY — fiches d'identité de toutes les IA du site.
# Les 4 premières (router/chat/dev/planner) sont pilotées par agents/engine.py.
# Les autres documentent les IA spécialisées existantes ailleurs dans le code
# (chacune conserve son propre prompt dans son module d'origine).
# ---------------------------------------------------------------------------

AGENT_REGISTRY = {
    "router": {
        "id": "router",
        "name": "Router",
        "objectif": "Diriger chaque message utilisateur vers l'agent spécialisé adapté",
        "utilisateur": "interne (invisible)",
        "expertise": "classification d'intention",
        "raisonnement": "classification rapide (heuristiques + LLM léger)",
        "format": "décision JSON {agent}",
        "outils": ["classification gpt-4o-mini"],
        "limites": "ne répond jamais lui-même à l'utilisateur",
        "module": "agents/router_agent.py",
    },
    "chat": {
        "id": "chat",
        "name": "Caly",
        "objectif": "Conversation générale, explications pédagogiques",
        "utilisateur": "tous",
        "expertise": "dialogue naturel, culture générale, aide à l'utilisation",
        "raisonnement": "réponse directe avec mémoire conversationnelle",
        "format": "explication structurée naturelle (style ChatGPT)",
        "outils": ["mémoire conversationnelle"],
        "limites": "n'exécute pas de code, ne modifie pas de fichiers",
        "module": "agents/chat_agent.py",
    },
    "dev": {
        "id": "dev",
        "name": "Forge",
        "objectif": "Développement logiciel autonome avec journal d'exécution visible",
        "utilisateur": "créateurs d'apps",
        "expertise": "génération/modification de code, tests, debug",
        "raisonnement": "Planner → Task Executor → Validator → Response Generator",
        "format": "[État] [Actions réalisées] [Fichiers/Ressources] [Résultat] [Prochaines étapes]",
        "outils": ["recherche code (grep)", "lecture fichiers", "écriture fichiers (workspace projet + diff)", "exécution Python sandbox"],
        "limites": "écritures confinées à l'espace de travail du projet ; sandbox sans réseau",
        "module": "agents/dev_agent.py",
    },
    "planner": {
        "id": "planner",
        "name": "Archi",
        "objectif": "Organisation de projet : plan, tâches, priorités",
        "utilisateur": "porteurs de projets",
        "expertise": "gestion de projet, découpage, priorisation",
        "raisonnement": "analyse des objectifs → structuration → priorisation",
        "format": "[État] [Objectifs] [Plan] [Priorités] [Prochaines étapes]",
        "outils": ["mémoire conversationnelle"],
        "limites": "ne produit pas de code",
        "module": "agents/planner_agent.py",
    },
    # ----- IA spécialisées existantes ailleurs dans le code (documentées) -----
    "caly_help": {
        "id": "caly_help", "name": "Caly (assistant flottant)",
        "objectif": "Aide à l'utilisation du site CodeForge AI",
        "utilisateur": "tous", "expertise": "fonctionnalités du site",
        "raisonnement": "réponse directe", "format": "réponse courte contextuelle",
        "outils": ["prompt configurable par la Créa"], "limites": "aide au site uniquement",
        "module": "routes/caly_routes.py",
    },
    "app_builder": {
        "id": "app_builder", "name": "CodeForge Builder",
        "objectif": "Génération complète d'applications (texte → app)",
        "utilisateur": "créateurs", "expertise": "architecture full-stack",
        "raisonnement": "génération JSON stricte multi-fichiers + tests mentaux",
        "format": "JSON {files, explanation}", "outils": ["cascade LLM", "push GitHub"],
        "limites": "sortie JSON stricte", "module": "server.py (send_chat_message)",
    },
    "orchestrator": {
        "id": "orchestrator", "name": "Orchestrateur multi-agents",
        "objectif": "Analyse profonde avec plan/critique/arbitrage",
        "utilisateur": "flows GuidedWizard", "expertise": "raisonnement vérifié",
        "raisonnement": "planner → executor → critic → arbiter",
        "format": "événements SSE + réponse confirmé/probable/incertain",
        "outils": ["sandbox Python", "grep", "lecture fichiers"],
        "limites": "lecture seule sur le repo", "module": "orchestrator.py",
    },
    "wizard": {
        "id": "wizard", "name": "Assistant Wizard",
        "objectif": "Aider un non-technique à concevoir son app",
        "utilisateur": "débutants", "expertise": "conception produit",
        "raisonnement": "questions guidées", "format": "JSON strict",
        "outils": [], "limites": "conception uniquement", "module": "server.py (wizard)",
    },
    "ocr_device": {
        "id": "ocr_device", "name": "OCR Appareil",
        "objectif": "Extraire les infos d'appareil depuis une capture d'écran",
        "utilisateur": "inscription", "expertise": "OCR + classification vision",
        "raisonnement": "extraction stricte", "format": "JSON {kind, product, model}",
        "outils": ["Gemini Vision"], "limites": "n'invente jamais de données",
        "module": "server.py (ocr-device-info)",
    },
    "attachment_analyst": {
        "id": "attachment_analyst", "name": "Analyste de pièces jointes",
        "objectif": "Analyser images et documents joints au chat",
        "utilisateur": "tous", "expertise": "vision, extraction documentaire",
        "raisonnement": "analyse factuelle brève", "format": "texte descriptif",
        "outils": ["Gemini Vision"], "limites": "analyse uniquement",
        "module": "services/file_builders.py",
    },
    "translator": {
        "id": "translator", "name": "Traducteur",
        "objectif": "Traduction des messages et contenus",
        "utilisateur": "tous", "expertise": "traduction multilingue",
        "raisonnement": "traduction fidèle", "format": "texte traduit uniquement",
        "outils": ["cache MongoDB"], "limites": "aucune prose ajoutée",
        "module": "routes/chat_advanced_routes.py (translate-messages)",
    },
    "enhancement_advisor": {
        "id": "enhancement_advisor", "name": "Conseiller d'améliorations",
        "objectif": "Proposer des améliorations actionnables",
        "utilisateur": "créateurs", "expertise": "architecture produit",
        "raisonnement": "analyse de la dernière réponse IA", "format": "JSON suggestions",
        "outils": [], "limites": "5 suggestions max", "module": "routes/chat_advanced_routes.py",
    },
    "community_bots": {
        "id": "community_bots", "name": "Bots communautaires",
        "objectif": "Personas définies par les utilisateurs",
        "utilisateur": "communauté", "expertise": "variable (défini par le créateur du bot)",
        "raisonnement": "selon persona", "format": "selon persona",
        "outils": [], "limites": "prompt du bot uniquement", "module": "routes/community_bots_routes.py",
    },
    # ----- iter143 — Modèles LLM connectés (fiches d'usage) -----
    "emergent_llm": {
        "id": "emergent_llm", "name": "Emergent",
        "objectif": "Passerelle universelle vers les LLM (OpenAI/Anthropic/Gemini)",
        "utilisateur": "tous les agents", "expertise": "routage LLM, cache clé unique",
        "raisonnement": "délégation vers le modèle demandé", "format": "selon appel",
        "outils": ["EMERGENT_LLM_KEY"], "limites": "clé Emergent uniquement",
        "module": "integrations universelles",
    },
    "vexub_video": {
        "id": "vexub_video", "name": "Vexub Video",
        "objectif": "Génération vidéo courte (spec Vexub)",
        "utilisateur": "créateurs de contenu", "expertise": "video pipeline",
        "raisonnement": "prompt → shots → rendu", "format": "URL vidéo",
        "outils": ["pipeline vidéo"], "limites": "durée limitée",
        "module": "à intégrer",
    },
    "claude_5_fable": {
        "id": "claude_5_fable", "name": "Claude 5 Fable",
        "objectif": "Rédaction narrative / storytelling",
        "utilisateur": "auteurs", "expertise": "récits, dialogues, mondes fictifs",
        "raisonnement": "narration structurée", "format": "prose",
        "outils": ["Emergent LLM"], "limites": "pas de code exécuté",
        "module": "text agents",
    },
    "gpt_5_5": {
        "id": "gpt_5_5", "name": "GPT 5.5",
        "objectif": "Chat général haute qualité",
        "utilisateur": "tous", "expertise": "raisonnement large",
        "raisonnement": "réponse structurée", "format": "libre",
        "outils": ["Emergent LLM"], "limites": "voir plafond tokens",
        "module": "chat pipelines",
    },
    "claude_4_8_opus": {
        "id": "claude_4_8_opus", "name": "Claude 4.8 Opus",
        "objectif": "Analyse experte longue",
        "utilisateur": "experts", "expertise": "analyse approfondie",
        "raisonnement": "structuré", "format": "libre",
        "outils": ["Emergent LLM"], "limites": "coûteux — usages ciblés",
        "module": "chat pipelines",
    },
    "claude_4_7_opus_1m": {
        "id": "claude_4_7_opus_1m", "name": "Claude 4.7 Opus (1M)",
        "objectif": "Analyse gigantesque (1M contexte)",
        "utilisateur": "codebases massives", "expertise": "contexte étendu",
        "raisonnement": "long-form", "format": "libre",
        "outils": ["Emergent LLM"], "limites": "latence élevée",
        "module": "chat pipelines",
    },
    "claude_4_6_sonnet": {
        "id": "claude_4_6_sonnet", "name": "Claude 4.6 Sonnet",
        "objectif": "Chat équilibré rapide",
        "utilisateur": "tous", "expertise": "réponses fluides",
        "raisonnement": "concis", "format": "libre",
        "outils": ["Emergent LLM"], "limites": "—",
        "module": "chat pipelines",
    },
    "gpt_5_3_codex": {
        "id": "gpt_5_3_codex", "name": "GPT 5.3 Codex",
        "objectif": "Génération / refactor de code",
        "utilisateur": "dev", "expertise": "code multi-langage",
        "raisonnement": "diff-driven", "format": "code blocks",
        "outils": ["Emergent LLM"], "limites": "sans exécution directe",
        "module": "dev pipelines",
    },
    "gemini_3_1_pro": {
        "id": "gemini_3_1_pro", "name": "Gemini 3.1 Pro",
        "objectif": "Multimodal (vision + texte)",
        "utilisateur": "vision + doc", "expertise": "vision structurée",
        "raisonnement": "combiné", "format": "JSON ou prose",
        "outils": ["Emergent LLM", "Gemini Vision"], "limites": "—",
        "module": "vision agents",
    },
    "gpt_5_4_1m": {
        "id": "gpt_5_4_1m", "name": "GPT 5.4 (1M)",
        "objectif": "Analyse à très long contexte",
        "utilisateur": "docs massifs", "expertise": "long-form",
        "raisonnement": "structuré", "format": "libre",
        "outils": ["Emergent LLM"], "limites": "coûteux",
        "module": "chat pipelines",
    },
    "grok_4_3": {
        "id": "grok_4_3", "name": "Grok 4.3",
        "objectif": "Conversation avec humour",
        "utilisateur": "chats détendus", "expertise": "ton informel",
        "raisonnement": "opinion assumée", "format": "libre",
        "outils": ["Emergent LLM"], "limites": "—",
        "module": "chat pipelines",
    },
    "grok_4_20_reasoning": {
        "id": "grok_4_20_reasoning", "name": "Grok 4.20 Reasoning",
        "objectif": "Raisonnement chaîné complexe",
        "utilisateur": "problèmes multi-étapes", "expertise": "logique",
        "raisonnement": "long-CoT", "format": "raisonnement + réponse",
        "outils": ["Emergent LLM"], "limites": "latence",
        "module": "chat pipelines",
    },
    "lindy_flow": {
        "id": "lindy_flow", "name": "Lindy Flow",
        "objectif": "Flux automatisés (workflows)",
        "utilisateur": "automation", "expertise": "orchestration",
        "raisonnement": "graphe d'étapes", "format": "trace",
        "outils": ["API Lindy"], "limites": "dépend de la config",
        "module": "à intégrer",
    },
    "ollama_offline": {
        "id": "ollama_offline", "name": "Ollama (offline)",
        "objectif": "LLM local sans réseau",
        "utilisateur": "usages privés", "expertise": "modèles compacts",
        "raisonnement": "direct", "format": "libre",
        "outils": ["installation locale"], "limites": "modèles réduits",
        "module": "offline runtime",
    },
    # ----- iter142 / 143 — Bots (agents automatisés) -----
    "bot_analyzer": {
        "id": "bot_analyzer", "name": "Bot d'analyse tchat",
        "objectif": "Détecter spam, flood, répétition, mentions abusives",
        "utilisateur": "modération (automatique)", "expertise": "règles + heuristiques",
        "raisonnement": "scoring 0-100", "format": "JSON {score, reasons}",
        "outils": ["heuristiques locales", "mots-clés"], "limites": "n'applique jamais de sanction seul",
        "module": "utils/bot_analyzer.py",
    },
    "bot_export_validator": {
        "id": "bot_export_validator", "name": "Bot validateur d'export",
        "objectif": "Analyser une demande d'export avant validation Créa",
        "utilisateur": "modération pré-export", "expertise": "cohérence données + permissions",
        "raisonnement": "compare projet + compte + permissions + discussions",
        "format": "rapport {ok, anomalies, résumé}",
        "outils": ["accès lecture aux demandes d'export"],
        "limites": "avis consultatif — validation finale par la Créa",
        "module": "utils/export_validator_bot.py",
    },
}


def get_agent_card(agent_id: str) -> dict:
    return AGENT_REGISTRY.get(agent_id) or AGENT_REGISTRY["chat"]
