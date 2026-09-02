"""Connecteur Tally : transforme un webhook Tally vers le format générique
attendu par le moteur (ContexteProspect.reponses_formulaire).

Ce module est le seul de connectors/ à connaître la forme exacte des
webhooks Tally (data.fields, options par id...). Le moteur, lui, ne
reçoit jamais cette forme brute — uniquement le dict générique produit
ici.
"""

TYPES_A_EXCLURE = {"INPUT_EMAIL"}


def _resoudre_valeur(champ: dict) -> str:
    """Convertit la valeur brute d'un champ Tally en texte lisible.

    Pour les champs à choix (MULTIPLE_CHOICE, CHECKBOXES, DROPDOWN), Tally
    renvoie un ou plusieurs identifiants d'option : on les résout vers
    leur texte via la liste `options` du champ.
    """
    options = champ.get("options") or []
    options_par_id = {option["id"]: option["text"] for option in options}

    valeur = champ.get("value")
    if valeur is None:
        return ""

    if options_par_id:
        valeurs = valeur if isinstance(valeur, list) else [valeur]
        return ", ".join(options_par_id.get(v, v) for v in valeurs)

    if isinstance(valeur, list):
        return ", ".join(str(v) for v in valeur)

    return str(valeur)


def extraire_reponses_formulaire(payload_webhook: dict) -> dict[str, str]:
    """Extrait toutes les questions/réponses d'un webhook Tally, sous la
    forme {libellé de la question: réponse lisible}.

    Les champs d'identité sensibles sans valeur de qualification (email)
    sont exclus. Fonctionne pour n'importe quel formulaire Tally, sans
    connaissance des questions précises codée en dur.
    """
    champs = payload_webhook.get("data", {}).get("fields", [])

    reponses = {}
    for champ in champs:
        if champ.get("type") in TYPES_A_EXCLURE:
            continue
        label = champ.get("label") or champ.get("key", "Question sans libellé")
        reponses[label] = _resoudre_valeur(champ)

    return reponses
