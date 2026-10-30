from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.formula.types import BaserowFormulaObject
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.mark.django_db
def test_viewer_reads_shared_selections_but_only_builder_can_update_them(
    api_client, data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    viewer, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[viewer])
    roles = RoleAssignmentHandler()
    roles.assign_role(admin, workspace, role=roles.get_role_by_uid("ADMIN"))
    roles.assign_role(viewer, workspace, role=roles.get_role_by_uid("VIEWER"))
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        user=admin,
        database=database,
        columns=[("Team", "text"), ("Amount", "number")],
        rows=[["Design", 10], ["Sales", 20]],
    )
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=admin
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard,
        integration=integration,
        table=table,
        field=fields[1],
        aggregation_type="sum",
    )
    widget = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    config = DashboardFilterService().create_filter(
        admin,
        dashboard.id,
        label="Team",
        values=["Design"],
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=source.service,
        field=fields[0],
        type="equal",
        value=BaserowFormulaObject.create(f"get('dashboard_filter.{config.id}')"),
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    listing = reverse(
        "api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}
    )
    item = reverse("api:dashboard:filters:item", kwargs={"filter_id": config.id})
    order = reverse(
        "api:dashboard:filters:order", kwargs={"dashboard_id": dashboard.id}
    )
    assert api_client.get(listing, **headers).status_code == 200
    choices = api_client.post(
        reverse("api:dashboard:filters:options", kwargs={"filter_id": config.id}),
        {},
        format="json",
        **headers,
    )
    assert choices.status_code == 200, choices.json()
    assert choices.json()["results"] == ["Design", "Sales"]
    result = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {"filters": [{"filter_id": config.id, "values": ["Sales"]}]},
        format="json",
        **headers,
    )
    assert result.status_code == 200, result.json()
    assert result.json() == {"result": "10"}
    for response in [
        api_client.post(listing, {"label": "Other"}, format="json", **headers),
        api_client.patch(item, {"label": "Renamed"}, format="json", **headers),
        api_client.patch(item, {"values": ["Sales"]}, format="json", **headers),
        api_client.delete(item, **headers),
        api_client.post(order, {"order": [config.id]}, format="json", **headers),
    ]:
        assert response.status_code == 401
        assert response.json()["error"] == "PERMISSION_DENIED"
    roles.assign_role(viewer, workspace, role=roles.get_role_by_uid("BUILDER"))
    assert (
        api_client.post(
            order, {"order": [config.id]}, format="json", **headers
        ).status_code
        == 204
    )
    assert (
        api_client.patch(
            item, {"label": "Renamed", "values": ["Sales"]}, format="json", **headers
        ).status_code
        == 200
    )

    assert api_client.get(listing, **headers).json()[0]["values"] == ["Sales"]
