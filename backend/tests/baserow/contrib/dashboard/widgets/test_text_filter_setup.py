from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.widgets.actions import UpdateWidgetActionType
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


def configure_target(api_client, setup, widget, field=None):
    """Save a condition explicitly, as an editor would before copying it."""
    link = {
        "target_widget_id": widget.id,
        "enabled": True,
        "empty_behavior": "apply_nothing",
        "group": {
            "filter_type": "AND",
            "filter_groups": [],
            "filters": [
                {
                    "id": "manual",
                    "field": (field or setup["name"]).id,
                    "type": "contains",
                    "group": None,
                    "value": {
                        "formula": f"get('widget_data.{setup['filter'].id}')",
                        "mode": "simple",
                    },
                }
            ],
        },
    }
    response = patch_filter(
        api_client,
        setup,
        {
            "target_filters": [*links_of(setup["filter"].id).values(), link],
        },
    )
    assert response.status_code == 200, response.json()


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


def redo(setup):
    ActionHandler.redo(
        setup["user"],
        [ApplicationActionScopeType.value(setup["dashboard"].id)],
        "default-test-user-session-id",
    )


def update_links(setup, links):
    """Save the filter's links as an undoable editor action."""

    UpdateWidgetActionType.do(
        setup["user"], setup["filter"].id, "text_filter", {"target_filters": links}
    )


def new_widget(setup, title, table):
    """A widget added to the dashboard, then pointed at a table."""

    widget = setup["summary"](setup["tickets"], title)
    if table != setup["tickets"]:
        switch_table(setup, widget, table)
    return widget


@pytest.mark.django_db
def test_enabling_automatic_linking_does_not_link_existing_widgets(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    setup["summary"](setup["orders"], "Revenue")
    response = patch_filter(api_client, setup, {"apply_to_new_widgets": True})
    assert response.status_code == 200, response.json()
    assert response.json()["apply_to_new_widgets"] is True
    assert response.json()["target_filters"] == []


@pytest.mark.django_db
@pytest.mark.parametrize("empty_target", [False, True])
def test_new_widgets_do_not_generate_conditions(
    api_client, setup_dashboard, empty_target
):
    """Automatic linking alone, or an empty link, cannot invent conditions."""
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {
            "apply_to_new_widgets": True,
        },
    )
    if empty_target:
        existing = setup["summary"](setup["orders"], "Existing")
        response = patch_filter(
            api_client,
            setup,
            {
                "target_filters": [
                    {
                        "target_widget_id": existing.id,
                        "group": {
                            "filter_type": "AND",
                            "filters": [],
                            "filter_groups": [],
                        },
                    }
                ]
            },
        )
        assert response.status_code == 200
    before = links_of(setup["filter"].id)

    new_widget(setup, "Revenue", setup["orders"])

    assert links_of(setup["filter"].id) == before


@pytest.mark.django_db
def test_another_new_widget_gets_the_conditions_of_the_first_displayed_one(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"apply_to_new_widgets": True},
    )
    first = new_widget(setup, "Revenue", setup["orders"])
    configure_target(api_client, setup, first)
    second = new_widget(setup, "Count", setup["orders"])
    # Put the second widget first in the displayed list.
    first.grid_y = 1
    first.save(update_fields=["grid_y"])
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
    patch_filter(api_client, setup, {"apply_to_new_widgets": False})
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    original_links = links_of(setup["filter"].id)
    off = new_widget(setup, "Revenue", setup["orders"])
    patch_filter(api_client, setup, {"apply_to_new_widgets": True})
    tickets = new_widget(setup, "Tickets", setup["tickets"])
    switch_table(setup, tickets, setup["tickets"])

    assert links_of(setup["filter"].id) == original_links
    assert off.id and tickets.id


