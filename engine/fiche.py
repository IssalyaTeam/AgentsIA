"""Assemblage de la fiche de synthèse finale, à partir des résultats déjà
produits par scoring.py, red_flags.py et qualification.py.

Ne fait aucun calcul propre : combine des résultats déjà obtenus. Comme
le reste du moteur, ne connaît aucune source de données externe.
"""

from engine.schema import (
    ContexteProspect,
    FicheSynthese,
    HypothesesQualification,
    ResultatRedFlags,
    ResultatScoring,
)


def assembler_fiche(
    contexte: ContexteProspect,
    resultat_scoring: ResultatScoring,
    resultat_red_flags: ResultatRedFlags,
    hypotheses: HypothesesQualification,
) -> FicheSynthese:
    return FicheSynthese(
        nom_entreprise=contexte.nom_entreprise,
        resultat_scoring=resultat_scoring,
        resultat_red_flags=resultat_red_flags,
        hypotheses=hypotheses,
    )
