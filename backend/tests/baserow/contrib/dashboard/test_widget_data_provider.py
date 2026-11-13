from contextlib import nullcontext

from django.http import HttpRequest
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.data_providers import WidgetDataProviderType
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.widgets.models import SummaryWidget, TextFilterWidget
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.deferred_callbacks import deferred_callback_context
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.registries import ImportExportConfig
from baserow.core.trash.handler import TrashHandler


@pytest.fixture
def filter_dashboard(data_fixture):
    """Create distinguishable groups so clearing a filter changes the aggregate."""
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table)
    amount = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        [
            {name.db_column: "Alpha", amount.db_column: 10},
            {name.db_column: "Beta", amount.db_column: 20},
            {name.db_column: " ", amount.db_column: 40},
        ],
    )
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, public=True
    )
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        integration=integration, table=table, field=amount, aggregation_type="sum"
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, service=service
    )
    widget = TextFilterWidget.objects.create(
        dashboard=dashboard,
        title="Search",
        default_value="Alpha",
        grid_width=2,
        grid_height=2,
    )
    target = SummaryWidget.objects.create(
        dashboard=dashboard,
        title="Total",
        data_source=source,
        grid_x=2,
        grid_width=2,
        grid_height=4,
    )
    widget.target_filters = [
        {
            "target_widget_id": target.id,
            "group": {
                "filter_type": "AND",
                "filter_groups": [],
                "filters": [
                    {
                        "field": name.id,
                        "type": "equal",
                        "value": BaserowFormulaObject.create(
                            f"get('widget_data.{widget.id}')"
                        ),
                    }
                ],
            },
            "empty_behavior": "apply_nothing",
        }
    ]
    widget.save()
    condition = widget.target_filters[0]["group"]["filters"][0]
    return user, token, dashboard, source, widget, condition


@pytest.mark.django_db
@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("value,enabled_result", [("Alpha", "10"), ("", "20")])
def test_disable_target_preserves_conditions(
    api_client, filter_dashboard, public, value, enabled_result
):
    from copy import deepcopy

    _, token, dashboard, source, widget, _ = filter_dashboard
    link = widget.target_filters[0]
    link["empty_behavior"] = "apply_alternative"
    link["alternative_group"] = deepcopy(link["group"])
    link["alternative_group"]["filters"][0]["value"] = BaserowFormulaObject.create(
        "Beta", mode="raw"
    )
    original = deepcopy(link)
    dispatch_url = reverse(
        "api:dashboard:public:data_source_dispatch"
        if public
        else "api:dashboard:data_sources:dispatch",
        kwargs={"slug": dashboard.slug, "data_source_id": source.id}
        if public
        else {"data_source_id": source.id},
    )
    for enabled, expected in [(False, "70"), (True, enabled_result)]:
        link["enabled"] = enabled
        response = api_client.patch(
            reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id}),
            {"type": "text_filter", "target_filters": [link]},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == 200, response.json()
        widget.refresh_from_db()
        assert widget.target_filters == [{**original, "enabled": enabled}]
        response = api_client.post(
            dispatch_url,
            {"widget_data": {str(widget.id): value}},
            format="json",
            **({} if public else {"HTTP_AUTHORIZATION": f"JWT {token}"}),
        )
        assert response.status_code == 200, response.json()
        assert response.json()["result"] == expected
        assert response.json().get("_is_filtered", False) is enabled


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["input", "dropdown"])
@pytest.mark.parametrize(
    "public,password", [(False, False), (True, False), (True, True)]
)
def test_dispatch_widget_values(api_client, filter_dashboard, public, password, mode):
    """Defaults and explicit empties work through each authenticated dispatch surface."""
    _, token, dashboard, source, widget, _ = filter_dashboard
    widget.mode = mode
    widget.options = "Alpha, Beta"
    widget.save()
    if public:
        url = reverse(
            "api:dashboard:public:data_source_dispatch",
            kwargs={"slug": dashboard.slug, "data_source_id": source.id},
        )
        headers = {}
        if password:
            dashboard.set_password("test-password")
            dashboard.save()
            assert api_client.post(url, {}, format="json").status_code == 401
            auth = api_client.post(
                reverse("api:dashboard:public:auth", kwargs={"slug": dashboard.slug}),
                {"password": "test-password"},
                format="json",
            )
            headers = {
                "HTTP_BASEROW_DASHBOARD_AUTHORIZATION": f"JWT {auth.json()['access_token']}"
            }
    else:
        url = reverse(
            "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": source.id}
        )
        headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    for payload, expected in [
        ({}, "10"),
        ({"widget_data": {str(widget.id): "Beta"}}, "20"),
        ({"widget_data": {str(widget.id): ""}}, "70"),
        ({"widget_data": {str(widget.id): " "}}, "70"),
    ]:
        response = api_client.post(url, payload, format="json", **headers)
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "result": expected,
            **(
                {"_is_filtered": True}
                if payload.get("widget_data", {}).get(str(widget.id), "Alpha") != ""
                else {}
            ),
        }
    widget.refresh_from_db()
    assert widget.default_value == "Alpha"


