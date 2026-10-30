from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.contrib.dashboard.filters.trash_types import (
    DashboardFilterTrashableItemType,
)
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.handler import CoreHandler


@pytest.fixture
def filtered_dashboard(data_fixture):
    user, token = data_fixture.create_user_and_token(session_id="filter-dispatch")
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Team", "text"), ("Amount", "number")],
        rows=[["Design", 1], ["Marketing", 4], ["", 16]],
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
    widget = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user, dashboard.id, label="Team", mode="input"
    )
    condition = data_fixture.create_local_baserow_table_service_filter(
        service=source.service,
        field=fields[0],
        type="equal",
        value=BaserowFormulaObject.create(f"get('dashboard_filter.{selection.id}')"),
    )
    return user, token, widget, selection, condition


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,values,expected",
    [
        ("equal", ["Design"], "1"),
        ("equal", [" Design "], "1"),
        ("equal", ["  "], "21"),
        ("equal", [], "21"),
        ("not_equal", ["Design"], "20"),
        ("contains", ["DESIGN"], "1"),
        ("contains_not", ["DESIGN"], "20"),
        ("starts_with", ["Des"], "1"),
        ("contains_word", ["Design"], "1"),
        ("doesnt_contain_word", ["Design"], "20"),
        ("length_is_lower_than", ["7"], "17"),
        ("empty", ["true"], "16"),
        ("not_empty", ["true"], "5"),
        ("empty", [], "21"),
        ("not_empty", [], "21"),
    ],
)
def test_dashboard_control_uses_builder_filter_operators(
    api_client, filtered_dashboard, operator, values, expected
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(
        user, selection.id, operator=operator, values=values
    )
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": expected}


@pytest.mark.django_db
def test_dispatch_ignores_stale_client_selections(api_client, filtered_dashboard):
    user, token, widget, selection, _ = filtered_dashboard
    DashboardFilterService().update_filter(user, selection.id, values=["Design"])
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {"filters": [{"filter_id": selection.id, "values": ["Marketing"]}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "1"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator", ["equal", "not_equal", "contains", "contains_not", "empty", "not_empty"]
)
def test_deleting_dashboard_filter_restores_unfiltered_widget_data(
    api_client, filtered_dashboard, operator
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(user, selection.id, operator=operator)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.delete(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        **headers,
    )
    assert response.status_code == 204
    sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list",
            kwargs={"dashboard_id": widget.dashboard_id},
        ),
        **headers,
    )
    assert sources.status_code == 200
    assert sources.json()[0]["filters"] == []
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "21"}


@pytest.mark.django_db
def test_source_cannot_read_a_filter_from_another_dashboard(
    api_client, data_fixture, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    other = data_fixture.create_dashboard_application(
        user=user, workspace=widget.dashboard.workspace
    )
    selection.dashboard = other
    selection.save()
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400, response.json()


@pytest.mark.django_db
def test_deleted_multiple_filter_removes_its_selection_from_dispatch(
    api_client, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(
        user,
        selection.id,
        mode="dropdown",
        multiple=True,
        values=["Design", "Marketing"],
    )
    condition.value = BaserowFormulaObject.create(
        f"get('dashboard_filter.{selection.id}.1')"
    )
    condition.save()
    DashboardFilterService().delete_filter(user, selection.id)
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "21"}


@pytest.mark.django_db
@pytest.mark.parametrize("path_suffix", ["", ".1"])
def test_copy_after_deleting_filter_keeps_widget_data_available(
    api_client, filtered_dashboard, path_suffix
):
    user, token, widget, selection, condition = filtered_dashboard
    condition.value = BaserowFormulaObject.create(
        f"get('dashboard_filter.{selection.id}{path_suffix}')"
    )
    condition.save()
    headers = {
        "HTTP_AUTHORIZATION": f"JWT {token}",
        "HTTP_CLIENTSESSIONID": "filter-dispatch",
    }
    response = api_client.delete(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        **headers,
    )
    assert response.status_code == 204
    copied = CoreHandler().duplicate_application(user, widget.dashboard)
    copied_widget = WidgetService().get_widgets(user, copied.id)[0]
    dispatch_url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": copied_widget.data_source_id},
    )
    response = api_client.post(dispatch_url, {}, format="json", **headers)
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "21"}

    # Restoring the original control must not reconnect the copied source to it.
    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(widget.dashboard_id)], "filter-dispatch"
    )
    response = api_client.post(
        dispatch_url,
        {},
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "21"}


