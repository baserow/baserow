import json
from unittest.mock import Mock

import pytest

from baserow.contrib.integrations.core.integration_types import SMTPIntegrationType
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_smtp_integration_creation(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("smtp")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    assert integration.host == "smtp.example.com"
    assert integration.port == 587
    assert integration.use_tls is True
    assert integration.username == "user@example.com"
    assert integration.password == "password123"
    assert integration.application_id == application.id


@pytest.mark.django_db
def test_smtp_integration_creation_minimal(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("smtp")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        host="smtp.example.com",
    )

    assert integration.host == "smtp.example.com"
    assert integration.port == 587
    assert integration.use_tls is True
    assert integration.username is None
    assert integration.password is None


@pytest.mark.django_db
def test_smtp_integration_update(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_smtp_integration(
        user=user,
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    updated_integration = IntegrationService().update_integration(
        user,
        integration,
        host="smtp.newhost.com",
        port=465,
        use_tls=False,
        username="newuser@example.com",
        password="newpassword456",
    )

    assert updated_integration.host == "smtp.newhost.com"
    assert updated_integration.port == 465
    assert updated_integration.use_tls is False
    assert updated_integration.username == "newuser@example.com"
    assert updated_integration.password == "newpassword456"


@pytest.mark.django_db
def test_smtp_integration_partial_update(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_smtp_integration(
        user=user,
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    updated_integration = IntegrationService().update_integration(
        user,
        integration,
        host="smtp.newhost.com",
        port=465,
    )

    assert updated_integration.host == "smtp.newhost.com"
    assert updated_integration.port == 465
    assert updated_integration.use_tls is True  # unchanged
    assert updated_integration.username == "user@example.com"  # unchanged
    assert updated_integration.password == "password123"  # unchanged


@pytest.mark.django_db
def test_smtp_integration_serializer_field_names(data_fixture):
    integration_type = SMTPIntegrationType()

    expected_fields = ["host", "port", "use_tls", "username", "password"]
    assert integration_type.serializer_field_names == expected_fields
    assert integration_type.allowed_fields == expected_fields
    assert integration_type.request_serializer_field_names == expected_fields


@pytest.mark.django_db
def test_smtp_integration_serialized_dict_type(data_fixture):
    integration_type = SMTPIntegrationType()

    # Check that SerializedDict has the correct annotations
    serialized_dict_class = integration_type.SerializedDict
    annotations = getattr(serialized_dict_class, "__annotations__", {})

    expected_annotations = {
        "host": str,
        "port": int,
        "use_tls": bool,
        "username": str,
        "password": str,
    }

    for field, expected_type in expected_annotations.items():
        assert field in annotations
        assert annotations[field] == expected_type


@pytest.mark.django_db
def test_smtp_integration_prepare_values(data_fixture):
    user = data_fixture.create_user()
    integration_type = SMTPIntegrationType()

    input_values = {
        "host": "smtp.example.com",
        "port": 587,
        "use_tls": True,
        "username": "user@example.com",
        "password": "password123",
    }

    prepared_values = integration_type.prepare_values(input_values, user)

    # Should return the same values as it doesn't do any special processing
    assert prepared_values == input_values


@pytest.mark.django_db
def test_smtp_integration_enhance_queryset(data_fixture):
    integration_type = SMTPIntegrationType()
    mock_queryset = Mock()

    enhanced_queryset = integration_type.enhance_queryset(mock_queryset)

    # Should return the same queryset as it doesn't add any special enhancements
    assert enhanced_queryset == mock_queryset


@pytest.mark.django_db
def test_smtp_integration_export_serialized(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_smtp_integration(
        user=user,
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    integration_type = integration.get_type()
    serialized = json.loads(json.dumps(integration_type.export_serialized(integration)))

    expected_serialized = {
        "id": AnyInt(),
        "type": "smtp",
        "host": "smtp.example.com",
        "port": 587,
        "use_tls": True,
        "username": "user@example.com",
        "password": "password123",
        "name": "",
        "order": "1.00000000000000000000",
    }

    assert serialized == expected_serialized


@pytest.mark.django_db
def test_smtp_integration_export_serialized_exclude_sensitive(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_smtp_integration(
        user=user,
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    integration_type = integration.get_type()

    serialized = json.loads(
        json.dumps(
            integration_type.export_serialized(
                integration,
                import_export_config=ImportExportConfig(
                    include_permission_data=False,
                    reduce_disk_space_usage=False,
                    exclude_sensitive_data=True,
                ),
            )
        )
    )

    expected_serialized = {
        "id": AnyInt(),
        "type": "smtp",
        "host": "smtp.example.com",
        "port": 587,
        "use_tls": True,
        "username": None,
        "password": None,
        "name": "",
        "order": "1.00000000000000000000",
    }

    assert serialized == expected_serialized


@pytest.mark.django_db
def test_smtp_integration_import_serialized(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = SMTPIntegrationType()

    serialized_data = {
        "id": 1,
        "type": "smtp",
        "host": "smtp.example.com",
        "port": 587,
        "use_tls": True,
        "username": "user@example.com",
        "password": "password123",
    }

    imported_integration = integration_type.import_serialized(
        application, serialized_data, {}, lambda x, d: x
    )

    assert imported_integration.host == "smtp.example.com"
    assert imported_integration.port == 587
    assert imported_integration.use_tls is True
    assert imported_integration.username == "user@example.com"
    assert imported_integration.password == "password123"
    assert imported_integration.application_id == application.id


@pytest.mark.django_db
def test_smtp_integration_deletion(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_smtp_integration(
        user=user,
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    integration_id = integration.id

    IntegrationService().delete_integration(user, integration)

    # Verify integration is deleted
    from baserow.contrib.integrations.core.models import SMTPIntegration

    assert not SMTPIntegration.objects.filter(id=integration_id).exists()
