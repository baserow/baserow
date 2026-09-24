import pytest

from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import RestoreIntegrationOperationType
from baserow.core.integrations.trash_types import IntegrationTrashableItemType
from baserow.core.models import TrashEntry


def make_trash_entry(user, integration):
    return TrashEntry.objects.create(
        user_who_trashed=user,
        workspace=integration.application.workspace,
        application=integration.application,
        trash_item_type=IntegrationTrashableItemType.type,
        trash_item_id=integration.id,
        name=IntegrationTrashableItemType().get_name(integration),
        names=IntegrationTrashableItemType().get_names(integration),
    )


@pytest.mark.django_db
def test_integration_trashable_get_parent(data_fixture):
    integration = data_fixture.create_local_baserow_integration()

    result = IntegrationTrashableItemType().get_parent(integration)

    assert result == integration.application


@pytest.mark.django_db
def test_integration_trashable_get_name(data_fixture):
    integration = data_fixture.create_local_baserow_integration(name="My Integration")

    result = IntegrationTrashableItemType().get_name(integration)

    assert result == f"My Integration ({integration.id})"


@pytest.mark.django_db
def test_integration_trashable_trash(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )

    trash_entry = make_trash_entry(user, integration)
    result = IntegrationTrashableItemType().trash(integration, user, trash_entry)

    assert result is None
    integration.refresh_from_db()
    assert integration.trashed is True


@pytest.mark.django_db
def test_integration_trashable_restore(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )

    trash_entry = make_trash_entry(user, integration)
    IntegrationTrashableItemType().trash(integration, user, trash_entry)
    integration.refresh_from_db()
    assert integration.trashed is True

    result = IntegrationTrashableItemType().restore(integration, trash_entry)

    assert result is None
    integration.refresh_from_db()
    assert integration.trashed is False


@pytest.mark.django_db
def test_integration_trashable_permanently_delete_item(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )
    integration_id = integration.id

    trash_entry = make_trash_entry(user, integration)
    IntegrationTrashableItemType().trash(integration, user, trash_entry)
    IntegrationTrashableItemType().permanently_delete_item(integration)

    assert Integration.objects_and_trash.filter(id=integration_id).count() == 0


def test_integration_trashable_get_restore_operation_type():
    result = IntegrationTrashableItemType().get_restore_operation_type()

    assert result == RestoreIntegrationOperationType.type
