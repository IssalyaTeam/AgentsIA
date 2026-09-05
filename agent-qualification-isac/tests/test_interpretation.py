"""Tests de l'interprétation du contexte en ProspectInput (par
propriétés, pas de texte/booléen exact — sauf pour les signaux les
moins ambigus). Appelle réellement l'API Claude (marqueur `api`),
comme tests/test_qualification.py.
"""

import pytest

from engine.interpretation import interpreter_prospect
from engine.schema import (
    CriteresScore,
    FiltresEliminatoires,
    ProspectInput,
    RedFlagsEntree,
    RedFlagsFitIsaa,
)
from tests.test_flux_complet import _construire_contexte


@pytest.mark.api
def test_interpretation_produit_un_prospect_input_bien_type():
    contexte = _construire_contexte()

    prospect_input = interpreter_prospect(contexte)

    assert isinstance(prospect_input, ProspectInput)
    assert isinstance(prospect_input.filtres, FiltresEliminatoires)
    assert isinstance(prospect_input.criteres_score, CriteresScore)
    assert isinstance(prospect_input.red_flags_entree, RedFlagsEntree)
    assert isinstance(prospect_input.red_flags_fit_isaa, RedFlagsFitIsaa)

    for valeur in vars(prospect_input.filtres).values():
        assert isinstance(valeur, bool)
    for valeur in vars(prospect_input.criteres_score).values():
        assert isinstance(valeur, bool)
    for valeur in vars(prospect_input.red_flags_entree).values():
        assert isinstance(valeur, bool)
    for valeur in vars(prospect_input.red_flags_fit_isaa).values():
        assert isinstance(valeur, bool)


@pytest.mark.api
def test_effectif_10_a_50_est_calcule_pas_juge():
    """contexte.effectif == 19 (Pappers, TOMCO) -> toujours True, sans
    dépendre du jugement de Claude."""
    contexte = _construire_contexte()
    assert contexte.effectif == 19

    prospect_input = interpreter_prospect(contexte)

    assert prospect_input.criteres_score.effectif_10_a_50 is True


@pytest.mark.api
def test_usage_ia_disperse_est_correctement_detecte():
    """Le payload Tally de test répond explicitement 'plusieurs outils,
    mais de façon dispersée entre collaborateurs' à la question sur
    l'usage de l'IA : signal explicite, sans ambiguïté."""
    contexte = _construire_contexte()

    prospect_input = interpreter_prospect(contexte)

    assert prospect_input.criteres_score.ia_deja_utilisee_plusieurs_collaborateurs is True
    assert prospect_input.criteres_score.usages_disperses_ou_absence_cadre_commun is True
