from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.contrib.dashboard.api.filters.options import (
    DashboardFilterOptionsRequestSerializer,
)
from baserow.contrib.dashboard.api.filters.serializers import DashboardFilterSerializer
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.contrib.dashboard.filters.values import (
    MAX_SELECTION_BYTES,
    MAX_SELECTION_VALUES,
)


@pytest.fixture(params=["options", "saved"])
def selection_serializer(request):
    def create(values):
        if request.param == "options":
            return DashboardFilterOptionsRequestSerializer(data={"selected": values})
        return DashboardFilterSerializer(data={"values": values}, partial=True)

    return create


@pytest.mark.parametrize("count", [MAX_SELECTION_VALUES + 1, 50_000])
def test_selection_count_is_bounded_before_validating_values(
    selection_serializer, count
):
    serializer = selection_serializer(["Alpha"] * count)
    with patch(
        "rest_framework.serializers.CharField.to_internal_value",
        side_effect=AssertionError("Oversized selections must be rejected first."),
    ):
        assert not serializer.is_valid()
    assert "max_selection_values" in str(serializer.errors)


@pytest.mark.parametrize(
    "values",
    [
        ["A"] * MAX_SELECTION_VALUES,
        ["é" * (MAX_SELECTION_BYTES // 2)],
        ["first", "first", "second", " spaced "],
        [],
    ],
)
def test_selection_budget_accepts_boundaries_and_preserves_positions(
    selection_serializer, values
):
    serializer = selection_serializer(values)
    assert serializer.is_valid(), serializer.errors
    data = serializer.validated_data
    assert data.get("selected", data.get("values")) == values


@pytest.mark.parametrize(
    "values",
    [
        ["é" * (MAX_SELECTION_BYTES // 2), "x"],
        ["界" * (MAX_SELECTION_BYTES // 3 + 1)],
        ["x" * (MAX_SELECTION_BYTES + 1)],
    ],
)
def test_selection_utf8_bytes_are_bounded_before_validating_values(
    selection_serializer, values
):
    serializer = selection_serializer(values)
    with patch(
        "rest_framework.serializers.CharField.to_internal_value",
        side_effect=AssertionError("Oversized selections must be rejected first."),
    ):
        assert not serializer.is_valid()
    assert "max_selection_bytes" in str(serializer.errors)


def test_invalid_unicode_uses_normal_field_validation(selection_serializer):
    serializer = selection_serializer(["\ud800"])
    assert not serializer.is_valid()
    assert "surrogate_characters_not_allowed" in str(serializer.errors)


@pytest.mark.parametrize("values", [None, "Design", [None], [True], [{}]])
def test_saved_selection_rejects_malformed_values(values):
    serializer = DashboardFilterSerializer(data={"values": values}, partial=True)
    assert not serializer.is_valid()


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["options", "saved"])
@pytest.mark.parametrize(
    "values",
    [
        ["Alpha"] * (MAX_SELECTION_VALUES + 1),
        ["é" * (MAX_SELECTION_BYTES // 2 + 1)],
    ],
)
def test_selection_api_rejects_oversized_payload_before_service_work(
    api_client, data_fixture, endpoint, values
):
    _, token = data_fixture.create_user_and_token()
    if endpoint == "options":
        url = reverse("api:dashboard:filters:options", kwargs={"filter_id": 1})
        body = {"selected": values}
        service_method = (
            "baserow.contrib.dashboard.filters.options."
            "DashboardFilterOptionsService.get_options"
        )
        method = api_client.post
    else:
        url = reverse("api:dashboard:filters:item", kwargs={"filter_id": 1})
        body = {"values": values}
        service_method = (
            "baserow.contrib.dashboard.filters.service."
            "DashboardFilterService.update_filter"
        )
        method = api_client.patch
    with patch(service_method) as service:
        response = method(url, body, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 400, response.json()
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    service.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values", [["A"] * (MAX_SELECTION_VALUES // 2), ["é" * (MAX_SELECTION_BYTES // 4)]]
)
def test_saved_selections_share_one_dashboard_budget(api_client, data_fixture, values):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    first, second = [
        service.create_filter(
            user, dashboard.id, label=label, multiple=True, values=values
        )
        for label in ["Country", "Channel"]
    ]
    url = reverse("api:dashboard:filters:item", kwargs={"filter_id": second.id})
    response = api_client.patch(
        url,
        {"values": values + ["x"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400, response.json()
    assert response.json()["error"] == "ERROR_DASHBOARD_FILTER_INVALID_VALUES"
    second.refresh_from_db()
    assert second.values == values
    service.update_filter(user, first.id, values=[])
    response = api_client.patch(
        url,
        {"values": values + ["x"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