@pytest.mark.django_db
@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("operator", ["equal", "not_equal"])
def test_multiple_dropdown_matches_individual_values(
    api_client, filter_dashboard, public, operator
):
    user, token, dashboard, source, widget, condition = filter_dashboard
    service = source.service.specific
    # A literal comma in a value must not be confused with multiple selections.
    RowHandler().create_row(
        user,
        service.table,
        {f"field_{condition['field']}": "Alpha,Beta", service.field.db_column: 80},
    )
    widget.mode = "dropdown"
    widget.multiple = True
    condition["type"] = operator
    widget.save()
    url = reverse(
        "api:dashboard:public:data_source_dispatch"
        if public
        else "api:dashboard:data_sources:dispatch",
        kwargs={"slug": dashboard.slug, "data_source_id": source.id}
        if public
        else {"data_source_id": source.id},
    )
    headers = {} if public else {"HTTP_AUTHORIZATION": f"JWT {token}"}
    for values, matching in [
        (["Alpha", "Beta"], 30),
        (["Alpha", "Beta", "Alpha"], 30),
        (["Alpha"], 10),
        (["Alpha,Beta"], 80),
        (["Missing"], 0),
        ([], 150),
    ]:
        expected = matching if operator == "equal" or not values else 150 - matching
        response = api_client.post(
            url, {"widget_data": {str(widget.id): values}}, format="json", **headers
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "result": str(expected) if expected else None,
            **({"_is_filtered": True} if values else {}),
        }

    # An explicit formula that joins values still requests a scalar comparison.
    widget.target_filters[0]["group"]["filters"][0]["value"] = (
        BaserowFormulaObject.create(f"join(get('widget_data.{widget.id}'), ',')")
    )
    widget.save()
    response = api_client.post(
        url,
        {"widget_data": {str(widget.id): ["Alpha", "Beta"]}},
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {
        "result": "80" if operator == "equal" else "70",
        "_is_filtered": True,
    }


@pytest.mark.django_db
def test_multiple_dropdown_preserves_other_conditions(data_fixture, filter_dashboard):
    _, _, dashboard, source, widget, condition = filter_dashboard
    service = source.service.specific
    widget.mode = "dropdown"
    widget.multiple = True
    group = widget.target_filters[0]["group"]
    group["filter_groups"] = [
        {"id": "countries", "parent_group": None, "filter_type": "AND"}
    ]
    condition["group"] = "countries"
    widget.save()
    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=service.field,
        type="higher_than",
        value=BaserowFormulaObject.create("15", mode="raw"),
    )
    context = DashboardDispatchContext(
        HttpRequest(),
        dashboard=dashboard,
        data={"widget_data": {str(widget.id): ["Alpha", "Beta"]}},
    )
    assert DashboardDataSourceHandler().dispatch_data_source(source, context) == {
        "result": "20",
        "_is_filtered": True,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("public", [False, True])
def test_multiple_dropdown_exposes_lists_and_empty_policy(
    api_client, filter_dashboard, public
):
    from baserow.contrib.dashboard.formula_importer import import_formula

    _, token, dashboard, source, widget, condition = filter_dashboard
    widget.mode = "dropdown"
    widget.multiple = True
    # The configured formula explicitly selects a value, as in the Builder.
    condition["value"] = BaserowFormulaObject.create(
        f"get('widget_data.{widget.id}.0')"
    )
    widget.save()
    context = DashboardDispatchContext(
        HttpRequest(),
        dashboard=dashboard,
        data={
            "widget_data": {str(widget.id): ["Beta", "Alpha"]},
        },
    )
    assert context[f"widget_data.{widget.id}"] == ["Beta", "Alpha"]
    assert context[f"widget_data.{widget.id}.*"] == ["Beta", "Alpha"]
    assert context[f"widget_data.{widget.id}.1"] == "Alpha"
    assert (
        import_formula(condition["value"], {"dashboard_widgets": {widget.id: 123}})[
            "formula"
        ]
        == "get('widget_data.123.0')"
    )
    url = reverse(
        "api:dashboard:public:data_source_dispatch"
        if public
        else "api:dashboard:data_sources:dispatch",
        kwargs={"slug": dashboard.slug, "data_source_id": source.id}
        if public
        else {"data_source_id": source.id},
    )
    headers = {} if public else {"HTTP_AUTHORIZATION": f"JWT {token}"}
    for payload, expected in [
        ({}, "10"),
        ({"widget_data": {str(widget.id): ["Beta", "Alpha"]}}, "20"),
        ({"widget_data": {str(widget.id): []}}, "70"),
    ]:
        response = api_client.post(url, payload, format="json", **headers)
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "result": expected,
            **(
                {"_is_filtered": True}
                if payload.get("widget_data", {}).get(str(widget.id), ["Alpha"]) != []
                else {}
            ),
        }
    for value in ["Beta", [1], [None], [["Beta"]]]:
        assert (
            api_client.post(
                url, {"widget_data": {str(widget.id): value}}, format="json", **headers
            ).status_code
            == 400
        )
    widget.target_filters[0]["empty_behavior"] = "apply_alternative"
    widget.target_filters[0]["alternative_group"] = {
        "filters": [
            {**condition, "value": BaserowFormulaObject.create("Beta", mode="raw")}
        ],
        "filter_groups": [],
        "filter_type": "AND",
    }
    widget.save()
    assert api_client.post(
        url, {"widget_data": {str(widget.id): []}}, format="json", **headers
    ).json() == {"result": "20", "_is_filtered": True}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "bad",
        {"x": "value"},
        {"1": 123},
        {"1": None},
        {"999999": "value"},
        {"01": "value"},
    ],
)
def test_invalid_widget_payload(api_client, filter_dashboard, value):
    _, token, _, source, _, _ = filter_dashboard
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": source.id}
        ),
        {"widget_data": value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400, response.json()


@pytest.mark.django_db
def test_provider_rejects_foreign_deleted_and_unsupported_widgets(
    data_fixture, filter_dashboard
):
    _, _, dashboard, _, widget, _ = filter_dashboard
    context = DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    assert context[f"widget_data.{widget.id}"] == "Alpha"
    foreign = TextFilterWidget.objects.create(
        dashboard=data_fixture.create_dashboard_application()
    )
    unsupported = data_fixture.create_summary_widget(dashboard=dashboard)
    for widget_id in [foreign.id, unsupported.id, 999999]:
        with pytest.raises(InvalidFormulaContext):
            context[f"widget_data.{widget_id}"]
    TrashHandler.trash(None, dashboard.workspace, dashboard, widget)
    with pytest.raises(InvalidFormulaContext):
        DashboardDispatchContext(HttpRequest(), dashboard=dashboard)[
            f"widget_data.{widget.id}"
        ]
    for path in [[], ["abc"], [str(widget.id), "extra"]]:
        with pytest.raises(BaserowFormulaSyntaxError):
            WidgetDataProviderType().is_valid(path)


@pytest.mark.django_db
@pytest.mark.parametrize("operator", ["AND", "OR"])
def test_clearing_preserves_selected_view_filtering(
    data_fixture, filter_dashboard, operator
):
    _, _, dashboard, source, widget, _ = filter_dashboard
    service = source.service.specific
    view = data_fixture.create_grid_view(table=service.table)
    data_fixture.create_view_filter(
        view=view, field=service.field, type="higher_than", value="10"
    )
    service.view = view
    service.filter_type = operator
    service.save()
    context = DashboardDispatchContext(
        HttpRequest(), dashboard=dashboard, data={"widget_data": {str(widget.id): ""}}
    )
    assert DashboardDataSourceHandler().dispatch_data_source(source, context) == {
        "result": "60",
        "_is_filtered": True,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "behavior,expected",
    [("apply_nothing", "70"), ("apply_alternative", "20")],
)
def test_empty_policy_and_constant_dependencies(filter_dashboard, behavior, expected):
    _, _, dashboard, source, widget, condition = filter_dashboard
    link = widget.target_filters[0]
    link["empty_behavior"] = behavior
    link["group"]["filters"][0]["value"] = BaserowFormulaObject.create(
        "Alpha", mode="raw"
    )
    link["alternative_group"] = {
        "filter_type": "OR",
        "filter_groups": [],
        "filters": [
            {**condition, "value": BaserowFormulaObject.create("Beta", mode="raw")}
        ],
    }
    widget.save()
    assert DashboardDataSourceHandler().dispatch_data_source(
        source,
        DashboardDispatchContext(
            HttpRequest(),
            dashboard=dashboard,
            data={"widget_data": {str(widget.id): ""}},
        ),
    ) == {
        "result": expected,
        **({"_is_filtered": True} if behavior == "apply_alternative" else {}),
    }
    link["group"]["filters"][0]["value"] = BaserowFormulaObject.create(
        "Alpha", mode="raw"
    )
    widget.save()


@pytest.mark.django_db
@pytest.mark.parametrize("operator,expected", [("AND", None), ("OR", "30")])
def test_permanent_and_contributed_groups(
    data_fixture, filter_dashboard, operator, expected
):
    """The source operator combines permanent and contributed groups."""

    _, _, dashboard, source, widget, condition = filter_dashboard
    service = source.service.specific
    service.filter_type = operator
    service.save()

    data_fixture.create_local_baserow_table_service_filter(
        service=source.service.specific,
        field_id=condition["field"],
        type="equal",
        value=BaserowFormulaObject.create("Beta", mode="raw"),
    )
    assert DashboardDataSourceHandler().dispatch_data_source(
        source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    ) == {"result": expected, "_is_filtered": True}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid",
    ["foreign", "duplicate", "field", "cycle", "empty_behavior", "enabled"],
)
def test_invalid_target_configuration(data_fixture, filter_dashboard, invalid):
    from rest_framework.exceptions import ValidationError

    _, _, dashboard, source, widget, condition = filter_dashboard
    link = widget.target_filters[0]
    if invalid == "enabled":
        link["enabled"] = "false"
    elif invalid == "empty_behavior":
        link["empty_behavior"] = "apply_group"
    elif invalid == "foreign":
        link["target_widget_id"] = data_fixture.create_summary_widget().id
    elif invalid == "duplicate":
        widget.target_filters.append(link)
    elif invalid == "field":
        condition["field"] = data_fixture.create_text_field().id
    else:
        link["group"]["filter_groups"] = [
            {"id": "a", "parent_group": "a", "filter_type": "AND"}
        ]
    with pytest.raises(ValidationError):
        widget.get_type().prepare_value_for_db(
            {"target_filters": widget.target_filters}, instance=widget
        )


