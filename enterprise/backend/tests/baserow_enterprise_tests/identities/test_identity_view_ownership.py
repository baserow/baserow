import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import OWNERSHIP_TYPE_COLLABORATIVE
from baserow.core.exceptions import PermissionDenied
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL
from baserow_premium.views.view_ownership_types import PersonalViewOwnershipType


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_identity_cannot_access_human_personal_view(data_fixture):
    """Identity workspace access never grants access to a human personal view."""

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
    identity = data_fixture.create_identity(
        workspace=workspace,
        name="Viewer identity",
        role_uid="VIEWER",
    )
    handler = ViewHandler()

    assert [view.id for view in handler.list_views(identity, table)] == [
        collaborative_view.id
    ]
    assert (
        handler.get_view_as_user(identity, collaborative_view.id).id
        == collaborative_view.id
    )
    with pytest.raises(PermissionDenied):
        handler.get_view_as_user(identity, personal_view.id)


@pytest.mark.django_db
def test_builder_identity_cannot_modify_or_publish_human_personal_view(data_fixture):
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
    identity = data_fixture.create_identity(
        workspace=workspace,
        name="Builder identity",
        role_uid="BUILDER",
    )
    handler = ViewHandler()

    with pytest.raises(PermissionDenied):
        handler.update_view(identity, personal_view, name="Leaked", public=True)
    personal_view.refresh_from_db()
    assert personal_view.name != "Leaked"
    assert personal_view.public is False

    handler.update_view(identity, collaborative_view, name="Allowed", public=True)
    collaborative_view.refresh_from_db()
    assert collaborative_view.name == "Allowed"
    assert collaborative_view.public is True


@pytest.mark.django_db
def test_identity_cannot_create_or_adopt_personal_views(data_fixture):
    table = data_fixture.create_database_table()
    identity = data_fixture.create_identity(
        workspace=table.database.workspace, role_uid="ADMIN"
    )
    view = data_fixture.create_grid_view(table=table)
    ownership = PersonalViewOwnershipType()

    with pytest.raises(PermissionDenied):
        ViewHandler().create_view(
            identity,
            table,
            "grid",
            ownership_type=OWNERSHIP_TYPE_PERSONAL,
            name="Private",
        )
    with pytest.raises(PermissionDenied):
        ownership.change_ownership_type(identity, view)
