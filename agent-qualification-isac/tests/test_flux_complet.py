"""Test du flux complet : connecteurs (Tally + Pappers) -> format
générique -> moteur -> fiche de synthèse.

Utilise les mêmes données de test réelles que les tests des
connecteurs (payload Tally, résultat Pappers TOMCO). Le seul appel
réseau réel est celui de generer_hypotheses() (API Claude), isolé dans
le dernier test, marqué `api` (hors CI).

La transformation des réponses Tally/Pappers en critères de scoring
(ProspectInput) relève d'un jugement métier qui n'est pas encore
automatisé (voir la conception du schéma) : elle est simulée ici à la
main, comme le ferait un humain relisant le dossier.
"""

import pytest

from connectors.pappers import extraire_donnees_entreprise
from connectors.tally import extraire_reponses_formulaire
from engine.fiche import assembler_fiche
from engine.qualification import generer_hypotheses
from engine.red_flags import detecter_red_flags_entree, detecter_red_flags_fit_isaa
from engine.schema import (
    ContexteProspect,
    CriteresScore,
    FiltresEliminatoires,
    ProspectInput,
    RedFlagsEntree,
    RedFlagsFitIsaa,
    ResultatRedFlags,
)
from engine.scoring import qualifier
from tests.test_connector_pappers import RESULTAT_TOMCO
from tests.test_connector_tally import PAYLOAD_EXEMPLE

RESUME_SITE_WEB_TEST = (
    "Cabinet de conseil en stratégie, présence web sobre, pas de blog actif."
)


def _construire_contexte() -> ContexteProspect:
    reponses_formulaire = extraire_reponses_formulaire(PAYLOAD_EXEMPLE)
    donnees_pappers = extraire_donnees_entreprise(RESULTAT_TOMCO)

    return ContexteProspect(
        reponses_formulaire=reponses_formulaire,
        resume_site_web=RESUME_SITE_WEB_TEST,
        **donnees_pappers,
    )


def _construire_prospect_input() -> ProspectInput:
    """Simule la couche de jugement métier (pas encore automatisée) qui
    transforme les réponses Tally/Pappers en critères de scoring.
    """
    return ProspectInput(
        filtres=FiltresEliminatoires(
            expertise_metier_differenciee_de_ia=True,
            production_collaborative_recurrente=True,
            probleme_depasse_curiosite_ia=True,
        ),
        criteres_score=CriteresScore(
            effectif_10_a_50=True,
            expertise_metier_forte_differenciee=True,
            ia_deja_utilisee_plusieurs_collaborateurs=True,
            usages_disperses_ou_absence_cadre_commun=True,
            production_importante_livrables_reutilisables=True,
            risque_confidentialite_qualite_marque_identifie=False,
            declencheur_achat_visible_6_mois=True,
            sponsor_niveau_associe_dg_coo=False,
            budget_compatible_isaa_et_chantier_ulterieur=True,
            potentiel_relation_au_dela_action_isolee=True,
        ),
        red_flags_entree=RedFlagsEntree(
            est_auto_entrepreneur_ou_freelance=False,
            structure_trop_petite_sans_capacite_investissement=False,
            gouvernance_ia_deja_mature_sans_besoin_formation=False,
        ),
        red_flags_fit_isaa=RedFlagsFitIsaa(
            cherche_validation_decision_deja_prise=False,
            attend_quissalya_choisisse_outil=False,
            refuse_fournir_informations_necessaires=False,
            personnes_necessaires_non_accessibles=False,
            aucun_sponsor_interne_actif=False,
            sujet_hors_champ_competences_issalya=False,
        ),
    )


def test_connecteurs_produisent_un_contexte_prospect_coherent():
    contexte = _construire_contexte()

    assert contexte.nom_entreprise == "TOMCO (TOP MANAGER COUNCIL)"
    assert contexte.secteur_activite == "Conseil pour les affaires et autres conseils de gestion"
    assert contexte.effectif == 19
    assert contexte.forme_juridique == "SAS, société par actions simplifiée"
    assert len(contexte.etablissements) == 4
    assert "Prénom" in contexte.reponses_formulaire
    assert "1. Combien de collaborateurs compte votre cabinet ?" in contexte.reponses_formulaire


def test_moteur_calcule_score_et_red_flags_a_partir_du_flux():
    prospect_input = _construire_prospect_input()

    resultat_scoring = qualifier(prospect_input)
    resultat_red_flags = ResultatRedFlags(
        red_flags_entree_detectes=detecter_red_flags_entree(prospect_input.red_flags_entree),
        red_flags_fit_isaa_detectes=detecter_red_flags_fit_isaa(prospect_input.red_flags_fit_isaa),
    )

    assert resultat_scoring.score == 16
    assert resultat_scoring.priorite == "B"
    assert resultat_scoring.filtres_ok is True
    assert resultat_red_flags.red_flags_entree_detectes == []
    assert resultat_red_flags.red_flags_fit_isaa_detectes == []


@pytest.mark.api
def test_flux_complet_de_bout_en_bout_avec_appel_claude():
    contexte = _construire_contexte()
    prospect_input = _construire_prospect_input()

    resultat_scoring = qualifier(prospect_input)
    resultat_red_flags = ResultatRedFlags(
        red_flags_entree_detectes=detecter_red_flags_entree(prospect_input.red_flags_entree),
        red_flags_fit_isaa_detectes=detecter_red_flags_fit_isaa(prospect_input.red_flags_fit_isaa),
    )
    hypotheses = generer_hypotheses(contexte, resultat_scoring, resultat_red_flags)

    fiche = assembler_fiche(contexte, resultat_scoring, resultat_red_flags, hypotheses)

    assert fiche.nom_entreprise == "TOMCO (TOP MANAGER COUNCIL)"
    assert fiche.resultat_scoring.score == 16
    assert fiche.resultat_scoring.priorite == "B"
    assert fiche.resultat_red_flags.red_flags_entree_detectes == []
    assert len(fiche.hypotheses.enjeux_probables) > 0
    assert len(fiche.hypotheses.opportunites_probables) > 0
    assert len(fiche.hypotheses.synthese) > 20
