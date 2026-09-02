"""Structures de données génériques du moteur de qualification.

Ces structures ne dépendent d'aucune source de données (Tally, Pappers...).
Tout connecteur doit produire un ProspectInput ; le moteur ne connaît
que ce format.
"""

from dataclasses import dataclass, field


@dataclass
class FiltresEliminatoires:
    expertise_metier_differenciee_de_ia: bool
    production_collaborative_recurrente: bool
    probleme_depasse_curiosite_ia: bool


@dataclass
class CriteresScore:
    effectif_10_a_50: bool
    expertise_metier_forte_differenciee: bool
    ia_deja_utilisee_plusieurs_collaborateurs: bool
    usages_disperses_ou_absence_cadre_commun: bool
    production_importante_livrables_reutilisables: bool
    risque_confidentialite_qualite_marque_identifie: bool
    declencheur_achat_visible_6_mois: bool
    sponsor_niveau_associe_dg_coo: bool
    budget_compatible_isaa_et_chantier_ulterieur: bool
    potentiel_relation_au_dela_action_isolee: bool


@dataclass
class RedFlagsEntree:
    est_auto_entrepreneur_ou_freelance: bool
    structure_trop_petite_sans_capacite_investissement: bool
    gouvernance_ia_deja_mature_sans_besoin_formation: bool


@dataclass
class RedFlagsFitIsaa:
    cherche_validation_decision_deja_prise: bool
    attend_quissalya_choisisse_outil: bool
    refuse_fournir_informations_necessaires: bool
    personnes_necessaires_non_accessibles: bool
    aucun_sponsor_interne_actif: bool
    sujet_hors_champ_competences_issalya: bool


@dataclass
class ProspectInput:
    filtres: FiltresEliminatoires
    criteres_score: CriteresScore
    red_flags_entree: RedFlagsEntree
    red_flags_fit_isaa: RedFlagsFitIsaa


@dataclass
class ResultatScoring:
    score: int
    priorite: str
    filtres_ok: bool
    filtres_echoues: list[str]


@dataclass
class ResultatRedFlags:
    red_flags_entree_detectes: list[str]
    red_flags_fit_isaa_detectes: list[str]


@dataclass
class Dirigeant:
    nom: str
    fonction: str
    date_nomination: str  # format "AAAA-MM-JJ", chaîne vide si inconnue


@dataclass
class Etablissement:
    nom_ou_enseigne: str
    ville: str
    est_siege: bool


@dataclass
class ExerciceFinancier:
    annee: int
    chiffre_affaires_euros: int | None
    resultat_net_euros: int | None


@dataclass
class ContexteProspect:
    """Informations textuelles libres, utilisées pour rédiger la synthèse.

    Contrairement à ProspectInput (booléens déjà tranchés pour le scoring),
    ce contexte reste brut : c'est le module de génération d'hypothèses qui
    l'interprète, pas le moteur de scoring.
    """

    nom_entreprise: str
    secteur_activite: str
    effectif: int
    anciennete_annees: int
    appartient_a_un_groupe: bool
    reponses_formulaire: dict[str, str]
    resume_site_web: str
    forme_juridique: str = ""
    capital_social_euros: int | None = None
    dirigeants: list[Dirigeant] = field(default_factory=list)
    etablissements: list[Etablissement] = field(default_factory=list)
    historique_financier: list[ExerciceFinancier] = field(default_factory=list)
    procedures_collectives: list[str] = field(default_factory=list)
    changements_recents: list[str] = field(default_factory=list)


@dataclass
class HypothesesQualification:
    enjeux_probables: list[str]
    opportunites_probables: list[str]
    synthese: str
