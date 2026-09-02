"""Point d'entrée : webhook Cal.com (réservation ISAC créée).

Corrèle avec la réponse Tally en attente (par email), enrichit avec
Pappers, fait tourner le moteur de qualification, puis publie le
résultat (Google Sheets + Slack). N'effectue aucun calcul métier
lui-même : orchestre les connecteurs et le moteur.
"""

from connectors import calcom, google_sheets, pappers, slack
from engine.fiche import assembler_fiche
from engine.interpretation import interpreter_prospect
from engine.qualification import generer_hypotheses
from engine.red_flags import detecter_red_flags_entree, detecter_red_flags_fit_isaa
from engine.schema import ContexteProspect, FicheSynthese, ResultatRedFlags
from engine.scoring import qualifier

DONNEES_PAPPERS_PAR_DEFAUT = {
    "secteur_activite": "",
    "effectif": 0,
    "anciennete_annees": 0,
    "appartient_a_un_groupe": False,
}


def gerer_webhook_calcom(
    payload_webhook: dict,
    purger_tally_expires=None,
    chercher_tally=None,
    rechercher_entreprise_pappers=None,
    extraire_donnees_pappers=None,
    interpreter=None,
    qualifier_prospect=None,
    generer_hypotheses_prospect=None,
    enregistrer_fiche_sheets=None,
    envoyer_fiche_slack=None,
) -> FicheSynthese:
    """Traite un webhook Cal.com de bout en bout : identifie le
    participant, corrèle avec Tally, enrichit avec Pappers, fait tourner
    le moteur, publie le résultat.

    Chaque dépendance externe est injectable (tests avec des doublures,
    sans appel réseau réel) ; par défaut, les vraies implémentations.
    """
    purger_tally_expires = purger_tally_expires or google_sheets.purger_reponses_tally_expirees
    chercher_tally = chercher_tally or google_sheets.chercher_et_supprimer_reponse_tally
    rechercher_entreprise_pappers = rechercher_entreprise_pappers or pappers.rechercher_entreprise
    extraire_donnees_pappers = extraire_donnees_pappers or pappers.extraire_donnees_entreprise
    interpreter = interpreter or interpreter_prospect
    qualifier_prospect = qualifier_prospect or qualifier
    generer_hypotheses_prospect = generer_hypotheses_prospect or generer_hypotheses
    enregistrer_fiche_sheets = enregistrer_fiche_sheets or google_sheets.enregistrer_fiche
    envoyer_fiche_slack = envoyer_fiche_slack or slack.envoyer_fiche

    purger_tally_expires()

    email = calcom.extraire_email_participant(payload_webhook)
    if not email:
        raise ValueError(
            "Impossible d'identifier l'email du participant dans ce webhook Cal.com."
        )

    donnees_manquantes = []

    donnees_tally = chercher_tally(email)
    if donnees_tally is None:
        donnees_manquantes.append("reponses_tally")
        reponses_formulaire: dict[str, str] = {}
        nom_entreprise_tally = ""
    else:
        reponses_formulaire = donnees_tally["reponses_formulaire"]
        nom_entreprise_tally = donnees_tally["nom_entreprise"]

    donnees_pappers = None
    if nom_entreprise_tally:
        resultat_pappers = rechercher_entreprise_pappers(nom_entreprise_tally)
        if resultat_pappers:
            donnees_pappers = extraire_donnees_pappers(resultat_pappers)

    if donnees_pappers is None:
        donnees_manquantes.append("donnees_pappers")
        donnees_pappers = {
            "nom_entreprise": nom_entreprise_tally or "Entreprise inconnue",
            **DONNEES_PAPPERS_PAR_DEFAUT,
        }

    contexte = ContexteProspect(
        reponses_formulaire=reponses_formulaire,
        resume_site_web="",  # connecteur site web pas encore construit
        **donnees_pappers,
    )

    prospect_input = interpreter(contexte)
    resultat_scoring = qualifier_prospect(prospect_input)
    resultat_red_flags = ResultatRedFlags(
        red_flags_entree_detectes=detecter_red_flags_entree(prospect_input.red_flags_entree),
        red_flags_fit_isaa_detectes=detecter_red_flags_fit_isaa(prospect_input.red_flags_fit_isaa),
    )
    hypotheses = generer_hypotheses_prospect(contexte, resultat_scoring, resultat_red_flags)

    fiche = assembler_fiche(
        contexte, resultat_scoring, resultat_red_flags, hypotheses, donnees_manquantes
    )

    enregistrer_fiche_sheets(fiche)
    envoyer_fiche_slack(fiche)

    return fiche