@pytest.mark.django_db
def test_deleting_one_filter_preserves_other_conditions_and_can_be_undone(
    api_client, data_fixture, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    other = DashboardFilterService().create_filter(
        user,
        widget.dashboard_id,
        label="Other team",
        mode="input",
        values=["Marketing"],
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=condition.service,
        field=condition.field,
        type="equal",
        value=BaserowFormulaObject.create(f"get('dashboard_filter.{other.id}')"),
    )
    headers = {
        "HTTP_AUTHORIZATION": f"JWT {token}",
        "HTTP_CLIENTSESSIONID": "filter-dispatch",
    }
    deleted = api_client.delete(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        **headers,
    )
    assert deleted.status_code == 204
    dispatch_url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": widget.data_source_id},
    )
    response = api_client.post(
        dispatch_url,
        {},
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "4"}

    scope = [ApplicationActionScopeType.value(widget.dashboard_id)]
    sources_url = reverse(
        "api:dashboard:data_sources:list", kwargs={"dashboard_id": widget.dashboard_id}
    )
    remaining = api_client.get(sources_url, **headers).json()[0]["filters"]
    assert [item["value"]["formula"] for item in remaining] == [
        f"get('dashboard_filter.{other.id}')"
    ]
    ActionHandler.undo(user, scope, "filter-dispatch")
    DashboardFilterService().update_filter(user, other.id, values=[])
    DashboardFilterService().update_filter(user, selection.id, values=["Design"])
    restored = api_client.get(sources_url, **headers).json()[0]["filters"]
    assert {item["value"]["formula"] for item in restored} == {
        f"get('dashboard_filter.{selection.id}')",
        f"get('dashboard_filter.{other.id}')",
    }
    response = api_client.post(
        dispatch_url,
        {},
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "1"}

    ActionHandler.redo(user, scope, "filter-dispatch")
    response = api_client.post(dispatch_url, {}, format="json", **headers)
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "21"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,mode,removed",
    [
        ("concat(get('dashboard_filter.{id}'), 'suffix')", "simple", True),
        (" ( get( ('dashboard_filter.{id}.0') ) ) ", "advanced", True),
        ("get('dashboard_filter.{id}')", "raw", False),
        ("'dashboard_filter.{id}'", "simple", False),
        ("concat(", "simple", False),
        ("get('')", "simple", False),
    ],
)
def test_delete_removes_references_but_preserves_literals_and_unrelated_invalid_formulas(
    api_client, filtered_dashboard, formula, mode, removed
):
    user, token, widget, selection, condition = filtered_dashboard
    condition.value = BaserowFormulaObject.create(formula.format(id=selection.id), mode)
    condition.save()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.delete(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        **headers,
    )
    assert response.status_code == 204
    sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list",
            kwargs={"dashboard_id": widget.dashboard_id},
        ),
        **headers,
    )
    filters = sources.json()[0]["filters"]
    assert len(filters) == (0 if removed else 1)
    if not removed:
        assert filters[0]["value"] == condition.value


@pytest.mark.django_db
def test_delete_cleans_all_dashboard_sources_but_not_other_dashboards_or_builder(
    api_client, data_fixture, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    second_table = data_fixture.create_database_table(user=user)
    second_field = data_fixture.create_text_field(table=second_table)
    second_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=widget.dashboard, table=second_table
        )
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=second_source.service, field=second_field, value=condition.value
    )
    other_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            table=condition.field.table
        )
    )
    builder_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=condition.field.table
    )
    untouched = [
        data_fixture.create_local_baserow_table_service_filter(
            service=source.service, field=condition.field, value=condition.value
        )
        for source in (other_source, builder_source)
    ]
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.delete(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        **headers,
    )
    assert response.status_code == 204
    sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list",
            kwargs={"dashboard_id": widget.dashboard_id},
        ),
        **headers,
    )
    assert len(sources.json()) == 2
    assert all(source["filters"] == [] for source in sources.json())
    for other_condition in untouched:
        other_condition.refresh_from_db()
        assert other_condition.value == condition.value


