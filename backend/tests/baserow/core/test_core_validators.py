from django.core.exceptions import ValidationError

import pytest

from baserow.core.formula.validator import ensure_array
from baserow.core.user.password_validation import MaximumLengthValidator

very_long_password = (
    "Bgvmt95en6HGJZ9Xz0F8xysQ6eYgo2Y54YzRPxxv10b5n16F4rZ6YH4ulonocwiFK6970KiAxoYhU"
    "LYA3JFDPIQGj5gMZZl25M46sO810Zd3nyBg699a2TDMJdHG7hAAi0YeDnuHuabyBawnb4962OQ1OO"
    "f1MxzFyNWG7NR2X6MZQL5G1V61x56lQTXbvK1AG1IPM87bQ3YAtIBtGT2vK3Wd83q3he5ezMtUfzK"
    "2ibj0WWhf86DyQB4EHRUJjYcBiI78iEJv5hcu33X2I345YosO66cTBWK45SqJEDudrCOq"
)


def test_max_length_validator_validate():
    expected_error = "This password is too long. It must not exceed %d characters."
    assert MaximumLengthValidator().validate("12345678") is None
    assert MaximumLengthValidator(max_length=10).validate("1234567890") is None

    with pytest.raises(ValidationError) as cm:
        MaximumLengthValidator(max_length=10).validate("12345678901")

    assert cm.value.messages == [expected_error % 10]
    assert cm.value.error_list[0].code == "password_too_long"

    with pytest.raises(ValidationError) as cm:
        MaximumLengthValidator().validate(very_long_password)

    assert cm.value.messages == [expected_error % 256]


def test_max_length_validator_help_text():
    expected_help_text_plural = "Your password must not exceed 256 characters."
    expected_help_text_singular = "Your password must not exceed 1 character."

    assert MaximumLengthValidator().get_help_text() == expected_help_text_plural
    assert (
        MaximumLengthValidator(max_length=1).get_help_text()
        == expected_help_text_singular
    )


def test_ensure_array_with_unquoted_newline_raises_validation_error():
    with pytest.raises(ValidationError):
        ensure_array('[\n  {\n    "name": ""\n  }\n]')