@pytest.mark.django_db
@pytest.mark.parametrize("deferred", [False, True])
@pytest.mark.parametrize("enabled", [True, False])
def test_target_import(filter_dashboard, deferred, enabled, monkeypatch):
    _, _, dashboard, source, widget, _ = filter_dashboard
    widget.target_filters[0]["enabled"] = enabled
    widget.save()
    app_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True)
    mapping = {}
    from baserow.contrib.dashboard.widgets.registries import widget_type_registry

    finalized = []
    target = SummaryWidget.objects.get(data_source=source)

    summary_type = widget_type_registry.get("summary")
    original_widget_after_import = summary_type.after_import

    def finalize_summary(instance, id_mapping, **kwargs):
        assert kwargs["import_export_config"] is config
        assert widget.id in id_mapping["dashboard_widgets"]
        assert target.id in id_mapping["dashboard_widgets"]
        assert TextFilterWidget.objects.filter(dashboard=instance.dashboard).exists()
        finalized.append(instance.id)
        return original_widget_after_import(instance, id_mapping, **kwargs)

    monkeypatch.setattr(summary_type, "after_import", finalize_summary)

    source_type = source.service.specific.get_type()
    original_after_import = source_type.after_import
    finalized_sources = []

    def finalize_source(instance, id_mapping, **kwargs):
        assert widget.id in id_mapping["dashboard_widgets"]
        assert target.id in id_mapping["dashboard_widgets"]
        assert kwargs["import_export_config"] is config
        finalized_sources.append(instance.id)
        updated_models = original_after_import(instance, id_mapping, **kwargs)
        instance.sample_data = {"finalized": True}
        updated_models.add(instance)
        return updated_models

    monkeypatch.setattr(source_type, "after_import", finalize_source)
    with deferred_callback_context() if deferred else nullcontext():
        copied = app_type.import_serialized(
            dashboard.workspace,
            app_type.export_serialized(dashboard, config),
            config,
            mapping,
        )
        if deferred:
            assert finalized == []
            assert finalized_sources == []
            assert (
                TextFilterWidget.objects.get(dashboard=copied).target_filters
                == widget.target_filters
            )
    copied_widget = TextFilterWidget.objects.get(dashboard=copied)
    copied_target = SummaryWidget.objects.get(dashboard=copied)
    assert finalized == [copied_target.id]
    assert finalized_sources == [copied_target.data_source.service_id]
    assert copied_target.data_source.service.sample_data == {"finalized": True}
    assert copied_widget.target_filters[0]["target_widget_id"] == copied_target.id
    assert copied_widget.target_filters[0]["enabled"] is enabled
    assert (
        str(copied_widget.id)
        in copied_widget.target_filters[0]["group"]["filters"][0]["value"]["formula"]
    )


