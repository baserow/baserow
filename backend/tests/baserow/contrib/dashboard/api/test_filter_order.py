from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.actions import OrderDashboardFiltersActionType
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType


@pytest.mark.django_db
def test_reorder_filters_persists_and_supports_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(session_id="order-filters")
    dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    first, second, third = [
        service.create_filter(user, dashboard.id, label=label)
        for label in ["Country", "Channel", "Team"]
    ]
    headers = {
        "HTTP_AUTHORIZATION": f"JWT {token}",
        "HTTP_CLIENTSESSIONID": "order-filters",
    }
    url = reverse("api:dashboard:filters:order", kwargs={"dashboard_id": dashboard.id})
    listing = reverse(
        "api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}
    )
    with patch(
        "baserow.contrib.dashboard.filters.service.dashboard_filters_updated.send"
    ) as signal:
        response = api_client.post(
            url,
            {"order": [third.id, first.id, second.id]},
            format="json",
            **headers,
        )
    assert response.status_code == 204
    signal.assert_called_once()
    assert signal.call_args.kwargs["dashboard"] == dashboard
    assert signal.call_args.kwargs["user"] == user
    assert signal.call_args.kwargs["order_only"] is True
    assert [f["id"] for f in api_client.get(listing, **headers).json()] == [
        third.id,
        first.id,
        second.id,
    ]
    assert [f["order"] for f in api_client.get(listing, **headers).json()] == [1, 2, 3]

    scope = [ApplicationActionScopeType.value(dashboard.id)]
    ActionHandler.undo(user, scope, "order-filters")
    assert list(service.get_filters(user, dashboard.id)) == [first, second, third]
    ActionHandler.redo(user, scope, "order-filters")
    assert list(service.get_filters(user, dashboard.id)) == [third, first, second]

    # Duplicating/creating a filter appends it after the reordered controls.
    added = service.create_filter(user, dashboard.id, label="New")
    assert list(service.get_filters(user, dashboard.id)) == [
        third,
        first,
        second,
        added,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_order", ["duplicate", "foreign", "trashed", "missing"]
)
def test_reorder_filters_rejects_invalid_ids_without_changing_order(
    api_client, data_fixture, invalid_order
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    other_dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    first = service.create_filter(user, dashboard.id, label="Country")
    second = service.create_filter(user, dashboard.id, label="Channel")
    foreign = service.create_filter(user, other_dashboard.id, label="Elsewhere")
    trashed = service.create_filter(user, dashboard.id, label="Deleted")
    service.delete_filter(user, trashed.id)
    invalid_id = {
        "duplicate": second.id,
        "foreign": foreign.id,
        "trashed": trashed.id,
        "missing": 999999,
    }[invalid_order]

    response = api_client.post(
        reverse("api:dashboard:filters:order", kwargs={"dashboard_id": dashboard.id}),
        {"order": [second.id, invalid_id, first.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_DASHBOARD_FILTER_ORDER_INVALID"
    assert list(service.get_filters(user, dashboard.id)) == [first, second]


@pytest.mark.django_db
@pytest.mark.parametrize("order", [None, "1,2", [0], ["bad"]])
def test_reorder_filters_validates_body(api_client, data_fixture, order):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    response = api_client.post(
        reverse("api:dashboard:filters:order", kwargs={"dashboard_id": dashboard.id}),
        {"order": order},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_reorder_filters_requires_dashboard_access(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()
    url = reverse("api:dashboard:filters:order", kwargs={"dashboard_id": dashboard.id})
    assert api_client.post(url, {"order": []}, format="json").status_code == 401
    assert (
        api_client.post(
            url, {"order": []}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        ).status_code
        == 401
    )
    response = api_client.post(
        reverse("api:dashboard:filters:order", kwargs={"dashboard_id": 999999}),
        {"order": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_partial_order_and_undo_keep_concurrent_new_filters(data_fixture):
    user = data_fixture.create_user(session_id="order-filters")
    dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    first, second, third = [
        service.create_filter(user, dashboard.id, label=label)
        for label in ["Country", "Channel", "Team"]
    ]
    OrderDashboardFiltersActionType.do(user, dashboard.id, [second.id, first.id])
    assert list(service.get_filters(user, dashboard.id)) == [second, first, third]

    # Another editor deletes a filter and adds one before undo is requested.
    service.delete_filter(user, second.id)
    added = service.create_filter(user, dashboard.id, label="New")
    scope = [ApplicationActionScopeType.value(dashboard.id)]
    ActionHandler.undo(user, scope, "order-filters")
    assert list(service.get_filters(user, dashboard.id)) == [first, third, added]
    ActionHandler.redo(user, scope, "order-filters")
    assert list(service.get_filters(user, dashboard.id)) == [first, third, added]


@pytest.mark.django_db
def test_order_is_not_writable_through_filter_configuration(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}),
        {"label": "Country", "order": 999},
        format="json",
        **headers,
    )
    created = response.json()
    assert response.status_code == 200
    assert created["order"] == 1
    response = api_client.patch(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": created["id"]}),
        {"order": 999},
        format="json",
        **headers,
    )
    assert response.status_code == 200
    assert response.json()["order"] == 1
