"""Vérification de signature des webhooks entrants (Tally, Cal.com).

Les fonctions Cloud sont publiques (--allow-unauthenticated, nécessaire
pour que Tally et Cal.com puissent les appeler). Sans vérification de
signature, n'importe qui connaissant l'URL pourrait déclencher le flux
avec un payload arbitraire. Ce module rejette toute requête dont la
signature est absente ou invalide, avant tout traitement métier.
"""

import base64
import hashlib
import hmac


def verifier_signature_tally(corps_brut: bytes, signature_recue: str | None, secret: str) -> bool:
    """Tally-Signature : base64(HMAC-SHA256(secret, corps_brut))."""
    if not signature_recue:
        return False
    attendu = hmac.new(secret.encode(), corps_brut, hashlib.sha256).digest()
    attendu_b64 = base64.b64encode(attendu).decode()
    return hmac.compare_digest(attendu_b64, signature_recue.strip())


def verifier_signature_calcom(corps_brut: bytes, signature_recue: str | None, secret: str) -> bool:
    """X-Cal-Signature-256 : hex(HMAC-SHA256(secret, corps_brut)).

    Tolère un éventuel préfixe "sha256=" (convention vue chez d'autres
    fournisseurs de webhooks, incertain pour Cal.com faute de documentation
    consultable depuis cet environnement — voir le log d'avertissement en
    cas d'échec pour ajuster si besoin).
    """
    if not signature_recue:
        return False
    attendu_hex = hmac.new(secret.encode(), corps_brut, hashlib.sha256).hexdigest()
    recu = signature_recue.strip()
    if recu.startswith("sha256="):
        recu = recu[len("sha256=") :]
    return hmac.compare_digest(attendu_hex, recu)
