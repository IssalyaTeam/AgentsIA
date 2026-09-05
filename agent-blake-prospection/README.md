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

### Point d'attention — contrainte de performance ≤4s non tenue (arbitrage acté)

Latence Claude seule observée : 6 à 20s selon les cas (prompt volumineux,
~27 000 caractères, gardé tel quel sur décision explicite). Décision actée :
on accepte cette latence plutôt que de réduire le prompt. Hébergement
confirmé : Cloud Functions 2ᵉ gen (voir "Déploiement" plus bas), pas de
couche applicative intermédiaire (Gunicorn) à régler séparément — deux
niveaux de timeout à tenir, chacun avec de la marge sur le suivant :

| Niveau | Valeur | Configuré où |
|---|---|---|
| Module HTTP Make (appelle cet endpoint) | **60s** | Dans le scénario Make lui-même — je n'ai pas accès à Make depuis ce dépôt, c'est un réglage manuel à faire côté Make quand le scénario existera |
| Cloud Function (`--timeout`) | **90s** | À passer explicitement au déploiement (voir "Déploiement" plus bas) — le défaut Cloud Functions 2ᵉ gen est 60s, pile à la limite du pire cas pipeline (~63s), sans marge |

## Architecture

```
engine/
  scraping.py                # un seul appel HTTP -> HTML brut
  extraction.py               # HTML -> texte, titre, signaux de taille/groupe (regex)
  prompt_qualification.py     # texte verbatim du prompt (isolé pour rester <200 lignes/fichier)
  qualification.py            # templating -> appel Claude -> parsing -> anti-hallucination
connectors/
  http_endpoint.py    # point d'entrée functions_framework.http, orchestre le pipeline
tests/
  test_extraction.py    # déterministe, TDD avant code
  test_qualification.py # déterministe (parsing/template) + non déterministe (marqueur `api`)
```

## Contrat de l'endpoint

Point d'entrée unique `qualifier_prospect_http` (Cloud Function `2ᵉ gen`,
`functions_framework.http` — même modèle que `main.py` de l'Agent
Qualification ISAC). Cloud Functions ne route pas par chemin au sein d'une
même fonction déployée : toute requête POST vers l'URL de la fonction
l'atteint, quel que soit le chemin. Seule exception gérée explicitement :
`GET /healthz` → `{"status": "ok"}`.

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

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `ANTHROPIC_API_KEY` | Clé API Claude (jamais loguée, jamais en dur) |
| `ANTHROPIC_MODEL` | Modèle utilisé (défaut : `claude-sonnet-5`) |

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

## Déploiement — Google Cloud Function (2ᵉ génération)

Hébergement confirmé : Cloud Functions 2ᵉ gen, région `europe-west9`, même
pattern que l'Agent Qualification ISAC. Déploiement manuel via `gcloud
functions deploy` depuis Cloud Shell :

```bash
gcloud functions deploy agent-blake-qualifier \
  --gen2 \
  --runtime=python311 \
  --region=europe-west9 \
  --source=. \
  --entry-point=qualifier_prospect_http \
  --trigger-http \
  --timeout=90s \
  --set-env-vars=ANTHROPIC_MODEL=claude-sonnet-5 \
  --set-secrets=ANTHROPIC_API_KEY=projects/.../secrets/...:latest
```

`--timeout=90s` explicite car le défaut Cloud Functions 2ᵉ gen est 60s — pile
à la limite du pire cas pipeline (~63s), sans marge. À régler au-dessus à
chaque déploiement, ce n'est pas un défaut qu'on peut fixer une fois pour
toutes dans le code.

`connectors/http_endpoint.py` expose `qualifier_prospect_http`, décorée
`@functions_framework.http` — exactement le pattern de `main.py` de l'Agent
Qualification ISAC. Plus d'app Flask autonome, plus de Dockerfile/Gunicorn à
maintenir : `gcloud functions deploy --source=.` construit via buildpacks à
partir de `requirements.txt` et de ce point d'entrée, comme pour l'ISAC.