@pytest.mark.django_db
def test_restore_preserves_nested_groups_and_source_edits_since_deletion(
    api_client, data_fixture, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    parent = data_fixture.create_local_baserow_table_service_filter_group(
        service=condition.service, filter_type="AND"
    )
    child = data_fixture.create_local_baserow_table_service_filter_group(
        service=condition.service, filter_type="OR", parent_group=parent
    )
    condition.group = child
    condition.save()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    DashboardFilterService().delete_filter(user, selection.id)
    source_url = reverse(
        "api:dashboard:data_sources:item",
        kwargs={"data_source_id": widget.data_source_id},
    )
    edited = api_client.patch(
        source_url,
        {
            "filters": [
                {
                    "field": condition.field_id,
                    "type": "not_equal",
                    "value": BaserowFormulaObject.create("Marketing", "raw"),
                    "group": str(child.id),
                }
            ]
        },
        format="json",
        **headers,
    )
    assert edited.status_code == 200, edited.json()
    DashboardFilterService().restore_filter(user, selection.id)
    sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list",
            kwargs={"dashboard_id": widget.dashboard_id},
        ),
        **headers,
    ).json()
    restored = sources[0]
    assert {item["value"]["formula"] for item in restored["filters"]} == {
        "Marketing",
        f"get('dashboard_filter.{selection.id}')",
    }
    assert all(item["group"] == str(child.id) for item in restored["filters"])
    assert restored["filter_groups"] == edited.json()["filter_groups"]


@pytest.mark.django_db
@pytest.mark.parametrize("remove", ["source", "field", "group"])
def test_restore_filter_after_its_linked_configuration_was_deleted(
    api_client, data_fixture, filtered_dashboard, remove
):
    user, token, widget, selection, condition = filtered_dashboard
    group = data_fixture.create_local_baserow_table_service_filter_group(
        service=condition.service
    )
    condition.group = group
    condition.save()
    DashboardFilterService().delete_filter(user, selection.id)
    if remove == "source":
        source = widget.data_source
        widget.delete()
        source.delete()
    elif remove == "field":
        condition.field.delete()
    else:
        group.delete()
    DashboardFilterService().restore_filter(user, selection.id)
    assert (
        DashboardFilterService().get_filter(user, selection.id).label == selection.label
    )
    sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list",
            kwargs={"dashboard_id": widget.dashboard_id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    ).json()
    assert all(source["filters"] == [] for source in sources)


@pytest.mark.django_db
@pytest.mark.parametrize("restore_order", [(0, 1), (1, 0)])
def test_restore_condition_only_when_all_referenced_filters_are_available(
    api_client, filtered_dashboard, restore_order
):
    user, token, widget, selection, condition = filtered_dashboard
    second = DashboardFilterService().create_filter(
        user, widget.dashboard_id, label="Second", mode="input"
    )
    condition.value = BaserowFormulaObject.create(
        f"concat(get('dashboard_filter.{selection.id}'), "
        f"get('dashboard_filter.{second.id}'))"
    )
    condition.save()
    selections = (selection, second)
    source_url = reverse(
        "api:dashboard:data_sources:list",
        kwargs={"dashboard_id": widget.dashboard_id},
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    for control in selections:
        DashboardFilterService().delete_filter(user, control.id)
    DashboardFilterService().restore_filter(user, selections[restore_order[0]].id)
    assert api_client.get(source_url, **headers).json()[0]["filters"] == []

    # Deleting the partially restored control must retain the shared snapshot.
    DashboardFilterService().delete_filter(user, selections[restore_order[0]].id)
    DashboardFilterService().restore_filter(user, selections[restore_order[1]].id)
    assert api_client.get(source_url, **headers).json()[0]["filters"] == []
    DashboardFilterService().restore_filter(user, selections[restore_order[0]].id)
    restored = api_client.get(source_url, **headers).json()[0]["filters"]
    assert len(restored) == 1
    assert restored[0]["value"] == condition.value


@pytest.mark.django_db(transaction=True)
def test_concurrent_filter_restorations_keep_the_shared_condition(
    api_client, filtered_dashboard, mocker
):
    user, token, widget, selection, condition = filtered_dashboard
    second = DashboardFilterService().create_filter(
        user, widget.dashboard_id, label="Second", mode="input"
    )
    condition.value = BaserowFormulaObject.create(
        f"concat(get('dashboard_filter.{selection.id}'), "
        f"get('dashboard_filter.{second.id}'))"
    )
    condition.save()
    for control in (selection, second):
        DashboardFilterService().delete_filter(user, control.id)

    barrier = Barrier(2)
    restore_filter = DashboardFilterTrashableItemType.restore

    def synchronized_restore(handler, *args, **kwargs):
        # Start both restores together before they acquire the dashboard lock.
        barrier.wait(timeout=20)
        return restore_filter(handler, *args, **kwargs)

    mocker.patch.object(
        DashboardFilterTrashableItemType, "restore", synchronized_restore
    )

    def restore(control):
        close_old_connections()
        try:
            DashboardFilterService().restore_filter(user, control.id)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(restore, (selection, second)))

    sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list",
            kwargs={"dashboard_id": widget.dashboard_id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    ).json()
    assert [item["value"] for item in sources[0]["filters"]] == [condition.value]


