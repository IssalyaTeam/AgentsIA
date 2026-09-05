"""Tests pour engine/qualification.py.

- construire_prompt / parser_reponse / valider_absence_hallucination sont
  déterministes : tests écrits normalement, actifs dès maintenant.
- L'appel réel à Claude (marqueur `api`, payant, non déterministe) est
  vérifié sur des propriétés (5 lignes, pas de chiffre halluciné), pas sur un
  texte exact — cf. méthodologie TDD partiel de l'agent ISAC.
- Les 6 cas de non-régression appellent réellement Claude (marqueur `api`,
  payant, local uniquement — aucune clé Anthropic n'est disponible dans
  l'environnement de développement qui a écrit ces tests, donc ils n'ont pas
  pu être exécutés ici : à lancer avec `pytest -m api` avant toute mise en
  production). Pour CDHR et Interfaces, seule l'égalité de préfixe
  "HORS ICP - Mauvaise spécialité" est vérifiée : c'est la seule formulation
  mandatée au mot près par le prompt pour ces deux catégories (contrairement
  à "agence" et "intermédiation/placement", qui ont un suffixe exact prévu).
"""

from __future__ import annotations

import pytest

from engine.qualification import (
    ErreurQualification,
    construire_prompt,
    parser_reponse,
    qualifier,
    valider_absence_hallucination,
)

# --- construire_prompt -------------------------------------------------------


def test_construire_prompt_remplace_toutes_les_variables():
    prompt = construire_prompt(
        titre_page="Cabinet Dupont — Conseil",
        signaux_taille="42 consultants",
        signal_groupe="",
        contenu_site="Cabinet de conseil en stratégie fondé en 2010.",
        effectif_pappers=42,
        objet_social_pappers="Conseil en gestion",
        )
    assert "{{" not in prompt
    assert "Cabinet Dupont — Conseil" in prompt
    assert "42 consultants" in prompt
    assert "Cabinet de conseil en stratégie fondé en 2010." in prompt
    assert "Conseil en gestion" in prompt


def test_construire_prompt_effectif_pappers_absent_laisse_vide():
    prompt = construire_prompt(
        titre_page="X",
        signaux_taille="",
        signal_groupe="",
        contenu_site="Contenu.",
        effectif_pappers=None,
        objet_social_pappers="Conseil",
    )
    assert (
        "Si un effectif Pappers est disponible pour ce cabinet, le voici "
        "(donnée officielle Insee, à privilégier sur toute estimation) :\n\n"
        "(laisser vide si non disponible)"
    ) in prompt


def test_construire_prompt_signaux_absents_remplaces_par_aucun():
    prompt = construire_prompt(
        titre_page="X",
        signaux_taille="",
        signal_groupe="",
        contenu_site="Contenu.",
        effectif_pappers=None,
        objet_social_pappers="Conseil",
    )
    assert "aucun" in prompt


# --- parser_reponse -----------------------------------------------------------


def _reponse_5_lignes(
    effectif="42",
    verdict="BON FIT",
    segment="Stratégie et organisation",
    signal_ia='Oui, "IA générative pour l\'optimisation des processus"',
    justification="Le cabinet mentionne une équipe de 42 consultants.",
) -> str:
    return (
        f"Effectif : {effectif}\n"
        f"Verdict : {verdict}\n"
        f"Segment : {segment}\n"
        f"Signal IA : {signal_ia}\n"
        f"Justification : {justification}"
    )


def test_parser_reponse_5_lignes_valides():
    resultat = parser_reponse(_reponse_5_lignes())
    assert resultat == {
        "effectif": "42",
        "verdict": "BON FIT",
        "segment": "Stratégie et organisation",
        "signal_ia": 'Oui, "IA générative pour l\'optimisation des processus"',
        "justification": "Le cabinet mentionne une équipe de 42 consultants.",
    }


def test_parser_reponse_tolere_un_bloc_markdown_autour():
    reponse = "```\n" + _reponse_5_lignes() + "\n```"
    resultat = parser_reponse(reponse)
    assert resultat["verdict"] == "BON FIT"


