# Agent Blake — Qualification de cabinets de conseil (prospection)

Remplace le scénario Make 2 (~14 modules, 10 crédits Make/prospect) par un
unique endpoint HTTP : scraping → extraction → qualification. Make garde la
main sur l'écriture Google Sheets, la notification Slack et les retries — cet
agent ne fait que qualifier un prospect à partir du contrat JSON défini
ci-dessous ; il ne connaît ni Sheets ni Slack.

## ✅ État d'avancement

Le prompt de qualification est complet (texte verbatim du scénario Make,
voir `engine/prompt_qualification.py`). Le pipeline est fonctionnel de bout
en bout (scraping, extraction, appel Claude, parsing, anti-hallucination,
endpoint HTTP). Les 38 tests déterministes et les 7 tests `api` (dont les 6
cas de non-régression) sont tous verts, validés avec une vraie clé Anthropic.

Trois bugs réels trouvés et corrigés pendant cette validation (avant, tout
échouait ou était non fiable en usage réel) :
- **Timeout Claude trop court** (3s) : le prompt fait ~27 000 caractères une
  fois construit, la latence réelle observée est de 6-20s selon les cas —
  bien au-dessus de la contrainte de performance visée (≤4s/prospect,
  scraping compris). Remonté ci-dessous en "Point d'attention".
- **`reponse.content[0]` supposé être le texte final** : peut être un bloc de
  raisonnement (`ThinkingBlock`) selon la réponse — `appeler_claude` filtre
  maintenant explicitement les blocs de type texte.
- **Faux positifs dans la validation anti-hallucination** : le "2" de
  "cabinet de conseil B2B" (vocabulaire du prompt lui-même, répété
  naturellement dans les Justifications) était détecté comme un chiffre
  métier halluciné. La validation ignore désormais les chiffres collés à des
  lettres (sigles) et les références internes à la grille ("Étape 2").

### ⚠️ Point d'attention — contrainte de performance ≤4s non tenue

Latence Claude seule observée : 6 à 20s selon les cas (prompt volumineux,
~27 000 caractères). Avec le scraping en amont, le total dépasse largement
la cible de 4s/prospect du cadrage initial. Ce n'est pas un bug côté agent —
c'est une conséquence directe de la taille du prompt fourni. À trancher avec
toi : réduire le prompt, accepter une latence plus réaliste (le webhook Make
attend simplement la réponse HTTP, un peu plus lentement), ou paralléliser
autrement.

## Architecture

```
engine/
  scraping.py                # un seul appel HTTP -> HTML brut
  extraction.py               # HTML -> texte, titre, signaux de taille/groupe (regex)
  prompt_qualification.py     # texte verbatim du prompt (isolé pour rester <200 lignes/fichier)
  qualification.py            # templating -> appel Claude -> parsing -> anti-hallucination
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
