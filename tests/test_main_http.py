"""Tests des points d'entrée HTTP (main.py) pour Cloud Functions. Les
handlers sous-jacents sont simulés (Mock) : aucun appel réseau réel.

Les fonctions sont appelées directement avec une fausse requête (plutôt
que via functions_framework.create_app, qui recharge main.py dans un
module séparé et rendrait les monkeypatch inefficaces).
"""

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock

import main

SECRET_TALLY = "secret-tally-de-test"
SECRET_CALCOM = "secret-calcom-de-test"


def _signer_tally(corps: bytes, secret: str = SECRET_TALLY) -> str:
    return base64.b64encode(hmac.new(secret.encode(), corps, hashlib.sha256).digest()).decode()


def _signer_calcom(corps: bytes, secret: str = SECRET_CALCOM) -> str:
    return hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()


class FausseRequete:
    def __init__(self, json_body, headers=None, corps_brut=None):
        self._json_body = json_body
        self._corps_brut = (
            corps_brut if corps_brut is not None else json.dumps(json_body or {}).encode()
        )
        self.headers = headers or {}

    def get_json(self, silent=True):
        return self._json_body

    def get_data(self):
        return self._corps_brut


def _requete_tally_signee(payload, secret=SECRET_TALLY):
    corps = json.dumps(payload).encode()
    return FausseRequete(payload, headers={"Tally-Signature": _signer_tally(corps, secret)})


def _requete_calcom_signee(payload, secret=SECRET_CALCOM):
    corps = json.dumps(payload).encode()
    return FausseRequete(payload, headers={"X-Cal-Signature-256": _signer_calcom(corps, secret)})


# --- Tally : signature -----------------------------------------------

def test_tally_webhook_http_retourne_401_si_signature_absente(monkeypatch):
    monkeypatch.setenv("TALLY_SIGNING_SECRET", SECRET_TALLY)
    reponse, code = main.tally_webhook_http(FausseRequete({"quelconque": "payload"}))
    assert code == 401


def test_tally_webhook_http_retourne_401_si_signature_invalide(monkeypatch):
    monkeypatch.setenv("TALLY_SIGNING_SECRET", SECRET_TALLY)
    requete = FausseRequete(
        {"quelconque": "payload"}, headers={"Tally-Signature": "signature-bidon"}
    )
    reponse, code = main.tally_webhook_http(requete)
    assert code == 401


def test_tally_webhook_http_retourne_401_si_secret_non_configure(monkeypatch):
    monkeypatch.delenv("TALLY_SIGNING_SECRET", raising=False)
    requete = _requete_tally_signee({"quelconque": "payload"})
    reponse, code = main.tally_webhook_http(requete)
    assert code == 401


def test_tally_webhook_http_retourne_400_si_pas_de_json(monkeypatch):
    monkeypatch.setenv("TALLY_SIGNING_SECRET", SECRET_TALLY)
    requete = FausseRequete(None, corps_brut=b"pas du json")
    requete.headers = {"Tally-Signature": _signer_tally(b"pas du json")}
    reponse, code = main.tally_webhook_http(requete)
    assert code == 400


def test_tally_webhook_http_retourne_400_si_erreur_metier(monkeypatch):
    monkeypatch.setenv("TALLY_SIGNING_SECRET", SECRET_TALLY)
    monkeypatch.setattr(
        main, "gerer_webhook_tally", MagicMock(side_effect=ValueError("email manquant"))
    )
    reponse, code = main.tally_webhook_http(_requete_tally_signee({"quelconque": "payload"}))

    assert code == 400
    assert "email manquant" in reponse


def test_tally_webhook_http_retourne_200_si_ok(monkeypatch):
    monkeypatch.setenv("TALLY_SIGNING_SECRET", SECRET_TALLY)
    gerer_simule = MagicMock()
    monkeypatch.setattr(main, "gerer_webhook_tally", gerer_simule)

    reponse, code = main.tally_webhook_http(_requete_tally_signee({"quelconque": "payload"}))

    assert code == 200
    gerer_simule.assert_called_once_with({"quelconque": "payload"})


# --- Cal.com : signature -----------------------------------------------

def test_calcom_webhook_http_retourne_401_si_signature_absente(monkeypatch):
    monkeypatch.setenv("CALCOM_SIGNING_SECRET", SECRET_CALCOM)
    reponse, code = main.calcom_webhook_http(
        FausseRequete({"triggerEvent": "BOOKING_CREATED"})
    )
    assert code == 401


def test_calcom_webhook_http_retourne_401_si_signature_invalide(monkeypatch):
    monkeypatch.setenv("CALCOM_SIGNING_SECRET", SECRET_CALCOM)
    requete = FausseRequete(
        {"triggerEvent": "BOOKING_CREATED"},
        headers={"X-Cal-Signature-256": "signature-bidon"},
    )
    reponse, code = main.calcom_webhook_http(requete)
    assert code == 401


def test_calcom_webhook_http_retourne_401_si_secret_non_configure(monkeypatch):
    monkeypatch.delenv("CALCOM_SIGNING_SECRET", raising=False)
    requete = _requete_calcom_signee({"triggerEvent": "BOOKING_CREATED"})
    reponse, code = main.calcom_webhook_http(requete)
    assert code == 401


def test_calcom_webhook_http_retourne_400_si_pas_de_json(monkeypatch):
    monkeypatch.setenv("CALCOM_SIGNING_SECRET", SECRET_CALCOM)
    requete = FausseRequete(None, corps_brut=b"pas du json")
    requete.headers = {"X-Cal-Signature-256": _signer_calcom(b"pas du json")}
    reponse, code = main.calcom_webhook_http(requete)
    assert code == 400


def test_calcom_webhook_http_retourne_400_si_erreur_metier(monkeypatch):
    monkeypatch.setenv("CALCOM_SIGNING_SECRET", SECRET_CALCOM)
    monkeypatch.setattr(
        main,
        "gerer_webhook_calcom",
        MagicMock(side_effect=ValueError("participant introuvable")),
    )
    payload = {"triggerEvent": "BOOKING_CREATED", "quelconque": "payload"}
    reponse, code = main.calcom_webhook_http(_requete_calcom_signee(payload))

    assert code == 400
    assert "participant introuvable" in reponse


def test_calcom_webhook_http_retourne_200_si_ok(monkeypatch):
    monkeypatch.setenv("CALCOM_SIGNING_SECRET", SECRET_CALCOM)
    gerer_simule = MagicMock()
    monkeypatch.setattr(main, "gerer_webhook_calcom", gerer_simule)

    payload = {"triggerEvent": "BOOKING_CREATED", "quelconque": "payload"}
    reponse, code = main.calcom_webhook_http(_requete_calcom_signee(payload))

    assert code == 200
    gerer_simule.assert_called_once_with(payload)


def test_calcom_webhook_http_ignore_les_evenements_autres_que_booking_created(monkeypatch):
    monkeypatch.setenv("CALCOM_SIGNING_SECRET", SECRET_CALCOM)
    gerer_simule = MagicMock()
    monkeypatch.setattr(main, "gerer_webhook_calcom", gerer_simule)

    payload = {"triggerEvent": "BOOKING_CANCELLED", "quelconque": "payload"}
    reponse, code = main.calcom_webhook_http(_requete_calcom_signee(payload))

    assert code == 200
    gerer_simule.assert_not_called()
