"""Tests du connecteur Tally (déterministe, aucun appel réseau)."""

from connectors.tally import extraire_email, extraire_nom_entreprise, extraire_reponses_formulaire

# Payload d'exemple réel (webhook Tally, formulaire "Pré-qualification audit Issalya")
PAYLOAD_EXEMPLE = {
    "eventId": "ce9f355d-2fc8-4f16-b56f-db656ef57f4a",
    "eventType": "FORM_RESPONSE",
    "createdAt": "2026-08-14T10:55:00.000Z",
    "data": {
        "responseId": "Z9Z97Go",
        "submissionId": "Z9Z97Go",
        "respondentId": "Pdgjl70",
        "formId": "XxA4WO",
        "formName": "Pré-qualification audit Issalya",
        "createdAt": "2026-08-14T10:55:00.000Z",
        "fields": [
            {
                "key": "question_OYq4Za",
                "label": "Prénom",
                "type": "INPUT_TEXT",
                "value": "Dylan",
            },
            {
                "key": "question_VY7Qaj",
                "label": "Email",
                "type": "INPUT_EMAIL",
                "value": "dylan.durand88@outlook.fr",
            },
            {
                "key": "question_ZkNq8m",
                "label": "Entreprise",
                "type": "INPUT_TEXT",
                "value": "Cabinet Delacroix & Associés",
            },
            {
                "key": "question_DDoQjq",
                "label": "1. Combien de collaborateurs compte votre cabinet ?",
                "type": "MULTIPLE_CHOICE",
                "value": ["9de059f4-6b35-4e20-9be0-268f8e08afae"],
                "options": [
                    {"id": "9de059f4-6b35-4e20-9be0-268f8e08afae", "text": "Moins de 10"},
                    {"id": "55e5d702-06b0-4bc5-b43b-f8015de4954f", "text": "Entre 10 et 50"},
                    {"id": "3380f081-d760-4bef-bbae-5b398d076250", "text": "Plus de 50"},
                ],
            },
            {
                "key": "question_lWjQxB",
                "label": "2.Utilisez-vous déjà des outils d'IA dans votre activité aujourd'hui ?",
                "type": "MULTIPLE_CHOICE",
                "value": ["0f2f9c4a-4845-40f7-b15c-2c1fe03eab50"],
                "options": [
                    {"id": "ea59ed66-e8bf-4670-8327-785f05858bfe", "text": "Non, pas encore"},
                    {
                        "id": "25951563-b0e2-446d-af46-3c024db57559",
                        "text": "Oui, un peu, de façon informelle",
                    },
                    {
                        "id": "0f2f9c4a-4845-40f7-b15c-2c1fe03eab50",
                        "text": (
                            "Oui, plusieurs outils, mais de façon dispersée entre collaborateurs"
                        ),
                    },
                ],
            },
            {
                "key": "question_RYQpAd",
                "label": "3. Qu'est-ce qui vous pousse aujourd'hui à envisager un audit d'alignement IA ?",
                "type": "TEXTAREA",
                "value": "Plus de clarté et de contrôle dans les utilisations",
            },
        ],
    },
}


def test_extrait_les_reponses_textuelles_directement():
    reponses = extraire_reponses_formulaire(PAYLOAD_EXEMPLE)

    assert reponses["Prénom"] == "Dylan"
    assert reponses[
        "3. Qu'est-ce qui vous pousse aujourd'hui à envisager un audit d'alignement IA ?"
    ] == "Plus de clarté et de contrôle dans les utilisations"


def test_resout_les_choix_multiples_vers_leur_texte():
    reponses = extraire_reponses_formulaire(PAYLOAD_EXEMPLE)

    assert reponses["1. Combien de collaborateurs compte votre cabinet ?"] == "Moins de 10"
    assert reponses[
        "2.Utilisez-vous déjà des outils d'IA dans votre activité aujourd'hui ?"
    ] == "Oui, plusieurs outils, mais de façon dispersée entre collaborateurs"


def test_exclut_le_champ_email():
    reponses = extraire_reponses_formulaire(PAYLOAD_EXEMPLE)

    assert "Email" not in reponses


def test_gere_un_payload_sans_champs():
    assert extraire_reponses_formulaire({"data": {"fields": []}}) == {}


def test_extrait_le_nom_de_lentreprise():
    assert extraire_nom_entreprise(PAYLOAD_EXEMPLE) == "Cabinet Delacroix & Associés"


def test_nom_entreprise_absent_retourne_none():
    payload_sans_entreprise = {
        "data": {"fields": [{"key": "k", "label": "Prénom", "type": "INPUT_TEXT", "value": "Dylan"}]}
    }
    assert extraire_nom_entreprise(payload_sans_entreprise) is None


def test_extrait_lemail():
    assert extraire_email(PAYLOAD_EXEMPLE) == "dylan.durand88@outlook.fr"


def test_email_absent_retourne_none():
    payload_sans_email = {
        "data": {"fields": [{"key": "k", "label": "Prénom", "type": "INPUT_TEXT", "value": "Dylan"}]}
    }
    assert extraire_email(payload_sans_email) is None
