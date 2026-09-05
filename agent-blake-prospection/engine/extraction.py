"""Extraction déterministe : HTML brut -> texte, titre, signaux de taille et de groupe.

Aucun appel réseau ni appel LLM ici — uniquement du parsing et des regex,
donc entièrement testable en TDD classique (pas de propriétés statistiques).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Regex de détection groupe/filiale/fusion, fournie telle quelle par la
# spécification métier — ne pas modifier sans repasser les 6 cas de
# non-régression (Axioncom et Ombello en dépendent directement).
SIGNAL_GROUPE_PATTERN = re.compile(
    r"(filiale (?:de|du groupe)[^.<]{0,80}"
    r"|fait partie (?:de|du groupe)[^.<]{0,80}"
    r"|(?:rejoint|membre) (?:le|du) groupe[^.<]{0,80}"
    r"|a\s+[A-Z][A-Za-z\s&]{2,40}group company"
    r"|part of the\s+[A-Z][A-Za-z\s&]{2,40}group"
    r"|unissent leurs forces[^.<]{0,80}"
    r"|racheté par[^.<]{0,80}"
    r"|rachat par[^.<]{0,80}"
    r"|acquisition par[^.<]{0,80}"
    r"|s'associe à[^.<]{0,80}"
    r"|fusion avec[^.<]{0,80}"
    r"|rapprochement avec[^.<]{0,80}"
    r"|\d+\s+filiales?[^.<]{0,80}"
    r"|écosystème\s+[A-Z][A-Za-z]{2,30}[^.<]{0,80}"
    r"|sociétés spécialisées[^.<]{0,80})",
    re.IGNORECASE,
)

# Signaux de taille : nombre suivi d'une unité type (consultants, clients,
# bureaux...). Le "+" est toléré avant ou après le nombre ("+300 clients",
# "300+ clients"). Pas de spécification verbatim fournie pour ce motif
# (contrairement à SIGNAL_GROUPE_PATTERN) : conçu à partir des exemples
# donnés ("X consultants", "+300 clients", "5 bureaux").
SIGNAUX_TAILLE_PATTERN = re.compile(
    r"\+?\d+\+?\s+(?:consultants?|collaborateurs?|salariés?|employés?"
    r"|experts?|associés?|clients?|bureaux?|agences?|sites?)\b",
    re.IGNORECASE,
)

_BALISES_A_IGNORER = ("script", "style", "noscript")


def html_vers_texte(html: str) -> str:
    """Convertit le HTML brut en texte visible normalisé (espaces compressés)."""
    soup = BeautifulSoup(html, "html.parser")
    for balise in soup(_BALISES_A_IGNORER):
        balise.decompose()
    texte = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", texte).strip()


def extraire_titre(html: str) -> str:
    """Extrait le contenu de <title>, ou "" si absent."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def detecter_signal_groupe(texte: str) -> str:
    """Retourne l'extrait détecté par SIGNAL_GROUPE_PATTERN, ou "" si aucun."""
    match = SIGNAL_GROUPE_PATTERN.search(texte)
    return match.group(0).strip() if match else ""


def detecter_signaux_taille(texte: str) -> str:
    """Retourne les signaux de taille détectés, joints par ", ", ou "" si aucun."""
    signaux = SIGNAUX_TAILLE_PATTERN.findall(texte)
    return ", ".join(dict.fromkeys(signaux))
