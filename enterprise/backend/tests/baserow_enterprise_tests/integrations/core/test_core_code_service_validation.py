from django.core.exceptions import ValidationError as DjangoValidationError

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow_enterprise.integrations.core.models import (
    CORE_CODE_SERVICE_CODE_MAX_LENGTH,
    CoreCodeService,
)
from baserow_enterprise.integrations.core.service_types import CoreCodeServiceType


def test_core_code_service_code_model_field_has_max_length_validator():
    code_field = CoreCodeService._meta.get_field("code")

    assert code_field.max_length == CORE_CODE_SERVICE_CODE_MAX_LENGTH
    code_field.run_validators("a" * CORE_CODE_SERVICE_CODE_MAX_LENGTH)

    with pytest.raises(DjangoValidationError):
        code_field.run_validators("a" * (CORE_CODE_SERVICE_CODE_MAX_LENGTH + 1))


def test_core_code_service_code_serializer_field_has_max_length_validator():
    code_serializer_field = CoreCodeServiceType().serializer_field_overrides["code"]

    assert code_serializer_field.max_length == CORE_CODE_SERVICE_CODE_MAX_LENGTH
    assert (
        code_serializer_field.run_validation("a" * CORE_CODE_SERVICE_CODE_MAX_LENGTH)
        == "a" * CORE_CODE_SERVICE_CODE_MAX_LENGTH
    )

    with pytest.raises(DRFValidationError):
        code_serializer_field.run_validation(
            "a" * (CORE_CODE_SERVICE_CODE_MAX_LENGTH + 1)
        )


def test_core_code_service_code_request_serializer_field_has_max_length_validator():
    service_type = CoreCodeServiceType()
    code_serializer_field = service_type.request_serializer_field_overrides["code"]

    assert code_serializer_field.max_length == CORE_CODE_SERVICE_CODE_MAX_LENGTH
    assert (
        code_serializer_field.run_validation("a" * CORE_CODE_SERVICE_CODE_MAX_LENGTH)
        == "a" * CORE_CODE_SERVICE_CODE_MAX_LENGTH
    )

    with pytest.raises(DRFValidationError):
        code_serializer_field.run_validation(
            "a" * (CORE_CODE_SERVICE_CODE_MAX_LENGTH + 1)
        )


def test_core_code_service_request_serializer_validates_code_length():
    serializer_class = CoreCodeServiceType().get_serializer_class(
        request_serializer=True
    )

    serializer = serializer_class(
        data={"code": "a" * (CORE_CODE_SERVICE_CODE_MAX_LENGTH + 1)}
    )

    assert not serializer.is_valid()
    assert "code" in serializer.errors
