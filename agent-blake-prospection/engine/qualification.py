"""Construction du prompt, appel Claude, parsing et validation de la réponse.

Le moteur ne connaît aucune source de données externe (Make, Sheets, Slack) :
il reçoit des chaînes déjà extraites (titre, signaux, contenu) et retourne un
verdict structuré. L'orchestration (scraping -> extraction -> qualification)
vit dans connectors/http_endpoint.py.
"""

from __future__ import annotations

import logging
import os
import re

import anthropic

from engine.prompt_qualification import PROMPT_TEMPLATE

MODELE_CLAUDE = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_TENTATIVES = 3
# Le prompt fait ~27000 caractères une fois construit (texte complet des étapes
# 0-4 + contenu du site) : la latence réelle observée en test est de l'ordre de
# 6-7 secondes, largement au-dessus des 3s initialement fixées par analogie
# avec le timeout de scraping. Un timeout trop court ici ne "protège" rien :
# il transforme des réponses valides en échecs systématiques après retries.
TIMEOUT_SECONDES = 20.0

CHAMPS_ATTENDUS = ("Effectif", "Verdict", "Segment", "Signal IA", "Justification")


class ErreurQualification(Exception):
    """Échec technique (API Claude) ou réponse ne respectant pas le format/l'anti-hallucination."""


def construire_prompt(
    *,
    titre_page: str,
    signaux_taille: str,
    signal_groupe: str,
    contenu_site: str,
    effectif_pappers: int | None,
    objet_social_pappers: str,
) -> str:
    """Remplace les {{placeholders}} du template par les valeurs extraites."""
    valeurs = {
        "titre_page": titre_page or "information non disponible",
        "signaux_taille": signaux_taille or "aucun",
        "signal_groupe": signal_groupe or "aucun",
        "contenu_site": contenu_site,
        "effectif_pappers": str(effectif_pappers) if effectif_pappers is not None else "",
        "objet_social_pappers": objet_social_pappers or "information non disponible",
    }
    prompt = PROMPT_TEMPLATE
    for cle, valeur in valeurs.items():
        prompt = prompt.replace("{{" + cle + "}}", valeur)
    return prompt


def _extraire_texte(reponse: object) -> str:
    """Extrait le(s) bloc(s) de type texte de la réponse.

    reponse.content peut contenir un bloc de raisonnement (ThinkingBlock) avant
    le bloc de texte final : ce n'est PAS toujours content[0], donc on filtre
    explicitement par type plutôt que de supposer un index fixe.
    """
    blocs_texte = [bloc.text for bloc in reponse.content if getattr(bloc, "type", None) == "text"]
    if not blocs_texte:
        raise ErreurQualification("Réponse Claude sans bloc de texte exploitable.")
    return "".join(blocs_texte).strip()


def appeler_claude(prompt: str) -> str:
    """Appelle l'API Claude avec retries et timeout ; lève ErreurQualification si tout échoue."""
    client = anthropic.Anthropic(timeout=TIMEOUT_SECONDES)
    derniere_erreur: Exception | None = None

    for tentative in range(1, MAX_TENTATIVES + 1):
        try:
            reponse = client.messages.create(
                model=MODELE_CLAUDE,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return _extraire_texte(reponse)
        except (anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.RateLimitError) as erreur:
            derniere_erreur = erreur
            logging.warning("Appel Claude échoué (tentative %d/%d) : %s", tentative, MAX_TENTATIVES, erreur)
        except anthropic.APIError as erreur:
            logging.error("Erreur Claude non retriable : %s", erreur)
            raise ErreurQualification(f"Appel Claude en échec : {erreur}") from erreur

    raise ErreurQualification(f"Appel Claude en échec après {MAX_TENTATIVES} tentatives : {derniere_erreur}")


def parser_reponse(reponse_brute: str) -> dict[str, str]:
    """Parse les 5 lignes strictes ; lève ErreurQualification si le format est invalide."""
    texte = re.sub(r"^```[a-zA-Z]*\n?|```$", "", reponse_brute.strip(), flags=re.MULTILINE).strip()

    resultat: dict[str, str] = {}
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne or ":" not in ligne:
            continue
        cle, _, valeur = ligne.partition(":")
        cle = cle.strip()
        if cle in CHAMPS_ATTENDUS:
            resultat[cle] = valeur.strip()

    manquants = [champ for champ in CHAMPS_ATTENDUS if champ not in resultat]
    if manquants:
        raise ErreurQualification(f"Réponse Claude mal formée, champs manquants : {manquants} — reçu : {reponse_brute!r}")

    return {
        "effectif": resultat["Effectif"],
        "verdict": resultat["Verdict"],
        "segment": resultat["Segment"],
        "signal_ia": resultat["Signal IA"],
        "justification": resultat["Justification"],
    }


# Références internes à la grille de qualification elle-même (numéros
# d'étape/test/critère du prompt), jamais des données métier hallucinées.
# Ex. "hors périmètre au sens de l'Étape 2" ne doit pas déclencher un rejet.
_REFERENCE_INTERNE = re.compile(r"\b(?:Étape|Test|critère)\s*\d+[a-z]?\b", re.IGNORECASE)

# Chiffre "isolé" (non collé à des lettres) uniquement : un \d+ nu attraperait
# aussi le "2" de sigles comme "B2B" (vocabulaire du prompt lui-même, pas une
# donnée métier) — bug réel trouvé en test avec une vraie clé API sur les cas
# CDHR/Axioncom/Ombello, où la Justification répète naturellement "cabinet de
# conseil B2B".
_CHIFFRE_ISOLE = re.compile(r"(?<![A-Za-z])\d+(?![A-Za-z])")


def valider_absence_hallucination(
    resultat: dict[str, str],
    *,
    contenu_site: str,
    signaux_taille: str,
    effectif_pappers: int | None,
) -> None:
    """Vérifie que tout chiffre cité dans Effectif/Justification apparaît dans une source fournie."""
    source = f"{contenu_site} {signaux_taille} {effectif_pappers or ''}"
    chiffres_source = set(_CHIFFRE_ISOLE.findall(source))

    for champ in ("effectif", "justification"):
        texte_sans_references = _REFERENCE_INTERNE.sub("", resultat[champ])
        for chiffre in _CHIFFRE_ISOLE.findall(texte_sans_references):
            if chiffre not in chiffres_source:
                raise ErreurQualification(
                    f"Chiffre halluciné détecté dans '{champ}' : {chiffre!r} n'apparaît dans aucune source fournie."
                )


def qualifier(
    *,
    titre_page: str,
    signaux_taille: str,
    signal_groupe: str,
    contenu_site: str,
    effectif_pappers: int | None,
    objet_social_pappers: str,
) -> dict[str, str]:
    """Pipeline complet : construction du prompt -> appel Claude -> parsing -> validation."""
    prompt = construire_prompt(
        titre_page=titre_page,
        signaux_taille=signaux_taille,
        signal_groupe=signal_groupe,
        contenu_site=contenu_site,
        effectif_pappers=effectif_pappers,
        objet_social_pappers=objet_social_pappers,
    )
    reponse_brute = appeler_claude(prompt)
    resultat = parser_reponse(reponse_brute)
    valider_absence_hallucination(
        resultat,
        contenu_site=contenu_site,
        signaux_taille=signaux_taille,
        effectif_pappers=effectif_pappers,
    )
    return resultat
