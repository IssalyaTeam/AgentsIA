"""Tests de la détection des red flags (TDD : écrits avant l'implémentation)."""

from engine.red_flags import detecter_red_flags_entree, detecter_red_flags_fit_isaa
from engine.schema import RedFlagsEntree, RedFlagsFitIsaa


def test_aucun_red_flag_entree_si_tout_est_faux():
    red_flags = RedFlagsEntree(
        est_auto_entrepreneur_ou_freelance=False,
        structure_trop_petite_sans_capacite_investissement=False,
        gouvernance_ia_deja_mature_sans_besoin_formation=False,
    )
    assert detecter_red_flags_entree(red_flags) == []


def test_red_flags_entree_detectes_sont_listes_par_nom():
    red_flags = RedFlagsEntree(
        est_auto_entrepreneur_ou_freelance=True,
        structure_trop_petite_sans_capacite_investissement=False,
        gouvernance_ia_deja_mature_sans_besoin_formation=True,
    )
    detectes = detecter_red_flags_entree(red_flags)
    assert set(detectes) == {
        "est_auto_entrepreneur_ou_freelance",
        "gouvernance_ia_deja_mature_sans_besoin_formation",
    }


def test_aucun_red_flag_fit_isaa_si_tout_est_faux():
    red_flags = RedFlagsFitIsaa(
        cherche_validation_decision_deja_prise=False,
        attend_quissalya_choisisse_outil=False,
        refuse_fournir_informations_necessaires=False,
        personnes_necessaires_non_accessibles=False,
        aucun_sponsor_interne_actif=False,
        sujet_hors_champ_competences_issalya=False,
    )
    assert detecter_red_flags_fit_isaa(red_flags) == []


def test_red_flags_fit_isaa_detectes_sont_listes_par_nom():
    red_flags = RedFlagsFitIsaa(
        cherche_validation_decision_deja_prise=False,
        attend_quissalya_choisisse_outil=False,
        refuse_fournir_informations_necessaires=False,
        personnes_necessaires_non_accessibles=True,
        aucun_sponsor_interne_actif=True,
        sujet_hors_champ_competences_issalya=False,
    )
    detectes = detecter_red_flags_fit_isaa(red_flags)
    assert set(detectes) == {
        "personnes_necessaires_non_accessibles",
        "aucun_sponsor_interne_actif",
    }


def test_tous_les_red_flags_fit_isaa_detectes():
    red_flags = RedFlagsFitIsaa(
        cherche_validation_decision_deja_prise=True,
        attend_quissalya_choisisse_outil=True,
        refuse_fournir_informations_necessaires=True,
        personnes_necessaires_non_accessibles=True,
        aucun_sponsor_interne_actif=True,
        sujet_hors_champ_competences_issalya=True,
    )
    detectes = detecter_red_flags_fit_isaa(red_flags)
    assert len(detectes) == 6
