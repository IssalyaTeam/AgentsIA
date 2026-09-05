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
on accepte cette latence plutôt que de réduire le prompt. En conséquence,
trois timeouts en cascade doivent tous être supérieurs à la latence réelle
du pipeline, chacun avec de la marge sur le suivant :

| Niveau | Valeur | Configuré où |
|---|---|---|
| Module HTTP Make (appelle cet endpoint) | **60s** | Dans le scénario Make lui-même — je n'ai pas accès à Make depuis ce dépôt, c'est un réglage manuel à faire côté Make |
| Applicatif (Gunicorn, `start.sh`) | **90s** | `start.sh` de ce dépôt, déjà réglé |
| Hosting (plateforme de déploiement) | *voir ci-dessous* | Dépend de la plateforme choisie |

**Hosting — je ne peux pas confirmer que c'est au-dessus de 30s pour toutes les plateformes**, rien n'étant encore déployé pour le vérifier en conditions réelles. D'après la documentation actuelle de chaque plateforme (recherche faite au moment d'écrire ceci, sources en fin de section) :

- **Railway** : timeout de requête HTTP publique de 5 minutes (300s) — largement suffisant, aucune action requise.
- **Google Cloud Function (2ᵉ génération)** : timeout par défaut de 60s, configurable jusqu'à 60 minutes via `--timeout` au déploiement (`gcloud functions deploy ... --timeout=90s`) — à régler explicitement au-dessus du défaut pour garder la marge.
- **Render** : ⚠️ **risque réel**. Plusieurs retours (forum communautaire Render, pas de documentation officielle contredisant ces retours trouvée) indiquent un timeout de proxy imposé par la plateforme autour de 15-30s sur les web services, **non configurable** par l'utilisateur sur les offres standards. Si Blake est déployé sur Render, une réponse qui prend 20-60s (notre cas normal, pas un incident) risque d'être coupée par la plateforme avant même d'atteindre les 60s du timeout Make — indépendamment de tout ce qu'on règle dans `start.sh`.

Sources : [Specs & Limits — Railway Docs](https://docs.railway.com/networking/public-networking/specs-and-limits) · [Configure Cloud Functions timeout](https://cloud.google.com/functions/docs/configuring/timeout) · [15 second request timeout — Render community](https://community.render.com/t/15-second-request-timeout/568) · [Can I configure web service timeout — Render community](https://render.discourse.group/t/can-i-configure-web-service-timeout/18233)

**Recommandation** : si le choix de plateforme n'est pas encore figé, privilégier Railway ou Cloud Function plutôt que Render pour cet agent, vu la latence assumée. Si Render est néanmoins retenu, il faut le valider par un test réel en conditions de prod (une requête qui prend ~20-30s) avant la mise en production — je ne peux pas m'y substituer sans y déployer.

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

**⚠️ Écart à corriger avant un déploiement réel — pas fait dans le cadre de
cette tâche, je n'ai pas voulu l'ajouter sans que ce soit demandé :**
`connectors/http_endpoint.py` expose actuellement une app Flask classique
(routes `/qualifier`, `/healthz`, lancée via Gunicorn) — un modèle pensé pour
un hébergement conteneur générique (Railway/Render, cf. `Dockerfile` et
`start.sh`), pas pour `gcloud functions deploy --source=.`, qui construit via
buildpacks et attend un point d'entrée unique décoré
`@functions_framework.http` (exactement comme `main.py` de l'Agent
Qualification ISAC). En l'état, `gcloud functions deploy` avec
`--entry-point=qualifier_prospect_http` échouera : cette fonction n'existe
pas encore sous cette forme. Il faudra soit adapter `http_endpoint.py` à ce
pattern (le plus cohérent avec l'ISAC), soit déployer via Cloud Run plutôt
que Cloud Functions (qui, lui, accepte un Dockerfile). `Dockerfile` et
`start.sh` deviennent alors inutiles si on part sur l'option
`functions_framework`.
