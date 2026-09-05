"""Mise en forme texte de ContexteProspect, pour les prompts envoyés à
Claude. Partagé par qualification.py et interpretation.py.
"""

from engine.schema import ContexteProspect


def formater_liste(elements: list[str], texte_si_vide: str) -> str:
    if not elements:
        return texte_si_vide
    return "\n".join(f"- {element}" for element in elements)


def formater_contexte_entreprise(contexte: ContexteProspect) -> str:
    """Décrit l'entreprise et ses réponses au formulaire, sans les
    résultats du scoring (calculés après, à partir de ce que ce module
    produit — l'ordre d'appel est : interpretation -> scoring -> red_flags
    -> qualification).
    """
    reponses = "\n".join(
        f"- {question} : {reponse}" for question, reponse in contexte.reponses_formulaire.items()
    )

    capital_social = (
        f"{contexte.capital_social_euros} €"
        if contexte.capital_social_euros is not None
        else "non renseigné"
    )

    dirigeants = formater_liste(
        [
            f"{d.nom} — {d.fonction}"
            + (f" (nommé le {d.date_nomination})" if d.date_nomination else "")
            for d in contexte.dirigeants
        ],
        "aucun dirigeant renseigné",
    )

    etablissements = formater_liste(
        [
            f"{e.nom_ou_enseigne} ({e.ville})" + (" — siège" if e.est_siege else "")
            for e in contexte.etablissements
        ],
        "aucun établissement renseigné",
    )

    historique_financier = formater_liste(
        [
            f"{ex.annee} : chiffre d'affaires "
            + (
                f"{ex.chiffre_affaires_euros} €"
                if ex.chiffre_affaires_euros is not None
                else "non renseigné"
            )
            + ", résultat net "
            + (
                f"{ex.resultat_net_euros} €"
                if ex.resultat_net_euros is not None
                else "non renseigné"
            )
            for ex in contexte.historique_financier
        ],
        "aucun exercice renseigné",
    )

    procedures_collectives = formater_liste(
        contexte.procedures_collectives, "aucune procédure collective détectée"
    )
    changements_recents = formater_liste(
        contexte.changements_recents, "aucun changement récent notable"
    )

    return f"""Entreprise : {contexte.nom_entreprise}
Forme juridique : {contexte.forme_juridique or "non renseignée"}
Capital social : {capital_social}
Secteur d'activité : {contexte.secteur_activite}
Effectif : {contexte.effectif}
Ancienneté : {contexte.anciennete_annees} ans
Appartient à un groupe : {"oui" if contexte.appartient_a_un_groupe else "non"}

Dirigeants :
{dirigeants}

Établissements / filiales :
{etablissements}

Historique financier (chiffre d'affaires, résultat net) :
{historique_financier}

Procédures collectives :
{procedures_collectives}

Changements récents (dirigeant, capital) :
{changements_recents}

Réponses au formulaire de pré-qualification :
{reponses}

Résumé du site web : {contexte.resume_site_web}"""
