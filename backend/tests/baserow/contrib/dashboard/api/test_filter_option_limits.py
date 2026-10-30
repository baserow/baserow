from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.formula.types import BaserowFormulaObject


@pytest.mark.django_db
@pytest.mark.parametrize("budget", ["records", "bytes", "combined_fields"])
def test_calculated_option_formulas_reject_excess_data_without_truncating(
    api_client, data_fixture, monkeypatch, budget
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Country", "text"), ("Region", "text")],
        rows=[["France", "Europe"], ["Belgium", "Europe"], ["Morocco", "Africa"]],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    reference = f"get('table.{table.id}.*.{fields[0].db_column}')"
    formula = f"if(true, {reference}, '')"
    if budget == "combined_fields":
        other_reference = f"get('table.{table.id}.*.{fields[1].db_column}')"
        formula = f"concat(join({reference}, ','), join({other_reference}, ','))"
    limit_name, limit = (
        ("MAX_OPTION_FORMULA_BYTES", 10)
        if budget == "bytes"
        else ("MAX_OPTION_FORMULA_RECORDS", 4 if budget == "combined_fields" else 2)
    )
    monkeypatch.setattr(
        f"baserow.contrib.dashboard.filters.options.{limit_name}", limit
    )
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(formula),
    )
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(url, {"limit": 1}, format="json", **headers)

    assert response.status_code == 400, response.json()
    assert response.json()["error"] == "ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE"
    assert "results" not in response.json()

    # A direct field selection remains paginated and does not need formula arrays.
    DashboardFilterService().update_filter(
        user, selection.id, formula_value=BaserowFormulaObject.create(reference)
    )
    response = api_client.post(url, {"limit": 1}, format="json", **headers)
    assert response.status_code == 200, response.json()
    assert response.json()["results"] == ["France"]
