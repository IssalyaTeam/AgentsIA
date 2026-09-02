"""Tests de la logique de scoring (TDD : écrits avant l'implémentation).

Aucun de ces tests n'appelle une API : la logique est déterministe,
donc testable avec des exemples exacts.
"""

import pytest

from engine.schema import (
    CriteresScore,
    FiltresEliminatoires,
    ProspectInput,
    RedFlagsEntree,
    RedFlagsFitIsaa,
)
from engine.scoring import calculer_score, determiner_priorite, evaluer_filtres, qualifier


def _filtres_ok():
    return FiltresEliminatoires(
        expertise_metier_differenciee_de_ia=True,
        production_collaborative_recurrente=True,
        probleme_depasse_curiosite_ia=True,
    )


def _criteres(nb_faux=0):
    """10 critères vrais, sauf les `nb_faux` premiers (dans l'ordre de définition)."""
    noms = list(CriteresScore.__dataclass_fields__.keys())
    valeurs = {nom: (i >= nb_faux) for i, nom in enumerate(noms)}
    return CriteresScore(**valeurs)


def _aucun_red_flag_entree():
    return RedFlagsEntree(
        est_auto_entrepreneur_ou_freelance=False,
        structure_trop_petite_sans_capacite_investissement=False,
        gouvernance_ia_deja_mature_sans_besoin_formation=False,
    )


def _aucun_red_flag_fit_isaa():
    return RedFlagsFitIsaa(
        cherche_validation_decision_deja_prise=False,
        attend_quissalya_choisisse_outil=False,
        refuse_fournir_informations_necessaires=False,
        personnes_necessaires_non_accessibles=False,
        aucun_sponsor_interne_actif=False,
        sujet_hors_champ_competences_issalya=False,
    )


def _prospect(filtres=None, nb_criteres_faux=0):
    return ProspectInput(
        filtres=filtres if filtres is not None else _filtres_ok(),
        criteres_score=_criteres(nb_criteres_faux),
        red_flags_entree=_aucun_red_flag_entree(),
        red_flags_fit_isaa=_aucun_red_flag_fit_isaa(),
    )


# --- evaluer_filtres --------------------------------------------------

def test_filtres_tous_valides():
    ok, echoues = evaluer_filtres(_filtres_ok())
    assert ok is True
    assert echoues == []


def test_un_seul_filtre_invalide_suffit_a_echouer():
    filtres = _filtres_ok()
    filtres.probleme_depasse_curiosite_ia = False
    ok, echoues = evaluer_filtres(filtres)
    assert ok is False
    assert echoues == ["probleme_depasse_curiosite_ia"]


def test_plusieurs_filtres_invalides_sont_tous_listes():
    filtres = FiltresEliminatoires(
        expertise_metier_differenciee_de_ia=False,
        production_collaborative_recurrente=False,
        probleme_depasse_curiosite_ia=True,
    )
    ok, echoues = evaluer_filtres(filtres)
    assert ok is False
    assert set(echoues) == {
        "expertise_metier_differenciee_de_ia",
        "production_collaborative_recurrente",
    }


# --- calculer_score -----------------------------------------------------

def test_score_maximal_quand_tous_les_criteres_sont_vrais():
    assert calculer_score(_criteres(nb_faux=0)) == 20


def test_score_minimal_quand_aucun_critere_nest_vrai():
    assert calculer_score(_criteres(nb_faux=10)) == 0


def test_chaque_critere_faux_retire_2_points():
    assert calculer_score(_criteres(nb_faux=1)) == 18
    assert calculer_score(_criteres(nb_faux=3)) == 14


# --- determiner_priorite -------------------------------------------------

@pytest.mark.parametrize(
    "score,priorite_attendue",
    [
        (20, "A"),
        (17, "A"),
        (16, "B"),
        (13, "B"),
        (12, "C"),
        (9, "C"),
        (8, "Hors cible"),
        (0, "Hors cible"),
    ],
)
def test_seuils_de_priorite(score, priorite_attendue):
    assert determiner_priorite(score, filtres_ok=True) == priorite_attendue


def test_priorite_hors_cible_si_un_filtre_echoue_meme_avec_score_maximal():
    assert determiner_priorite(20, filtres_ok=False) == "Hors cible"


# --- qualifier (fonction d'assemblage) -----------------------------------

def test_qualifier_prospect_ideal():
    resultat = qualifier(_prospect())
    assert resultat.score == 20
    assert resultat.priorite == "A"
    assert resultat.filtres_ok is True
    assert resultat.filtres_echoues == []


def test_qualifier_prospect_exclu_par_filtre_malgre_bon_score():
    filtres = _filtres_ok()
    filtres.expertise_metier_differenciee_de_ia = False
    resultat = qualifier(_prospect(filtres=filtres))
    assert resultat.score == 20
    assert resultat.filtres_ok is False
    assert resultat.priorite == "Hors cible"
    assert resultat.filtres_echoues == ["expertise_metier_differenciee_de_ia"]
