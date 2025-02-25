from unittest.mock import MagicMock, Mock, PropertyMock

import pytest
from rest_framework.exceptions import ValidationError

from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType


def test_service_type_get_schema_name():
    mock_service = Mock(id=123)
    service_type_cls = ServiceType
    service_type_cls.model_class = Mock()
    assert service_type_cls().get_schema_name(mock_service) == "Service123Schema"


def test_service_type_generate_schema():
    mock_service = Mock(id=123)
    service_type_cls = ServiceType
    service_type_cls.model_class = Mock()
    assert service_type_cls().generate_schema(mock_service) is None


@pytest.mark.django_db
def test_service_type_prepare_values(data_fixture):
    user = data_fixture.create_user()
    service_type_cls = ServiceType
    service_type_cls.model_class = Mock()

    application_a = data_fixture.create_builder_application(user=user)
    integration_a = data_fixture.create_local_baserow_integration(
        application=application_a
    )
    instance = Service.objects.create(integration=integration_a)
    application_b = data_fixture.create_builder_application(user=user)
    integration_b = data_fixture.create_local_baserow_integration(
        application=application_b
    )
    integration_c = data_fixture.create_local_baserow_integration(
        application=application_a
    )

    # Unknown integrations throw a validation error.
    with pytest.raises(ValidationError) as exc:
        service_type_cls().prepare_values({"integration_id": 9999999999999999}, user)
    assert (
        exc.value.args[0] == f"The integration with ID 9999999999999999 does not exist."
    )

    # The PATCHed integration cannot belong to a different
    # application to the current one.
    with pytest.raises(ValidationError) as exc:
        service_type_cls().prepare_values(
            {"integration_id": integration_b.id}, user, instance
        )
    assert (
        str(exc.value.detail[0]) == f"The integration with ID {integration_b.id} is "
        f"not related to the given application {application_a.id}."
    )

    # The PATCHed integration does belong to the same application as the current one.
    assert service_type_cls().prepare_values(
        {"integration_id": integration_c.id}, user, instance
    ) == {"integration": integration_c}

    # We are creating a new service with an integration
    assert service_type_cls().prepare_values(
        {"integration_id": integration_c.id}, user
    ) == {"integration": integration_c}


@pytest.mark.parametrize(
    "field_names,expected_field_names",
    [
        (
            {"external": {}},
            [],
        ),
        (
            {"external": {100: ["field_123"]}},
            ["field_123"],
        ),
    ],
)
def test_dispatch_passes_field_names(field_names, expected_field_names):
    """
    Test the base implementation of dispatch(). Ensure it passes field_names
    to dispatch_transform().
    """

    service_type_cls = ServiceType
    service_type_cls.model_class = MagicMock()
    service_type = service_type_cls()

    service_type.resolve_service_formulas = MagicMock()
    mock_data = MagicMock()
    service_type.dispatch_data = MagicMock(return_value=mock_data)
    service_type.dispatch_transform = MagicMock()

    mock_service = MagicMock()
    type(mock_service).id = PropertyMock(return_value=100)
    mock_dispatch_context = MagicMock()

    mock_dispatch_context.public_allowed_properties = field_names

    service_type.dispatch(mock_service, mock_dispatch_context)

    service_type.dispatch_transform.assert_called_once_with(mock_data)


def test_extract_properties():
    """Test the base implementation of extract_properties()."""

    service_type_cls = ServiceType
    service_type_cls.model_class = MagicMock()
    service_type = service_type_cls()

    result = service_type.extract_properties(["foo"])
    assert result == []
