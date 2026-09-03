"""Points d'entrée HTTP pour Google Cloud Functions (2ᵉ génération).

Ce fichier ne contient aucune logique métier : il adapte les handlers
(handlers/) au format attendu par Cloud Functions — une requête HTTP en
entrée, une réponse HTTP en sortie. Deux fonctions, deux déploiements
séparés (--entry-point=tally_webhook_http ou =calcom_webhook_http).
"""

import functions_framework

from handlers.calcom_webhook import gerer_webhook_calcom
from handlers.tally_webhook import gerer_webhook_tally


@functions_framework.http
def tally_webhook_http(request):
    """Entrée du webhook Tally (soumission du formulaire de
    pré-qualification)."""
    payload = request.get_json(silent=True)
    if payload is None:
        return ("Corps de requête JSON invalide ou absent.", 400)

    try:
        gerer_webhook_tally(payload)
    except ValueError as erreur:
        return (str(erreur), 400)

    return ("OK", 200)


@functions_framework.http
def calcom_webhook_http(request):
    """Entrée du webhook Cal.com (réservation ISAC créée)."""
    payload = request.get_json(silent=True)
    if payload is None:
        return ("Corps de requête JSON invalide ou absent.", 400)

    try:
        gerer_webhook_calcom(payload)
    except ValueError as erreur:
        return (str(erreur), 400)

    return ("OK", 200)
