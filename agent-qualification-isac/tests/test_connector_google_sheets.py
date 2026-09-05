"""Tests du connecteur Google Sheets.

formater_ligne_fiche() est pure et testée normalement. enregistrer_fiche()
est testée avec un client Google simulé (Mock) : aucun appel réseau réel,
donc aucun besoin du marqueur `api`.
"""

import datetime
import json
from unittest.mock import MagicMock

from connectors.google_sheets import (
    ONGLET_TALLY_EN_ATTENTE,
    PLAGE_PAR_DEFAUT,
    PLAGE_TALLY_EN_ATTENTE,
    PLAGE_VERROUS,
    a_deja_ete_traite,
    chercher_et_supprimer_reponse_tally,
    enregistrer_fiche,
    enregistrer_reponse_tally_en_attente,
    formater_ligne_fiche,
    purger_reponses_tally_expirees,
    verrouiller_reservation,
)
from engine.schema import (
    FicheSynthese,
    HypothesesQualification,
    ResultatRedFlags,
    ResultatScoring,
)


def _fiche_exemple(filtres_ok=True, filtres_echoues=None, red_flags_entree=None, red_flags_fit=None):
    return FicheSynthese(
        nom_entreprise="Cabinet Delacroix & Associés",
        resultat_scoring=ResultatScoring(
            score=16,
            priorite="B",
            filtres_ok=filtres_ok,
            filtres_echoues=filtres_echoues or [],
        ),
        resultat_red_flags=ResultatRedFlags(
            red_flags_entree_detectes=red_flags_entree or [],
            red_flags_fit_isaa_detectes=red_flags_fit or [],
        ),
        hypotheses=HypothesesQualification(
            enjeux_probables=["Usages IA dispersés entre collaborateurs"],
            opportunites_probables=["Cadrer une gouvernance commune"],
            synthese="Ce prospect présente un potentiel intéressant, à confirmer pendant l'appel.",
        ),
    )


def test_formater_ligne_fiche_contient_les_champs_attendus():
    ligne = formater_ligne_fiche(_fiche_exemple())

    assert len(ligne) == 8
    assert ligne[1] == "Cabinet Delacroix & Associés"
    assert ligne[2] == "16/20"
    assert ligne[3] == "B"
    assert ligne[4] == "Tous validés"
    assert ligne[5] == "aucun"
    assert ligne[6] == "Ce prospect présente un potentiel intéressant, à confirmer pendant l'appel."
    assert ligne[7] == ""


def test_formater_ligne_fiche_inclut_lid_de_reservation():
    ligne = formater_ligne_fiche(_fiche_exemple(), id_reservation="uLKSExGBt74TDytfyheh6q")
    assert ligne[7] == "uLKSExGBt74TDytfyheh6q"


def test_formater_ligne_fiche_signale_les_filtres_echoues():
    fiche = _fiche_exemple(filtres_ok=False, filtres_echoues=["probleme_depasse_curiosite_ia"])
    ligne = formater_ligne_fiche(fiche)

    assert ligne[4] == "Échoués : probleme_depasse_curiosite_ia"


def test_formater_ligne_fiche_liste_les_red_flags():
    fiche = _fiche_exemple(
        red_flags_entree=["est_auto_entrepreneur_ou_freelance"],
        red_flags_fit=["aucun_sponsor_interne_actif"],
    )
    ligne = formater_ligne_fiche(fiche)

    assert ligne[5] == "est_auto_entrepreneur_ou_freelance, aucun_sponsor_interne_actif"


def test_formater_ligne_fiche_date_est_une_date_iso():
    ligne = formater_ligne_fiche(_fiche_exemple())
    # Ne lève pas d'exception si le format ISO est valide
    from datetime import datetime

    datetime.fromisoformat(ligne[0])


def test_enregistrer_fiche_appelle_lapi_avec_la_bonne_plage_et_les_bonnes_donnees(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")

    service_simule = MagicMock()
    enregistrer_fiche(_fiche_exemple(), service=service_simule)

    service_simule.spreadsheets.return_value.values.return_value.append.assert_called_once()
    _, kwargs = service_simule.spreadsheets.return_value.values.return_value.append.call_args

    assert kwargs["spreadsheetId"] == "id-de-test"
    assert kwargs["range"] == PLAGE_PAR_DEFAUT
    assert kwargs["valueInputOption"] == "USER_ENTERED"
    assert len(kwargs["body"]["values"]) == 1
    assert kwargs["body"]["values"][0][1] == "Cabinet Delacroix & Associés"

    service_simule.spreadsheets.return_value.values.return_value.append.return_value.execute.assert_called_once()


# --- enregistrer_reponse_tally_en_attente ---------------------------------

def test_enregistrer_reponse_tally_en_attente_appelle_append_avec_les_bonnes_donnees(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")

    service_simule = MagicMock()
    enregistrer_reponse_tally_en_attente(
        email="alex@example.com",
        nom_entreprise="TOMCO",
        reponses_formulaire={"Q1": "R1"},
        service=service_simule,
    )

    append_mock = service_simule.spreadsheets.return_value.values.return_value.append
    append_mock.assert_called_once()
    _, kwargs = append_mock.call_args

    assert kwargs["spreadsheetId"] == "id-de-test"
    assert kwargs["range"] == PLAGE_TALLY_EN_ATTENTE
    ligne = kwargs["body"]["values"][0]
    assert ligne[1] == "alex@example.com"
    assert ligne[2] == "TOMCO"
    assert json.loads(ligne[3]) == {"Q1": "R1"}


# --- chercher_et_supprimer_reponse_tally ----------------------------------

def _configurer_lignes_tally_en_attente(service_simule, lignes):
    """lignes : liste de [date, email, entreprise, reponses_json], sans
    en-tête (ajouté automatiquement)."""
    entetes = ["Date", "Email", "Entreprise", "Réponses"]
    service_simule.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [entetes] + lignes
    }
    service_simule.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": ONGLET_TALLY_EN_ATTENTE, "sheetId": 42}}]
    }


