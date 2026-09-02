"""Tests du connecteur Google Sheets.

formater_ligne_fiche() est pure et testée normalement. enregistrer_fiche()
est testée avec un client Google simulé (Mock) : aucun appel réseau réel,
donc aucun besoin du marqueur `api`.
"""

from unittest.mock import MagicMock

from connectors.google_sheets import PLAGE_PAR_DEFAUT, enregistrer_fiche, formater_ligne_fiche
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

    assert len(ligne) == 7
    assert ligne[1] == "Cabinet Delacroix & Associés"
    assert ligne[2] == "16/20"
    assert ligne[3] == "B"
    assert ligne[4] == "Tous validés"
    assert ligne[5] == "aucun"
    assert ligne[6] == "Ce prospect présente un potentiel intéressant, à confirmer pendant l'appel."


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
