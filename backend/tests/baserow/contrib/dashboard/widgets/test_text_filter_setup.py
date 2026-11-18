from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.widgets.models import SummaryWidget, TextFilterWidget
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.handler import CoreHandler
from baserow.core.services.registries import service_type_registry


@pytest.fixture
def setup_dashboard(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    orders = data_fixture.create_database_table(database=database, name="Orders")
    tickets = data_fixture.create_database_table(database=database, name="Tickets")
    category = data_fixture.create_single_select_field(table=orders, name="Category")
    name = data_fixture.create_text_field(table=orders, name="Name", primary=True)
    notes = data_fixture.create_text_field(table=orders, name="Notes")
    subject = data_fixture.create_text_field(
        table=tickets, name="Subject", primary=True
    )
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )

    def summary(table, title):
        service = data_fixture.create_local_baserow_aggregate_rows_service(
            integration=integration, table=table
        )
        source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, service=service
        )
        return SummaryWidget.objects.create(
            dashboard=dashboard, title=title, data_source=source
        )

    filter_widget = TextFilterWidget.objects.create(
        dashboard=dashboard, title="Filter", mode="input"
    )
    return {
        "user": user,
        "token": token,
        "workspace": workspace,
        "dashboard": dashboard,
        "orders": orders,
        "tickets": tickets,
        "category": category,
        "name": name,
        "notes": notes,
        "subject": subject,
        "filter": filter_widget,
        "summary": summary,
    }


def patch_filter(api_client, setup, values):
    return api_client.patch(
        reverse(
            "api:dashboard:widgets:item",
            kwargs={"widget_id": setup["filter"].id},
        ),
        {"type": "text_filter", **values},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {setup['token']}",
    )


def links_of(widget_id):
    return {
        link["target_widget_id"]: link
        for link in TextFilterWidget.objects_and_trash.get(id=widget_id).target_filters
    }


def condition_fields(link):
    return [condition["field"] for condition in link["group"]["filters"]]


def switch_table(setup, widget, table):
    UpdateDashboardDataSourceActionType.do(
        setup["user"],
        widget.data_source_id,
        service_type_registry.get("local_baserow_aggregate_rows"),
        {"table_id": table.id},
    )


def undo(setup):
    ActionHandler.undo(
        setup["user"],
        [ApplicationActionScopeType.value(setup["dashboard"].id)],
        "default-test-user-session-id",
    )


def new_widget(setup, title, table):
    """A widget added to the dashboard, then pointed at a table."""

    widget = setup["summary"](setup["tickets"], title)
    if table != setup["tickets"]:
        switch_table(setup, widget, table)
    return widget