@pytest.mark.django_db
@pytest.mark.parametrize("enabled", [True, False])
def test_public_configuration_privacy(api_client, filter_dashboard, enabled):
    _, _, dashboard, source, widget, _ = filter_dashboard
    widget.target_filters[0]["enabled"] = enabled
    widget.save()
    response = api_client.get(
        reverse("api:dashboard:public:info", kwargs={"slug": dashboard.slug})
    )
    assert response.status_code == 200
    assert "widget_dependencies" not in response.json()["data_sources"][0]
    public_input = next(
        item for item in response.json()["widgets"] if item["id"] == widget.id
    )
    assert public_input["target_widget_ids"] == (
        [widget.target_filters[0]["target_widget_id"]] if enabled else []
    )
    assert "filters" not in response.json()["data_sources"][0]
    for item in response.json()["widgets"]:
        assert "target_filters" not in item


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_target_delete_undo_redo(filter_dashboard):
    from baserow.contrib.dashboard.widgets.actions import DeleteWidgetActionType
    from baserow.core.action.handler import ActionHandler
    from baserow.core.action.scopes import ApplicationActionScopeType

    user, _, dashboard, source, widget, _ = filter_dashboard
    user.web_socket_id = "test"
    from baserow.api.sessions import set_untrusted_client_session_id

    set_untrusted_client_session_id(user, "target-links")
    target = SummaryWidget.objects.get(data_source=source)
    original = widget.target_filters
    DeleteWidgetActionType.do(user, target.id)
    widget.refresh_from_db()
    assert widget.target_filters == []
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    actions = ActionHandler.undo(user, scopes, "target-links")
    assert actions and not actions[0].error
    widget.refresh_from_db()
    assert widget.target_filters == original
    actions = ActionHandler.redo(user, scopes, "target-links")
    assert actions and not actions[0].error
    widget.refresh_from_db()
    assert widget.target_filters == []


