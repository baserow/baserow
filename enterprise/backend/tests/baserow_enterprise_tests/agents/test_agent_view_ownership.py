import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import OWNERSHIP_TYPE_COLLABORATIVE
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Agent
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_agent_cannot_access_human_personal_view_with_matching_id(data_fixture):
    """A matching integer ID must not make an agent the owner of a user view."""

    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    personal_view = data_fixture.create_grid_view(
        table=table,
        owned_by=owner,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    collaborative_view = data_fixture.create_grid_view(
        table=table,
        owned_by=owner,
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    agent = Agent.objects.create(
        id=owner.id,
        workspace=workspace,
        name="Viewer agent",
        role_uid="VIEWER",
    )
    handler = ViewHandler()

    assert [view.id for view in handler.list_views(agent, table)] == [
        collaborative_view.id
    ]
    assert (
        handler.get_view_as_user(agent, collaborative_view.id).id
        == collaborative_view.id
    )
    with pytest.raises(PermissionDenied):
        handler.get_view_as_user(agent, personal_view.id)


@pytest.mark.django_db
def test_builder_agent_cannot_modify_or_publish_human_personal_view(data_fixture):
    """A role granting normal view updates must not bypass personal ownership."""

    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=workspace)
    )
    personal_view = data_fixture.create_grid_view(
        table=table,
        owned_by=owner,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    collaborative_view = data_fixture.create_grid_view(
        table=table,
        owned_by=owner,
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    agent = Agent.objects.create(
        workspace=workspace,
        name="Builder agent",
        role_uid="BUILDER",
    )
    handler = ViewHandler()

    with pytest.raises(PermissionDenied):
        handler.update_view(agent, personal_view, name="Leaked", public=True)
    personal_view.refresh_from_db()
    assert personal_view.name != "Leaked"
    assert personal_view.public is False

    handler.update_view(agent, collaborative_view, name="Allowed", public=True)
    collaborative_view.refresh_from_db()
    assert collaborative_view.name == "Allowed"
    assert collaborative_view.public is True
