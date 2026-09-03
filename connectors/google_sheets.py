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

import google.auth
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

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

ONGLET_TALLY_EN_ATTENTE = "Tally_en_attente"
PLAGE_TALLY_EN_ATTENTE = f"{ONGLET_TALLY_EN_ATTENTE}!A:D"
DELAI_EXPIRATION_JOURS_PAR_DEFAUT = 30


def _construire_service():
    """Construit le client Google Sheets.

    Deux modes d'authentification :
    - GOOGLE_SERVICE_ACCOUNT_JSON définie (dev local, hors de GCP) : la
      clé du compte de service, lue depuis cette variable d'environnement
      (le JSON complet, pas un chemin de fichier).
    - GOOGLE_SERVICE_ACCOUNT_JSON absente : Application Default
      Credentials — le cas normal en production, quand la fonction
      Cloud Functions tourne avec le compte de service
      (--service-account=...) comme identité d'exécution. Aucune clé à
      gérer dans ce cas.
    """
    identifiants_bruts = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if identifiants_bruts:
        informations = json.loads(identifiants_bruts)
        credentials = service_account.Credentials.from_service_account_info(
            informations, scopes=SCOPES
        )
    else:
        credentials, _ = google.auth.default(scopes=SCOPES)
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


def _obtenir_id_onglet(service, spreadsheet_id: str, nom_onglet: str) -> int:
    """Résout l'identifiant numérique d'un onglet à partir de son nom,
    nécessaire pour supprimer des lignes (l'API Sheets l'exige, en plus
    de l'identifiant du classeur).
    """
    metadonnees = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for feuille in metadonnees["sheets"]:
        if feuille["properties"]["title"] == nom_onglet:
            return feuille["properties"]["sheetId"]
    raise RuntimeError(f"Onglet {nom_onglet!r} introuvable dans le classeur.")


def enregistrer_reponse_tally_en_attente(
    email: str,
    nom_entreprise: str,
    reponses_formulaire: dict[str, str],
    service=None,
) -> None:
    """Stocke une réponse Tally en attente d'une réservation Cal.com
    corrélée par email (l'onglet Tally_en_attente sert de buffer
    temporaire, seul mécanisme de persistance en environnement
    serverless).
    """
    service = service or _construire_service()
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

    ligne = [
        datetime.datetime.now(datetime.timezone.utc).isoformat(),
        email,
        nom_entreprise,
        json.dumps(reponses_formulaire, ensure_ascii=False),
    ]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=PLAGE_TALLY_EN_ATTENTE,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [ligne]},
    ).execute()


def chercher_et_supprimer_reponse_tally(email: str, service=None) -> dict | None:
    """Cherche une réponse Tally en attente pour cet email. Si trouvée,
    la supprime de l'onglet (corrélation réussie : plus besoin de la
    donnée brute, l'historique complet vit dans l'onglet Fiches) et
    retourne {"nom_entreprise": ..., "reponses_formulaire": {...}}.
    Retourne None si aucune réponse ne correspond.
    """
    service = service or _construire_service()
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

    resultat = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=PLAGE_TALLY_EN_ATTENTE)
        .execute()
    )
    lignes = resultat.get("values", [])

    for index_ligne, ligne in enumerate(lignes):
        if index_ligne == 0:
            continue  # en-têtes
        if len(ligne) < 2 or ligne[1] != email:
            continue

        nom_entreprise = ligne[2] if len(ligne) > 2 else ""
        reponses_formulaire = json.loads(ligne[3]) if len(ligne) > 3 else {}

        id_onglet = _obtenir_id_onglet(service, spreadsheet_id, ONGLET_TALLY_EN_ATTENTE)
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": id_onglet,
                                "dimension": "ROWS",
                                "startIndex": index_ligne,
                                "endIndex": index_ligne + 1,
                            }
                        }
                    }
                ]
            },
        ).execute()

        return {"nom_entreprise": nom_entreprise, "reponses_formulaire": reponses_formulaire}

    return None


def purger_reponses_tally_expirees(
    delai_jours: int = DELAI_EXPIRATION_JOURS_PAR_DEFAUT, service=None
) -> int:
    """Supprime les réponses Tally en attente depuis plus de `delai_jours`
    (jamais corrélées à une réservation). Retourne le nombre de lignes
    supprimées. Conçu pour être appelé à chaque exécution du handler
    Cal.com (pas de tâche planifiée séparée en V1).
    """
    service = service or _construire_service()
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

    resultat = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=PLAGE_TALLY_EN_ATTENTE)
        .execute()
    )
    lignes = resultat.get("values", [])
    seuil = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=delai_jours)

    indices_expires = []
    for index_ligne, ligne in enumerate(lignes):
        if index_ligne == 0 or not ligne:
            continue
        try:
            date_ligne = datetime.datetime.fromisoformat(ligne[0])
        except (ValueError, IndexError):
            continue
        if date_ligne < seuil:
            indices_expires.append(index_ligne)

    if not indices_expires:
        return 0

    id_onglet = _obtenir_id_onglet(service, spreadsheet_id, ONGLET_TALLY_EN_ATTENTE)
    requetes = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": id_onglet,
                    "dimension": "ROWS",
                    "startIndex": index,
                    "endIndex": index + 1,
                }
            }
        }
        # Du bas vers le haut : supprimer de haut en bas décalerait les
        # index des lignes suivantes avant leur suppression.
        for index in sorted(indices_expires, reverse=True)
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": requetes}
    ).execute()

    return len(indices_expires)
