from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.exceptions import InvalidDashboardFilterValues
from baserow.contrib.dashboard.filters.handler import DashboardFilterHandler
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.contrib.dashboard.filters.values import MAX_SELECTION_VALUES
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed


@pytest.mark.django_db
def test_selection_is_shared_with_other_users_and_supports_undo_redo(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(session_id="shared-filters")
    reader, reader_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[reader])
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    control = DashboardFilterService().create_filter(
        user, dashboard.id, label="Country", multiple=True
    )
    item = reverse("api:dashboard:filters:item", kwargs={"filter_id": control.id})
    listing = reverse(
        "api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}
    )
    with patch(
        "baserow.contrib.dashboard.filters.service.dashboard_filters_updated.send"
    ) as signal:
        response = api_client.patch(
            item,
            {"values": ["France", "Belgium"]},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
            HTTP_CLIENTSESSIONID="shared-filters",
        )
    assert response.status_code == 200, response.json()
    signal.assert_called_once()
    assert api_client.get(listing, HTTP_AUTHORIZATION=f"JWT {reader_token}").json()[0][
        "values"
    ] == ["France", "Belgium"]
    scope = [ApplicationActionScopeType.value(dashboard.id)]
    ActionHandler.undo(user, scope, "shared-filters")
    control.refresh_from_db()
    assert control.values == []
    ActionHandler.redo(user, scope, "shared-filters")
    control.refresh_from_db()
    assert control.values == ["France", "Belgium"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "initial,change,reset",
    [
        ({}, {"mode": "input"}, True),
        ({"mode": "input"}, {"mode": "dropdown"}, True),
        ({"multiple": True}, {"multiple": False}, True),
        ({}, {"multiple": True}, True),
        ({}, {"type": "number"}, True),
        ({}, {"operator": "empty"}, True),
        ({"operator": "empty"}, {"operator": "not_empty"}, False),
        ({}, {"operator": "contains"}, False),
        ({}, {"label": "Renamed"}, False),
        ({"type": "date"}, {"operator": "date_is_before"}, False),
        ({"type": "date"}, {"operator": "date_is_within"}, True),
        ({"type": "date"}, {"operator": "date_equals_day_of_month"}, True),
        ({"type": "date"}, {"operator": "contains"}, True),
        ({"mode": "input"}, {"multiple": True}, False),
    ],
)
def test_format_changes_reset_shared_values_and_undo_restores_them(
    api_client, data_fixture, initial, change, reset
):
    user, token = data_fixture.create_user_and_token(session_id="shared-filters")
    dashboard = data_fixture.create_dashboard_application(user=user)
    control = DashboardFilterService().create_filter(
        user, dashboard.id, label="Value", values=["original"], **initial
    )
    response = api_client.patch(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": control.id}),
        change,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="shared-filters",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["values"] == ([] if reset else ["original"])
    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(dashboard.id)], "shared-filters"
    )
    control.refresh_from_db()
    assert control.values == ["original"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [None, [1], [True], ["\ud800"], ["\x00"], ["A"] * (MAX_SELECTION_VALUES + 1)],
)
def test_direct_handler_and_import_validate_selections(data_fixture, values):
    dashboard = data_fixture.create_dashboard_application()
    handler = DashboardFilterHandler()
    with pytest.raises(InvalidDashboardFilterValues):
        handler.import_filter(
            dashboard, {"id": 1, "label": "Invalid", "values": values}, {}
        )
    assert not handler.get_filters(dashboard).exists()


@pytest.mark.django_db
def test_deleted_values_restore_unless_another_selection_exhausted_the_budget(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    first = service.create_filter(user, dashboard.id, label="First", values=["A"])
    service.delete_filter(user, first.id)
    second = service.create_filter(
        user,
        dashboard.id,
        label="Second",
        multiple=True,
        values=["B"] * MAX_SELECTION_VALUES,
    )
    with pytest.raises(TrashItemRestorationDisallowed):
        service.restore_filter(user, first.id)
    service.update_filter(user, second.id, values=[])
    service.restore_filter(user, first.id)
    first.refresh_from_db()
    assert first.values == ["A"]
    assert not first.trashed


@pytest.mark.django_db(transaction=True)
def test_simultaneous_saves_cannot_exceed_the_dashboard_selection_budget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    controls = [
        service.create_filter(user, dashboard.id, label=str(index), multiple=True)
        for index in range(2)
    ]
    barrier = Barrier(2)

    def save(control):
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            service.update_filter(
                user, control.id, values=["A"] * (MAX_SELECTION_VALUES // 2 + 1)
            )
            return True
        except InvalidDashboardFilterValues:
            return False
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, controls))
    assert sorted(results) == [False, True]
    assert (
        sum(len(control.values) for control in service.get_filters(user, dashboard.id))
        == MAX_SELECTION_VALUES // 2 + 1
    )
