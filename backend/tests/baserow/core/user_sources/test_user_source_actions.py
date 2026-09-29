import uuid

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.user_sources.actions import (
    CreateUserSourceActionType,
    DeleteUserSourceActionType,
    MoveUserSourceActionType,
    UpdateUserSourceActionType,
)
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import user_source_type_registry


def _scope(application):
    return [ApplicationActionScopeType.value(application.id)]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_user_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )
    user_source_type = list(user_source_type_registry.get_all())[0]

    user_source = CreateUserSourceActionType.do(
        user,
        user_source_type,
        application,
        name="US",
        integration_id=integration.id,
    )

    assert UserSource.objects.filter(id=user_source.id).exists()

    ActionHandler.undo(user, _scope(application), session_id)
    assert not UserSource.objects.filter(id=user_source.id).exists()
    assert UserSource.trash.filter(id=user_source.id).exists()

    ActionHandler.redo(user, _scope(application), session_id)
    assert UserSource.objects.filter(id=user_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_user_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(
        user=user, application=application
    )

    DeleteUserSourceActionType.do(user, user_source)
    assert not UserSource.objects.filter(id=user_source.id).exists()
    assert UserSource.trash.filter(id=user_source.id).exists()

    ActionHandler.undo(user, _scope(application), session_id)
    assert UserSource.objects.filter(id=user_source.id).exists()

    ActionHandler.redo(user, _scope(application), session_id)
    assert not UserSource.objects.filter(id=user_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_user_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(
        user=user, application=application, name="Original"
    )

    user_source_for_update = UserSourceHandler().get_user_source_for_update(
        user_source.id
    )
    UpdateUserSourceActionType.do(user, user_source_for_update, name="Updated")

    user_source.refresh_from_db()
    assert user_source.name == "Updated"

    ActionHandler.undo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.name == "Original"

    ActionHandler.redo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.name == "Updated"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_user_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    us1 = data_fixture.create_user_source_with_first_type(application=application)
    us2 = data_fixture.create_user_source_with_first_type(application=application)
    us3 = data_fixture.create_user_source_with_first_type(application=application)

    def order():
        return list(
            UserSource.objects.filter(application=application)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    assert order() == [us1.id, us2.id, us3.id]

    # Move us3 before us2 → [us1, us3, us2]
    us3_for_update = UserSourceHandler().get_user_source_for_update(us3.id)
    MoveUserSourceActionType.do(user, us3_for_update, before=us2)
    assert order() == [us1.id, us3.id, us2.id]

    ActionHandler.undo(user, _scope(application), session_id)
    assert order() == [us1.id, us2.id, us3.id]

    ActionHandler.redo(user, _scope(application), session_id)
    assert order() == [us1.id, us3.id, us2.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_user_source_create_configure_undo_redo(data_fixture):
    # create -> configure (rename) -> undo -> redo, then undo create -> trashed.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    user_source_type = list(user_source_type_registry.get_all())[0]

    user_source = CreateUserSourceActionType.do(
        user,
        user_source_type,
        application,
        name="Original",
        integration_id=integration.id,
    )

    us_fu = UserSourceHandler().get_user_source_for_update(user_source.id)
    UpdateUserSourceActionType.do(user, us_fu, name="Configured")
    user_source.refresh_from_db()
    assert user_source.name == "Configured"

    ActionHandler.undo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.name == "Original"

    ActionHandler.redo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.name == "Configured"

    # Undo rename + undo create -> trashed; then redo both -> restored & configured.
    ActionHandler.undo(user, _scope(application), session_id)
    ActionHandler.undo(user, _scope(application), session_id)
    assert not UserSource.objects.filter(id=user_source.id).exists()

    ActionHandler.redo(user, _scope(application), session_id)
    assert UserSource.objects.filter(id=user_source.id).exists()
    ActionHandler.redo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.name == "Configured"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_user_source_assign_integration_undo_redo(data_fixture):
    # create with integration1 -> reassign integration2 -> undo (integration1) ->
    # redo (integration2). Exercises the FK (integration_id) round-trip.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    user_source = data_fixture.create_user_source_with_first_type(
        user=user, application=application, integration=integration1
    )

    us_fu = UserSourceHandler().get_user_source_for_update(user_source.id)
    UpdateUserSourceActionType.do(user, us_fu, integration_id=integration2.id)
    user_source.refresh_from_db()
    assert user_source.integration_id == integration2.id

    ActionHandler.undo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.integration_id == integration1.id

    ActionHandler.redo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.integration_id == integration2.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_user_source_reassign_integration_undo_with_trashed_integration(data_fixture):
    # integration1 trashed, reassign to integration2, undo restores integration1's
    # id (still trashed) without raising.
    from baserow.core.integrations.service import IntegrationService

    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    user_source = data_fixture.create_user_source_with_first_type(
        user=user, application=application, integration=integration1
    )

    IntegrationService().delete_integration(user, integration1)

    us_fu = UserSourceHandler().get_user_source_for_update(user_source.id)
    UpdateUserSourceActionType.do(user, us_fu, integration_id=integration2.id)
    user_source.refresh_from_db()
    assert user_source.integration_id == integration2.id

    ActionHandler.undo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.integration_id == integration1.id

    ActionHandler.redo(user, _scope(application), session_id)
    user_source.refresh_from_db()
    assert user_source.integration_id == integration2.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_user_source_create_configure_delete_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    user_source = CreateUserSourceActionType.do(
        user,
        list(user_source_type_registry.get_all())[0],
        application,
        name="A",
        integration_id=integration.id,
    )
    us_fu = UserSourceHandler().get_user_source_for_update(user_source.id)
    UpdateUserSourceActionType.do(user, us_fu, name="B")

    us_fu = UserSourceHandler().get_user_source_for_update(user_source.id)
    DeleteUserSourceActionType.do(user, us_fu)
    assert not UserSource.objects.filter(id=user_source.id).exists()

    ActionHandler.undo(user, _scope(application), session_id)
    assert UserSource.objects.filter(id=user_source.id).exists()
    user_source.refresh_from_db()
    assert user_source.name == "B"

    ActionHandler.redo(user, _scope(application), session_id)
    assert not UserSource.objects.filter(id=user_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_user_source_grouped_create_configure_undo_redo(data_fixture):
    session_id = "session-id"
    action_group = uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )
    user_source = CreateUserSourceActionType.do(
        user,
        list(user_source_type_registry.get_all())[0],
        application,
        name="Original",
        integration_id=integration.id,
    )
    us_fu = UserSourceHandler().get_user_source_for_update(user_source.id)
    UpdateUserSourceActionType.do(user, us_fu, name="Configured")

    ActionHandler.undo(user, _scope(application), session_id)
    assert not UserSource.objects.filter(id=user_source.id).exists()

    ActionHandler.redo(user, _scope(application), session_id)
    assert UserSource.objects.filter(id=user_source.id).exists()
    user_source.refresh_from_db()
    assert user_source.name == "Configured"
