"""Tests du handler webhook Tally. enregistrer() est simulée (Mock) :
aucun appel réseau réel (ni Google Sheets, ni ailleurs).
"""

from unittest.mock import MagicMock

import pytest

from handlers.tally_webhook import gerer_webhook_tally
from tests.test_connector_tally import PAYLOAD_EXEMPLE


def test_gerer_webhook_tally_enregistre_les_bonnes_donnees():
    enregistrer_simule = MagicMock()

    gerer_webhook_tally(PAYLOAD_EXEMPLE, enregistrer=enregistrer_simule)

    enregistrer_simule.assert_called_once_with(
        email="dylan.durand88@outlook.fr",
        nom_entreprise="Cabinet Delacroix & Associés",
        reponses_formulaire=enregistrer_simule.call_args.kwargs["reponses_formulaire"],
    )
    reponses = enregistrer_simule.call_args.kwargs["reponses_formulaire"]
    assert "1. Combien de collaborateurs compte votre cabinet ?" in reponses
    assert "Email" not in reponses


def test_gerer_webhook_tally_leve_une_erreur_si_email_absent():
    payload_sans_email = {
        "data": {"fields": [{"key": "k", "label": "Prénom", "type": "INPUT_TEXT", "value": "Dylan"}]}
    }

    with pytest.raises(ValueError):
        gerer_webhook_tally(payload_sans_email, enregistrer=MagicMock())
