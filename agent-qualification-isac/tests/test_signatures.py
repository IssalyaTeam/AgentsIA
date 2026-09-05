"""Tests de la vérification de signature des webhooks (déterministe,
aucun appel réseau)."""

import base64
import hashlib
import hmac

from handlers.signatures import verifier_signature_calcom, verifier_signature_tally

SECRET = "un-secret-de-test"
CORPS = b'{"cle": "valeur"}'


def _signature_tally_valide(corps=CORPS, secret=SECRET):
    digest = hmac.new(secret.encode(), corps, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _signature_calcom_valide(corps=CORPS, secret=SECRET):
    return hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()


# --- Tally -----------------------------------------------------------

def test_tally_signature_valide_est_acceptee():
    assert verifier_signature_tally(CORPS, _signature_tally_valide(), SECRET) is True


def test_tally_signature_absente_est_rejetee():
    assert verifier_signature_tally(CORPS, None, SECRET) is False
    assert verifier_signature_tally(CORPS, "", SECRET) is False


def test_tally_signature_incorrecte_est_rejetee():
    assert verifier_signature_tally(CORPS, "signature-bidon", SECRET) is False


def test_tally_signature_dun_autre_secret_est_rejetee():
    signature = _signature_tally_valide(secret="mauvais-secret")
    assert verifier_signature_tally(CORPS, signature, SECRET) is False


def test_tally_signature_dun_corps_modifie_est_rejetee():
    signature = _signature_tally_valide(corps=b'{"cle": "valeur modifiee"}')
    assert verifier_signature_tally(CORPS, signature, SECRET) is False


# --- Cal.com -----------------------------------------------------------

def test_calcom_signature_valide_est_acceptee():
    assert verifier_signature_calcom(CORPS, _signature_calcom_valide(), SECRET) is True


def test_calcom_signature_avec_prefixe_sha256_est_acceptee():
    signature = "sha256=" + _signature_calcom_valide()
    assert verifier_signature_calcom(CORPS, signature, SECRET) is True


def test_calcom_signature_absente_est_rejetee():
    assert verifier_signature_calcom(CORPS, None, SECRET) is False
    assert verifier_signature_calcom(CORPS, "", SECRET) is False


def test_calcom_signature_incorrecte_est_rejetee():
    assert verifier_signature_calcom(CORPS, "signature-bidon", SECRET) is False


def test_calcom_signature_dun_autre_secret_est_rejetee():
    signature = _signature_calcom_valide(secret="mauvais-secret")
    assert verifier_signature_calcom(CORPS, signature, SECRET) is False


def test_calcom_signature_dun_corps_modifie_est_rejetee():
    signature = _signature_calcom_valide(corps=b'{"cle": "valeur modifiee"}')
    assert verifier_signature_calcom(CORPS, signature, SECRET) is False