@pytest.mark.django_db
def test_a_linked_widget_switching_tables_is_filtered_like_the_others(
    api_client, setup_dashboard
):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"apply_to_new_widgets": True},
    )
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    widget = setup["summary"](setup["tickets"], "Tickets")
    patch_filter(
        api_client,
        setup,
        {
            "target_filters": [
                *links_of(setup["filter"].id).values(),
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
                },
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
        {"apply_to_new_widgets": True},
    )
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    original_links = links_of(setup["filter"].id)
    TextFilterWidget.objects.filter(id=setup["filter"].id).update(trashed=True)

    new_widget(setup, "Revenue", setup["orders"])

    assert links_of(setup["filter"].id) == original_links


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_table_switch_removes_the_link_it_added(api_client, setup_dashboard):
    setup = setup_dashboard
    patch_filter(
        api_client,
        setup,
        {"apply_to_new_widgets": True},
    )
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    original_links = links_of(setup["filter"].id)
    widget = setup["summary"](setup["tickets"], "Tickets")

    switch_table(setup, widget, setup["orders"])
    assert widget.id in links_of(setup["filter"].id)
    undo(setup)

    assert links_of(setup["filter"].id) == original_links


@pytest.mark.django_db
def test_switching_a_table_looks_up_widgets_once(setup_dashboard):
    setup = setup_dashboard
    widget = setup["summary"](setup["tickets"], "Tickets")

    def add_filters(count):
        for i in range(count):
            TextFilterWidget.objects.create(
                dashboard=setup["dashboard"],
                title=f"F{i}",
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
def test_duplicating_the_dashboard_keeps_automatic_linking(api_client, setup_dashboard):
    setup = setup_dashboard
    patch_filter(api_client, setup, {"apply_to_new_widgets": True})
    copy = CoreHandler().duplicate_application(setup["user"], setup["dashboard"])
    copied = TextFilterWidget.objects.get(dashboard=copy)
    assert copied.apply_to_new_widgets is True


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_table_switch_keeps_existing_widgets_unlinked(
    api_client, setup_dashboard
):
    """Undo must not auto-link a widget that was unlinked before the switch."""
    setup = setup_dashboard
    widget = setup["summary"](setup["orders"], "Existing")
    response = patch_filter(
        api_client,
        setup,
        {"apply_to_new_widgets": True},
    )
    assert response.status_code == 200
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    original_links = links_of(setup["filter"].id)
    assert widget.id not in original_links

    switch_table(setup, widget, setup["tickets"])
    undo(setup)

    widget.data_source.service.refresh_from_db()
    assert widget.data_source.service.specific.table_id == setup["orders"].id
    assert links_of(setup["filter"].id) == original_links

    ActionHandler.redo(
        setup["user"],
        [ApplicationActionScopeType.value(setup["dashboard"].id)],
        "default-test-user-session-id",
    )
    widget.data_source.service.refresh_from_db()
    assert widget.data_source.service.specific.table_id == setup["tickets"].id
    assert links_of(setup["filter"].id) == original_links


@pytest.mark.django_db
def test_new_widgets_copy_conditions_without_copying_a_targets_pause(
    api_client, setup_dashboard
):
    """Pausing one target must not pause automatic filtering of future targets."""
    setup = setup_dashboard
    response = patch_filter(
        api_client,
        setup,
        {"apply_to_new_widgets": True},
    )
    assert response.status_code == 200
    first = new_widget(setup, "First", setup["orders"])
    configure_target(api_client, setup, first)
    link = links_of(setup["filter"].id)[first.id]
    link["enabled"] = False
    link["group"]["filters"][0]["field"] = setup["notes"].id
    response = patch_filter(api_client, setup, {"target_filters": [link]})
    assert response.status_code == 200

    second = new_widget(setup, "Second", setup["orders"])

    links = links_of(setup["filter"].id)
    assert links[first.id]["enabled"] is False
    assert links[second.id]["enabled"] is True
    assert condition_fields(links[second.id]) == [setup["notes"].id]


@pytest.mark.django_db
def test_a_filter_copies_conditions_independently_for_each_table(
    api_client, setup_dashboard
):
    """One filter can serve different fields on multiple tables without a table setting."""
    setup = setup_dashboard
    values = {"apply_to_new_widgets": True}
    response = patch_filter(api_client, setup, values)
    assert response.status_code == 200
    orders = setup["summary"](setup["orders"], "Orders template")
    tickets = setup["summary"](setup["tickets"], "Tickets template")
    configure_target(api_client, setup, orders)
    configure_target(api_client, setup, tickets, setup["subject"])

    new_orders = new_widget(setup, "New orders", setup["orders"])
    new_tickets = setup["summary"](setup["orders"], "New tickets")
    switch_table(setup, new_tickets, setup["tickets"])

    links = links_of(setup["filter"].id)
    assert condition_fields(links[new_orders.id]) == [setup["name"].id]
    assert condition_fields(links[new_tickets.id]) == [setup["subject"].id]


@pytest.mark.django_db
def test_associating_widgets_copies_saved_conditions_only_for_the_same_table(
    api_client, setup_dashboard
):
    """Explicit association copies conditions even with future auto-linking off."""
    setup = setup_dashboard
    patch_filter(api_client, setup, {"apply_to_new_widgets": False})
    first = setup["summary"](setup["orders"], "First")
    configure_target(api_client, setup, first)
    last = setup["summary"](setup["orders"], "Last")
    first.grid_y = 1
    first.save(update_fields=["grid_y"])
    configure_target(api_client, setup, last, setup["notes"])
    saved = links_of(setup["filter"].id)
    saved[last.id]["enabled"] = False
    patch_filter(api_client, setup, {"target_filters": list(saved.values())})
    same_table = setup["summary"](setup["orders"], "Same table")
    other_table = setup["summary"](setup["tickets"], "Other table")
    empty = {"filter_type": "AND", "filters": [], "filter_groups": []}

    response = patch_filter(
        api_client,
        setup,
        {
            "target_filters": [
                *saved.values(),
                {"target_widget_id": same_table.id, "group": empty},
                {"target_widget_id": other_table.id, "group": empty},
            ]
        },
    )

    assert response.status_code == 200, response.json()
    links = links_of(setup["filter"].id)
    assert condition_fields(links[same_table.id]) == [setup["notes"].id]
    assert links[same_table.id]["enabled"] is True
    assert links[last.id]["enabled"] is False
    assert (
        links[same_table.id]["group"]["filters"][0]["id"]
        != saved[last.id]["group"]["filters"][0]["id"]
    )
    assert condition_fields(links[other_table.id]) == []

    # Clearing an existing target is an edit, not a request to seed it again.
    links[same_table.id]["group"] = empty
    response = patch_filter(api_client, setup, {"target_filters": list(links.values())})
    assert response.status_code == 200, response.json()
    assert condition_fields(links_of(setup["filter"].id)[same_table.id]) == []


@pytest.mark.django_db
def test_associating_a_widget_keeps_explicit_conditions(api_client, setup_dashboard):
    """An explicitly supplied condition is never replaced with a template."""
    setup = setup_dashboard
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    target = setup["summary"](setup["orders"], "Target")
    configure_target(api_client, setup, target, setup["notes"])
    assert condition_fields(links_of(setup["filter"].id)[target.id]) == [
        setup["notes"].id
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("preference,expected", [(None, True), (False, False)])
def test_new_filters_automatically_link_by_default_unless_explicitly_disabled(
    api_client, setup_dashboard, preference, expected
):
    """The creation default has an effect, while an explicit opt-out survives."""
    setup = setup_dashboard
    values = {"type": "text_filter", "title": "New filter"}
    if preference is not None:
        values["apply_to_new_widgets"] = preference
    response = api_client.post(
        reverse(
            "api:dashboard:widgets:list", kwargs={"dashboard_id": setup["dashboard"].id}
        ),
        values,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {setup['token']}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["apply_to_new_widgets"] is expected
    created = TextFilterWidget.objects.get(id=response.json()["id"])
    setup = {**setup, "filter": created}
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)

    widget = new_widget(setup, "New widget", setup["orders"])

    links = links_of(created.id)
    if expected:
        assert condition_fields(links[widget.id]) == [setup["name"].id]
    else:
        assert widget.id not in links


@pytest.mark.django_db
@pytest.mark.parametrize("first_y,second_y", [(0, 2), (2, 0)])
def test_template_selection_follows_display_order_for_both_association_paths(
    api_client, setup_dashboard, first_y, second_y
):
    """Grid order, rather than link insertion order or highest id, picks the model."""
    setup = setup_dashboard
    first = setup["summary"](setup["orders"], "First created")
    second = setup["summary"](setup["orders"], "Second created")
    first.grid_y, second.grid_y = first_y, second_y
    first.save(update_fields=["grid_y"])
    second.save(update_fields=["grid_y"])
    configure_target(api_client, setup, first)
    configure_target(api_client, setup, second, setup["notes"])
    expected = setup["name"].id if first_y < second_y else setup["notes"].id

    automatic = new_widget(setup, "Automatic", setup["orders"])
    assert condition_fields(links_of(setup["filter"].id)[automatic.id]) == [expected]
    explicit = setup["summary"](setup["orders"], "Explicit")
    response = patch_filter(
        api_client,
        setup,
        {
            "target_filters": [
                *links_of(setup["filter"].id).values(),
                {
                    "target_widget_id": explicit.id,
                    "group": {"filter_type": "AND", "filters": [], "filter_groups": []},
                },
            ]
        },
    )
    assert response.status_code == 200, response.json()
    assert condition_fields(links_of(setup["filter"].id)[explicit.id]) == [expected]


def choose_table(api_client, setup, widget, table):
    """Pick the widget's table in the guided setup of the filter."""

    response = api_client.patch(
        reverse(
            "api:dashboard:data_sources:item",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {"table_id": table.id, "link_filter_widget_id": setup["filter"].id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {setup['token']}",
        # The session `undo` and `redo` replay.
        HTTP_CLIENTSESSIONID="default-test-user-session-id",
    )
    assert response.status_code == 200, response.json()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_guided_setup_links_the_widget_as_soon_as_it_shows_a_table(
    api_client, setup_dashboard
):
    """The asking filter links the widget, copying its first widget on the table."""
    setup = setup_dashboard
    patch_filter(api_client, setup, {"apply_to_new_widgets": False})
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    other_filter = TextFilterWidget.objects.create(
        dashboard=setup["dashboard"], title="Other", apply_to_new_widgets=False
    )
    configure_target(api_client, {**setup, "filter": other_filter}, template)
    widget = setup["summary"](setup["tickets"], "Guided widget")

    choose_table(api_client, setup, widget, setup["orders"])

    link = links_of(setup["filter"].id)[widget.id]
    assert condition_fields(link) == [setup["name"].id]
    assert link["enabled"] is True
    # Only the asking filter links it: the other doesn't filter new widgets.
    assert widget.id not in links_of(other_filter.id)

    undo(setup)
    assert widget.id not in links_of(setup["filter"].id)
    redo(setup)
    assert condition_fields(links_of(setup["filter"].id)[widget.id]) == [
        setup["name"].id
    ]


@pytest.mark.django_db
def test_guided_setup_links_without_conditions_and_follows_table_changes(
    api_client, setup_dashboard
):
    """Without a widget to copy, the link starts empty; a new table re-seeds it."""
    setup = setup_dashboard
    widget = setup["summary"](setup["orders"], "Guided widget")
    choose_table(api_client, setup, widget, setup["tickets"])
    assert condition_fields(links_of(setup["filter"].id)[widget.id]) == []

    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template, setup["notes"])
    choose_table(api_client, setup, widget, setup["orders"])
    assert condition_fields(links_of(setup["filter"].id)[widget.id]) == [
        setup["notes"].id
    ]


@pytest.mark.django_db
def test_undo_and_redo_restore_links_without_copying_conditions(
    api_client, setup_dashboard
):
    """Copying applies to links an editor adds, not to links undo/redo restores."""
    setup = setup_dashboard
    template = setup["summary"](setup["orders"], "Template")
    configure_target(api_client, setup, template)
    other = setup["summary"](setup["orders"], "Other")
    empty = {"filter_type": "AND", "filters": [], "filter_groups": []}

    # An editor adding the widget gets the template's conditions.
    update_links(
        setup,
        [
            *links_of(setup["filter"].id).values(),
            {"target_widget_id": other.id, "group": empty},
        ],
    )
    copied = links_of(setup["filter"].id)[other.id]
    assert condition_fields(copied) == [setup["name"].id]
    undo(setup)
    assert other.id not in links_of(setup["filter"].id)
    redo(setup)
    assert links_of(setup["filter"].id)[other.id] == copied

    # The editor deliberately clears them, then removes the link.
    links = links_of(setup["filter"].id)
    links[other.id]["group"] = empty
    update_links(setup, list(links.values()))
    update_links(
        setup,
        [
            link
            for link in links_of(setup["filter"].id).values()
            if link["target_widget_id"] != other.id
        ],
    )

    undo(setup)
    assert condition_fields(links_of(setup["filter"].id)[other.id]) == []
    undo(setup)
    redo(setup)
    assert condition_fields(links_of(setup["filter"].id)[other.id]) == []
