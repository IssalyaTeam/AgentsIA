"""Scraping minimal : un seul appel HTTP sur le site du prospect.

Aucune logique métier ici — uniquement la récupération du HTML brut. Toute
l'interprétation (texte visible, titre, signaux) est faite dans extraction.py,
pour garder ce module remplaçable indépendamment (ex. si un jour on ajoute un
rendu JS, un proxy, ou un cache).
"""

from __future__ import annotations

import logging

import requests

TIMEOUT_SECONDES = 3.0
USER_AGENT = "Mozilla/5.0 (compatible; AgentBlake/1.0; +https://issalya.fr)"


def recuperer_html(url: str) -> str:
    """Récupère le HTML brut de `url` en un seul appel HTTP.

    Retourne une chaîne vide si le scraping échoue (timeout, DNS, 4xx/5xx,
    contenu non HTML) plutôt que de lever une exception : le sondage d'un site
    prospect externe est par nature peu fiable, et un échec de scraping est un
    cas métier normal (verdict CONTENU INSUFFISANT en aval), pas une erreur
    technique de l'agent.
    """
    try:
        reponse = requests.get(
            url,
            timeout=TIMEOUT_SECONDES,
            headers={"User-Agent": USER_AGENT},
        )
        reponse.raise_for_status()
    except requests.RequestException as erreur:
        logging.warning("Scraping échoué pour %s : %s", url, erreur)
        return ""

    content_type = reponse.headers.get("Content-Type", "")
    if "html" not in content_type and content_type != "":
        logging.warning("Contenu non HTML pour %s (Content-Type: %s)", url, content_type)
        return ""

    return reponse.text
