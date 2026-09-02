"""Connecteur Cal.com : extrait les informations utiles d'un webhook
BOOKING_CREATED (réservation d'un ISAC).

Ce module est le seul de connectors/ à connaître la forme des webhooks
Cal.com (payload.attendees...). Le moteur ne reçoit jamais cette forme
brute — Cal.com ne fournit qu'un identifiant (l'email) pour corréler
avec la réponse Tally, jamais de données de qualification.
"""


def _premier_participant(payload_webhook: dict) -> dict | None:
    attendees = payload_webhook.get("payload", {}).get("attendees", [])
    return attendees[0] if attendees else None


def extraire_email_participant(payload_webhook: dict) -> str | None:
    """Extrait l'email de la personne qui a réservé, utilisé pour corréler
    la réservation à une réponse Tally. Retourne None si absent.
    """
    participant = _premier_participant(payload_webhook)
    return (participant or {}).get("email") or None


def extraire_nom_participant(payload_webhook: dict) -> str | None:
    """Extrait le nom de la personne qui a réservé (affichage/logs)."""
    participant = _premier_participant(payload_webhook)
    return (participant or {}).get("name") or None
