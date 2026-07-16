# CHANGELOG — CodeForge AI
(Les itérations ≤128 sont documentées dans PRD.md. À partir d'iter129, les nouvelles entrées vont ici.)

## iter129 — Écosystème multi-agents spécialisés (2026-07-16)
**Demande** : « Je veux un système multi-agents spécialisé, pas un chatbot multi-personnalités. Chaque IA doit être un agent indépendant avec sa propre logique, son propre prompt système, ses propres outils et son propre workflow. » + moteur d'exécution visible (journal d'activité type Emergent/Cursor), format de réponse standardisé, architecture Router→Planner→Executor→Validator→Responder.
**Choix utilisateur** : 1a (workspace sandbox par projet), 2a (chat principal d'abord, Caly ensuite).

### Backend — package `/app/backend/agents/`
- `registry.py` : fiches d'identité des 13 IA du site (nom, objectif, expertise, raisonnement, format, outils, limites, module) + prompts système PROPRES à chaque agent (interdiction de fusion des personnalités, testée par pytest).
- `router_agent.py` : IA Router (heuristiques regex + classification gpt-4o-mini) → `chat` | `dev` | `planner`.
- `chat_agent.py` : **Caly** — conversation directe streamée, mémoire conversationnelle (12 derniers messages), pas de journal.
- `dev_agent.py` : **Forge** — Planner → Task Executor (grep, lecture repo, écriture workspace avec diff avant/après, sandbox Python) → Validator (score/issues) → Responder streamé au format `[État]/[Actions réalisées]/[Fichiers-Ressources utilisées]/[Résultat]/[Prochaines étapes]`.
- `planner_agent.py` : **Archi** — plan de projet `[État]/[Objectifs]/[Plan]/[Priorités]/[Prochaines étapes]`.
- `tools.py` : workspace sandbox `/app/agent_workspaces/{project_id}/` (create/modify + unified diff, anti-escape), réutilise `_read_file_safe`/`_grep_safe`/`_execute_python` d'orchestrator.py.
- `engine.py` : `run_pipeline()` — dispatch unifié, yields `{"agent"}` / `{"event"}` / `{"delta"}`.
- `routes/chat_advanced_routes.py` : `/chat/stream` rebranché sur le pipeline (événements SSE compacts + persistance `agent_events`/`agent_id` sur le message + détails complets dans `orchestrator_events` pour lazy-load) ; nouvel endpoint `GET /agents/registry`.

### Frontend
- `components/AgentActivityLog.jsx` : journal d'activité live dans la bulle IA — lignes dépliables (flèche >), diff coloré avec onglets diff/avant/après, spinner sur l'étape courante, header repliable, lazy-load des détails via `/orchestrate/event/{id}/details`.
- `pages/Chat.js` : gestion SSE `evt.agent`/`evt.event`/`evt.delta`, badge agent (`msg-agent-badge`), restauration du journal depuis l'historique, `data-testid="chat-send-btn"`.
- Fixes testing agent : clés React dupliquées (map messages + events), hydratation `<p>`→`<div>` dans MessageContent, clé i18n `chatLoadingHistory` (fr/en), skip traduction auto des sorties structurées d'agents (`useTranslatedMessages`).

### Tests
- `tests/test_iter129_agents.py` (14 tests) : registre complet, non-fusion des prompts, workspace diff + anti-escape, router heuristique, câblage routes/frontend.
- Tests obsolètes réparés (post-refacto iter123) : `test_iter114b_native_streaming.py`, `test_iter95` (2 endpoint checks), `test_iter110` (site/issues/create).
- Testing agent iteration_105 : 6/6 scénarios frontend PASS (Caly/Forge/Archi, diff, toggle, persistance après reload).

### Notes d'état
- `site_config.modes` laissé sur `['public']` (il avait été mis sur `['creator']` par des tests live antérieurs). À reconfigurer via le futur multi-select « Qui peut voir actuellement ».
- Le mot de passe du user de test a été resynchronisé (Pass1234) par le testing agent.
- Suite pytest complète : ~97 échecs PRÉEXISTANTS (tests live/stale des iters 22-62 dépendant d'états DB/SMTP), non liés à iter129.
