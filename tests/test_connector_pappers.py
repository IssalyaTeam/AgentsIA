"""Tests du connecteur Pappers (déterministe, aucun appel réseau).

Ces tests portent sur extraire_donnees_entreprise() et ses fonctions
internes, à partir d'un vrai résultat de l'API Pappers (endpoint
/v2/recherche, entreprise TOMCO). rechercher_entreprise() elle-même
(l'appel HTTP) n'est pas testée ici : c'est un simple appel `requests`,
et un test réel coûterait un appel API pour peu de valeur ajoutée.
"""

from engine.schema import Etablissement, ExerciceFinancier
from connectors.pappers import extraire_donnees_entreprise

# Résultat réel de /v2/recherche pour l'entreprise TOMCO (TOP MANAGER COUNCIL)
RESULTAT_TOMCO = {
    "siren": "803557057",
    "siren_formate": "803 557 057",
    "diffusable": True,
    "nom_entreprise": "TOMCO (TOP MANAGER COUNCIL)",
    "personne_morale": True,
    "denomination": "TOMCO (TOP MANAGER COUNCIL)",
    "nom": None,
    "prenom": None,
    "sexe": None,
    "entreprise_cessee": 0,
    "statut_rcs": "Inscrit",
    "statut_consolide": "actif",
    "categorie_juridique": "5710",
    "forme_juridique": "SAS, société par actions simplifiée",
    "date_creation": "2014-07-15",
    "date_creation_formate": "15/07/2014",
    "code_naf": "70.22Z",
    "libelle_code_naf": "Conseil pour les affaires et autres conseils de gestion",
    "domaine_activite": "Activités des sièges sociaux ; conseil de gestion",
    "siege": {
        "siret": "80355705700046",
        "siret_formate": "803 557 057 00046",
        "nic": "00046",
        "numero_voie": "82",
        "indice_repetition": None,
        "type_voie": "AVENUE",
        "libelle_voie": "DU MAINE",
        "complement_adresse": None,
        "adresse_ligne_1": "82 AVENUE DU MAINE",
        "adresse_ligne_2": None,
        "code_postal": "75014",
        "code_commune": "75114",
        "ville": "PARIS",
        "pays": "France",
        "code_pays": "FR",
        "latitude": 48.83840302900245,
        "longitude": 2.322111988834179,
    },
    "villes": ["PARIS"],
    "conventions_collectives": [
        {
            "nom": (
                "Convention collective nationale des bureaux d'études techniques, "
                "des cabinets d'ingénieurs-conseils et des sociétés de conseils"
            ),
            "idcc": 1486,
            "pourcentage": None,
            "confirmee": True,
        }
    ],
    "date_cessation": None,
    "entreprise_employeuse": 0,
    "tranche_effectif": "11",
    "effectif": "Entre 10 et 19 salariés",
    "effectif_min": 10,
    "effectif_max": 19,
    "economie_sociale_et_solidaire": False,
    "annee_effectif": 2023,
    "association": None,
    "capital": 43640,
    "chiffre_affaires": None,
    "resultat": 62563,
    "effectifs_finances": None,
    "annee_finances": 2023,
    "etablissements": [
        {
            "siret": "80355705700046",
            "adresse_ligne_1": "82 AVENUE DU MAINE",
            "ville": "PARIS",
        },
        {
            "siret": "80355705700012",
            "adresse_ligne_1": "14 AVENUE D'EYLAU",
            "ville": "PARIS",
        },
        {
            "siret": "80355705700020",
            "adresse_ligne_1": "19 RUE DE BASSANO",
            "ville": "PARIS",
        },
        {
            "siret": "80355705700038",
            "adresse_ligne_1": "25 RUE JEAN GIRAUDOUX",
            "ville": "PARIS",
        },
    ],
    "dirigeants": [],
    "beneficiaires": [],
    "documents": [],
    "publications": [],
    "nb_dirigeants_total": 3,
    "nb_beneficiaires_total": 1,
    "nb_documents_avec_mentions": 0,
    "nb_documents_total": 13,
    "nb_publications_avec_mentions": 0,
    "nb_publications_total": 15,
}


def test_extrait_les_champs_simples():
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)

    assert donnees["nom_entreprise"] == "TOMCO (TOP MANAGER COUNCIL)"
    assert donnees["secteur_activite"] == "Conseil pour les affaires et autres conseils de gestion"
    assert donnees["forme_juridique"] == "SAS, société par actions simplifiée"
    assert donnees["capital_social_euros"] == 43640


def test_effectif_prend_la_borne_haute_de_la_tranche():
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)
    assert donnees["effectif"] == 19


def test_anciennete_calculee_depuis_la_date_de_creation():
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)
    # Créée le 2014-07-15 ; test exécuté après le 15 juillet de l'année en
    # cours, donc l'anniversaire 2026 est déjà passé.
    assert donnees["anciennete_annees"] == 12


def test_appartenance_groupe_par_defaut_a_false():
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)
    assert donnees["appartient_a_un_groupe"] is False


def test_etablissements_avec_siege_identifie():
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)
    etablissements = donnees["etablissements"]

    assert len(etablissements) == 4
    assert all(isinstance(e, Etablissement) for e in etablissements)

    siege = next(e for e in etablissements if e.est_siege)
    assert siege.nom_ou_enseigne == "82 AVENUE DU MAINE"
    assert siege.ville == "PARIS"

    autres = [e for e in etablissements if not e.est_siege]
    assert len(autres) == 3


def test_historique_financier_avec_un_seul_exercice():
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)
    historique = donnees["historique_financier"]

    assert historique == [
        ExerciceFinancier(annee=2023, chiffre_affaires_euros=None, resultat_net_euros=62563)
    ]


def test_historique_financier_vide_si_aucune_donnee():
    resultat_sans_finances = {**RESULTAT_TOMCO, "resultat": None, "chiffre_affaires": None}
    donnees = extraire_donnees_entreprise(resultat_sans_finances)
    assert donnees["historique_financier"] == []


def test_dirigeants_procedures_et_changements_absents_du_resultat():
    """Ces champs ne sont pas produits par le connecteur Pappers actuel
    (non disponibles via /v2/recherche) : ContexteProspect les gardera à
    leurs valeurs par défaut (listes vides) si rien d'autre ne les remplit.
    """
    donnees = extraire_donnees_entreprise(RESULTAT_TOMCO)
    assert "dirigeants" not in donnees
    assert "procedures_collectives" not in donnees
    assert "changements_recents" not in donnees
