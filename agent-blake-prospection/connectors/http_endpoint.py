"""Point d'entrée HTTP pour Google Cloud Function (2ᵉ génération).

Ce fichier ne contient aucune logique métier : il valide le contrat JSON
attendu par Make et adapte le pipeline (engine/) au format attendu par Cloud
Functions. Même modèle que main.py de l'Agent Qualification ISAC —
functions_framework.http, pas d'app Flask autonome à faire tourner soi-même.
"""

from __future__ import annotations

import logging

import functions_framework

from engine.extraction import (
    detecter_signal_groupe,
    detecter_signaux_taille,
    extraire_titre,
    html_vers_texte,
)
from engine.qualification import ErreurQualification, qualifier
from engine.scraping import recuperer_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CONTENU_MINIMUM_CARACTERES = 300
CHAMPS_ENTREE_REQUIS = ("nom_cabinet", "site_web", "objet_social_pappers", "siren")


def _erreur_validation_entree(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "Corps de requête JSON invalide ou absent."
    for champ in CHAMPS_ENTREE_REQUIS:
        valeur = payload.get(champ)
        if not isinstance(valeur, str) or not valeur.strip():
            return f"Champ requis manquant ou invalide : {champ!r}."
    effectif = payload.get("effectif_pappers")
    if effectif is not None and not isinstance(effectif, (int, float)):
        return "effectif_pappers doit être un nombre ou null."
    return None


def _verdict_contenu_insuffisant(raison: str) -> dict[str, str]:
    return {
        "effectif": "information non disponible",
        "verdict": "CONTENU INSUFFISANT",
        "segment": "",
        "signal_ia": "Non",
        "justification": raison,
    }


@functions_framework.http
def qualifier_prospect_http(request):
    """Entrée HTTP du pipeline de qualification (appelée par Make).

    Cloud Functions ne fait pas de routage par chemin au sein d'une même
    fonction déployée : le check de santé est géré ici via request.path
    plutôt que par une route Flask séparée, pour préserver le comportement
    sans avoir à déployer une deuxième fonction.
    """
    if getattr(request, "path", "") == "/healthz":
        return {"status": "ok"}, 200

    payload = request.get_json(silent=True)
    erreur = _erreur_validation_entree(payload)
    if erreur:
        logging.warning("Requête invalide : %s", erreur)
        return {"erreur": erreur}, 400

    nom_cabinet = payload["nom_cabinet"]
    site_web = payload["site_web"]
    siren = payload["siren"]
    effectif_pappers = payload.get("effectif_pappers")
    objet_social_pappers = payload["objet_social_pappers"]

    logging.info("Qualification démarrée : %s (%s, SIREN %s)", nom_cabinet, site_web, siren)

    html = recuperer_html(site_web)
    contenu_site = html_vers_texte(html) if html else ""

    if len(contenu_site) < CONTENU_MINIMUM_CARACTERES:
        logging.warning(
            "Contenu insuffisant pour %s : %d caractère(s) exploitable(s)", nom_cabinet, len(contenu_site)
        )
        return _verdict_contenu_insuffisant(
            "Le site n'a pas pu être scrapé ou ne contient pas assez de contenu exploitable."
        ), 200

    try:
        resultat = qualifier(
            titre_page=extraire_titre(html),
            signaux_taille=detecter_signaux_taille(contenu_site),
            signal_groupe=detecter_signal_groupe(contenu_site),
            contenu_site=contenu_site,
            effectif_pappers=effectif_pappers,
            objet_social_pappers=objet_social_pappers,
        )
    except ErreurQualification as erreur:
        logging.error("Qualification échouée pour %s : %s", nom_cabinet, erreur)
        return {"erreur": "Qualification indisponible, réessayez plus tard."}, 502

    logging.info("Qualification terminée pour %s : %s", nom_cabinet, resultat["verdict"])
    return resultat, 200