def test_chercher_et_supprimer_reponse_tally_trouve_et_supprime(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()
    _configurer_lignes_tally_en_attente(
        service_simule,
        [
            ["2026-08-20T10:00:00+00:00", "autre@example.com", "Autre SAS", "{}"],
            ["2026-08-24T08:00:00+00:00", "alex@example.com", "TOMCO", json.dumps({"Q1": "R1"})],
        ],
    )

    resultat = chercher_et_supprimer_reponse_tally("alex@example.com", service=service_simule)

    assert resultat == {"nom_entreprise": "TOMCO", "reponses_formulaire": {"Q1": "R1"}}

    batch_mock = service_simule.spreadsheets.return_value.batchUpdate
    batch_mock.assert_called_once()
    _, kwargs = batch_mock.call_args
    requete = kwargs["body"]["requests"][0]["deleteDimension"]["range"]
    assert requete["sheetId"] == 42
    assert requete["startIndex"] == 2  # ligne trouvée (index 2 : après l'en-tête et la 1re ligne)
    assert requete["endIndex"] == 3


def test_chercher_et_supprimer_reponse_tally_retourne_none_si_absent(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()
    _configurer_lignes_tally_en_attente(
        service_simule,
        [["2026-08-20T10:00:00+00:00", "autre@example.com", "Autre SAS", "{}"]],
    )

    resultat = chercher_et_supprimer_reponse_tally("alex@example.com", service=service_simule)

    assert resultat is None
    service_simule.spreadsheets.return_value.batchUpdate.assert_not_called()


# --- purger_reponses_tally_expirees ---------------------------------------

def test_purge_supprime_les_lignes_de_plus_de_30_jours(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()

    maintenant = datetime.datetime.now(datetime.timezone.utc)
    date_vieille = (maintenant - datetime.timedelta(days=45)).isoformat()
    date_recente = (maintenant - datetime.timedelta(days=2)).isoformat()

    _configurer_lignes_tally_en_attente(
        service_simule,
        [
            [date_vieille, "vieux@example.com", "Vieux SAS", "{}"],
            [date_recente, "recent@example.com", "Recent SAS", "{}"],
        ],
    )

    nb_supprimees = purger_reponses_tally_expirees(service=service_simule)

    assert nb_supprimees == 1
    batch_mock = service_simule.spreadsheets.return_value.batchUpdate
    batch_mock.assert_called_once()
    _, kwargs = batch_mock.call_args
    requetes = kwargs["body"]["requests"]
    assert len(requetes) == 1
    assert requetes[0]["deleteDimension"]["range"]["startIndex"] == 1  # la ligne vieille


def test_purge_ne_fait_rien_si_aucune_ligne_expiree(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()

    date_recente = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    ).isoformat()
    _configurer_lignes_tally_en_attente(
        service_simule, [[date_recente, "recent@example.com", "Recent SAS", "{}"]]
    )

    nb_supprimees = purger_reponses_tally_expirees(service=service_simule)

    assert nb_supprimees == 0
    service_simule.spreadsheets.return_value.batchUpdate.assert_not_called()


# --- a_deja_ete_traite / verrouiller_reservation ----------------------

def test_a_deja_ete_traite_retourne_true_si_id_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()
    service_simule.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["abc123"], ["def456"]]
    }

    assert a_deja_ete_traite("def456", service=service_simule) is True

    _, kwargs = service_simule.spreadsheets.return_value.values.return_value.get.call_args
    assert kwargs["range"] == PLAGE_VERROUS


def test_a_deja_ete_traite_retourne_false_si_id_absent(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()
    service_simule.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["abc123"]]
    }

    assert a_deja_ete_traite("inconnu", service=service_simule) is False


def test_a_deja_ete_traite_retourne_false_si_colonne_vide(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()
    service_simule.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": []
    }

    assert a_deja_ete_traite("nimporte-quoi", service=service_simule) is False


def test_verrouiller_reservation_ajoute_lid_dans_longlet_verrous(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "id-de-test")
    service_simule = MagicMock()

    verrouiller_reservation("uLKSExGBt74TDytfyheh6q", service=service_simule)

    append_mock = service_simule.spreadsheets.return_value.values.return_value.append
    append_mock.assert_called_once()
    _, kwargs = append_mock.call_args
    assert kwargs["spreadsheetId"] == "id-de-test"
    assert kwargs["range"] == PLAGE_VERROUS
    assert kwargs["body"]["values"] == [["uLKSExGBt74TDytfyheh6q"]]
