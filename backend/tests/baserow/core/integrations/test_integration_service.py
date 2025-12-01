from decimal import Decimal
from unittest.mock import patch

import pytest

from baserow.core.exceptions import PermissionException
from baserow.core.integrations.exceptions import (
    IntegrationDoesNotExist,
    IntegrationNotInSameApplication,
)
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService


def pytest_generate_tests(metafunc):
    if "integration_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "integration_type",
            [pytest.param(e, id=e.type) for e in integration_type_registry.get_all()],
        )


@pytest.mark.django_db
@patch("baserow.core.integrations.service.integration_created")
def test_create_integration(integration_created_mock, data_fixture, integration_type):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application, order="1.0000"
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application, order="2.0000"
    )

    service = IntegrationService()
    integration = service.create_integration(
        user, integration_type, application=application
    )

    last_integration = Integration.objects.last()

    # Check it's the last integration
    assert last_integration.id == integration.id

    integration_created_mock.send.assert_called_once_with(
        service, integration=integration, user=user, before_id=None
    )


@pytest.mark.django_db
def test_create_integration_before(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application, order="1.0000"
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application, order="2.0000"
    )

    integration_type = integration_type_registry.get("local_baserow")

    integration2 = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        before=integration3,
    )

    integrations = Integration.objects.all()
    assert integrations[0].id == integration1.id
    assert integrations[1].id == integration2.id
    assert integrations[2].id == integration3.id


@pytest.mark.django_db
def test_get_unique_orders_before_integration_triggering_full_application_order_reset(
    data_fixture,
):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration_1 = data_fixture.create_local_baserow_integration(
        application=application, order="1.00000000000000000000"
    )
    integration_2 = data_fixture.create_local_baserow_integration(
        application=application, order="1.00000000000000001000"
    )
    integration_3 = data_fixture.create_local_baserow_integration(
        application=application, order="2.99999999999999999999"
    )
    integration_4 = data_fixture.create_local_baserow_integration(
        application=application, order="2.99999999999999999998"
    )

    integration_type = integration_type_registry.get("local_baserow")

    integration_created = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        before=integration_3,
    )

    integration_1.refresh_from_db()
    integration_2.refresh_from_db()
    integration_3.refresh_from_db()
    integration_4.refresh_from_db()

    assert integration_1.order == Decimal("1.00000000000000000000")
    assert integration_2.order == Decimal("2.00000000000000000000")
    assert integration_4.order == Decimal("3.00000000000000000000")
    assert integration_3.order == Decimal("4.00000000000000000000")
    assert integration_created.order == Decimal("3.50000000000000000000")


@pytest.mark.django_db
@patch("baserow.core.integrations.service.integration_orders_recalculated")
def test_recalculate_full_order(integration_orders_recalculated_mock, data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    data_fixture.create_local_baserow_integration(
        application=application, order="1.9000"
    )
    data_fixture.create_local_baserow_integration(
        application=application, order="3.4000"
    )

    service = IntegrationService()
    service.recalculate_full_orders(user, application)

    integration_orders_recalculated_mock.send.assert_called_once_with(
        service, application=application
    )


@pytest.mark.django_db
def test_create_integration_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("local_baserow")

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        IntegrationService().create_integration(
            user, integration_type, application=application
        )


@pytest.mark.django_db
def test_get_integration(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    assert (
        IntegrationService().get_integration(user, integration.id).id == integration.id
    )


@pytest.mark.django_db
def test_get_integration_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(IntegrationDoesNotExist):
        assert IntegrationService().get_integration(user, 0)


@pytest.mark.django_db
def test_get_integration_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        IntegrationService().get_integration(user, integration.id)


@pytest.mark.django_db
def test_get_integrations(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application
    )

    assert [p.id for p in IntegrationService().get_integrations(user, application)] == [
        integration1.id,
        integration2.id,
        integration3.id,
    ]

    def exclude_integration_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=integration1.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_integration_1

        assert [
            p.id for p in IntegrationService().get_integrations(user, application)
        ] == [
            integration2.id,
            integration3.id,
        ]


@pytest.mark.django_db
@patch("baserow.core.integrations.service.integration_deleted")
def test_delete_integration(integration_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    service = IntegrationService()
    service.delete_integration(user, integration)

    integration_deleted_mock.send.assert_called_once_with(
        service,
        integration_id=integration.id,
        application=integration.application,
        user=user,
    )


@pytest.mark.django_db(transaction=True)
def test_delete_integration_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        IntegrationService().delete_integration(user, integration)


@pytest.mark.django_db
@patch("baserow.core.integrations.service.integration_updated")
def test_update_integration(integration_updated_mock, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    service = IntegrationService()
    integration_updated = service.update_integration(
        user, integration, value="newValue"
    )

    integration_updated_mock.send.assert_called_once_with(
        service, integration=integration_updated, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_update_integration_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        IntegrationService().update_integration(user, integration, value="newValue")


@pytest.mark.django_db
@patch("baserow.core.integrations.service.integration_moved")
def test_move_integration(integration_moved_mock, data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application
    )

    service = IntegrationService()
    integration_moved = service.move_integration(
        user, integration3, before=integration2
    )

    integration_moved_mock.send.assert_called_once_with(
        service, integration=integration_moved, user=user, before=integration2
    )


@pytest.mark.django_db
def test_move_integration_not_same_application(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    application2 = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application2
    )

    with pytest.raises(IntegrationNotInSameApplication):
        IntegrationService().move_integration(user, integration3, before=integration2)


@pytest.mark.django_db
def test_move_integration_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application
    )

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        IntegrationService().move_integration(user, integration3, before=integration2)


@pytest.mark.django_db
@patch("baserow.core.integrations.service.integration_orders_recalculated")
def test_move_integration_trigger_order_recalculated(
    integration_orders_recalculated_mock, data_fixture
):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application, order="2.99999999999999999998"
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application, order="2.99999999999999999999"
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application, order="3.0000"
    )

    service = IntegrationService()
    service.move_integration(user, integration3, before=integration2)

    integration_orders_recalculated_mock.send.assert_called_once_with(
        service, application=application
    )
