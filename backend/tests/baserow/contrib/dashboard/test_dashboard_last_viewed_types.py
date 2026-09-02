import pytest

from baserow.contrib.dashboard.last_viewed_types import DashboardLastViewedItemType
from baserow.core.registries import last_viewed_item_type_registry
from baserow.core.trash.handler import TrashHandler


def test_type_is_registered():
    assert isinstance(
        last_viewed_item_type_registry.get("dashboard"), DashboardLastViewedItemType
    )


@pytest.mark.django_db
def test_get_queryset_for_user_only_returns_dashboards_the_user_can_open(
    data_fixture,
):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    trashed_dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    trashed_workspace = data_fixture.create_workspace(user=user)
    dashboard_of_trashed_workspace = data_fixture.create_dashboard_application(
        workspace=trashed_workspace
    )

    TrashHandler.trash(user, workspace, None, trashed_dashboard)
    TrashHandler.trash(user, trashed_workspace, None, trashed_workspace)

    item_type = DashboardLastViewedItemType()
    assert set(item_type.get_queryset_for_user(user.id)) == {dashboard}
    assert list(item_type.get_queryset_for_user(other_user.id)) == []
    assert dashboard_of_trashed_workspace not in item_type.get_queryset_for_user(
        user.id
    )
    assert set(item_type.get_existing_item_ids_queryset()) >= {
        dashboard,
        trashed_dashboard,
    }


@pytest.mark.django_db
def test_dashboard_is_its_own_application(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)

    item_type = DashboardLastViewedItemType()
    instance = item_type.get_queryset_for_user(user.id).get(id=dashboard.id)
    assert item_type.get_application_id(instance) == dashboard.id
    assert item_type.get_workspace_id(instance) == workspace.id
    # The foreign key cascade removes the rows, so no trash item is claimed.
    assert (
        list(item_type.get_item_ids_of_permanently_deleted("application", dashboard))
        == []
    )
