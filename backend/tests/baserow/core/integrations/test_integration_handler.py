from decimal import Decimal

import pytest

from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.exceptions import (
    ApplicationOperationNotSupported,
    CannotCalculateIntermediateOrder,
)
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import (
    IntegrationType,
    integration_type_registry,
)
from baserow.core.registries import application_type_registry


def pytest_generate_tests(metafunc):
    if "integration_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "integration_type",
            [pytest.param(e, id=e.type) for e in integration_type_registry.get_all()],
        )


@pytest.mark.django_db
def test_create_integration(data_fixture, integration_type: IntegrationType):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration = IntegrationHandler().create_integration(
        integration_type,
        application=application,
        **integration_type.prepare_values({}, user),
    )

    assert integration.application.id == application.id

    assert integration.order == 1
    assert Integration.objects.count() == 1


@pytest.mark.django_db
def test_create_integration_bad_application(data_fixture, monkeypatch):
    # Every registered application type supports integrations now, so the
    # guard is exercised by turning one off. The type has to be one the
    # application would otherwise accept, or the allow-list refuses it either
    # way and the flag is never read.
    user = data_fixture.create_user()
    application = data_fixture.create_database_application(user=user)
    application_type = application_type_registry.get("database")
    monkeypatch.setattr(application_type, "supports_integrations", False)

    integration_type = integration_type_registry.get("slack_bot")

    with pytest.raises(ApplicationOperationNotSupported):
        IntegrationHandler().create_integration(
            integration_type,
            application=application,
            **integration_type.prepare_values({}, user),
        )


@pytest.mark.django_db
def test_get_integration(data_fixture):
    integration = data_fixture.create_local_baserow_integration()
    assert IntegrationHandler().get_integration(integration.id).id == integration.id


@pytest.mark.django_db
def test_get_integration_does_not_exist(data_fixture):
    with pytest.raises(IntegrationDoesNotExist):
        assert IntegrationHandler().get_integration(0)


@pytest.mark.django_db
def test_get_integrations(data_fixture):
    builder = data_fixture.create_builder_application()
    integration1 = data_fixture.create_local_baserow_integration(application=builder)
    integration2 = data_fixture.create_local_baserow_integration(application=builder)
    integration3 = data_fixture.create_local_baserow_integration(application=builder)

    integrations = IntegrationHandler().get_integrations(application=builder)

    assert [e.id for e in integrations] == [
        integration1.id,
        integration2.id,
        integration3.id,
    ]

    assert isinstance(integrations[0], LocalBaserowIntegration)


@pytest.mark.django_db
def test_delete_integration(data_fixture):
    integration = data_fixture.create_local_baserow_integration()

    IntegrationHandler().delete_integration(integration)

    assert Integration.objects.count() == 0


@pytest.mark.django_db
def test_update_integration(data_fixture):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    integration_type = integration_type_registry.get("local_baserow")

    integration_updated = IntegrationHandler().update_integration(
        integration_type, integration, authorized_user=user2
    )

    assert integration_updated.authorized_user.id == user2.id


@pytest.mark.django_db
def test_update_integration_invalid_values(data_fixture):
    integration = data_fixture.create_local_baserow_integration()

    integration_type = integration_type_registry.get("local_baserow")

    integration_updated = IntegrationHandler().update_integration(
        integration_type, integration, nonsense="hello"
    )

    assert not hasattr(integration_updated, "nonsense")


@pytest.mark.django_db
def test_move_integration_end_of_application(data_fixture):
    builder = data_fixture.create_builder_application()
    integration1 = data_fixture.create_local_baserow_integration(application=builder)
    integration2 = data_fixture.create_local_baserow_integration(application=builder)
    integration3 = data_fixture.create_local_baserow_integration(application=builder)

    integration_moved = IntegrationHandler().move_integration(integration1)

    assert (
        Integration.objects.filter(application=builder).last().id
        == integration_moved.id
    )


@pytest.mark.django_db
def test_move_integration_before(data_fixture):
    builder = data_fixture.create_builder_application()
    integration1 = data_fixture.create_local_baserow_integration(application=builder)
    integration2 = data_fixture.create_local_baserow_integration(application=builder)
    integration3 = data_fixture.create_local_baserow_integration(application=builder)

    IntegrationHandler().move_integration(integration3, before=integration2)

    assert [e.id for e in Integration.objects.filter(application=builder).all()] == [
        integration1.id,
        integration3.id,
        integration2.id,
    ]


@pytest.mark.django_db
def test_move_integration_before_fails(data_fixture):
    builder = data_fixture.create_builder_application()
    integration1 = data_fixture.create_local_baserow_integration(
        application=builder, order="2.99999999999999999998"
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=builder, order="2.99999999999999999999"
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=builder, order="3.0000"
    )

    with pytest.raises(CannotCalculateIntermediateOrder):
        IntegrationHandler().move_integration(integration3, before=integration2)


@pytest.mark.django_db
def test_recalculate_full_orders(data_fixture):
    builder = data_fixture.create_builder_application()
    integration1 = data_fixture.create_local_baserow_integration(
        application=builder, order="1.99999999999999999999"
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=builder, order="2.00000000000000000000"
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=builder, order="1.99999999999999999999"
    )
    integration4 = data_fixture.create_local_baserow_integration(
        application=builder, order="2.10000000000000000000"
    )
    integration5 = data_fixture.create_local_baserow_integration(
        application=builder, order="3.00000000000000000000"
    )
    integration6 = data_fixture.create_local_baserow_integration(
        application=builder, order="1.00000000000000000001"
    )
    integration7 = data_fixture.create_local_baserow_integration(
        application=builder, order="3.99999999999999999999"
    )
    integration8 = data_fixture.create_local_baserow_integration(
        application=builder, order="4.00000000000000000001"
    )

    builder2 = data_fixture.create_builder_application()

    integrationA = data_fixture.create_local_baserow_integration(
        application=builder2, order="1.99999999999999999999"
    )
    integrationB = data_fixture.create_local_baserow_integration(
        application=builder2, order="2.00300000000000000000"
    )

    IntegrationHandler().recalculate_full_orders(builder)

    integrations = Integration.objects.filter(application=builder)
    assert integrations[0].id == integration6.id
    assert integrations[0].order == Decimal("1.00000000000000000000")

    assert integrations[1].id == integration1.id
    assert integrations[1].order == Decimal("2.00000000000000000000")

    assert integrations[2].id == integration3.id
    assert integrations[2].order == Decimal("3.00000000000000000000")

    assert integrations[3].id == integration2.id
    assert integrations[3].order == Decimal("4.00000000000000000000")

    assert integrations[4].id == integration4.id
    assert integrations[4].order == Decimal("5.00000000000000000000")

    assert integrations[5].id == integration5.id
    assert integrations[5].order == Decimal("6.00000000000000000000")

    assert integrations[6].id == integration7.id
    assert integrations[6].order == Decimal("7.00000000000000000000")

    assert integrations[7].id == integration8.id
    assert integrations[7].order == Decimal("8.00000000000000000000")

    # Other page integrations shouldn't be reordered
    integrations = Integration.objects.filter(application=builder2)
    assert integrations[0].id == integrationA.id
    assert integrations[0].order == Decimal("1.99999999999999999999")

    assert integrations[1].id == integrationB.id
    assert integrations[1].order == Decimal("2.00300000000000000000")
