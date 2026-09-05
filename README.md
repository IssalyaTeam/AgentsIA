# AgentsIA

Monorepo des agents IA d'Issalya. Chaque agent répond à **un seul objectif
métier** et vit dans son propre dossier à la racine du dépôt :

```
AgentsIA/
  agent-qualification-isac/          Agent Qualification ISAC
    engine/                          Logique métier (scoring, red flags, interprétation LLM...)
    connectors/                      Intégrations externes (Cal.com, Tally, Pappers, Google Sheets, Slack)
    handlers/                        Orchestration des webhooks (adapte connectors/ + engine/)
    tests/
    main.py                          Points d'entrée HTTP (Google Cloud Functions)
    requirements.txt
    .env.example

  agent-blake-prospection/           Agent Qualification Prospection (en développement)
    engine/
    connectors/
    tests/

  shared/                            Vide pour l'instant (voir plus bas)
```

## Principe : un dossier = un agent, autonome et à objectif unique

- Chaque agent a sa propre structure `engine/` (logique métier), `connectors/`
  (intégrations externes) et `tests/`, et gère ses propres dépendances
  (`requirements.txt`), sa propre configuration (`.env.example`) et son
  propre point d'entrée de déploiement.
- **Polyvalence exclue** : un agent ne doit pas chercher à couvrir plusieurs
  objectifs métier à la fois. L'Agent Qualification ISAC qualifie les
  prospects entrants (webhooks Tally + Cal.com) ; l'Agent Qualification
  Prospection qualifiera les prospects sourcés (scraping, extraction,
  qualification via l'API Claude). Ce sont deux agents distincts, pas deux
  fonctionnalités d'un même agent.
- Cette autonomie par dossier prépare le passage en dépôts séparés au moment
  de la V2 Marketplace, quand un agent devra être livré/déployé de façon
  indépendante chez un client. Tant qu'on est en V1 interne (avant la
  signature d'un premier client), on reste en monorepo.

## `shared/`

Vide intentionnellement. Ce dossier ne sert qu'à signaler l'intention : si du
code générique émerge naturellement entre plusieurs agents (ex. logique de
parsing de sortie IA, gestion des retries HTTP), il sera remonté ici — mais
jamais par anticipation, seulement quand un besoin concret et partagé est
constaté.

## Développement et tests

Chaque agent se développe et se teste depuis son propre dossier :

```bash
cd agent-qualification-isac
pip install -r requirements.txt
pytest tests/ -v -m "not api"
```

Le déploiement (Google Cloud Functions) se fait aussi depuis le dossier de
l'agent concerné, en pointant `--source` sur ce dossier.
