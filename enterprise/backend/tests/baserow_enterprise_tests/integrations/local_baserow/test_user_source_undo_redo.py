import uuid

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.user_sources.actions import UpdateUserSourceActionType
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_user_source_auth_providers_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Password A", "password"),
            ("Password B", "password"),
        ],
        rows=[["a@baserow.io", "x", "y"]],
    )
    email_field, password_a, password_b = fields

    user_source_type = user_source_type_registry.get("local_baserow")
    user_source = UserSourceService().create_user_source(
        user,
        user_source_type,
        application,
        name="US",
        integration_id=integration.id,
        table_id=table.id,
        email_field_id=email_field.id,
        auth_providers=[
            {"type": "local_baserow_password", "password_field_id": password_a.id},
        ],
    )

    def current_password_field_id():
        return LocalBaserowPasswordAppAuthProvider.objects.get(
            user_source=user_source
        ).password_field_id

    assert current_password_field_id() == password_a.id

    user_source_for_update = UserSourceHandler().get_user_source_for_update(
        user_source.id
    )
    UpdateUserSourceActionType.do(
        user,
        user_source_for_update,
        auth_providers=[
            {"type": "local_baserow_password", "password_field_id": password_b.id},
        ],
    )
    assert current_password_field_id() == password_b.id

    scope = [ApplicationActionScopeType.value(application.id)]

    ActionHandler.undo(user, scope, session_id)
    # The password field must be restored to its original value.
    assert current_password_field_id() == password_a.id

    ActionHandler.redo(user, scope, session_id)
    assert current_password_field_id() == password_b.id