@pytest.mark.django_db
def test_nested_contribution_and_source_change(data_fixture, filter_dashboard):
    from rest_framework.exceptions import ValidationError

    _, _, dashboard, source, widget, condition = filter_dashboard
    group = widget.target_filters[0]["group"]
    group["filter_groups"] = [
        {"id": "parent", "parent_group": None, "filter_type": "OR"},
        {"id": "child", "parent_group": "parent", "filter_type": "AND"},
    ]
    condition["group"] = "child"
    group["filters"].append(
        {
            **condition,
            "group": "parent",
            "value": BaserowFormulaObject.create("Beta", mode="raw"),
        }
    )
    widget.save()
    assert DashboardDataSourceHandler().dispatch_data_source(
        source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    ) == {"result": "30", "_is_filtered": True}
    service = source.service.specific
    service.table = data_fixture.create_database_table(database=service.table.database)
    service.field = data_fixture.create_number_field(table=service.table)
    service.save()
    with pytest.raises(ValidationError):
        DashboardDataSourceHandler().dispatch_data_source(
            source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
        )
    widget.refresh_from_db()
    assert widget.target_filters[0]["group"]["filters"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,status",
    [
        ("get('widget_data.999')", 200),
        ("concat(get('widget_data.999'), get('widget_data.123'))", 200),
        ("concat(", 400),
    ],
)
def test_filter_formula_validation_is_not_restricted_to_owner(
    api_client, filter_dashboard, formula, status
):
    """Accept cross-widget references while retaining normal formula validation."""
    _, token, _, _, widget, condition = filter_dashboard
    original = condition["value"]["formula"]
    condition["value"] = BaserowFormulaObject.create(formula)
    response = api_client.patch(
        reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id}),
        {"target_filters": widget.target_filters},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == status, response.json()
    widget.refresh_from_db()
    assert widget.target_filters[0]["group"]["filters"][0]["value"]["formula"] == (
        formula if status == 200 else original
    )


@pytest.mark.django_db
def test_whitespace_activates_constant_only_group(filter_dashboard):
    _, _, dashboard, source, widget, condition = filter_dashboard
    condition["value"] = BaserowFormulaObject.create("Beta", mode="raw")
    widget.save()
    for value, expected in [("", "70"), (" ", "20")]:
        assert DashboardDataSourceHandler().dispatch_data_source(
            source,
            DashboardDispatchContext(
                HttpRequest(),
                dashboard=dashboard,
                data={"widget_data": {str(widget.id): value}},
            ),
        ) == {"result": expected, **({"_is_filtered": True} if value != "" else {})}


