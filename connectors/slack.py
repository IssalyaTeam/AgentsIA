"""Connecteur Slack : envoie la fiche de synthèse sur un canal Slack,
avant l'appel ISAC.

Utilise un Incoming Webhook (une URL, pas de jeton de bot) : le plus
simple pour une notification à sens unique vers un canal fixe. Ce
module est le seul de connectors/ à connaître ce format.
"""

import os

import requests

URL_WEBHOOK_ENV = "SLACK_WEBHOOK_URL"

LIBELLES_DONNEES_MANQUANTES = {
    "reponses_tally": "réponses au formulaire de pré-qualification (Tally)",
    "donnees_pappers": "données publiques de l'entreprise (Pappers)",
}


def _construire_blocks(fiche) -> list[dict]:
    blocks = []

    if fiche.donnees_manquantes:
        libelles = [
            LIBELLES_DONNEES_MANQUANTES.get(cle, cle) for cle in fiche.donnees_manquantes
        ]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "⚠️ *Données manquantes* : " + ", ".join(libelles),
                },
            }
        )

    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Fiche de qualification — {fiche.nom_entreprise}",
            },
        }
    )

    blocks.append(
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Score ICP*\n{fiche.resultat_scoring.score}/20"},
                {"type": "mrkdwn", "text": f"*Priorité*\n{fiche.resultat_scoring.priorite}"},
            ],
        }
    )

    filtres_texte = (
        "Tous validés"
        if fiche.resultat_scoring.filtres_ok
        else "Échoués : " + ", ".join(fiche.resultat_scoring.filtres_echoues)
    )
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Filtres éliminatoires*\n{filtres_texte}"},
        }
    )

    red_flags = (
        fiche.resultat_red_flags.red_flags_entree_detectes
        + fiche.resultat_red_flags.red_flags_fit_isaa_detectes
    )
    red_flags_texte = ", ".join(red_flags) if red_flags else "aucun"
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Red flags*\n{red_flags_texte}"},
        }
    )

    blocks.append({"type": "divider"})

    enjeux = "\n".join(f"• {e}" for e in fiche.hypotheses.enjeux_probables) or "Aucun identifié"
    blocks.append(
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Enjeux probables*\n{enjeux}"}}
    )

    opportunites = (
        "\n".join(f"• {o}" for o in fiche.hypotheses.opportunites_probables)
        or "Aucune identifiée"
    )
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Opportunités probables*\n{opportunites}"},
        }
    )

    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Synthèse*\n{fiche.hypotheses.synthese}"},
        }
    )

    return blocks


def envoyer_fiche(fiche, poster=None) -> None:
    """Poste la fiche sur le canal Slack configuré."""
    poster = poster or requests.post
    webhook_url = os.getenv(URL_WEBHOOK_ENV)
    if not webhook_url:
        raise RuntimeError(f"{URL_WEBHOOK_ENV} n'est pas configurée.")

    reponse = poster(
        webhook_url,
        json={
            "text": (
                f"Fiche de qualification — {fiche.nom_entreprise} "
                f"(score {fiche.resultat_scoring.score}/20)"
            ),
            "blocks": _construire_blocks(fiche),
        },
        timeout=10,
    )
    reponse.raise_for_status()
