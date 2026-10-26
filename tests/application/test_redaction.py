from agent.application.redaction import contains_personal_data, redact_personal_data


def test_card_numbers_and_dni_are_masked():
    text = "La clienta, DNI 70451238, usó la tarjeta 4111 1111 1111 1111."
    assert redact_personal_data(text) == "La clienta, DNI [DNI], usó la tarjeta [TARJETA]."


def test_amounts_phones_dates_and_claim_codes_are_kept():
    text = "Monto S/ 150 000, teléfono (01) 555-0100, fecha 2025-07-28, reclamo RC-2025-000123."
    assert redact_personal_data(text) == text
    assert not contains_personal_data(text)
