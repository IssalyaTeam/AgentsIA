"""Tests déterministes pour engine/extraction.py — écrits avant le code (TDD)."""

from __future__ import annotations

from engine.extraction import (
    detecter_signal_groupe,
    detecter_signaux_taille,
    extraire_titre,
    html_vers_texte,
)

# --- html_vers_texte -------------------------------------------------------


def test_html_vers_texte_supprime_scripts_et_styles():
    html = """
    <html><head><style>.x{color:red}</style></head>
    <body>
      <script>console.log('bruit');</script>
      <p>Cabinet de conseil en stratégie.</p>
    </body></html>
    """
    texte = html_vers_texte(html)
    assert "console.log" not in texte
    assert "color:red" not in texte
    assert "Cabinet de conseil en stratégie." in texte


def test_html_vers_texte_normalise_les_espaces():
    html = "<div>Notre équipe de\n            42\n            consultants</div>"
    texte = html_vers_texte(html)
    assert "Notre équipe de 42 consultants" in texte


# --- extraire_titre ---------------------------------------------------------


def test_extraire_titre_present():
    html = "<html><head><title> Cabinet Dupont — Conseil en stratégie </title></head></html>"
    assert extraire_titre(html) == "Cabinet Dupont — Conseil en stratégie"


def test_extraire_titre_absent_retourne_chaine_vide():
    html = "<html><head></head><body><p>Sans titre</p></body></html>"
    assert extraire_titre(html) == ""


# --- detecter_signal_groupe : cas positifs (une branche par motif du regex) --


def test_signal_groupe_filiale_de_groupe():
    texte = "Notre cabinet est une filiale du groupe Duractive, présent dans toute l'Europe."
    signal = detecter_signal_groupe(texte)
    assert signal.startswith("filiale du groupe Duractive")


def test_signal_groupe_fait_partie_du_groupe():
    texte = "Le cabinet fait partie du groupe Kereis depuis 2019."
    assert detecter_signal_groupe(texte).startswith("fait partie du groupe Kereis")


def test_signal_groupe_membre_du_groupe():
    texte = "Depuis cette date, le cabinet est membre du groupe Onepoint."
    assert detecter_signal_groupe(texte).startswith("membre du groupe Onepoint")


def test_signal_groupe_group_company_anglais():
    texte = "Acme Consulting is a Duractive Consulting Group company serving clients worldwide."
    signal = detecter_signal_groupe(texte)
    assert "group company" in signal.lower()


def test_signal_groupe_part_of_the_group_anglais():
    texte = "We are part of the Stanwell Advisory group, active in twelve countries."
    signal = detecter_signal_groupe(texte)
    assert signal.lower().startswith("part of the stanwell advisory group")


def test_signal_groupe_unissent_leurs_forces():
    texte = "Les deux cabinets unissent leurs forces pour accompagner leurs clients communs."
    assert detecter_signal_groupe(texte).startswith("unissent leurs forces")


def test_signal_groupe_rachete_par():
    texte = "Le cabinet a été racheté par TNP en début d'année."
    assert detecter_signal_groupe(texte).startswith("racheté par TNP")


def test_signal_groupe_rachat_par():
    texte = "On note un rachat par le groupe Adventia annoncé la semaine dernière."
    assert detecter_signal_groupe(texte).startswith("rachat par le groupe Adventia")


def test_signal_groupe_acquisition_par():
    texte = "Une acquisition par Wavestone a été finalisée au premier trimestre."
    assert detecter_signal_groupe(texte).startswith("acquisition par Wavestone")


def test_signal_groupe_sassocie_a():
    texte = "Le cabinet s'associe à un acteur européen pour élargir son offre."
    assert detecter_signal_groupe(texte).startswith("s'associe à un acteur européen")


def test_signal_groupe_fusion_avec():
    texte = "Une fusion avec le cabinet voisin est actée depuis janvier."
    assert detecter_signal_groupe(texte).startswith("fusion avec le cabinet voisin")


def test_signal_groupe_rapprochement_avec():
    texte = "Un rapprochement avec un cabinet spécialisé en cybersécurité a été annoncé."
    assert detecter_signal_groupe(texte).startswith("rapprochement avec un cabinet")


def test_signal_groupe_nombre_de_filiales():
    texte = "Le groupe Axioncom compte aujourd'hui 8 filiales spécialisées par secteur."
    signal = detecter_signal_groupe(texte)
    assert "8 filiales" in signal


def test_signal_groupe_ecosysteme():
    texte = "L'écosystème Axioncom regroupe des expertises complémentaires depuis 2015."
    signal = detecter_signal_groupe(texte)
    assert signal.lower().startswith("écosystème axioncom")


def test_signal_groupe_absent_retourne_chaine_vide():
    texte = "Cabinet de conseil indépendant depuis 1998, spécialisé en organisation."
    assert detecter_signal_groupe(texte) == ""


# --- detecter_signal_groupe : faux positif connu (motif "sociétés spécialisées") --


def test_signal_groupe_faux_positif_reseau_de_partenaires_externes():
    """Limite connue et acceptée du motif 'sociétés spécialisées' (voir changelog
    Notion du 04/09) : il ne distingue pas un réseau de partenaires externes
    d'une structure de filiales internes, et se déclenche donc aussi ici alors
    qu'il ne s'agit pas d'un signal de taille/groupe pertinent. Ce test documente
    ce faux positif connu plutôt que de le cacher — à surveiller en usage réel."""
    texte = (
        "Nous nous appuyons sur un réseau de sociétés spécialisées partenaires "
        "dans chaque région pour compléter notre offre."
    )
    signal = detecter_signal_groupe(texte)
    assert signal != ""
    assert "sociétés spécialisées" in signal


# --- detecter_signaux_taille --------------------------------------------------


def test_signal_taille_nombre_de_consultants():
    texte = "Notre équipe de 42 consultants accompagne des clients ambitieux."
    assert "42 consultants" in detecter_signaux_taille(texte)


def test_signal_taille_nombre_de_clients_avec_prefixe_plus():
    texte = "+300 clients nous font confiance chaque année."
    assert "+300 clients" in detecter_signaux_taille(texte)


def test_signal_taille_nombre_de_bureaux():
    texte = "Nous sommes présents dans 5 bureaux en France."
    assert "5 bureaux" in detecter_signaux_taille(texte)


def test_signal_taille_plusieurs_signaux_detectes_ensemble():
    texte = "Notre équipe de 42 consultants sert +300 clients depuis 5 bureaux en France."
    signaux = detecter_signaux_taille(texte)
    assert "42 consultants" in signaux
    assert "+300 clients" in signaux
    assert "5 bureaux" in signaux


def test_signal_taille_absent_retourne_chaine_vide():
    texte = "Cabinet de conseil en stratégie, sans indication chiffrée sur cette page."
    assert detecter_signaux_taille(texte) == ""


def test_signal_taille_detecte_apres_normalisation_html_bruite():
    """Cas limite : le chiffre et le mot du signal sont séparés par du bruit de
    mise en page (retours à la ligne, indentation) dans le HTML source — le
    signal doit être détecté une fois le texte normalisé par html_vers_texte."""
    html = """
    <div class="stats">
        <span>42</span>
        <span>
            consultants
        </span>
    </div>
    """
    texte = html_vers_texte(html)
    assert "42 consultants" in detecter_signaux_taille(texte)
