"""Connecteur Google Sheets : journalise chaque fiche de synthèse générée
dans un Google Sheet dédié (une ligne par fiche).

Authentification par compte de service (adapté au serverless : pas
d'étape interactive, les identifiants viennent d'une variable
d'environnement plutôt que d'un fichier — le disque ne persiste pas
entre deux exécutions).

Ce module est le seul de connectors/ à connaître l'API Google Sheets.
Le moteur ne l'appelle jamais directement.
"""

import datetime
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PLAGE_PAR_DEFAUT = "Fiches!A:G"

EN_TETES = [
    "Date",
    "Entreprise",
    "Score ICP",
    "Priorité",
    "Filtres éliminatoires",
    "Red flags",
    "Hypothèses (résumé)",
]


def _construire_service():
    """Construit le client Google Sheets à partir des identifiants du
    compte de service, lus depuis la variable d'environnement
    GOOGLE_SERVICE_ACCOUNT_JSON (le JSON complet, pas un chemin de
    fichier — cohérent avec un déploiement serverless sans disque
    persistant).
    """
    identifiants_bruts = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not identifiants_bruts:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON n'est pas configurée : impossible de "
            "s'authentifier auprès de Google Sheets."
        )
    informations = json.loads(identifiants_bruts)
    credentials = service_account.Credentials.from_service_account_info(
        informations, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials)


def formater_ligne_fiche(fiche) -> list[str]:
    """Transforme une FicheSynthese en une ligne de tableur."""
    filtres_ok = fiche.resultat_scoring.filtres_ok
    filtres_texte = (
        "Tous validés"
        if filtres_ok
        else "Échoués : " + ", ".join(fiche.resultat_scoring.filtres_echoues)
    )

    red_flags = (
        fiche.resultat_red_flags.red_flags_entree_detectes
        + fiche.resultat_red_flags.red_flags_fit_isaa_detectes
    )
    red_flags_texte = ", ".join(red_flags) if red_flags else "aucun"

    return [
        datetime.datetime.now(datetime.timezone.utc).isoformat(),
        fiche.nom_entreprise,
        f"{fiche.resultat_scoring.score}/20",
        fiche.resultat_scoring.priorite,
        filtres_texte,
        red_flags_texte,
        fiche.hypotheses.synthese,
    ]


def enregistrer_fiche(fiche, service=None) -> None:
    """Ajoute une ligne au Google Sheet de suivi des fiches de synthèse."""
    service = service or _construire_service()
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=PLAGE_PAR_DEFAUT,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [formater_ligne_fiche(fiche)]},
    ).execute()
