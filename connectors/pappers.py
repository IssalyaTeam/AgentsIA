"""Connecteur Pappers : transforme une fiche entreprise Pappers vers le
format générique attendu par le moteur (champs de ContexteProspect).

Ce module est le seul de connectors/ à connaître la forme des réponses
de l'API Pappers (endpoint /v2/recherche). Le moteur ne reçoit jamais
cette forme brute — uniquement les champs génériques produits ici.

Limitation connue (endpoint /v2/recherche, périmètre du plan Pappers
utilisé) : dirigeants, procédures collectives et changements récents
ne sont pas disponibles à ce niveau (l'API ne renvoie que des
compteurs, pas le détail) et restent donc vides dans le résultat.
"""

import datetime
import os

import requests

from engine.schema import Etablissement, ExerciceFinancier

URL_RECHERCHE = "https://api.pappers.fr/v2/recherche"


def rechercher_entreprise(nom_entreprise: str) -> dict | None:
    """Cherche une entreprise par son nom via l'API Pappers et retourne le
    premier résultat brut (dict), ou None si aucun résultat.
    """
    reponse = requests.get(
        URL_RECHERCHE,
        params={
            "api_token": os.getenv("PAPPERS_API_KEY"),
            "q": nom_entreprise,
            "par_page": 1,
        },
        timeout=10,
    )
    reponse.raise_for_status()
    resultats = reponse.json().get("resultats", [])
    return resultats[0] if resultats else None


def _calculer_anciennete_annees(date_creation: str | None) -> int:
    if not date_creation:
        return 0
    creation = datetime.date.fromisoformat(date_creation)
    aujourdhui = datetime.date.today()
    annees = aujourdhui.year - creation.year
    if (aujourdhui.month, aujourdhui.day) < (creation.month, creation.day):
        annees -= 1
    return max(annees, 0)


def _extraire_etablissements(resultat: dict) -> list[Etablissement]:
    siege = resultat.get("siege") or {}
    siret_siege = siege.get("siret")

    return [
        Etablissement(
            nom_ou_enseigne=etablissement.get("adresse_ligne_1", ""),
            ville=etablissement.get("ville", ""),
            est_siege=etablissement.get("siret") == siret_siege,
        )
        for etablissement in resultat.get("etablissements", [])
    ]


def _extraire_historique_financier(resultat: dict) -> list[ExerciceFinancier]:
    annee = resultat.get("annee_finances")
    chiffre_affaires = resultat.get("chiffre_affaires")
    resultat_net = resultat.get("resultat")

    if annee is None or (chiffre_affaires is None and resultat_net is None):
        return []

    return [
        ExerciceFinancier(
            annee=annee,
            chiffre_affaires_euros=chiffre_affaires,
            resultat_net_euros=resultat_net,
        )
    ]


def extraire_donnees_entreprise(resultat: dict) -> dict:
    """Transforme un résultat brut Pappers en dict de champs génériques,
    prêt à être fusionné dans un ContexteProspect (avec les données Tally
    et le résumé du site web, assemblés ailleurs).
    """
    effectif = resultat.get("effectif_max") or resultat.get("effectif_min") or 0

    return {
        "nom_entreprise": resultat.get("denomination") or resultat.get("nom_entreprise", ""),
        "secteur_activite": resultat.get("libelle_code_naf", ""),
        "effectif": effectif,
        "anciennete_annees": _calculer_anciennete_annees(resultat.get("date_creation")),
        "appartient_a_un_groupe": False,  # non détectable via cet endpoint (voir limitation ci-dessus)
        "forme_juridique": resultat.get("forme_juridique", ""),
        "capital_social_euros": resultat.get("capital"),
        "etablissements": _extraire_etablissements(resultat),
        "historique_financier": _extraire_historique_financier(resultat),
    }