@pytest.mark.django_db
def test_import_remaps_contributed_fields_and_results(data_fixture, filter_dashboard):
    from copy import deepcopy

    user, _, dashboard, source, widget, condition = filter_dashboard
    original = source.service.specific
    table = data_fixture.create_database_table(database=original.table.database)
    name = data_fixture.create_text_field(table=table)
    amount = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        [
            {name.db_column: "Alpha", amount.db_column: 100},
            {name.db_column: "Beta", amount.db_column: 200},
        ],
    )
    widget.target_filters[0]["empty_behavior"] = "apply_alternative"
    widget.target_filters[0]["alternative_group"] = deepcopy(
        widget.target_filters[0]["group"]
    )
    widget.target_filters[0]["alternative_group"]["filters"][0]["value"] = (
        BaserowFormulaObject.create("Beta", mode="raw")
    )
    widget.save()
    mapping = {
        "database_tables": {original.table_id: table.id},
        "database_fields": {condition["field"]: name.id, original.field_id: amount.id},
    }
    app_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True)
    copied = app_type.import_serialized(
        dashboard.workspace,
        app_type.export_serialized(dashboard, config),
        config,
        mapping,
    )
    copied_widget = TextFilterWidget.objects.get(dashboard=copied)
    target = SummaryWidget.objects.get(dashboard=copied)
    integration = target.data_source.service.integration.specific
    integration.authorized_subject_type = "auth.User"
    integration.authorized_subject_id = user.id
    integration.save()
    for key in ("group", "alternative_group"):
        assert copied_widget.target_filters[0][key]["filters"][0]["field"] == name.id
    for value, expected in [("Alpha", "100"), ("", "200")]:
        assert DashboardDataSourceHandler().dispatch_data_source(
            target.data_source,
            DashboardDispatchContext(
                HttpRequest(),
                dashboard=copied,
                data={"widget_data": {str(copied_widget.id): value}},
            ),
        ) == {"result": expected, "_is_filtered": True}


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("disable", [False, True])
def test_contribution_update_undo_redo(filter_dashboard, disable):
    from baserow.api.sessions import set_untrusted_client_session_id
    from baserow.contrib.dashboard.widgets.actions import UpdateWidgetActionType
    from baserow.core.action.handler import ActionHandler
    from baserow.core.action.scopes import ApplicationActionScopeType

    user, _, dashboard, source, widget, condition = filter_dashboard
    set_untrusted_client_session_id(user, "contribution-update")
    if disable:
        widget.target_filters[0]["enabled"] = False
    else:
        condition["value"] = BaserowFormulaObject.create("Beta", mode="raw")
    UpdateWidgetActionType.do(
        user, widget.id, "text_filter", {"target_filters": widget.target_filters}
    )
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    for operation, expected in [
        (None, "70" if disable else "20"),
        (ActionHandler.undo, "10"),
        (ActionHandler.redo, "70" if disable else "20"),
    ]:
        if operation:
            actions = operation(user, scopes, "contribution-update")
            assert actions and not actions[0].error
        assert DashboardDataSourceHandler().dispatch_data_source(
            source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
        ) == {
            "result": expected,
            **({"_is_filtered": True} if expected != "70" else {}),
        }


@pytest.mark.django_db
def test_filter_capabilities_control_dispatch_and_dependencies(
    filter_dashboard, monkeypatch
):
    """A registered filter's capabilities, value resolver and groups drive execution."""
    from baserow.contrib.dashboard.api.data_sources.serializers import (
        DashboardDispatchSerializer,
    )
    from baserow.contrib.dashboard.widgets.mixins import FilterWidgetTypeMixin
    from baserow.contrib.dashboard.widgets.registries import (
        WidgetType,
        widget_type_registry,
    )

    _, _, dashboard, source, widget, condition = filter_dashboard
    original_lookup = widget_type_registry.get_by_model

    class FutureFilterWidgetType(FilterWidgetTypeMixin, WidgetType):
        type = "future_filter"
        model_class = TextFilterWidget

        def get_filter_value(self, instance, values):
            return values.get(str(instance.id), "Beta")

        def validate_filter_value(self, instance, value):
            return value

        def get_target_filters(self, instance):
            # Exercise the accessor instead of relying on the stored link list.
            return widget.target_filters

    future_type = FutureFilterWidgetType()
    monkeypatch.setattr(
        widget_type_registry,
        "get_by_model",
        lambda model: (
            future_type
            if model is TextFilterWidget or isinstance(model, TextFilterWidget)
            else original_lookup(model)
        ),
    )
    widget.target_filters[0]["group"]["filters"][0]["value"] = (
        BaserowFormulaObject.create(f"get('widget_data.{widget.id}')")
    )
    TextFilterWidget.objects.filter(id=widget.id).update(target_filters=[])

    context = DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    assert DashboardDataSourceHandler().dispatch_data_source(source, context) == {
        "result": "20",
        "_is_filtered": True,
    }
    serializer = DashboardDispatchSerializer(
        data={"widget_data": {str(widget.id): "Alpha"}},
        context={"dashboard": dashboard},
    )
    assert serializer.is_valid(), serializer.errors

    monkeypatch.setattr(future_type, "is_filter_widget", False)
    assert DashboardDataSourceHandler().dispatch_data_source(
        source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    ) == {"result": "70"}
    serializer = DashboardDispatchSerializer(
        data={"widget_data": {str(widget.id): "Alpha"}},
        context={"dashboard": dashboard},
    )
    assert not serializer.is_valid()

    monkeypatch.setattr(future_type, "is_filter_widget", True)
    display_type = original_lookup(SummaryWidget)
    monkeypatch.setattr(display_type, "is_display_widget", False)
    assert DashboardDataSourceHandler().dispatch_data_source(
        source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    ) == {"result": "70"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,second_value,expected",
    [("OR", "Beta", "20"), ("OR", "", "30"), ("AND", "Beta", None)],
)
def test_multiple_filters_own_independent_group_operators(
    filter_dashboard, data_fixture, operator, second_value, expected
):
    """Two inputs intersect their groups while preserving each group's operator."""
    _, _, dashboard, source, first, condition = filter_dashboard
    group = first.target_filters[0]["group"]
    group["filter_type"] = operator
    group["filters"] = [
        {**condition, "value": BaserowFormulaObject.create(value, mode="raw")}
        for value in ["Alpha", "Beta"]
    ]
    first.save()
    second = TextFilterWidget.objects.create(
        dashboard=dashboard, title="Second filter", grid_width=2, grid_height=4
    )
    second.target_filters = [
        {
            "target_widget_id": first.target_filters[0]["target_widget_id"],
            "group": {
                "filter_type": "AND",
                "filter_groups": [],
                "filters": [
                    {
                        **condition,
                        "value": BaserowFormulaObject.create(
                            f"get('widget_data.{second.id}')"
                        ),
                    }
                ],
            },
            "empty_behavior": "apply_nothing",
        }
    ]
    second.save()
    data_fixture.create_local_baserow_table_service_filter(
        service=source.service.specific,
        field_id=condition["field"],
        type="not_equal",
        value=BaserowFormulaObject.create(" ", mode="raw"),
    )
    assert DashboardDataSourceHandler().dispatch_data_source(
        source,
        DashboardDispatchContext(
            HttpRequest(),
            dashboard=dashboard,
            data={
                "widget_data": {str(first.id): "active", str(second.id): second_value}
            },
        ),
    ) == {"result": expected, "_is_filtered": True}


