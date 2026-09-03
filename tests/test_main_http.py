"""Tests des points d'entrée HTTP (main.py) pour Cloud Functions. Les
handlers sous-jacents sont simulés (Mock) : aucun appel réseau réel.

Les fonctions sont appelées directement avec une fausse requête (plutôt
que via functions_framework.create_app, qui recharge main.py dans un
module séparé et rendrait les monkeypatch inefficaces).
"""

from unittest.mock import MagicMock

import main


class FausseRequete:
    def __init__(self, json_body):
        self._json_body = json_body

    def get_json(self, silent=True):
        return self._json_body


def test_tally_webhook_http_retourne_400_si_pas_de_json():
    reponse, code = main.tally_webhook_http(FausseRequete(None))
    assert code == 400


def test_tally_webhook_http_retourne_400_si_erreur_metier(monkeypatch):
    monkeypatch.setattr(
        main, "gerer_webhook_tally", MagicMock(side_effect=ValueError("email manquant"))
    )
    reponse, code = main.tally_webhook_http(FausseRequete({"quelconque": "payload"}))

    assert code == 400
    assert "email manquant" in reponse


def test_tally_webhook_http_retourne_200_si_ok(monkeypatch):
    gerer_simule = MagicMock()
    monkeypatch.setattr(main, "gerer_webhook_tally", gerer_simule)

    reponse, code = main.tally_webhook_http(FausseRequete({"quelconque": "payload"}))

    assert code == 200
    gerer_simule.assert_called_once_with({"quelconque": "payload"})


def test_calcom_webhook_http_retourne_400_si_pas_de_json():
    reponse, code = main.calcom_webhook_http(FausseRequete(None))
    assert code == 400


def test_calcom_webhook_http_retourne_400_si_erreur_metier(monkeypatch):
    monkeypatch.setattr(
        main,
        "gerer_webhook_calcom",
        MagicMock(side_effect=ValueError("participant introuvable")),
    )
    reponse, code = main.calcom_webhook_http(FausseRequete({"quelconque": "payload"}))

    assert code == 400
    assert "participant introuvable" in reponse


def test_calcom_webhook_http_retourne_200_si_ok(monkeypatch):
    gerer_simule = MagicMock()
    monkeypatch.setattr(main, "gerer_webhook_calcom", gerer_simule)

    reponse, code = main.calcom_webhook_http(FausseRequete({"quelconque": "payload"}))

    assert code == 200
    gerer_simule.assert_called_once_with({"quelconque": "payload"})
