from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.formula.types import BaserowFormulaObject


@pytest.mark.django_db
def test_table_options_pagination_and_availability(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Team", "text")],
        rows=[["design"], ["marketing"], ["design"], ["Design"], [""], ["\u2003"]],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Team",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    result = api_client.post(
        url,
        {"limit": 1, "selected": ["marketing", "sales"]},
        format="json",
        **headers,
    ).json()
    assert result["results"] == ["design"]
    assert result["available"] == ["marketing"]
    first = api_client.post(url, {"limit": 1}, format="json", **headers).json()
    assert first["next"]
    second = api_client.post(
        url, {"after": first["next"]}, format="json", **headers
    ).json()
    assert second["results"] == ["marketing", "Design"]
    assert second["next"] is None
    missing = api_client.post(
        url, {"after": "deleted", "selected": ["marketing"]}, format="json", **headers
    )
    assert missing.status_code == 400, missing.json()
    assert missing.json()["error"] == "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rows, expected",
    [
        ([[None], [2]], ["2"]),
        ([[1], [2]], ["1", "2"]),
    ],
)
def test_table_options_omit_empty_numeric_values(
    api_client, data_fixture, rows, expected
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user, columns=[("Value", "number")], rows=rows
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["results"] == expected


@pytest.mark.django_db
def test_options_require_dashboard_permission(api_client, data_fixture):
    user = data_fixture.create_user()
    _, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    selection = DashboardFilterService().create_filter(user, dashboard.id, label="Team")
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid", ["unused_table", "deleted_widget", "deleted_field", "deleted_table"]
)
def test_table_options_reject_unavailable_or_unrelated_records(
    api_client, data_fixture, invalid
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user, columns=[("Country", "text")], rows=[["France"]]
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    widget = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    if invalid == "unused_table":
        source.service.table = data_fixture.create_database_table(user=user)
        source.service.save()
    elif invalid == "deleted_widget":
        widget.trashed = True
        widget.save()
    elif invalid == "deleted_field":
        fields[0].trashed = True
        fields[0].save()
    else:
        table.trashed = True
        table.save()
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400, response.json()


@pytest.mark.django_db
def test_table_options_require_access_to_the_underlying_database(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        columns=[("Country", "text")], rows=[["France"]]
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 401, response.json()


@pytest.mark.django_db
def test_table_options_include_rows_beyond_the_list_service_limit(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Country", "text")],
        rows=[["France"]] * 250 + [["Belgique"]],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    first = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    first.trashed = True
    first.save()
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["results"] == ["France", "Belgique"]


@pytest.mark.django_db
def test_text_option_pages_read_the_table_once_without_serializing_rows(
    api_client, data_fixture, monkeypatch
):
    from baserow.contrib.dashboard.data_sources.records import (
        DashboardTableRecordsHandler,
    )
    from baserow.contrib.database.api.rows.serializers import RowSerializer

    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Country", "text")],
        rows=[[f"Country {index}"] for index in range(10000)],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    serialized_rows = 0
    original = RowSerializer.to_representation

    def count_serialized_rows(self, instance):
        nonlocal serialized_rows
        serialized_rows += 1
        return original(self, instance)

    monkeypatch.setattr(RowSerializer, "to_representation", count_serialized_rows)
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    after = None
    for offset in [0, 50]:
        response = api_client.post(
            url,
            {"limit": 50, "after": after, "selected": ["Country 9999", "missing"]},
            format="json",
            **headers,
        )
        assert response.status_code == 200, response.json()
        assert response.json()["results"] == [
            f"Country {index}" for index in range(offset, offset + 50)
        ]
        assert response.json()["available"] == ["Country 9999"]
        after = response.json()["next"]
        assert after
        assert serialized_rows == 0
        if offset == 0:

            def forbid_reading_table_again(*args, **kwargs):
                pytest.fail("A continuation must read the snapshot, not the table.")

            monkeypatch.setattr(
                DashboardTableRecordsHandler,
                "iter_scalar_field_values",
                forbid_reading_table_again,
            )
            table.get_model().objects.all().update(**{fields[0].db_column: "Updated"})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula, expected",
    [
        (
            BaserowFormulaObject.create("France, Belgique, France, ", mode="raw"),
            ["France", "Belgique"],
        ),
        (
            BaserowFormulaObject.create("split('France|Belgique|France', '|')"),
            ["France", "Belgique"],
        ),
    ],
)
def test_options_preserve_literal_and_calculated_values(
    api_client, data_fixture, formula, expected
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    selection = DashboardFilterService().create_filter(
        user, dashboard.id, label="Country", formula_value=formula
    )
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    first = api_client.post(
        url, {"limit": 1, "selected": ["Belgique", "missing"]}, format="json", **headers
    )
    assert first.status_code == 200, first.json()
    assert first.json()["results"] == expected[:1]
    assert first.json()["available"] == ["Belgique"]
    assert first.json()["next"]
    second = api_client.post(
        url, {"after": first.json()["next"]}, format="json", **headers
    )
    assert second.json()["results"] == expected[1:]
    assert second.json()["next"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("reference, expected_count", [("*", 0), ("250", 1)])
def test_options_build_numeric_snapshots_once_and_read_only_indexed_records(
    api_client, data_fixture, monkeypatch, reference, expected_count
):
    from baserow.contrib.database.api.rows.serializers import RowSerializer

    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Number", "number")],
        rows=[[index] for index in range(300)],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Number",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.{reference}.{fields[0].db_column}')"
        ),
    )
    serialized_rows = 0
    original = RowSerializer.to_representation

    def count_serialized_rows(self, instance):
        nonlocal serialized_rows
        serialized_rows += 1
        return original(self, instance)

    monkeypatch.setattr(RowSerializer, "to_representation", count_serialized_rows)
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    expected_values = (
        [str(index) for index in range(50)] if reference == "*" else ["250"]
    )
    assert response.json()["results"] == expected_values
    assert serialized_rows == expected_count


@pytest.mark.django_db
@pytest.mark.parametrize("saved", [False, True])
def test_option_formulas_cannot_read_selected_control_values(
    api_client, data_fixture, saved
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    selection = DashboardFilterService().create_filter(
        user, dashboard.id, label="Country"
    )
    formula = BaserowFormulaObject.create(f"get('dashboard_filter.{selection.id}')")
    if saved:
        DashboardFilterService().update_filter(
            user, selection.id, formula_value=formula
        )
        url = reverse(
            "api:dashboard:filters:options", kwargs={"filter_id": selection.id}
        )
        response = api_client.post(
            url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )
    else:
        url = reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id})
        response = api_client.patch(
            url,
            {"formula_value": formula},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == 400, response.json()
    assert response.json()["error"] == (
        "ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED"
        if saved
        else "ERROR_REQUEST_BODY_VALIDATION"
    )