def test_parser_reponse_leve_une_erreur_si_champ_manquant():
    reponse = "Effectif : 42\nVerdict : BON FIT\nSegment : X"
    with pytest.raises(ErreurQualification):
        parser_reponse(reponse)


def test_parser_reponse_leve_une_erreur_si_texte_hors_format():
    with pytest.raises(ErreurQualification):
        parser_reponse("Voici mon raisonnement détaillé sur ce prospect...")


# --- valider_absence_hallucination -------------------------------------------


def test_valider_absence_hallucination_accepte_chiffre_present_dans_le_site():
    resultat = {
        "effectif": "42",
        "verdict": "BON FIT",
        "segment": "",
        "signal_ia": "Non",
        "justification": "Le site mentionne une équipe de 42 consultants.",
    }
    valider_absence_hallucination(
        resultat, contenu_site="Notre équipe de 42 consultants.", signaux_taille="42 consultants", effectif_pappers=None
    )


def test_valider_absence_hallucination_accepte_chiffre_venant_de_pappers():
    resultat = {
        "effectif": "15",
        "verdict": "BON FIT",
        "segment": "",
        "signal_ia": "Non",
        "justification": "Effectif de 15 confirmé par Pappers.",
    }
    valider_absence_hallucination(resultat, contenu_site="Aucun chiffre ici.", signaux_taille="", effectif_pappers=15)


def test_valider_absence_hallucination_rejette_chiffre_invente():
    resultat = {
        "effectif": "information non disponible",
        "verdict": "FIT EDGE",
        "segment": "",
        "signal_ia": "Non",
        "justification": "Le cabinet emploierait environ 250 personnes.",
    }
    with pytest.raises(ErreurQualification):
        valider_absence_hallucination(
            resultat, contenu_site="Cabinet de conseil indépendant.", signaux_taille="", effectif_pappers=None
        )


# --- tests non déterministes (appel réel à Claude) ---------------------------


@pytest.mark.api
def test_qualifier_respecte_le_format_5_lignes_sur_un_cas_simple():
    """Propriété structurelle uniquement : les 5 champs sont présents et
    cohérents avec le texte fourni — ne dépend pas du bloc étapes 0-4."""
    resultat = qualifier(
        titre_page="Dupont Conseil — Stratégie et organisation",
        signaux_taille="42 consultants",
        signal_groupe="",
        contenu_site=(
            "Dupont Conseil accompagne les directions générales sur leurs enjeux de "
            "stratégie et d'organisation depuis 2005. Notre équipe de 42 consultants "
            "intervient en France et en Europe. Nous avons développé une offre "
            "d'accompagnement à l'usage de l'IA générative pour nos clients."
        ),
        effectif_pappers=42,
        objet_social_pappers="Conseil en stratégie et organisation",
    )
    assert set(resultat.keys()) == {"effectif", "verdict", "segment", "signal_ia", "justification"}
    assert resultat["verdict"] != ""
    assert resultat["justification"] != ""


@pytest.mark.api
def test_non_regression_thomas_legrand_consultants_bon_fit():
    # effectif_pappers dans [10, 100] : précondition du filtre Make en Étape 0
    # (les cas hors de cette plage n'atteignent jamais ce module en production).
    resultat = qualifier(
        titre_page="Thomas Legrand Consultants — Conseil en stratégie",
        signaux_taille="",
        signal_groupe="",
        contenu_site=(
            "Thomas Legrand Consultants accompagne les cabinets de conseil et cabinets "
            "d'expertise dans leur transformation stratégique et organisationnelle. "
            "Nous aidons nos clients à structurer l'usage de l'intelligence artificielle "
            "générative dans leurs missions, sans diluer leur expertise métier."
        ),
        effectif_pappers=12,
        objet_social_pappers="Conseil en stratégie et organisation",
    )
    assert resultat["verdict"] == "BON FIT"


