"""Extraction de JSON depuis une réponse texte de Claude.

Utilitaire partagé par tous les modules du moteur qui demandent une
réponse structurée à l'API (qualification.py, interpretation.py...).
"""

import json
import re


def extraire_json(texte: str) -> dict:
    """Extrait l'objet JSON de la réponse, en tolérant deux artefacts
    fréquents des modèles de langage malgré la consigne de ne renvoyer
    que du JSON brut : les balises markdown (```json ... ```) et les
    virgules finales avant une accolade/crochet fermant.
    """
    correspondance = re.search(r"\{.*\}", texte, re.DOTALL)
    if not correspondance:
        raise ValueError(f"Réponse de Claude sans JSON exploitable : {texte!r}")
    brut = correspondance.group(0)
    nettoye = re.sub(r",(\s*[}\]])", r"\1", brut)
    return json.loads(nettoye)
