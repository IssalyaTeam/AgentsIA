"""Tests du connecteur Cal.com (déterministe, aucun appel réseau)."""

from connectors.calcom import (
    extraire_email_participant,
    extraire_id_reservation,
    extraire_nom_participant,
)

# Payload d'exemple réel (webhook Cal.com, BOOKING_CREATED)
PAYLOAD_EXEMPLE = {
    "triggerEvent": "BOOKING_CREATED",
    "createdAt": "2026-08-24T08:34:00.000Z",
    "payload": {
        "bookerUrl": "https://cal.com",
        "title": "Rendez-vous de 30 min entre Issalya et Alex",
        "startTime": "2026-08-24T12:00:00.000Z",
        "endTime": "2026-08-24T12:30:00.000Z",
        "additionalNotes": "",
        "type": "audit-30min",
        "eventTypeTitle": "Rendez-vous de 30 min",
        "description": "",
        "eventTypeId": 6324192,
        "organizer": {},
        "attendees": [
            {
                "name": "Alex",
                "email": "arekisanda1992@gmail.com",
                "timeZone": "Europe/Paris",
                "language": {"locale": "fr"},
                "phoneNumber": None,
                "bookingSeat": None,
                "utcOffset": 120,
                "firstName": "Alex",
                "lastName": "",
            }
        ],
        "customInputs": {},
        "responses": {},
        "userFieldsResponses": {},
        "location": "integrations:google:meet",
        "iCalUID": "uLKSExGBt74TDytfyheh6q@Cal.com",
        "uid": "uLKSExGBt74TDytfyheh6q",
        "bookingId": 24214004,
        "status": "ACCEPTED",
        "eventTitle": "Rendez-vous de 30 min",
        "price": 0,
        "currency": "usd",
        "length": 30,
    },
}


def test_extrait_lemail_du_participant():
    assert extraire_email_participant(PAYLOAD_EXEMPLE) == "arekisanda1992@gmail.com"


def test_extrait_le_nom_du_participant():
    assert extraire_nom_participant(PAYLOAD_EXEMPLE) == "Alex"


def test_email_absent_retourne_none():
    assert extraire_email_participant({"payload": {"attendees": []}}) is None


def test_payload_sans_participants_retourne_none():
    assert extraire_email_participant({"payload": {}}) is None
    assert extraire_nom_participant({"payload": {}}) is None


def test_extrait_lid_de_reservation():
    assert extraire_id_reservation(PAYLOAD_EXEMPLE) == "uLKSExGBt74TDytfyheh6q"


def test_id_reservation_absent_retourne_none():
    assert extraire_id_reservation({"payload": {}}) is None
