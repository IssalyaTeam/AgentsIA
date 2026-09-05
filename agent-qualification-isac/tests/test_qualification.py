"""Tests de la génération d'hypothèses (par propriétés, pas de texte exact).

Ces tests appellent réellement l'API Claude (marqueur `api`) : ils ne
tournent pas en CI (voir pytest.ini / .github/workflows/tests.yml),
seulement en local, à la demande, avec `pytest -m api`.
"""

import pytest

from engine.qualification import MOTS_INTERDITS, generer_hypotheses
from engine.schema import (
    ContexteProspect,
    HypothesesQualification,
    ResultatRedFlags,
    ResultatScoring,
)


def _contexte_bon_prospect():
    return ContexteProspect(
        nom_entreprise="Cabinet Delacroix & Associés",
        secteur_activite="Conseil en stratégie et organisation",
        effectif=32,
        anciennete_annees=12,
        appartient_a_un_groupe=False,
        reponses_formulaire={
            "Combien de collaborateurs utilisent déjà l'IA au quotidien ?": (
                "Une dizaine, chacun à sa façon, sans cadre commun"
            ),
            "Quel est le principal risque que vous identifiez ?": (
                "Confidentialité des données clients dans les outils IA utilisés"
            ),
            "Un budget est-il déjà alloué à ce sujet ?": (
                "Oui, un budget a été validé pour le second semestre"
            ),
        },
        resume_site_web=(
            "Cabinet de conseil en stratégie, produisant des analyses et "
            "recommandations pour des clients grands comptes. Met en avant "
            "son expertise sectorielle et ses méthodes propriétaires."
        ),
    )


def _resultat_scoring_priorite_a():
    return ResultatScoring(score=18, priorite="A", filtres_ok=True, filtres_echoues=[])


def _resultat_red_flags_aucun():
    return ResultatRedFlags(red_flags_entree_detectes=[], red_flags_fit_isaa_detectes=[])


def _contexte_hors_cible():
    return ContexteProspect(
        nom_entreprise="Studio Créatif Léa Martin",
        secteur_activite="Graphisme freelance",
        effectif=1,
        anciennete_annees=2,
        appartient_a_un_groupe=False,
        reponses_formulaire={
            "Combien de collaborateurs utilisent déjà l'IA au quotidien ?": "Seulement moi",
            "Quel est le principal risque que vous identifiez ?": (
                "Aucun risque identifié pour l'instant"
            ),
            "Un budget est-il déjà alloué à ce sujet ?": "Pas de budget particulier",
        },
        resume_site_web=(
            "Graphiste indépendante, propose des prestations de logo et identité visuelle."
        ),
    )


def _resultat_scoring_hors_cible():
    return ResultatScoring(
        score=4,
        priorite="Hors cible",
        filtres_ok=False,
        filtres_echoues=["production_collaborative_recurrente"],
    )


def _resultat_red_flags_entree():
    return ResultatRedFlags(
        red_flags_entree_detectes=["est_auto_entrepreneur_ou_freelance"],
        red_flags_fit_isaa_detectes=[],
    )


def _verifier_aucun_mot_interdit(hypotheses: HypothesesQualification):
    texte_complet = " ".join(
        hypotheses.enjeux_probables + hypotheses.opportunites_probables + [hypotheses.synthese]
    ).lower()
    for mot in MOTS_INTERDITS:
        assert mot not in texte_complet, f"Mot interdit détecté : {mot!r}"


@pytest.mark.api
def test_hypotheses_bon_prospect_a_la_structure_attendue():
    hypotheses = generer_hypotheses(
        _contexte_bon_prospect(),
        _resultat_scoring_priorite_a(),
        _resultat_red_flags_aucun(),
    )

    assert isinstance(hypotheses, HypothesesQualification)
    assert isinstance(hypotheses.enjeux_probables, list)
    assert len(hypotheses.enjeux_probables) > 0
    assert all(isinstance(e, str) and e for e in hypotheses.enjeux_probables)

    assert isinstance(hypotheses.opportunites_probables, list)
    assert len(hypotheses.opportunites_probables) > 0
    assert all(isinstance(o, str) and o for o in hypotheses.opportunites_probables)

    assert isinstance(hypotheses.synthese, str)
    assert len(hypotheses.synthese) > 20

    _verifier_aucun_mot_interdit(hypotheses)


@pytest.mark.api
def test_hypotheses_prospect_hors_cible_respecte_aussi_le_ton():
    hypotheses = generer_hypotheses(
        _contexte_hors_cible(),
        _resultat_scoring_hors_cible(),
        _resultat_red_flags_entree(),
    )

    assert isinstance(hypotheses, HypothesesQualification)
    assert len(hypotheses.synthese) > 20
    _verifier_aucun_mot_interdit(hypotheses)
