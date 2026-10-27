from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.formula.types import BaserowFormulaObject


def create_typed_dashboard(data_fixture, filter_type, rows, **field_options):
    user, token = data_fixture.create_user_and_token(session_id="typed-filters")
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Value", {"type": filter_type, **field_options}),
            ("Weight", "number"),
        ],
        rows=rows,
    )
    dashboard = data_fixture.create_dashboard_application(
        user=user, workspace=table.database.workspace
    )
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard,
        integration=integration,
        table=table,
        field=fields[1],
        aggregation_type="sum",
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Value",
        type=filter_type,
        mode="dropdown",
        multiple=True,
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=source.service,
        field=fields[0],
        type="date_is" if filter_type == "date" else "equal",
        value=BaserowFormulaObject.create(f"get('dashboard_filter.{selection.id}')"),
    )
    return user, token, source, selection


def dispatch(api_client, token, source, selection, values):
    response = api_client.patch(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        {"values": values},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    return api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": source.id}
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,values,expected",
    [
        ("equal", ["0"], "2"),
        ("equal", ["-2.5", "2"], "12"),
        ("equal", [], "31"),
        ("not_equal", ["0", "2"], "21"),
        ("higher_than", ["0"], "24"),
        ("higher_than_or_equal", ["0"], "26"),
        ("lower_than", ["0"], "4"),
        ("lower_than_or_equal", ["0"], "6"),
        ("contains", ["2"], "12"),
        ("contains_not", ["2"], "19"),
        ("starts_with", ["-2"], "4"),
        ("is_even_and_whole", ["true"], "26"),
        ("is_even_and_whole", [], "31"),
        ("empty", ["true"], "1"),
        ("not_empty", ["true"], "30"),
    ],
)
def test_number_filter_dispatch_uses_builder_operators(
    api_client, data_fixture, operator, values, expected
):
    user, token, source, selection = create_typed_dashboard(
        data_fixture,
        "number",
        [[None, 1], [0, 2], [-2.5, 4], [2, 8], [10, 16]],
        number_decimal_places=2,
        number_negative=True,
    )
    DashboardFilterService().update_filter(user, selection.id, operator=operator)
    response = dispatch(api_client, token, source, selection, values)
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": expected}