@pytest.mark.api
def test_non_regression_reseaulution_bon_fit():
    resultat = qualifier(
        titre_page="Reseaulution — Conseil en organisation",
        signaux_taille="",
        signal_groupe="",
        contenu_site=(
            "Reseaulution est un cabinet de conseil indépendant spécialisé en "
            "organisation et conduite du changement pour les entreprises de conseil "
            "et de services. Notre équipe accompagne les dirigeants dans leurs "
            "projets de transformation, y compris l'intégration de l'IA générative."
        ),
        effectif_pappers=18,
        objet_social_pappers="Conseil en organisation",
    )
    assert resultat["verdict"] == "BON FIT"


@pytest.mark.api
def test_non_regression_cdhr_hors_icp_structure_associative():
    # Le prompt ne mandate un suffixe entre parenthèses exact que pour les
    # catégories "agence" et "intermédiation/placement" (Étape 2). Pour
    # "structure associative/institut technique", seule la règle générique
    # "HORS ICP - Mauvaise spécialité" est un texte mandaté au mot près ; le
    # détail entre parenthèses reste à la libre formulation du modèle. On
    # vérifie donc le préfixe mandaté, et que la Justification qualifie bien
    # la bonne catégorie plutôt que d'exiger une égalité stricte fragile.
    resultat = qualifier(
        titre_page="CDHR — Institut technique de la filière",
        signaux_taille="",
        signal_groupe="",
        contenu_site=(
            "Le CDHR est une association loi 1901 agréée, institut technique de la "
            "filière, qui accompagne ses adhérents sur des missions réglementaires "
            "et propose un volet de conseil accessoire à ses membres."
        ),
        effectif_pappers=15,
        objet_social_pappers="Association technique professionnelle",
    )
    assert resultat["verdict"].startswith("HORS ICP - Mauvaise spécialité")


@pytest.mark.api
def test_non_regression_interfaces_hors_icp_operateur_de_lieux():
    resultat = qualifier(
        titre_page="Interfaces — Espaces et programmes d'accompagnement",
        signaux_taille="",
        signal_groupe="",
        contenu_site=(
            "Interfaces gère des espaces de coworking et anime des programmes "
            "d'accompagnement en présentiel pour entrepreneurs, avec des locaux "
            "dans plusieurs villes de France."
        ),
        effectif_pappers=12,
        objet_social_pappers="Gestion d'espaces et programmes d'accompagnement",
    )
    assert resultat["verdict"].startswith("HORS ICP - Mauvaise spécialité")


@pytest.mark.api
def test_non_regression_axioncom_hors_icp_taille_probable():
    # Test 2 (Étape 0) mandate cette chaîne exacte, mot pour mot, dès qu'un des
    # six signaux de groupe est détecté — équivalence stricte justifiée ici.
    resultat = qualifier(
        titre_page="Axioncom — Écosystème de conseil",
        signaux_taille="",
        signal_groupe="8 filiales spécialisées par secteur",
        contenu_site=(
            "L'écosystème Axioncom regroupe 8 filiales spécialisées par secteur, "
            "chacune apportant une expertise dédiée à ses clients depuis 2015."
        ),
        effectif_pappers=25,
        objet_social_pappers="Conseil en stratégie",
    )
    assert resultat["verdict"] == "HORS ICP - Taille probable (filiale de groupe, Pappers non représentatif)"


@pytest.mark.api
def test_non_regression_ombello_hors_icp_taille_probable():
    resultat = qualifier(
        titre_page="Ombello — Conseil en gestion",
        signaux_taille="",
        signal_groupe="filiale du groupe Baker Tilly",
        contenu_site=(
            "Ombello est une filiale du groupe Baker Tilly, dédiée au conseil en "
            "gestion pour les PME et ETI, s'appuyant sur l'expertise du groupe."
        ),
        effectif_pappers=18,
        objet_social_pappers="Conseil en gestion",
    )
    assert resultat["verdict"] == "HORS ICP - Taille probable (filiale de groupe, Pappers non représentatif)"
