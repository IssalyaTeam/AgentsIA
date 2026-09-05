"""Génération des hypothèses de qualification via l'API Claude.

Seul module du moteur à appeler une API externe. Il reçoit une entrée
générique (ContexteProspect + résultats déjà calculés par scoring.py et
red_flags.py) et ne sait jamais d'où viennent ces données (pas d'appel
direct à Tally ou Pappers ici).
"""

import os

import anthropic
from dotenv import load_dotenv

from engine.formatage import formater_contexte_entreprise
from engine.llm_json import extraire_json
from engine.schema import (
    ContexteProspect,
    HypothesesQualification,
    ResultatRedFlags,
    ResultatScoring,
)

load_dotenv()

MOTS_A_PRIVILEGIER = ["alignement", "clarté", "gouvernance", "confiance", "maîtrise"]
MOTS_INTERDITS = [
    "révolutionnaire",
    "magique",
    "hack",
    "growth",
    "disruptif",
    "booster",
    "ultime",
    "incroyable",
]

SYSTEM_PROMPT = f"""Tu rédiges, pour l'équipe interne d'Issalya (cabinet de conseil en IA \
Alignment), une fiche de préparation avant un appel de qualification (ISAC).

Ton de communication, "Le Langage Issalya" :
- Clair, pédagogue, calme. Jamais mystérieux, jamais pressant.
- Emploie naturellement, quand c'est pertinent, des mots comme : \
{", ".join(MOTS_A_PRIVILEGIER)}.
- N'utilise jamais les mots suivants, ni leurs variantes : {", ".join(MOTS_INTERDITS)}.

Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après, au format :
{{
  "enjeux_probables": ["...", "..."],
  "opportunites_probables": ["...", "..."],
  "synthese": "..."
}}

- "enjeux_probables" : 2 à 4 enjeux probables pour ce prospect, formulés comme des \
hypothèses à vérifier pendant l'appel, jamais comme des certitudes.
- "opportunites_probables" : 2 à 4 opportunités probables pour Issalya.
- "synthese" : un paragraphe de 3 à 5 phrases qui prépare la personne qui va mener l'appel.
"""


def _construire_message_utilisateur(
    contexte: ContexteProspect,
    resultat_scoring: ResultatScoring,
    resultat_red_flags: ResultatRedFlags,
) -> str:
    red_flags_entree = ", ".join(resultat_red_flags.red_flags_entree_detectes) or "aucun"
    red_flags_fit_isaa = ", ".join(resultat_red_flags.red_flags_fit_isaa_detectes) or "aucun"
    filtres_echoues = ", ".join(resultat_scoring.filtres_echoues) or "aucun"

    return f"""{formater_contexte_entreprise(contexte)}

Score ICP : {resultat_scoring.score}/20 — Priorité : {resultat_scoring.priorite}
Filtres éliminatoires échoués : {filtres_echoues}
Red flags d'entrée détectés : {red_flags_entree}
Red flags de fit ISAA détectés : {red_flags_fit_isaa}
"""


def generer_hypotheses(
    contexte: ContexteProspect,
    resultat_scoring: ResultatScoring,
    resultat_red_flags: ResultatRedFlags,
    client: anthropic.Anthropic | None = None,
) -> HypothesesQualification:
    """Appelle Claude pour produire les hypothèses de la fiche de synthèse."""
    client = client or anthropic.Anthropic()
    modele = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    reponse = client.messages.create(
        model=modele,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _construire_message_utilisateur(
                    contexte, resultat_scoring, resultat_red_flags
                ),
            }
        ],
    )

    texte = next(bloc.text for bloc in reponse.content if bloc.type == "text")
    donnees = extraire_json(texte)

    return HypothesesQualification(
        enjeux_probables=donnees["enjeux_probables"],
        opportunites_probables=donnees["opportunites_probables"],
        synthese=donnees["synthese"],
    )
