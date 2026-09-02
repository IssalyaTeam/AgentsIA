"""Tests du connecteur Slack. envoyer_fiche() est testée avec une fonction
`poster` simulée (Mock) : aucun appel réseau réel.
"""

from unittest.mock import MagicMock

import pytest

from connectors.slack import envoyer_fiche
from engine.schema import FicheSynthese, HypothesesQualification, ResultatRedFlags, ResultatScoring


def _fiche_exemple(donnees_manquantes=None):
    return FicheSynthese(
        nom_entreprise="Cabinet Delacroix & Associés",
        resultat_scoring=ResultatScoring(score=16, priorite="B", filtres_ok=True, filtres_echoues=[]),
        resultat_red_flags=ResultatRedFlags(
            red_flags_entree_detectes=[], red_flags_fit_isaa_detectes=["aucun_sponsor_interne_actif"]
        ),
        hypotheses=HypothesesQualification(
            enjeux_probables=["Usages IA dispersés"],
            opportunites_probables=["Cadrer une gouvernance commune"],
            synthese="Ce prospect présente un potentiel intéressant.",
        ),
        donnees_manquantes=donnees_manquantes or [],
    )


def test_envoyer_fiche_appelle_le_webhook_avec_le_bon_contenu(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/xxx")

    poster_simule = MagicMock()
    poster_simule.return_value.raise_for_status = MagicMock()

    envoyer_fiche(_fiche_exemple(), poster=poster_simule)

    poster_simule.assert_called_once()
    (url,), kwargs = poster_simule.call_args

    assert url == "https://hooks.slack.test/xxx"
    assert "Cabinet Delacroix & Associés" in kwargs["json"]["text"]

    texte_complet = str(kwargs["json"]["blocks"])
    assert "16/20" in texte_complet
    assert "aucun_sponsor_interne_actif" in texte_complet
    assert "Usages IA dispersés" in texte_complet


def test_envoyer_fiche_signale_les_donnees_manquantes(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/xxx")

    poster_simule = MagicMock()
    poster_simule.return_value.raise_for_status = MagicMock()

    envoyer_fiche(_fiche_exemple(donnees_manquantes=["reponses_tally"]), poster=poster_simule)

    _, kwargs = poster_simule.call_args
    premier_bloc = kwargs["json"]["blocks"][0]

    assert "⚠️" in premier_bloc["text"]["text"]
    assert "Tally" in premier_bloc["text"]["text"]


def test_envoyer_fiche_sans_donnees_manquantes_naffiche_pas_dalerte(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/xxx")

    poster_simule = MagicMock()
    poster_simule.return_value.raise_for_status = MagicMock()

    envoyer_fiche(_fiche_exemple(), poster=poster_simule)

    _, kwargs = poster_simule.call_args
    premier_bloc = kwargs["json"]["blocks"][0]

    assert premier_bloc["type"] == "header"


def test_envoyer_fiche_leve_une_erreur_si_webhook_non_configure(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    with pytest.raises(RuntimeError):
        envoyer_fiche(_fiche_exemple(), poster=MagicMock())


def test_envoyer_fiche_propage_les_erreurs_http(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/xxx")

    poster_simule = MagicMock()
    poster_simule.return_value.raise_for_status.side_effect = RuntimeError("erreur HTTP")

    with pytest.raises(RuntimeError):
        envoyer_fiche(_fiche_exemple(), poster=poster_simule)