@pytest.mark.django_db
@freeze_time("2026-10-26 12:00:00")
@pytest.mark.parametrize(
    "operator,values,expected",
    [
        ("date_is", ["2026-10-26"], "8"),
        ("date_is_not", ["2026-10-25", "2026-10-26"], "51"),
        ("date_is_before", ["2026-10-26"], "6"),
        ("date_is_on_or_before", ["2026-10-26"], "14"),
        ("date_is_after", ["2026-10-26"], "48"),
        ("date_is_on_or_after", ["2026-10-26"], "56"),
        ("date_is", ["UTC??today"], "8"),
        ("date_is", ["UTC??yesterday"], "4"),
        ("date_is", ["UTC??tomorrow"], "16"),
        ("date_is", ["UTC??this_week"], "24"),
        ("date_is", ["UTC??this_month"], "30"),
        ("date_is", ["UTC??this_year"], "62"),
        ("date_is", ["UTC?2?nr_days_ago"], "2"),
        ("date_is", ["UTC?1?nr_days_from_now"], "16"),
        ("date_is_within", ["UTC?2?nr_days_from_now"], "24"),
        ("date_is_within", ["UTC?2?nr_days_ago"], "14"),
        ("date_equals_day_of_month", ["26"], "8"),
        ("date_equals_day_of_month", ["UTC?27"], "16"),
        ("date_is", [], "63"),
        ("date_is", ["UTC??exact_date"], "63"),
        ("contains", ["10/2026"], "30"),
        ("contains_not", ["10/2026"], "33"),
        ("empty", ["true"], "1"),
        ("not_empty", ["true"], "62"),
    ],
)
def test_date_filter_dispatch_uses_builder_operators(
    api_client, data_fixture, operator, values, expected
):
    user, token, source, selection = create_typed_dashboard(
        data_fixture,
        "date",
        [
            [None, 1],
            ["2026-10-24", 2],
            ["2026-10-25", 4],
            ["2026-10-26", 8],
            ["2026-10-27", 16],
            ["2026-11-02", 32],
        ],
    )
    DashboardFilterService().update_filter(user, selection.id, operator=operator)
    response = dispatch(api_client, token, source, selection, values)
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": expected}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_timezone,value,expected",
    [
        ("Asia/Dubai", "2026-10-26", "1"),
        (None, "2026-10-26", "2"),
        ("Asia/Dubai", "UTC?2026-10-26?exact_date", "2"),
    ],
)
def test_date_dropdown_defaults_to_field_timezone_and_preserves_explicit_timezone(
    api_client, data_fixture, field_timezone, value, expected
):
    _, token, source, selection = create_typed_dashboard(
        data_fixture,
        "date",
        [["2026-10-25T22:30:00Z", 1], ["2026-10-26T22:30:00Z", 2]],
        date_include_time=True,
        date_force_timezone=field_timezone,
    )
    response = dispatch(api_client, token, source, selection, [value])
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": expected}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,expected",
    [("1", "1"), ("31", "2"), ("Asia/Dubai?1", "1"), ("0", None), ("32", None)],
)
def test_date_day_of_month_uses_builder_bounds_and_timezone(
    api_client, data_fixture, value, expected
):
    user, token, source, selection = create_typed_dashboard(
        data_fixture,
        "date",
        [["2026-09-30T22:30:00Z", 1], ["2026-10-30T22:30:00Z", 2]],
        date_include_time=True,
        date_force_timezone="Asia/Dubai",
    )
    DashboardFilterService().update_filter(
        user, selection.id, operator="date_equals_day_of_month"
    )
    response = dispatch(api_client, token, source, selection, [value])
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": expected}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_type,rows,options,expected",
    [
        (
            "number",
            [[None, 1], [0, 2], [-2.5, 4], [2, 8], [0, 16]],
            {"number_decimal_places": 2, "number_negative": True},
            ["0.00", "-2.50", "2.00"],
        ),
        (
            "date",
            [[None, 1], ["2026-10-26", 2], ["2026-10-27", 4], ["2026-10-26", 8]],
            {},
            ["2026-10-26", "2026-10-27"],
        ),
    ],
)
def test_number_and_date_dropdown_options_are_distinct_strings(
    api_client, data_fixture, filter_type, rows, options, expected
):
    _, token, _, selection = create_typed_dashboard(
        data_fixture, filter_type, rows, **options
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
def test_number_filter_options_preserve_precision_and_match_the_original_row(
    api_client, data_fixture
):
    values = [
        "123456789012345678901234567890.12345",
        "123456789012345678901234567890.12346",
    ]
    _, token, source, selection = create_typed_dashboard(
        data_fixture,
        "number",
        [[values[0], 1], [values[1], 2]],
        number_decimal_places=5,
    )
    response = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["results"] == values
    filtered = dispatch(api_client, token, source, selection, values[:1])
    assert filtered.status_code == 200, filtered.json()
    assert filtered.json() == {"result": "1"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_type,operator", [("number", "equal"), ("date", "date_is")]
)
def test_creating_typed_filter_selects_compatible_default_operator(
    api_client, data_fixture, filter_type, operator
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    response = api_client.post(
        reverse("api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}),
        {"label": "Value", "type": filter_type},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["type"] == filter_type
    assert response.json()["operator"] == operator


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_type,operator",
    [("text", "higher_than"), ("number", "date_is"), ("date", "equal")],
)
def test_type_operator_validation_checks_existing_configuration_on_partial_update(
    api_client, data_fixture, filter_type, operator
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    selection = DashboardFilterService().create_filter(
        user, dashboard.id, label="Value", type=filter_type
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    create_response = api_client.post(
        reverse("api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}),
        {"label": "Invalid", "type": filter_type, "operator": operator},
        format="json",
        **headers,
    )
    patch_response = api_client.patch(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        {"operator": operator},
        format="json",
        **headers,
    )
    for response in [create_response, patch_response]:
        assert response.status_code == 400, response.json()
        assert (
            response.json()["error"] == "ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION"
        )
    selection.refresh_from_db()
    assert selection.operator != operator


@pytest.mark.django_db
def test_changing_filter_type_preserves_configuration_and_supports_undo_redo(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(session_id="typed-filters")
    dashboard = data_fixture.create_dashboard_application(user=user)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Value",
        multiple=True,
        formula_value=BaserowFormulaObject.create("2026-10-26,2026-10-27", "raw"),
    )
    response = api_client.patch(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        {"type": "date"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="typed-filters",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["operator"] == "date_is"
    assert response.json()["mode"] == "dropdown"
    assert response.json()["multiple"] is True
    assert response.json()["formula_value"] == selection.formula_value
    scopes = [ApplicationActionScopeType.value(dashboard.id)]
    ActionHandler.undo(user, scopes, "typed-filters")
    selection.refresh_from_db()
    assert (selection.type, selection.operator) == ("text", "equal")
    ActionHandler.redo(user, scopes, "typed-filters")
    selection.refresh_from_db()
    assert (selection.type, selection.operator) == ("date", "date_is")