@pytest.mark.django_db
@pytest.mark.parametrize("operator,both", [("AND", None), ("OR", "30")])
def test_source_operator_combines_multiple_inputs(filter_dashboard, operator, both):
    """Use the source operator across owners, omitting inactive groups entirely."""
    _, _, dashboard, source, first, condition = filter_dashboard
    service = source.service.specific
    service.filter_type = operator
    service.save()
    second = TextFilterWidget.objects.create(
        dashboard=dashboard, title="Second", grid_width=2, grid_height=4
    )
    second.target_filters = [
        {
            "target_widget_id": first.target_filters[0]["target_widget_id"],
            "empty_behavior": "apply_nothing",
            "group": {
                "filter_type": "AND",
                "filter_groups": [],
                "filters": [
                    {
                        **condition,
                        "value": BaserowFormulaObject.create(
                            f"get('widget_data.{second.id}')"
                        ),
                    }
                ],
            },
        }
    ]
    second.save()
    for a, b, expected in [
        ("Alpha", "Beta", both),
        ("Alpha", "", "10"),
        ("", "Beta", "20"),
        ("", "", "70"),
    ]:
        assert DashboardDataSourceHandler().dispatch_data_source(
            source,
            DashboardDispatchContext(
                HttpRequest(),
                dashboard=dashboard,
                data={"widget_data": {str(first.id): a, str(second.id): b}},
            ),
        ) == {"result": expected, **({"_is_filtered": True} if bool(a or b) else {})}


@pytest.mark.django_db
def test_import_finalizes_shared_widget_source_once(filter_dashboard, monkeypatch):
    """Two display widgets sharing a source must not remap its formulas twice."""
    _, _, dashboard, source, owner, _ = filter_dashboard
    shared = SummaryWidget.objects.create(
        dashboard=dashboard,
        data_source=source,
        title="Shared source",
        grid_width=2,
        grid_height=4,
    )
    source_type = source.service.specific.get_type()
    original_after_import = source_type.after_import
    finalized = []

    def finalize_source(instance, id_mapping, **kwargs):
        assert owner.id in id_mapping["dashboard_widgets"]
        assert shared.id in id_mapping["dashboard_widgets"]
        finalized.append(instance.id)
        return original_after_import(instance, id_mapping, **kwargs)

    monkeypatch.setattr(source_type, "after_import", finalize_source)
    app_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True)
    mapping = {}
    copied = app_type.import_serialized(
        dashboard.workspace,
        app_type.export_serialized(dashboard, config),
        config,
        mapping,
    )
    copied_sources = {
        widget.data_source_id
        for widget in SummaryWidget.objects.filter(dashboard=copied)
    }
    assert len(copied_sources) == 1
    assert finalized == [
        SummaryWidget.objects.filter(dashboard=copied).first().data_source.service_id
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("operator,expected", [("AND", None), ("OR", "30")])
def test_runtime_filter_is_complete_and_namespaces_nested_group_ids(
    data_fixture, filter_dashboard, operator, expected
):
    """Default and input groups form one tree even when their local IDs collide."""
    _, _, dashboard, source, owner, condition = filter_dashboard
    service = source.service.specific
    service.filter_type = operator
    service.save()
    permanent = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="AND"
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        group=permanent,
        field_id=condition["field"],
        type="equal",
        value=BaserowFormulaObject.create("Beta", mode="raw"),
    )
    group = owner.target_filters[0]["group"]
    group["filter_groups"] = [
        {"id": str(permanent.id), "parent_group": None, "filter_type": "OR"},
        {"id": "child", "parent_group": str(permanent.id), "filter_type": "AND"},
    ]
    condition["group"] = "child"
    owner.save()
    context = DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    runtime_filter = context.get_runtime_filter(service)
    assert runtime_filter["filter_type"] == operator
    assert len(runtime_filter["filters"]) == 2
    groups = runtime_filter["filter_groups"]
    assert len({group["id"] for group in groups}) == len(groups) == 5
    known = {group["id"] for group in groups}
    assert all(
        group["parent_group"] is None or group["parent_group"] in known
        for group in groups
    )
    assert len({condition["group"] for condition in runtime_filter["filters"]}) == 2
    assert DashboardDataSourceHandler().dispatch_data_source(source, context) == {
        "result": expected,
        "_is_filtered": True,
    }