@pytest.mark.django_db
def test_source_save_after_filter_deletion_keeps_only_available_conditions(
    api_client, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().delete_filter(user, selection.id)
    raw_value = BaserowFormulaObject.create("Marketing", "raw")
    response = api_client.patch(
        reverse(
            "api:dashboard:data_sources:item",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {
            "name": "Updated after deletion",
            "filters": [
                {
                    "field": condition.field_id,
                    "type": "equal",
                    "value": value,
                }
                for value in (condition.value, raw_value)
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    source = response.json()
    assert source["name"] == "Updated after deletion"
    assert [item["value"] for item in source["filters"]] == [raw_value]


@pytest.mark.django_db
def test_multiple_values_are_available_to_source_formulas(
    api_client, filtered_dashboard
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(
        user,
        selection.id,
        mode="dropdown",
        multiple=True,
        values=["Design", "Marketing"],
    )
    condition.value = BaserowFormulaObject.create(
        f"get('dashboard_filter.{selection.id}.1')"
    )
    condition.save()
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "4"}


@pytest.mark.django_db
def test_widgets_sharing_a_source_share_its_filter_conditions(
    api_client, data_fixture, filtered_dashboard
):
    user, token, widget, selection, _ = filtered_dashboard
    DashboardFilterService().update_filter(user, selection.id, values=["Design"])
    shared = data_fixture.create_summary_widget(
        dashboard=widget.dashboard, data_source=widget.data_source
    )
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": shared.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response.json() == {"result": "1"}


@pytest.mark.django_db
def test_dashboard_operator_controls_multiple_values(api_client, filtered_dashboard):
    _, token, widget, selection, _ = filtered_dashboard
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    item_url = reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id})
    response = api_client.patch(
        item_url,
        {
            "mode": "dropdown",
            "multiple": True,
            "operator": "equal",
            "values": ["Design", "Marketing"],
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    dispatch_url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": widget.data_source_id},
    )
    data = {}
    assert api_client.post(dispatch_url, data, format="json", **headers).json() == {
        "result": "5"
    }
    response = api_client.patch(
        item_url, {"operator": "not_equal"}, format="json", **headers
    )
    assert response.status_code == 200
    assert api_client.post(dispatch_url, data, format="json", **headers).json() == {
        "result": "16"
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,values,expected",
    [
        ("equal", ["Design", "Marketing"], "5"),
        ("not_equal", ["Design", "Marketing"], "16"),
        ("contains", ["DES", "MARK"], "5"),
        ("contains_not", ["DES", "MARK"], "16"),
        ("contains_word", ["Design", "Marketing"], "5"),
        ("doesnt_contain_word", ["Design", "Marketing"], "16"),
        ("starts_with", ["Des", "Mar"], "5"),
        ("length_is_lower_than", ["2", "7"], "17"),
        ("not_equal", [], "21"),
        ("not_equal", [" ", ""], "21"),
        ("equal", ["Design,Marketing"], None),
    ],
)
def test_multiple_dashboard_values_are_individual_operands(
    api_client, filtered_dashboard, operator, values, expected
):
    user, token, widget, selection, _ = filtered_dashboard
    DashboardFilterService().update_filter(
        user,
        selection.id,
        mode="dropdown",
        multiple=True,
        operator=operator,
        values=values,
    )
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": expected}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "expression",
    [
        "get('dashboard_filter.{id}')",
        ' GET("dashboard_filter.{id}") ',
        "get( 'dashboard_filter.{id}' )",
        "get(('dashboard_filter.{id}'))",
        "(get('dashboard_filter.{id}'))",
        "get('dashboard_filter.{id}.*')",
        "get('dashboard_filter[{id}]')",
        "get('dashboard_filter.{id}[0]')",
        "get( ('dashboard_filter[{id}][*]') )",
    ],
)
def test_dashboard_operator_overrides_only_direct_references(
    api_client, filtered_dashboard, expression
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(
        user,
        selection.id,
        mode="dropdown",
        multiple=True,
        operator="not_equal",
        values=["Design"],
    )
    condition.value = BaserowFormulaObject.create(expression.format(id=selection.id))
    condition.save()
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "20"}


@pytest.mark.django_db
def test_calculated_conditions_keep_their_own_operator(api_client, filtered_dashboard):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(
        user, selection.id, operator="not_equal", values=["Design"]
    )
    condition.value = BaserowFormulaObject.create(
        f"concat(get('dashboard_filter.{selection.id}'), '')"
    )
    condition.save()
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "1"}


@pytest.mark.django_db
def test_source_conditions_reject_option_table_references(
    api_client, filtered_dashboard
):
    _, token, widget, _, condition = filtered_dashboard
    response = api_client.patch(
        reverse(
            "api:dashboard:data_sources:item",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {
            "filters": [
                {
                    "field": condition.field_id,
                    "type": "equal",
                    "value": BaserowFormulaObject.create(
                        f"get('table.{condition.field.table_id}.*."
                        f"{condition.field.db_column}')"
                    ),
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400, response.json()
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_source_dispatch_rejects_saved_option_table_references_before_reading_records(
    api_client, filtered_dashboard, monkeypatch
):
    from baserow.contrib.dashboard.data_sources.records import (
        DashboardTableRecordsHandler,
    )

    _, token, widget, _, condition = filtered_dashboard
    condition.value = BaserowFormulaObject.create(
        f"get('table.{condition.field.table_id}.*.{condition.field.db_column}')"
    )
    condition.save()
    reads = []
    original = DashboardTableRecordsHandler.iter_records

    def read_records(*args, **kwargs):
        reads.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(DashboardTableRecordsHandler, "iter_records", read_records)
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400, response.json()
    assert reads == []


@pytest.mark.django_db
@pytest.mark.parametrize("next_mode", ["dropdown", "input"])
@pytest.mark.parametrize("suffix", ["", ".*", ".0"])
def test_control_links_survive_changing_multiple_to_single_or_input(
    api_client, filtered_dashboard, next_mode, suffix
):
    user, token, widget, selection, condition = filtered_dashboard
    DashboardFilterService().update_filter(
        user, selection.id, mode="dropdown", multiple=True, values=["Design"]
    )
    condition.value = BaserowFormulaObject.create(
        f"get('dashboard_filter.{selection.id}{suffix}')"
    )
    condition.save()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": widget.data_source_id},
    )
    payload = {}
    response = api_client.post(url, payload, format="json", **headers)
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "1"}

    changed = api_client.patch(
        reverse("api:dashboard:filters:item", kwargs={"filter_id": selection.id}),
        {"mode": next_mode, "multiple": False},
        format="json",
        **headers,
    )
    assert changed.status_code == 200, changed.json()
    reset = api_client.post(url, {}, format="json", **headers)
    assert reset.status_code == 200, reset.json()
    assert reset.json() == {"result": "21"}
    DashboardFilterService().update_filter(user, selection.id, values=["Design"])
    response = api_client.post(url, payload, format="json", **headers)
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "1"}


@pytest.mark.django_db
def test_public_dispatch_uses_shared_selection_without_exposing_configuration(
    api_client, filtered_dashboard
):
    user, _, widget, selection, _ = filtered_dashboard
    dashboard = widget.dashboard
    dashboard.public = True
    dashboard.save()
    DashboardFilterService().update_filter(user, selection.id, values=["Design"])
    response = api_client.post(
        reverse(
            "api:dashboard:public:data_source_dispatch",
            kwargs={"slug": dashboard.slug, "data_source_id": widget.data_source_id},
        ),
        {"filters": [{"filter_id": selection.id, "values": ["Marketing"]}]},
        format="json",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"result": "1"}
    info = api_client.get(
        reverse("api:dashboard:public:info", kwargs={"slug": dashboard.slug})
    ).json()
    assert "filters" not in info
    assert "dashboard_filter" not in str(info)