@pytest.mark.django_db
def test_choosing_a_table_stores_it_without_linking_widgets(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    setup["summary"](setup["orders"], "Revenue")

    response = patch_filter(
        api_client,
        setup,
        {"filter_table_id": setup["orders"].id, "apply_to_new_widgets": True},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["filter_table_id"] == setup["orders"].id
    assert response.json()["target_filters"] == []

    response = patch_filter(api_client, setup, {"filter_table_id": None})
    assert response.status_code == 200, response.json()
    assert response.json()["filter_table_id"] is None


@pytest.mark.django_db
def test_a_table_outside_the_workspace_is_rejected(
    api_client, setup_dashboard, data_fixture
):
    setup = setup_dashboard
    other = data_fixture.create_database_table()
    trashed = data_fixture.create_database_table(
        database=setup["orders"].database, trashed=True
    )

    for table_id in (other.id, trashed.id, 999999):
        response = patch_filter(api_client, setup, {"filter_table_id": table_id})
        assert response.status_code == 400, response.json()
        assert "filter_table_id" in str(response.json())


@pytest.mark.django_db
def test_a_first_new_widget_of_the_table_matches_its_first_field(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"filter_table_id": setup["orders"].id, "apply_to_new_widgets": True},
    )

    widget = new_widget(setup, "Revenue", setup["orders"])

    link = links_of(setup["filter"].id)[widget.id]
    # The primary field, although the table has others created before it.
    assert condition_fields(link) == [setup["name"].id]
    condition = link["group"]["filters"][0]
    assert condition["type"] == "contains"
    assert condition["value"]["formula"] == f"get('widget_data.{setup['filter'].id}')"
    assert link["empty_behavior"] == "apply_nothing"


@pytest.mark.django_db
def test_a_primary_field_that_cannot_be_matched_falls_back_to_the_next(
    api_client, setup_dashboard, data_fixture
):
    setup = setup_dashboard
    table = data_fixture.create_database_table(
        database=setup["orders"].database, name="Files"
    )
    data_fixture.create_file_field(table=table, primary=True, order=0)
    title = data_fixture.create_text_field(table=table, name="Title", order=1)
    patch_filter(
        api_client,
        setup,
        {"filter_table_id": table.id, "apply_to_new_widgets": True},
    )

    widget = new_widget(setup, "Files", table)

    assert condition_fields(links_of(setup["filter"].id)[widget.id]) == [title.id]


@pytest.mark.django_db
def test_another_new_widget_gets_the_conditions_of_the_previous_one(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"filter_table_id": setup["orders"].id, "apply_to_new_widgets": True},
    )
    first = new_widget(setup, "Revenue", setup["orders"])
    second = new_widget(setup, "Count", setup["orders"])
    # The editor changes the conditions of the last one.
    links = list(links_of(setup["filter"].id).values())
    edited = links_of(setup["filter"].id)[second.id]
    edited["group"]["filter_type"] = "OR"
    edited["group"]["filters"].append(
        {**edited["group"]["filters"][0], "id": "x", "field": setup["notes"].id}
    )
    edited["empty_behavior"] = "apply_alternative"
    edited["alternative_group"] = {
        "filter_type": "AND",
        "filter_groups": [],
        "filters": [{"id": "y", "field": setup["notes"].id, "type": "empty"}],
    }
    response = patch_filter(
        api_client,
        setup,
        {
            "target_filters": [
                link if link["target_widget_id"] != second.id else edited
                for link in links
            ]
        },
    )
    assert response.status_code == 200, response.json()

    third = new_widget(setup, "Average", setup["orders"])

    links = links_of(setup["filter"].id)
    assert condition_fields(links[first.id]) == [setup["name"].id]
    copied = links[third.id]
    assert copied["group"]["filter_type"] == "OR"
    assert condition_fields(copied) == [setup["name"].id, setup["notes"].id]
    assert copied["empty_behavior"] == "apply_alternative"
    assert [c["field"] for c in copied["alternative_group"]["filters"]] == [
        setup["notes"].id
    ]
    # The copy has conditions of its own.
    copied_ids = {c["id"] for c in copied["group"]["filters"]}
    assert not copied_ids & {c["id"] for c in links[second.id]["group"]["filters"]}


@pytest.mark.django_db
def test_widgets_are_not_linked_unless_asked_or_of_another_table(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    patch_filter(api_client, setup, {"filter_table_id": setup["orders"].id})
    off = new_widget(setup, "Revenue", setup["orders"])
    patch_filter(api_client, setup, {"apply_to_new_widgets": True})
    tickets = new_widget(setup, "Tickets", setup["tickets"])
    switch_table(setup, tickets, setup["tickets"])

    assert links_of(setup["filter"].id) == {}
    assert off.id and tickets.id


@pytest.mark.django_db
def test_a_linked_widget_switching_tables_is_filtered_like_the_others(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"filter_table_id": setup["orders"].id, "apply_to_new_widgets": True},
    )
    widget = setup["summary"](setup["tickets"], "Tickets")
    patch_filter(
        api_client,
        setup,
        {
            "target_filters": [
                {
                    "target_widget_id": widget.id,
                    "enabled": False,
                    "empty_behavior": "apply_nothing",
                    "group": {
                        "filter_type": "AND",
                        "filter_groups": [],
                        "filters": [
                            {
                                "id": "a",
                                "field": setup["subject"].id,
                                "type": "contains",
                                "value": "",
                            }
                        ],
                    },
                }
            ]
        },
    )

    switch_table(setup, widget, setup["orders"])
    link = links_of(setup["filter"].id)[widget.id]
    assert condition_fields(link) == [setup["name"].id]
    # The editor's choice to pause it is kept.
    assert link["enabled"] is False

    switch_table(setup, widget, setup["tickets"])
    assert condition_fields(links_of(setup["filter"].id)[widget.id]) == []


