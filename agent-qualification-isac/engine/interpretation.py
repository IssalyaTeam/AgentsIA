"""Interprétation du contexte prospect en critères de scoring (ProspectInput).

Sur les 22 critères binaires attendus par le moteur (filtres, score,
red flags), un seul est un simple calcul (effectif_10_a_50, à partir
d'un chiffre déjà connu) ; les 21 autres demandent une interprétation
de texte libre (réponses au formulaire, contexte entreprise). Ce
module fait ce travail via Claude — c'est le deuxième (et dernier)
module du moteur à appeler une API externe, avec qualification.py.

Reçoit une entrée générique (ContexteProspect) et ne sait jamais d'où
viennent ces données (pas d'appel direct à Tally ou Pappers ici).
"""

import os

import anthropic
from dotenv import load_dotenv

from engine.formatage import formater_contexte_entreprise
from engine.llm_json import extraire_json
from engine.schema import (
    ContexteProspect,
    CriteresScore,
    FiltresEliminatoires,
    ProspectInput,
    RedFlagsEntree,
    RedFlagsFitIsaa,
)

load_dotenv()

EFFECTIF_MIN_ICP = 10
EFFECTIF_MAX_ICP = 50

SYSTEM_PROMPT = """Tu qualifies, pour l'équipe interne d'Issalya (cabinet de conseil en \
IA Alignment), un prospect ayant réservé un ISAC (Issalya Alignment Check), à partir de son \
contexte (réponses à un formulaire de pré-qualification, données publiques de l'entreprise).

Tu dois juger chaque critère ci-dessous par vrai ou faux, à partir des informations \
disponibles. Si une information manque pour juger un critère avec confiance, réponds par \
défaut "false" plutôt que de deviner — un critère non confirmé ne doit jamais être compté \
comme acquis.

FILTRES ÉLIMINATOIRES (binaires, priment sur le score) :
- expertise_metier_differenciee_de_ia : l'entreprise vend principalement une expertise \
métier, et non les mêmes capacités IA qu'Issalya (exclut les pure players IA)
- production_collaborative_recurrente : plusieurs collaborateurs produisent des contenus, \
analyses, recommandations ou livrables récurrents
- probleme_depasse_curiosite_ia : le problème évoqué dépasse une simple curiosité pour l'IA

CRITÈRES DU SCORE ICP (chacun vaut 2 points sur 20) :
- effectif_10_a_50 : laisse ce champ à false, il est calculé séparément, ignore-le
- expertise_metier_forte_differenciee : expertise métier forte et clairement différenciée
- ia_deja_utilisee_plusieurs_collaborateurs : l'IA est déjà utilisée par plusieurs \
collaborateurs
- usages_disperses_ou_absence_cadre_commun : usages de l'IA dispersés, ou absence de cadre \
commun
- production_importante_livrables_reutilisables : production importante de livrables ou de \
connaissances réutilisables
- risque_confidentialite_qualite_marque_identifie : un risque de confidentialité, de \
qualité ou de marque est identifié
- declencheur_achat_visible_6_mois : un déclencheur d'achat est visible dans les 6 mois
- sponsor_niveau_associe_dg_coo : le sponsor est de niveau associé, DG ou COO
- budget_compatible_isaa_et_chantier_ulterieur : le budget est compatible avec l'ISAA et un \
chantier ultérieur
- potentiel_relation_au_dela_action_isolee : il y a un potentiel de relation au-delà d'une \
action isolée

RED FLAGS D'ENTRÉE (anti-ICP) :
- est_auto_entrepreneur_ou_freelance : l'entreprise est un auto-entrepreneur ou un freelance
- structure_trop_petite_sans_capacite_investissement : structure trop petite, sans capacité \
d'investissement
- gouvernance_ia_deja_mature_sans_besoin_formation : gouvernance IA déjà très mature, sans \
besoin spécifique de formation

RED FLAGS DE FIT ISAA (préparation post-ISAC) :
- cherche_validation_decision_deja_prise : le prospect cherche uniquement une validation \
d'une décision déjà prise
- attend_quissalya_choisisse_outil : il attend qu'Issalya lui indique quel outil acheter
- refuse_fournir_informations_necessaires : il n'est pas disposé à fournir les informations \
nécessaires
- personnes_necessaires_non_accessibles : les personnes nécessaires ne seront pas \
accessibles
- aucun_sponsor_interne_actif : aucun sponsor interne ne peut porter activement la démarche \
au quotidien (obtenir les accès, coordonner, relancer en interne — différent de la \
séniorité du sponsor, déjà comptée dans le score ICP)
- sujet_hors_champ_competences_issalya : le sujet sort du champ de compétences d'Issalya

Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après, au format :
{
  "filtres": {
    "expertise_metier_differenciee_de_ia": true/false,
    "production_collaborative_recurrente": true/false,
    "probleme_depasse_curiosite_ia": true/false
  },
  "criteres_score": {
    "effectif_10_a_50": false,
    "expertise_metier_forte_differenciee": true/false,
    "ia_deja_utilisee_plusieurs_collaborateurs": true/false,
    "usages_disperses_ou_absence_cadre_commun": true/false,
    "production_importante_livrables_reutilisables": true/false,
    "risque_confidentialite_qualite_marque_identifie": true/false,
    "declencheur_achat_visible_6_mois": true/false,
    "sponsor_niveau_associe_dg_coo": true/false,
    "budget_compatible_isaa_et_chantier_ulterieur": true/false,
    "potentiel_relation_au_dela_action_isolee": true/false
  },
  "red_flags_entree": {
    "est_auto_entrepreneur_ou_freelance": true/false,
    "structure_trop_petite_sans_capacite_investissement": true/false,
    "gouvernance_ia_deja_mature_sans_besoin_formation": true/false
  },
  "red_flags_fit_isaa": {
    "cherche_validation_decision_deja_prise": true/false,
    "attend_quissalya_choisisse_outil": true/false,
    "refuse_fournir_informations_necessaires": true/false,
    "personnes_necessaires_non_accessibles": true/false,
    "aucun_sponsor_interne_actif": true/false,
    "sujet_hors_champ_competences_issalya": true/false
  }
}
"""


def _calculer_effectif_10_a_50(effectif: int) -> bool:
    return EFFECTIF_MIN_ICP <= effectif <= EFFECTIF_MAX_ICP


def interpreter_prospect(
    contexte: ContexteProspect,
    client: anthropic.Anthropic | None = None,
) -> ProspectInput:
    """Appelle Claude pour juger les critères subjectifs, et calcule
    effectif_10_a_50 directement (pas besoin de jugement pour un chiffre
    déjà connu)."""
    client = client or anthropic.Anthropic()
    modele = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    reponse = client.messages.create(
        model=modele,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": formater_contexte_entreprise(contexte)}],
    )

    texte = next(bloc.text for bloc in reponse.content if bloc.type == "text")
    donnees = extraire_json(texte)

    criteres_score = dict(donnees["criteres_score"])
    criteres_score["effectif_10_a_50"] = _calculer_effectif_10_a_50(contexte.effectif)

    return ProspectInput(
        filtres=FiltresEliminatoires(**donnees["filtres"]),
        criteres_score=CriteresScore(**criteres_score),
        red_flags_entree=RedFlagsEntree(**donnees["red_flags_entree"]),
        red_flags_fit_isaa=RedFlagsFitIsaa(**donnees["red_flags_fit_isaa"]),
    )
