"""Logique de scoring ICP : filtres éliminatoires, score /20, priorité.

Module déterministe, sans aucun appel réseau ou API.
"""

from engine.schema import CriteresScore, FiltresEliminatoires, ProspectInput, ResultatScoring

POINTS_PAR_CRITERE = 2

SEUILS_PRIORITE = (
    (17, "A"),
    (13, "B"),
    (9, "C"),
)
PRIORITE_HORS_CIBLE = "Hors cible"


def evaluer_filtres(filtres: FiltresEliminatoires) -> tuple[bool, list[str]]:
    """Retourne (tous les filtres passent, liste des filtres qui ont échoué)."""
    echoues = [nom for nom, valeur in vars(filtres).items() if not valeur]
    return (len(echoues) == 0, echoues)


def calculer_score(criteres: CriteresScore) -> int:
    """Additionne les points des critères vrais (2 points chacun)."""
    nb_criteres_vrais = sum(1 for valeur in vars(criteres).values() if valeur)
    return nb_criteres_vrais * POINTS_PAR_CRITERE


def determiner_priorite(score: int, filtres_ok: bool) -> str:
    """Applique les seuils de priorité, en excluant d'abord les filtres échoués."""
    if not filtres_ok:
        return PRIORITE_HORS_CIBLE
    for seuil, priorite in SEUILS_PRIORITE:
        if score >= seuil:
            return priorite
    return PRIORITE_HORS_CIBLE


def qualifier(prospect: ProspectInput) -> ResultatScoring:
    """Assemble filtres, score et priorité pour un prospect donné."""
    filtres_ok, filtres_echoues = evaluer_filtres(prospect.filtres)
    score = calculer_score(prospect.criteres_score)
    priorite = determiner_priorite(score, filtres_ok)
    return ResultatScoring(
        score=score,
        priorite=priorite,
        filtres_ok=filtres_ok,
        filtres_echoues=filtres_echoues,
    )
