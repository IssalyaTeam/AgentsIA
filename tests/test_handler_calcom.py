"""Tests du handler webhook Cal.com. Toutes les dépendances externes
(Google Sheets, Pappers, Claude) sont injectées comme des doublures :
aucun appel réseau réel.
"""

from unittest.mock import MagicMock

import pytest

from engine.schema import (
    CriteresScore,
    FiltresEliminatoires,
    HypothesesQualification,
    ProspectInput,
    RedFlagsEntree,
    RedFlagsFitIsaa,
)
from handlers.calcom_webhook import gerer_webhook_calcom
from tests.test_connector_calcom import PAYLOAD_EXEMPLE


def _prospect_input_type():
    return ProspectInput(
        filtres=FiltresEliminatoires(True, True, True),
        criteres_score=CriteresScore(
            *([True] * 10)
        ),
        red_flags_entree=RedFlagsEntree(False, False, False),
        red_flags_fit_isaa=RedFlagsFitIsaa(False, False, False, False, False, False),
    )


def _hypotheses_type():
    return HypothesesQualification(
        enjeux_probables=["Enjeu test"],
        opportunites_probables=["Opportunité test"],
        synthese="Synthèse de test.",
    )


def _doublures(donnees_tally=None, resultat_pappers="present", deja_traite=False):
    """Construit un jeu de doublures pour toutes les dépendances externes.
    resultat_pappers="present" simule un résultat Pappers trouvé,
    None simule une absence de résultat.
    """
    return {
        "deja_traite": MagicMock(return_value=deja_traite),
        "verrouiller": MagicMock(),
        "purger_tally_expires": MagicMock(),
        "chercher_tally": MagicMock(return_value=donnees_tally),
        "rechercher_entreprise_pappers": MagicMock(
            return_value={"denomination": "TOMCO"} if resultat_pappers else None
        ),
        "extraire_donnees_pappers": MagicMock(
            return_value={
                "nom_entreprise": "TOMCO (TOP MANAGER COUNCIL)",
                "secteur_activite": "Conseil pour les affaires",
                "effectif": 19,
                "anciennete_annees": 12,
                "appartient_a_un_groupe": False,
            }
        ),
        "interpreter": MagicMock(return_value=_prospect_input_type()),
        "generer_hypotheses_prospect": MagicMock(return_value=_hypotheses_type()),
        "enregistrer_fiche_sheets": MagicMock(),
        "envoyer_fiche_slack": MagicMock(),
    }


def test_flux_nominal_sans_donnees_manquantes():
    doublures = _doublures(
        donnees_tally={
            "nom_entreprise": "TOMCO",
            "reponses_formulaire": {"Q1": "R1"},
        }
    )

    fiche = gerer_webhook_calcom(PAYLOAD_EXEMPLE, **doublures)

    assert fiche.donnees_manquantes == []
    assert fiche.nom_entreprise == "TOMCO (TOP MANAGER COUNCIL)"
    doublures["verrouiller"].assert_called_once_with("uLKSExGBt74TDytfyheh6q")
    doublures["purger_tally_expires"].assert_called_once()
    doublures["chercher_tally"].assert_called_once_with("arekisanda1992@gmail.com")
    doublures["enregistrer_fiche_sheets"].assert_called_once_with(
        fiche, id_reservation="uLKSExGBt74TDytfyheh6q"
    )
    doublures["envoyer_fiche_slack"].assert_called_once_with(fiche)


def test_aucune_reponse_tally_correlee_signale_la_donnee_manquante():
    doublures = _doublures(donnees_tally=None)

    fiche = gerer_webhook_calcom(PAYLOAD_EXEMPLE, **doublures)

    assert "reponses_tally" in fiche.donnees_manquantes
    doublures["rechercher_entreprise_pappers"].assert_not_called()
    assert "donnees_pappers" in fiche.donnees_manquantes
    assert fiche.nom_entreprise == "Entreprise inconnue"


def test_pappers_sans_resultat_signale_la_donnee_manquante():
    doublures = _doublures(
        donnees_tally={"nom_entreprise": "Introuvable SAS", "reponses_formulaire": {}},
        resultat_pappers=None,
    )

    fiche = gerer_webhook_calcom(PAYLOAD_EXEMPLE, **doublures)

    assert "donnees_pappers" in fiche.donnees_manquantes
    assert "reponses_tally" not in fiche.donnees_manquantes
    assert fiche.nom_entreprise == "Introuvable SAS"


def test_leve_une_erreur_si_email_absent_du_webhook_calcom():
    doublures = _doublures(donnees_tally={"nom_entreprise": "TOMCO", "reponses_formulaire": {}})

    with pytest.raises(ValueError):
        gerer_webhook_calcom({"payload": {"attendees": []}}, **doublures)


def test_purge_appelee_avant_tout_le_reste():
    doublures = _doublures(donnees_tally={"nom_entreprise": "TOMCO", "reponses_formulaire": {}})

    gerer_webhook_calcom(PAYLOAD_EXEMPLE, **doublures)

    doublures["purger_tally_expires"].assert_called_once()


def test_reservation_deja_traitee_ne_relance_rien():
    """Simule un webhook Cal.com relancé (délai d'attente dépassé côté
    Cal.com) pour une réservation déjà traitée : aucun appel coûteux ne
    doit être refait, et aucune seconde notification Slack envoyée."""
    doublures = _doublures(
        donnees_tally={"nom_entreprise": "TOMCO", "reponses_formulaire": {}},
        deja_traite=True,
    )

    resultat = gerer_webhook_calcom(PAYLOAD_EXEMPLE, **doublures)

    assert resultat is None
    doublures["deja_traite"].assert_called_once_with("uLKSExGBt74TDytfyheh6q")
    doublures["verrouiller"].assert_not_called()
    doublures["purger_tally_expires"].assert_not_called()
    doublures["chercher_tally"].assert_not_called()
    doublures["rechercher_entreprise_pappers"].assert_not_called()
    doublures["interpreter"].assert_not_called()
    doublures["generer_hypotheses_prospect"].assert_not_called()
    doublures["enregistrer_fiche_sheets"].assert_not_called()
    doublures["envoyer_fiche_slack"].assert_not_called()


def test_reservation_non_traitee_declenche_le_flux_normalement():
    doublures = _doublures(
        donnees_tally={"nom_entreprise": "TOMCO", "reponses_formulaire": {}},
        deja_traite=False,
    )

    fiche = gerer_webhook_calcom(PAYLOAD_EXEMPLE, **doublures)

    assert fiche is not None
    doublures["verrouiller"].assert_called_once_with("uLKSExGBt74TDytfyheh6q")
    doublures["envoyer_fiche_slack"].assert_called_once()
