"""Détection des red flags à partir de données déjà structurées.

Module déterministe, sans aucun appel réseau ou API.
"""

from engine.schema import RedFlagsEntree, RedFlagsFitIsaa


def detecter_red_flags_entree(red_flags: RedFlagsEntree) -> list[str]:
    return [nom for nom, valeur in vars(red_flags).items() if valeur]


def detecter_red_flags_fit_isaa(red_flags: RedFlagsFitIsaa) -> list[str]:
    return [nom for nom, valeur in vars(red_flags).items() if valeur]
