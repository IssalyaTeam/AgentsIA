# Agent Blake — Qualification de cabinets de conseil (prospection)

Remplace le scénario Make 2 (~14 modules, 10 crédits Make/prospect) par un
unique endpoint HTTP : scraping → extraction → qualification. Make garde la
main sur l'écriture Google Sheets, la notification Slack et les retries — cet
agent ne fait que qualifier un prospect à partir du contrat JSON défini
ci-dessous ; il ne connaît ni Sheets ni Slack.

## ⚠️ État d'avancement — bloc de prompt incomplet

`engine/qualification.py` contient un **TODO explicite** à la place des
« étapes 0‑4 » du prompt de qualification (règles de filtrage par
spécialité/taille, critères IA, segment). Le texte exact utilisé aujourd'hui
dans le scénario Make n'a pas encore été fourni verbatim — voir le
commentaire en tête de `PROMPT_TEMPLATE` dans ce fichier.

Tant que ce bloc n'est pas complété :
- Le pipeline est fonctionnel de bout en bout (scraping, extraction, appel
  Claude, parsing, anti-hallucination, endpoint HTTP) et entièrement testé.
- Les 6 tests de non-régression (`tests/test_qualification.py`, marqués
  `@pytest.mark.skip`) ne peuvent pas être considérés comme fiables : ils
  sont écrits et prêts, mais désactivés tant que la logique métier réelle
  n'est pas injectée dans le prompt.
- **Ne pas déployer en production** avant d'avoir complété ce bloc et
  réactivé/validé les 6 cas de non-régression.

## Architecture

```
engine/
  scraping.py        # un seul appel HTTP -> HTML brut
  extraction.py       # HTML -> texte, titre, signaux de taille/groupe (regex)
  qualification.py    # prompt -> appel Claude -> parsing -> anti-hallucination
connectors/
  http_endpoint.py    # endpoint HTTP POST /qualifier, orchestre le pipeline
tests/
  test_extraction.py    # déterministe, TDD avant code
  test_qualification.py # déterministe (parsing/template) + non déterministe (marqueur `api`)
```

## Contrat de l'endpoint

`POST /qualifier`

Entrée (JSON envoyé par Make) :
```json
{
  "nom_cabinet": "string",
  "site_web": "string (URL)",
  "effectif_pappers": "number ou null",
  "objet_social_pappers": "string",
  "siren": "string"
}
```

Sortie :
```json
{
  "effectif": "string",
  "verdict": "BON FIT / FIT EDGE / HORS ICP - <raison> / EFFECTIF NON VÉRIFIABLE / CONTENU INSUFFISANT",
  "segment": "string ou \"\"",
  "signal_ia": "string",
  "justification": "string"
}
```

`GET /healthz` → `{"status": "ok"}`.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `ANTHROPIC_API_KEY` | Clé API Claude (jamais loguée, jamais en dur) |
| `ANTHROPIC_MODEL` | Modèle utilisé (défaut : `claude-sonnet-5`) |
| `PORT` | Port HTTP (injecté automatiquement par Railway/Render) |
| `WEB_CONCURRENCY` | Nombre de workers Gunicorn (optionnel, défaut 2) |

Pas de `SLACK_WEBHOOK_URL` ni de credentials Google Sheets ici : ces
intégrations restent côté Make, en dehors du périmètre de cet endpoint (voir
plus haut). Si ça doit changer, il faut me le signaler avant d'ajouter quoi
que ce soit — pas d'ajout par anticipation.

## Développement et tests

```bash
cd agent-blake-prospection
pip install -r requirements.txt

pytest tests/ -v -m "not api"   # déterministe, gratuit (CI)
pytest tests/ -v -m "api"       # appelle réellement Claude, payant, local uniquement
```

## Déploiement (Railway / Render)

- `Dockerfile` minimal (Python 3.11-slim, `pip install -r requirements.txt`).
- `start.sh` lance Gunicorn sur `$PORT`, agnostique à la plateforme.
- Les deux plateformes injectent `PORT` et les variables d'environnement
  définies dans leur dashboard — aucun secret dans le dépôt.
