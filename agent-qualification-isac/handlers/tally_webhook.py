"""Point d'entrée : webhook Tally (soumission du formulaire de
pré-qualification).

Stocke la réponse en attente d'une réservation Cal.com corrélée par
email. Ne calcule rien, ne connaît pas le moteur.
"""

from connectors import google_sheets, tally


def gerer_webhook_tally(payload_webhook: dict, enregistrer=None) -> None:
    """Extrait l'email, le nom d'entreprise et les réponses d'un webhook
    Tally, puis les stocke en attente d'une réservation Cal.com.
    """
    enregistrer = enregistrer or google_sheets.enregistrer_reponse_tally_en_attente

    email = tally.extraire_email(payload_webhook)
    if not email:
        raise ValueError("Impossible d'identifier l'email du répondant dans ce webhook Tally.")

    enregistrer(
        email=email,
        nom_entreprise=tally.extraire_nom_entreprise(payload_webhook) or "",
        reponses_formulaire=tally.extraire_reponses_formulaire(payload_webhook),
    )