@pytest.fixture
def context_options(data_fixture, filter_dashboard):
    """Configured options exist without any row using them."""
    _, _, _, source, widget, _ = filter_dashboard
    field = data_fixture.create_single_select_field(table=source.service.specific.table)
    data_fixture.create_select_option(field=field, value="Europe", color="blue")
    data_fixture.create_select_option(field=field, value="Americas", color="red")
    source.service = data_fixture.create_local_baserow_list_rows_service(
        table=source.service.specific.table,
        integration=source.service.specific.integration,
    )
    source.save()
    widget.mode = "dropdown"
    widget.options = BaserowFormulaObject.create(
        f"get('data_source_context.{source.id}.field_{field.id}.*.value')"
    )
    widget.save()
    return field


@pytest.mark.django_db
def test_public_options_formula_and_referenced_context(
    api_client, filter_dashboard, context_options, data_fixture
):
    """Public dropdowns receive their saved formula and the permitted option context."""
    _, _, dashboard, source, widget, _ = filter_dashboard
    extra = data_fixture.create_single_select_field(table=source.service.specific.table)
    data_fixture.create_select_option(field=extra, value="Not referenced", color="blue")
    response = api_client.get(
        reverse("api:dashboard:public:info", kwargs={"slug": dashboard.slug})
    )
    assert response.status_code == 200
    payload = response.json()
    public_widget = next(w for w in payload["widgets"] if w["id"] == widget.id)
    assert public_widget["options"] == widget.options
    context = next(s for s in payload["data_sources"] if s["id"] == source.id)[
        "context_data"
    ]
    assert [option["value"] for option in context[f"field_{context_options.id}"]] == [
        "Europe",
        "Americas",
    ]
    assert f"field_{extra.id}" not in context


@pytest.mark.django_db
def test_option_context_formula_scope_and_import(
    api_client, filter_dashboard, context_options
):
    from baserow.contrib.dashboard.data_providers import (
        dashboard_options_data_provider_registry,
    )
    from baserow.contrib.dashboard.formula_importer import import_formula

    _, token, _, source, widget, _ = filter_dashboard
    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    assert (
        api_client.patch(
            url, {"options": widget.options}, format="json", **headers
        ).status_code
        == 200
    )
    for path in [
        "table.1.*.field_1",
        "widget_data.1",
        "data_source_context.invalid.field_1",
    ]:
        assert (
            api_client.patch(
                url,
                {"options": BaserowFormulaObject.create(f"get('{path}')")},
                format="json",
                **headers,
            ).status_code
            == 400
        )
    result = import_formula(
        widget.options,
        {
            "dashboard_data_sources": {source.id: source.id},
            "database_fields": {context_options.id: 5678},
        },
        data_provider_type_registry=dashboard_options_data_provider_registry,
    )
    assert (
        result["formula"]
        == f"get('data_source_context.{source.id}.field_5678.*.value')"
    )


@pytest.mark.django_db
def test_filter_status_tracks_source_conditions_and_empty_groups(
    data_fixture, filter_dashboard
):
    _, _, dashboard, source, widget, condition = filter_dashboard
    widget.target_filters[0]["group"]["filters"] = []
    widget.save()
    context = DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    handler = DashboardDataSourceHandler()
    assert handler.dispatch_data_source(source, context) == {"result": "70"}
    stored_filter = data_fixture.create_local_baserow_table_service_filter(
        service=source.service.specific,
        field_id=condition["field"],
        type="equal",
        value=BaserowFormulaObject.create("Beta", mode="raw"),
    )
    context = DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    assert handler.dispatch_data_source(source, context) == {
        "result": "20",
        "_is_filtered": True,
    }
    stored_filter.delete()
    context = DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    assert handler.dispatch_data_source(source, context) == {"result": "70"}


def test_context_provider_collects_nested_references_without_evaluating():
    from baserow.contrib.dashboard.data_providers import (
        DashboardDataSourceContextDataProviderType,
    )

    provider = DashboardDataSourceContextDataProviderType()
    assert provider.get_referenced_fields(
        [
            BaserowFormulaObject.create(
                "concat(get('data_source_context.13.field_886.*.value'), "
                "get('data_source_context.13.field_887.*.value'))"
            ),
            BaserowFormulaObject.create(
                "get('data_source_context.14.field_888.*.value')", mode="raw"
            ),
        ]
    ) == {13: {"field_886", "field_887"}}
