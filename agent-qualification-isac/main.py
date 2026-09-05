"""Points d'entrée HTTP pour Google Cloud Functions (2ᵉ génération).

Ce fichier ne contient aucune logique métier : il vérifie la signature
de la requête, adapte les handlers (handlers/) au format attendu par
Cloud Functions, et traduit les erreurs en codes HTTP.
"""

import logging
import os

import functions_framework

from handlers.calcom_webhook import gerer_webhook_calcom
from handlers.signatures import verifier_signature_calcom, verifier_signature_tally
from handlers.tally_webhook import gerer_webhook_tally

EVENEMENT_CALCOM_ATTENDU = "BOOKING_CREATED"


@functions_framework.http
def tally_webhook_http(request):
    """Entrée du webhook Tally (soumission du formulaire de
    pré-qualification)."""
    secret = os.getenv("TALLY_SIGNING_SECRET")
    signature = request.headers.get("Tally-Signature")
    if not secret or not verifier_signature_tally(request.get_data(), signature, secret):
        logging.warning("Signature Tally invalide ou absente. Reçu : %r", signature)
        return ("Signature invalide.", 401)

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
    secret = os.getenv("CALCOM_SIGNING_SECRET")
    signature = request.headers.get("X-Cal-Signature-256")
    if not secret or not verifier_signature_calcom(request.get_data(), signature, secret):
        logging.warning("Signature Cal.com invalide ou absente. Reçu : %r", signature)
        return ("Signature invalide.", 401)

    payload = request.get_json(silent=True)
    if payload is None:
        return ("Corps de requête JSON invalide ou absent.", 400)

    # Le webhook peut être configuré sur plusieurs types d'événements
    # (annulation, replanification...) : on ne traite que les nouvelles
    # réservations, le reste est acquitté sans déclencher le flux.
    if payload.get("triggerEvent") != EVENEMENT_CALCOM_ATTENDU:
        return ("OK (événement ignoré)", 200)

    try:
        gerer_webhook_calcom(payload)
    except ValueError as erreur:
        return (str(erreur), 400)

    return ("OK", 200)
