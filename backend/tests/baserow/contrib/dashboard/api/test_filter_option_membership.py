from django.urls import reverse

import pytest

from baserow.contrib.dashboard.data_sources.records import DashboardTableRecordsHandler
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.models import WorkspaceUser


@pytest.fixture
def membership_dashboard(data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Value", "text")],
        rows=[["Alpha"], ["Beta"], ["Gamma"]],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    control = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Value",
        multiple=True,
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    return user, token, control, table, fields[0]


@pytest.mark.django_db
@pytest.mark.parametrize("page_kind", ["first", "last", "only", "empty"])
def test_every_options_page_can_recheck_changed_selections_without_reading_rows(
    api_client, membership_dashboard, monkeypatch, page_kind
):
    user, token, control, table, field = membership_dashboard
    model = table.get_model()
    if page_kind == "only":
        model.objects.exclude(**{field.db_column: "Alpha"}).delete()
    elif page_kind == "empty":
        model.objects.all().delete()
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": control.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    page = api_client.post(url, {"limit": 1}, format="json", **headers)
    assert page.status_code == 200, page.json()
    if page_kind == "last":
        page = api_client.post(
            url, {"after": page.json()["next"]}, format="json", **headers
        )
        assert page.status_code == 200, page.json()
    if page_kind != "first":
        assert page.json()["next"] is None

    selected = ["Gamma" if page_kind == "first" else "Alpha", "missing"]
    DashboardFilterService().update_filter(user, control.id, values=selected)
    model.objects.all().update(**{field.db_column: "Changed"})

    def fail_if_rows_are_read(*args, **kwargs):
        pytest.fail("Membership checks must reuse the retained options snapshot.")

    monkeypatch.setattr(
        DashboardTableRecordsHandler, "iter_scalar_field_values", fail_if_rows_are_read
    )
    monkeypatch.setattr(
        DashboardTableRecordsHandler, "iter_records", fail_if_rows_are_read
    )
    membership = api_client.post(
        url,
        {"after": page.json()["snapshot"], "limit": 1, "selected": selected},
        format="json",
        **headers,
    )
    assert membership.status_code == 200, membership.json()
    assert membership.json()["available"] == (
        [] if page_kind == "empty" else selected[:1]
    )
    assert membership.json()["results"] == ([] if page_kind == "empty" else ["Alpha"])


@pytest.mark.django_db
def test_membership_recheck_requires_current_table_access(
    api_client, membership_dashboard
):
    user, token, control, table, _ = membership_dashboard
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": control.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    page = api_client.post(url, {}, format="json", **headers)
    assert page.status_code == 200, page.json()
    assert page.json()["next"] is None
    assert table.database.workspace_id != control.dashboard.workspace_id
    WorkspaceUser.objects.filter(user=user, workspace=table.database.workspace).delete()

    membership = api_client.post(
        url,
        {"after": page.json()["snapshot"], "limit": 1, "selected": ["Alpha"]},
        format="json",
        **headers,
    )
    assert membership.status_code == 401, membership.json()
    assert membership.json()["error"] == "PERMISSION_DENIED"