@pytest.mark.django_db
def test_a_trashed_filter_does_not_link_new_widgets(api_client, setup_dashboard):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"filter_table_id": setup["orders"].id, "apply_to_new_widgets": True},
    )
    TextFilterWidget.objects.filter(id=setup["filter"].id).update(trashed=True)

    new_widget(setup, "Revenue", setup["orders"])

    assert links_of(setup["filter"].id) == {}


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_table_switch_removes_the_link_it_added(api_client, setup_dashboard):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"filter_table_id": setup["orders"].id, "apply_to_new_widgets": True},
    )
    widget = setup["summary"](setup["tickets"], "Tickets")

    switch_table(setup, widget, setup["orders"])
    assert widget.id in links_of(setup["filter"].id)
    undo(setup)

    assert links_of(setup["filter"].id) == {}


@pytest.mark.django_db
def test_switching_a_table_looks_up_widgets_and_fields_once(setup_dashboard):
    setup = setup_dashboard
    widget = setup["summary"](setup["tickets"], "Tickets")

    def add_filters(count):
        for i in range(count):
            TextFilterWidget.objects.create(
                dashboard=setup["dashboard"],
                title=f"F{i}",
                filter_table=setup["orders"],
                apply_to_new_widgets=True,
            )

    def switch(table):
        with CaptureQueriesContext(connection) as ctx:
            switch_table(setup, widget, table)
        return {
            name: sum(
                1
                for query in ctx.captured_queries
                if query["sql"].startswith("SELECT")
                and f'FROM "{name}"' in query["sql"]
            )
            for name in ("database_field", "dashboard_dashboarddatasource")
        }

    add_filters(1)
    with_one_filter = switch(setup["orders"])
    switch(setup["tickets"])
    add_filters(4)
    with_five_filters = switch(setup["orders"])

    assert with_five_filters == with_one_filter


@pytest.mark.django_db
def test_duplicating_the_dashboard_keeps_the_filter_table(api_client, setup_dashboard):
    setup = setup_dashboard
    patch_filter(api_client, setup, {"filter_table_id": setup["orders"].id})

    copy = CoreHandler().duplicate_application(setup["user"], setup["dashboard"])

    copied = TextFilterWidget.objects.get(dashboard=copy)
    assert copied.filter_table_id == setup["orders"].id


def test_an_import_points_at_the_imported_table_or_forgets_it():
    from baserow.contrib.dashboard.widgets.widget_types import TextFilterWidgetType
    from baserow.core.registries import ImportExportConfig

    widget_type = TextFilterWidgetType()
    mapping = {"database_tables": {1: 2}}

    def imported(table_id, keeps):
        return widget_type.deserialize_property(
            "filter_table_id",
            table_id,
            mapping,
            import_export_config=ImportExportConfig(
                include_permission_data=False,
                reduce_disk_space_usage=False,
                is_duplicate=keeps,
            ),
        )

    assert imported(1, keeps=False) == 2
    # A table outside the import: kept by a duplicate, forgotten elsewhere.
    assert imported(3, keeps=True) == 3
    assert imported(3, keeps=False) is None
    assert imported(None, keeps=False) is None
