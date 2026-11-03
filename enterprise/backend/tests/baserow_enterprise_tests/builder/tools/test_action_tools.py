"""
The shared action tools store the formulas they are given and report the rest,
without a model. The conftest of this folder fails any model call.
"""

import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.sessions import (
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)
from baserow.contrib.automation.tools.formulas import wrap_static_string
from baserow.contrib.builder.action_scopes import PageActionScopeType
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    NotificationWorkflowAction,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.services.models import Service
from baserow.core.tools.errors import ToolInputError
from baserow_enterprise.builder.tools import BuilderWriteOptions, actions
from baserow_enterprise.builder.tools.types import ActionChanges, ActionCreate


def notification(element, title="Hi", **kwargs):
    return ActionCreate(type="notification", element=element, title=title, **kwargs)


def row_action(builder_ctx, element, row_id="'1'", type="update_row", **kwargs):
    table = builder_ctx["data_source"].service.specific.table
    if type == "update_row":
        kwargs.setdefault(
            "field_values",
            [{"field_id": str(table.field_set.first().id), "value": "'x'"}],
        )
    return ActionCreate(
        type=type, element=element, table_id=table.id, row_id=row_id, **kwargs
    )


def create(builder_ctx, *items):
    return actions.create_actions(
        builder_ctx["ctx"], builder_ctx["page"].id, list(items)
    )


def saved(result, index=0):
    return BuilderWorkflowAction.objects.get(
        id=result["created_actions"][index]["id"]
    ).specific


@pytest.fixture
def table_with_button(data_fixture, builder_ctx):
    return data_fixture.create_builder_table_element(
        page=builder_ctx["page"],
        data_source=builder_ctx["data_source"],
        fields=[
            {"name": "View", "type": "button", "config": {"label": "'View'"}},
        ],
    )


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_description_on_a_notification_is_left_empty_and_listed(builder_ctx):
    result = create(
        builder_ctx,
        notification(builder_ctx["button"].id, title="$formula: the product name"),
    )

    action = saved(result)
    assert action.title["formula"] == "''"
    entry = result["formula_errors"][0]
    assert entry["action_id"] == action.id
    assert entry["field"] == "title"
    assert entry["formula"] == "the product name"
    assert "needs a formula" in entry["error"]
    assert "errors" not in result


@pytest.mark.django_db
def test_a_valid_formula_is_stored_in_advanced_mode(builder_ctx):
    data_source_id = builder_ctx["data_source"].id

    result = create(
        builder_ctx,
        notification(
            builder_ctx["button"].id,
            title=f"get('data_source.{data_source_id}.0.id')",
            description="Fixed",
        ),
    )

    action = saved(result)
    assert action.title == {
        "formula": f"get('data_source.{data_source_id}.0.id')",
        "mode": BASEROW_FORMULA_MODE_ADVANCED,
        "version": "0.1",
    }
    assert action.description["formula"] == "'Fixed'"
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_an_action_can_read_what_an_earlier_action_returned(builder_ctx):
    result = create(
        builder_ctx,
        notification(builder_ctx["button"].id, title="get('previous_action.1.id')"),
    )

    assert "formula_errors" not in result
    assert saved(result).title["formula"] == "get('previous_action.1.id')"


@pytest.mark.django_db
def test_a_field_value_description_names_the_field(builder_ctx):
    table = builder_ctx["data_source"].service.specific.table
    field = table.field_set.first()

    result = create(
        builder_ctx,
        ActionCreate(
            type="create_row",
            element=builder_ctx["button"].id,
            table_id=table.id,
            field_values=[{"field_id": str(field.id), "value": "$formula: the name"}],
        ),
    )

    assert result["formula_errors"][0]["field"] == f"field_{field.id}"
    mapping = saved(result).service.specific.field_mappings.get()
    assert mapping.value["formula"] == "''"


@pytest.mark.django_db
def test_page_parameters_keep_their_position_in_the_report(builder_ctx):
    detail = builder_ctx["page"].builder.page_set.exclude(shared=True).last()

    result = create(
        builder_ctx,
        ActionCreate(
            type="open_page",
            element=builder_ctx["button"].id,
            navigate_to_page_id=detail.id,
            page_parameters=[
                {"name": "a", "value": "fixed"},
                {"name": "b", "value": "$formula: the id"},
            ],
        ),
    )

    assert [e["field"] for e in result["formula_errors"]] == ["page_param_1"]
    assert [p["value"]["formula"] for p in saved(result).page_parameters] == [
        "'fixed'",
        "''",
    ]


# ---------------------------------------------------------------------------
# row_id, which a row action can't run without
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("type", ["update_row", "delete_row"])
@pytest.mark.parametrize(
    "row_id",
    ["$formula: the id from the page", "the id from the page", "get('nope.id')"],
)
def test_a_row_id_that_is_not_a_formula_fails_the_item(builder_ctx, type, row_id):
    services = Service.objects.count()
    actions_before = BuilderWorkflowAction.objects.count()

    result = create(
        builder_ctx, row_action(builder_ctx, builder_ctx["button"].id, row_id, type)
    )

    assert result["created_actions"] == []
    assert result["errors"][0].startswith(f"{type} on {builder_ctx['button'].id}: ")
    assert "wasn't created" in result["errors"][0]
    assert BuilderWorkflowAction.objects.count() == actions_before
    assert Service.objects.count() == services


@pytest.mark.django_db
def test_a_valid_row_id_is_stored(builder_ctx):
    result = create(
        builder_ctx,
        row_action(builder_ctx, builder_ctx["button"].id, "5"),
        row_action(
            builder_ctx, builder_ctx["button"].id, "get('previous_action.1.id')"
        ),
    )

    assert "errors" not in result
    assert saved(result, 0).service.specific.row_id["formula"] == "5"
    assert (
        saved(result, 1).service.specific.row_id["formula"]
        == "get('previous_action.1.id')"
    )


@pytest.mark.django_db
def test_a_table_button_can_read_the_row_it_is_on(builder_ctx, table_with_button):
    result = create(
        builder_ctx,
        row_action(
            builder_ctx,
            table_with_button.id,
            "get('current_record.id')",
            type="delete_row",
            event="View_click",
        ),
    )

    assert "errors" not in result
    action = saved(result)
    assert action.service.specific.row_id["formula"] == "get('current_record.id')"
    assert action.event.endswith("_click")


@pytest.mark.django_db
def test_a_plain_button_can_not_read_a_row(builder_ctx):
    result = create(
        builder_ctx,
        row_action(
            builder_ctx,
            builder_ctx["button"].id,
            "get('current_record.id')",
            type="delete_row",
        ),
    )

    assert result["created_actions"] == []
    assert "inside a repeat or a table" in result["errors"][0]


@pytest.mark.django_db
def test_an_action_on_the_shared_page_can_not_read_what_one_page_has(
    data_fixture, builder_ctx
):
    builder_ctx["page"].path_params = [{"name": "id", "type": "text"}]
    builder_ctx["page"].path = "/home/:id"
    builder_ctx["page"].save()
    button = data_fixture.create_builder_button_element(
        page=builder_ctx["builder"].shared_page
    )

    result = create(
        builder_ctx,
        row_action(builder_ctx, button.id, "get('page_parameter.id')"),
        row_action(builder_ctx, builder_ctx["button"].id, "get('page_parameter.id')"),
    )

    assert len(result["created_actions"]) == 1
    assert result["created_actions"][0]["element"] == builder_ctx["button"].id
    assert "page parameter" in result["errors"][0]


@pytest.mark.django_db
def test_an_action_on_the_shared_page_stays_with_its_element(data_fixture, builder_ctx):
    shared_page = builder_ctx["builder"].shared_page
    button = data_fixture.create_builder_button_element(page=shared_page)

    result = create(builder_ctx, notification(button.id))

    assert saved(result).page_id == shared_page.id
    listed = actions.list_actions(builder_ctx["ctx"], builder_ctx["page"].id)
    assert saved(result).id in [a["id"] for a in listed["workflow_actions"]]


@pytest.mark.django_db
def test_a_deferred_row_id_is_created_and_reported(builder_ctx):
    result = actions.create_actions_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [row_action(builder_ctx, builder_ctx["button"].id, "$formula: the id")],
        BuilderWriteOptions(defer_required_formulas=True),
    )

    assert "errors" not in result
    assert result["formula_errors"][0]["field"] == "row_id"
    assert result["formula_errors"][0]["formula"] == "the id"


# ---------------------------------------------------------------------------
# Batches and refs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_one_bad_action_keeps_the_rest(builder_ctx):
    button_id = builder_ctx["button"].id

    result = create(
        builder_ctx,
        notification(button_id, title="First"),
        notification(button_id, title="Bad", event="nope"),
        notification(button_id, title="Last"),
    )

    assert [a["type"] for a in result["created_actions"]] == [
        "notification",
        "notification",
    ]
    assert len(result["errors"]) == 1
    assert result["errors"][0].startswith(f"notification on {button_id}: ")
    titles = {
        action.title["formula"]
        for action in NotificationWorkflowAction.objects.filter(
            element_id=button_id
        ).exclude(id=builder_ctx["action"].id)
    }
    assert titles == {"'First'", "'Last'"}


@pytest.mark.django_db
def test_an_element_ref_from_another_call_names_the_rule(builder_ctx):
    result = create(builder_ctx, notification("button"))

    assert result["errors"] == [
        "notification on button: Unknown ref 'button'. Refs only work inside one "
        "call; use the element ID."
    ]


@pytest.mark.django_db
def test_a_data_source_ref_from_another_call_names_the_rule(builder_ctx):
    result = create(
        builder_ctx,
        ActionCreate(
            type="refresh_data_source",
            element=builder_ctx["button"].id,
            data_source="products",
        ),
    )

    assert result["created_actions"] == []
    assert "Unknown data source ref 'products'" in result["errors"][0]


@pytest.mark.django_db
def test_a_data_source_id_sent_as_text_is_used(builder_ctx):
    result = create(
        builder_ctx,
        ActionCreate(
            type="refresh_data_source",
            element=builder_ctx["button"].id,
            data_source=str(builder_ctx["data_source"].id),
        ),
    )

    assert saved(result).data_source_id == builder_ctx["data_source"].id


@pytest.mark.django_db
def test_a_field_id_that_is_not_a_number_fails_the_item(builder_ctx):
    table = builder_ctx["data_source"].service.specific.table

    result = create(
        builder_ctx,
        ActionCreate(
            type="create_row",
            element=builder_ctx["button"].id,
            table_id=table.id,
            field_values=[{"field_id": "name", "value": "'x'"}],
        ),
    )

    assert result["created_actions"] == []
    assert "Field name is not in the table" in result["errors"][0]


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------


@pytest.fixture
def elsewhere(data_fixture, builder_ctx):
    """A page of the same builder, a sibling builder and another workspace."""

    user = builder_ctx["user"]
    sibling = data_fixture.create_builder_application(
        workspace=builder_ctx["workspace"]
    )
    other_workspace = data_fixture.create_workspace(user=user)
    foreign = data_fixture.create_builder_application(workspace=other_workspace)
    return {
        "same_builder": data_fixture.create_builder_page(
            builder=builder_ctx["builder"], name="Other"
        ),
        "sibling": data_fixture.create_builder_page(builder=sibling),
        "foreign": data_fixture.create_builder_page(builder=foreign),
        "foreign_table": data_fixture.create_database_table(
            database=data_fixture.create_database_application(workspace=other_workspace)
        ),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("where", ["same_builder", "sibling", "foreign"])
def test_an_element_of_another_page_is_refused(
    data_fixture, builder_ctx, elsewhere, where
):
    button = data_fixture.create_builder_button_element(page=elsewhere[where])

    result = create(builder_ctx, notification(button.id))

    assert result["created_actions"] == []
    assert "not found on this page" in result["errors"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("where", ["sibling", "foreign"])
def test_open_page_to_another_application_is_refused(builder_ctx, elsewhere, where):
    result = create(
        builder_ctx,
        ActionCreate(
            type="open_page",
            element=builder_ctx["button"].id,
            navigate_to_page_id=elsewhere[where].id,
        ),
    )

    assert result["created_actions"] == []
    assert f"page with id {elsewhere[where].id} doesn't exist" in result["errors"][0]


@pytest.mark.django_db
def test_a_table_of_another_workspace_is_refused(builder_ctx, elsewhere):
    result = create(
        builder_ctx,
        ActionCreate(
            type="delete_row",
            element=builder_ctx["button"].id,
            table_id=elsewhere["foreign_table"].id,
            row_id="1",
        ),
    )

    assert result["created_actions"] == []
    assert "not found" in result["errors"][0]


@pytest.mark.django_db
def test_a_field_of_another_table_is_refused(data_fixture, builder_ctx, elsewhere):
    field = data_fixture.create_text_field(table=elsewhere["foreign_table"])
    table = builder_ctx["data_source"].service.specific.table

    result = create(
        builder_ctx,
        ActionCreate(
            type="create_row",
            element=builder_ctx["button"].id,
            table_id=table.id,
            field_values=[{"field_id": str(field.id), "value": "'x'"}],
        ),
    )

    assert result["created_actions"] == []
    assert f"Field {field.id} is not in the table" in result["errors"][0]


# ---------------------------------------------------------------------------
# add_action_field_mapping
# ---------------------------------------------------------------------------


@pytest.fixture
def row_action_with_mapping(builder_ctx):
    table = builder_ctx["data_source"].service.specific.table
    field = table.field_set.first()
    result = create(
        builder_ctx,
        ActionCreate(
            type="create_row",
            element=builder_ctx["button"].id,
            table_id=table.id,
            field_values=[{"field_id": str(field.id), "value": "'x'"}],
        ),
    )
    return saved(result), table, field


@pytest.mark.django_db
def test_add_action_field_mapping_returns_the_action(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, table, field = row_action_with_mapping
    new_field = data_fixture.create_text_field(table=table, name="Other")

    result = actions.add_action_field_mapping(
        builder_ctx["ctx"], action.id, new_field.id, "'y'"
    )

    updated = result["updated_action"]
    assert updated["id"] == action.id
    assert updated["type"] == "create_row"
    assert {m["field_id"] for m in updated["field_mappings"]} == {
        field.id,
        new_field.id,
    }
    assert set(result) == {"updated_action"}


@pytest.mark.django_db
def test_add_action_field_mapping_can_be_undone(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, table, _field = row_action_with_mapping
    new_field = data_fixture.create_text_field(table=table, name="Other")
    user = builder_ctx["user"]
    session_id = "session-id"
    set_untrusted_client_session_id(user, session_id)

    actions.add_action_field_mapping(builder_ctx["ctx"], action.id, new_field.id, "'y'")

    ActionHandler.undo(
        user, [PageActionScopeType.value(builder_ctx["page"].id)], session_id
    )
    fields = action.service.specific.field_mappings.values_list("field_id", flat=True)
    assert new_field.id not in fields


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value", ["$formula: the name", "the name", "get('page_parameter.nope')"]
)
def test_add_action_field_mapping_refuses_what_is_not_a_formula(
    builder_ctx, row_action_with_mapping, value
):
    action, _table, field = row_action_with_mapping

    with pytest.raises(ToolInputError):
        actions.add_action_field_mapping(builder_ctx["ctx"], action.id, field.id, value)

    mapping = action.service.specific.field_mappings.get()
    assert mapping.value["formula"] == "'x'"


@pytest.mark.django_db
def test_add_action_field_mapping_reads_the_row_of_a_table_button(
    builder_ctx, table_with_button
):
    table = builder_ctx["data_source"].service.specific.table
    field = table.field_set.first()
    action = saved(
        create(
            builder_ctx,
            ActionCreate(
                type="create_row",
                element=table_with_button.id,
                event="View_click",
                table_id=table.id,
                field_values=[{"field_id": str(field.id), "value": "'x'"}],
            ),
        )
    )

    result = actions.add_action_field_mapping(
        builder_ctx["ctx"], action.id, field.id, "get('current_record.id')"
    )

    assert result["updated_action"]["field_mappings"][0]["value"]


@pytest.mark.django_db
def test_add_action_field_mapping_on_another_workspace_is_refused(
    data_fixture, builder_ctx
):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=other)
    )
    button = data_fixture.create_builder_button_element(page=page)
    action = data_fixture.create_notification_workflow_action(
        page=page, element=button, event="click"
    )

    with pytest.raises(ToolInputError, match="not found in this workspace"):
        actions.add_action_field_mapping(builder_ctx["ctx"], action.id, 1, "'x'")


@pytest.mark.django_db
def test_add_action_field_mapping_on_a_notification_is_refused(builder_ctx):
    with pytest.raises(ToolInputError, match="Cannot add field mappings"):
        actions.add_action_field_mapping(
            builder_ctx["ctx"], builder_ctx["action"].id, 1, "'x'"
        )


# ---------------------------------------------------------------------------
# A data source on the shared page rule, and what a data source value means
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_button(data_fixture, builder_ctx):
    return data_fixture.create_builder_button_element(
        page=builder_ctx["builder"].shared_page
    )


@pytest.fixture
def shared_data_source(data_fixture, builder_ctx):
    return data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=builder_ctx["builder"].shared_page,
        table=builder_ctx["data_source"].service.specific.table,
        name="Everywhere",
    )


@pytest.mark.django_db
def test_a_shared_page_action_can_not_refresh_a_data_source_of_one_page_by_id(
    builder_ctx, shared_button
):
    result = create(
        builder_ctx,
        ActionCreate(
            type="refresh_data_source",
            element=shared_button.id,
            data_source=builder_ctx["data_source"].id,
        ),
    )

    assert result["created_actions"] == []
    assert "shared page" in result["errors"][0]


@pytest.mark.django_db
def test_a_shared_page_action_can_not_refresh_a_data_source_of_one_page_by_ref(
    builder_ctx, shared_button
):
    result = actions.create_actions_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ActionCreate(
                type="refresh_data_source",
                element=shared_button.id,
                data_source="products",
            )
        ],
        BuilderWriteOptions(
            known_data_source_refs={"products": builder_ctx["data_source"].id}
        ),
    )

    assert result["created_actions"] == []
    assert "shared page" in result["errors"][0]


@pytest.mark.django_db
def test_a_shared_page_action_can_refresh_a_shared_page_data_source(
    builder_ctx, shared_button, shared_data_source
):
    result = actions.create_actions_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ActionCreate(
                type="refresh_data_source",
                element=shared_button.id,
                data_source=shared_data_source.id,
            ),
            ActionCreate(
                type="refresh_data_source",
                element=shared_button.id,
                data_source="everywhere",
            ),
        ],
        BuilderWriteOptions(
            known_data_source_refs={"everywhere": shared_data_source.id}
        ),
    )

    assert "errors" not in result
    assert saved(result).data_source_id == shared_data_source.id
    assert saved(result, 1).data_source_id == shared_data_source.id


@pytest.mark.django_db
def test_an_action_on_a_page_can_refresh_a_shared_page_data_source(
    builder_ctx, shared_data_source
):
    result = create(
        builder_ctx,
        ActionCreate(
            type="refresh_data_source",
            element=builder_ctx["button"].id,
            data_source=shared_data_source.id,
        ),
    )

    assert saved(result).data_source_id == shared_data_source.id


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["", "  ", "foo"])
def test_a_data_source_means_nothing_on_other_action_types(builder_ctx, value):
    result = create(
        builder_ctx, notification(builder_ctx["button"].id, data_source=value)
    )

    assert len(result["created_actions"]) == 1
    assert "errors" not in result


@pytest.mark.parametrize("data_source", [None, "", "  "])
def test_refresh_data_source_needs_a_data_source(data_source):
    with pytest.raises(PydanticValidationError, match="requires all of: data_source"):
        ActionCreate(type="refresh_data_source", element=1, data_source=data_source)


# ---------------------------------------------------------------------------
# update_action
# ---------------------------------------------------------------------------


def changes(**kwargs):
    return ActionChanges(**kwargs)


def update(builder_ctx, action_id, **kwargs):
    return actions.update_action(builder_ctx["ctx"], action_id, changes(**kwargs))


def stored(action_id):
    return BuilderWorkflowAction.objects.get(id=action_id).specific


@pytest.fixture
def detail_page(data_fixture, builder_ctx):
    return data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Detail",
        path="/detail/:id",
        path_params=[{"name": "id", "type": "text"}],
    )


@pytest.fixture
def titled(builder_ctx):
    return saved(
        create(
            builder_ctx,
            notification(builder_ctx["button"].id, title="Old", description="Text"),
        )
    )


@pytest.fixture
def opens_detail(builder_ctx, detail_page):
    return saved(
        create(
            builder_ctx,
            ActionCreate(
                type="open_page",
                element=builder_ctx["button"].id,
                navigate_to_page_id=detail_page.id,
                page_parameters=[{"name": "id", "value": "Fixed"}],
            ),
        )
    )


@pytest.mark.django_db
def test_update_action_keeps_the_old_title_when_the_new_one_is_refused(
    builder_ctx, titled
):
    result = update(builder_ctx, titled.id, title="$formula: the product name")

    assert stored(titled.id).title["formula"] == "'Old'"
    entry = result["formula_errors"][0]
    assert entry["action_id"] == titled.id
    assert entry["field"] == "title"
    assert entry["formula"] == "the product name"
    assert "needs a formula" in entry["error"]


@pytest.mark.django_db
def test_update_action_keeps_the_old_parameter_when_the_new_one_is_refused(
    builder_ctx, opens_detail
):
    result = update(
        builder_ctx,
        opens_detail.id,
        page_parameters=[{"name": "id", "value": "get('page_parameter.nope')"}],
        query_parameters=[{"name": "tab", "value": "$formula: the tab"}],
    )

    action = stored(opens_detail.id)
    assert action.page_parameters[0]["value"]["formula"] == "'Fixed'"
    assert action.query_parameters[0]["value"]["formula"] == "''"
    assert [entry["field"] for entry in result["formula_errors"]] == [
        "page_param_0",
        "query_param_0",
    ]


@pytest.mark.django_db
def test_update_action_changes_only_what_it_is_given(builder_ctx, titled):
    result = update(builder_ctx, titled.id, description="New text")

    action = stored(titled.id)
    assert action.title["formula"] == "'Old'"
    assert action.description["formula"] == "'New text'"
    assert action.description["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert action.event == "click"
    assert action.element_id == builder_ctx["button"].id
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_update_action_stores_fixed_text_and_a_formula_in_one_call(builder_ctx, titled):
    formula = f"get('data_source.{builder_ctx['data_source'].id}.0.id')"

    result = update(builder_ctx, titled.id, title=formula, description="Fixed")

    action = stored(titled.id)
    assert action.title["formula"] == formula
    assert action.description["formula"] == "'Fixed'"
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_update_action_changes_where_a_page_opens(
    data_fixture, builder_ctx, opens_detail
):
    other = data_fixture.create_builder_page(builder=builder_ctx["builder"], path="/o")

    update(
        builder_ctx,
        opens_detail.id,
        navigate_to_page_id=other.id,
        page_parameters=[],
        target="blank",
    )

    action = stored(opens_detail.id)
    assert action.navigate_to_page_id == other.id
    assert action.navigation_type == "page"
    assert action.page_parameters == []
    assert action.target == "blank"


@pytest.mark.django_db
def test_update_action_can_not_open_a_page_of_another_application(
    data_fixture, builder_ctx, opens_detail, detail_page
):
    other = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(
            workspace=builder_ctx["workspace"]
        )
    )

    with pytest.raises(DRFValidationError):
        update(builder_ctx, opens_detail.id, navigate_to_page_id=other.id)

    assert stored(opens_detail.id).navigate_to_page_id == detail_page.id


@pytest.mark.django_db
def test_update_action_on_another_workspace_is_refused(data_fixture, builder_ctx):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=other)
    )
    button = data_fixture.create_builder_button_element(page=page)
    action = data_fixture.create_notification_workflow_action(
        page=page, element=button, event="click"
    )

    title = stored(action.id).title

    with pytest.raises(ToolInputError, match="not found in this workspace"):
        update(builder_ctx, action.id, title="Taken")

    assert stored(action.id).title == title


@pytest.mark.django_db
def test_update_action_in_one_action_group_is_undone_in_one_step(builder_ctx, titled):
    user = builder_ctx["user"]
    session_id = "session-id"
    set_untrusted_client_session_id(user, session_id)
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))
    scopes = [PageActionScopeType.value(builder_ctx["page"].id)]
    formula = f"get('data_source.{builder_ctx['data_source'].id}.0.id')"

    update(builder_ctx, titled.id, title=formula, description="Fixed")

    ActionHandler.undo(user, scopes, session_id)

    action = stored(titled.id)
    assert action.title["formula"] == "'Old'"
    assert action.description["formula"] == "'Text'"


@pytest.mark.django_db
def test_update_action_of_a_shared_page_element_reads_the_shared_page(
    data_fixture, builder_ctx, shared_button
):
    builder_ctx["page"].path_params = [{"name": "id", "type": "text"}]
    builder_ctx["page"].path = "/home/:id"
    builder_ctx["page"].save()
    action = saved(create(builder_ctx, notification(shared_button.id, title="Old")))

    result = update(builder_ctx, action.id, title="get('page_parameter.id')")

    assert stored(action.id).title["formula"] == "'Old'"
    assert result["formula_errors"][0]["field"] == "title"


@pytest.mark.django_db
def test_update_action_reads_the_row_of_a_table_button(builder_ctx, table_with_button):
    action = saved(
        create(
            builder_ctx,
            notification(table_with_button.id, title="Old", event="View_click"),
        )
    )

    result = update(builder_ctx, action.id, title="get('current_record.id')")

    assert stored(action.id).title["formula"] == "get('current_record.id')"
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_update_action_refuses_what_its_type_does_not_take(builder_ctx, titled):
    with pytest.raises(ToolInputError, match="navigate_to_page_id.*notification"):
        update(builder_ctx, titled.id, navigate_to_page_id=1)


@pytest.mark.django_db
def test_update_action_with_nothing_to_change_is_refused(builder_ctx, titled):
    with pytest.raises(ToolInputError, match="nothing to change"):
        update(builder_ctx, titled.id)


@pytest.mark.parametrize(
    "name,value", [("type", "logout"), ("element", 1), ("event", "submit")]
)
def test_update_action_can_not_change_what_identifies_the_action(name, value):
    with pytest.raises(PydanticValidationError):
        changes(**{name: value})


@pytest.mark.django_db
def test_update_action_of_a_type_it_does_not_know_is_refused(data_fixture, builder_ctx):
    action = data_fixture.create_core_http_request_workflow_action(
        page=builder_ctx["page"],
        element=builder_ctx["button"],
        event="click",
    )

    with pytest.raises(ToolInputError, match="can't be changed"):
        update(builder_ctx, action.id, title="Hi")


@pytest.mark.django_db
def test_update_action_refreshes_another_data_source(
    data_fixture, builder_ctx, shared_data_source
):
    action = saved(
        create(
            builder_ctx,
            ActionCreate(
                type="refresh_data_source",
                element=builder_ctx["button"].id,
                data_source=builder_ctx["data_source"].id,
            ),
        )
    )

    update(builder_ctx, action.id, data_source=shared_data_source.id)

    assert stored(action.id).data_source_id == shared_data_source.id


@pytest.mark.django_db
def test_update_action_on_the_shared_page_can_not_name_a_data_source_of_one_page(
    builder_ctx, shared_button, shared_data_source
):
    action = saved(
        create(
            builder_ctx,
            ActionCreate(
                type="refresh_data_source",
                element=shared_button.id,
                data_source=shared_data_source.id,
            ),
        )
    )

    with pytest.raises(ToolInputError, match="shared page"):
        update(builder_ctx, action.id, data_source=builder_ctx["data_source"].id)

    assert stored(action.id).data_source_id == shared_data_source.id


@pytest.mark.django_db
def test_update_action_fixes_and_keeps_a_row_id(builder_ctx):
    action = saved(
        create(builder_ctx, row_action(builder_ctx, builder_ctx["button"].id))
    )
    formula = f"get('data_source.{builder_ctx['data_source'].id}.0.id')"

    fixed = update(builder_ctx, action.id, row_id=formula)
    refused = update(builder_ctx, action.id, row_id="the row")

    assert "formula_errors" not in fixed
    assert stored(action.id).service.specific.row_id["formula"] == formula
    assert refused["formula_errors"][0]["field"] == "row_id"
    assert refused["updated_action"]["row_id_formula"]


@pytest.mark.django_db
def test_update_action_changes_the_row_id_of_a_delete(builder_ctx):
    action = saved(
        create(
            builder_ctx,
            row_action(builder_ctx, builder_ctx["button"].id, type="delete_row"),
        )
    )

    result = update(builder_ctx, action.id, row_id="'2'")

    assert "formula_errors" not in result
    assert stored(action.id).service.specific.row_id["formula"] == "'2'"


@pytest.mark.django_db
@pytest.mark.parametrize("row_id", ["", "  "])
def test_update_action_refuses_an_empty_row_id(row_id):
    with pytest.raises(PydanticValidationError, match="row_id"):
        changes(row_id=row_id)


def _mappings(action_id):
    service = stored(action_id).service.specific
    return {m.field_id: m.value["formula"] for m in service.field_mappings.all()}


@pytest.mark.django_db
def test_update_action_changes_the_fields_it_names(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, table, field = row_action_with_mapping
    second = data_fixture.create_text_field(table=table, name="Second")
    actions.add_action_field_mapping(builder_ctx["ctx"], action.id, second.id, "'b'")
    third = data_fixture.create_text_field(table=table, name="Third")

    result = update(
        builder_ctx,
        action.id,
        field_values=[
            {"field_id": str(second.id), "value": "'c'"},
            {"field_id": f" {third.id} ", "value": "'d'"},
        ],
    )

    assert "formula_errors" not in result
    assert _mappings(action.id) == {field.id: "'x'", second.id: "'c'", third.id: "'d'"}


@pytest.mark.django_db
def test_update_action_leaves_a_refused_field_value_as_it_was(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, table, field = row_action_with_mapping
    new_field = data_fixture.create_text_field(table=table, name="New")

    result = update(
        builder_ctx,
        action.id,
        field_values=[
            {"field_id": str(field.id), "value": "$formula: the name"},
            {"field_id": str(new_field.id), "value": "not a formula"},
        ],
    )

    assert _mappings(action.id) == {field.id: "'x'"}
    assert {entry["field"] for entry in result["formula_errors"]} == {
        f"field_{field.id}",
        f"field_{new_field.id}",
    }


@pytest.mark.django_db
def test_update_action_refuses_a_field_of_another_table(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, _table, field = row_action_with_mapping
    other = data_fixture.create_text_field(
        table=data_fixture.create_database_table(
            database=data_fixture.create_database_application(
                workspace=builder_ctx["workspace"]
            )
        )
    )

    with pytest.raises(ToolInputError, match="not in the table"):
        update(
            builder_ctx,
            action.id,
            field_values=[{"field_id": str(other.id), "value": "'y'"}],
        )

    assert _mappings(action.id) == {field.id: "'x'"}


@pytest.mark.django_db
def test_update_action_moves_to_another_table_and_can_be_undone(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, table, field = row_action_with_mapping
    other_table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=builder_ctx["workspace"]
        )
    )
    other_field = data_fixture.create_text_field(table=other_table, name="Other")
    user = builder_ctx["user"]
    session_id = "session-id"
    set_untrusted_client_session_id(user, session_id)
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))

    result = update(
        builder_ctx,
        action.id,
        table_id=other_table.id,
        field_values=[{"field_id": str(other_field.id), "value": "'y'"}],
    )

    assert "formula_errors" not in result
    assert stored(action.id).service.specific.table_id == other_table.id
    assert _mappings(action.id) == {other_field.id: "'y'"}

    ActionHandler.undo(
        user, [PageActionScopeType.value(builder_ctx["page"].id)], session_id
    )

    assert stored(action.id).service.specific.table_id == table.id
    assert _mappings(action.id) == {field.id: "'x'"}


@pytest.mark.django_db
def test_update_action_refuses_a_table_of_another_workspace(
    data_fixture, builder_ctx, row_action_with_mapping
):
    action, table, _field = row_action_with_mapping
    other = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=data_fixture.create_workspace(user=builder_ctx["user"])
        )
    )

    with pytest.raises(ToolInputError, match="not found"):
        update(builder_ctx, action.id, table_id=other.id)

    assert stored(action.id).service.specific.table_id == table.id


# ---------------------------------------------------------------------------
# Reading actions back
# ---------------------------------------------------------------------------


def listed(builder_ctx, action_id):
    result = actions.list_actions(builder_ctx["ctx"], builder_ctx["page"].id)
    return next(a for a in result["workflow_actions"] if a["id"] == action_id)


@pytest.mark.django_db
def test_list_actions_shows_a_notification_title_and_description(builder_ctx, titled):
    item = listed(builder_ctx, titled.id)

    assert item["title"] == "'Old'"
    assert item["description"] == "'Text'"
    assert item["navigate_to_page_id"] is None
    assert item["page_parameters"] is None


@pytest.mark.django_db
def test_list_actions_shows_where_an_open_page_goes(
    builder_ctx, detail_page, opens_detail
):
    item = listed(builder_ctx, opens_detail.id)

    assert item["navigation_type"] == "page"
    assert item["navigate_to_page_id"] == detail_page.id
    assert item["target"] == opens_detail.target
    assert item["page_parameters"] == [{"name": "id", "value": "'Fixed'"}]
    assert item["query_parameters"] == []
    assert item["title"] is None


@pytest.mark.django_db
def test_list_actions_shows_the_data_source_a_refresh_uses(builder_ctx):
    action = saved(
        create(
            builder_ctx,
            ActionCreate(
                type="refresh_data_source",
                element=builder_ctx["button"].id,
                data_source=builder_ctx["data_source"].id,
            ),
        )
    )

    item = listed(builder_ctx, action.id)

    assert item["data_source_id"] == builder_ctx["data_source"].id


@pytest.mark.django_db
def test_list_actions_gives_row_formulas_as_plain_strings(builder_ctx):
    action = saved(
        create(builder_ctx, row_action(builder_ctx, builder_ctx["button"].id))
    )

    item = listed(builder_ctx, action.id)

    assert item["row_id_formula"] == "'1'"
    assert [m["value"] for m in item["field_mappings"]] == ["'x'"]


@pytest.mark.django_db
def test_list_actions_reads_the_same_as_update_action_returns(
    builder_ctx, opens_detail
):
    result = update(builder_ctx, opens_detail.id, target="blank")

    assert result["updated_action"] == listed(builder_ctx, opens_detail.id)
    assert result["updated_action"]["target"] == "blank"


@pytest.mark.django_db
def test_what_list_actions_shows_can_be_sent_back_to_update_action(
    builder_ctx, detail_page, opens_detail
):
    data_source_id = builder_ctx["data_source"].id
    update(
        builder_ctx,
        opens_detail.id,
        page_parameters=[
            {"name": "id", "value": f"get('data_source.{data_source_id}.0.id')"}
        ],
        query_parameters=[{"name": "tab", "value": "Fixed tab"}],
    )
    before = listed(builder_ctx, opens_detail.id)
    raw_before = stored(opens_detail.id)

    result = update(
        builder_ctx,
        opens_detail.id,
        navigate_to_page_id=before["navigate_to_page_id"],
        target=before["target"],
        page_parameters=before["page_parameters"],
        query_parameters=before["query_parameters"],
    )

    assert "formula_errors" not in result
    assert result["updated_action"] == before
    after = stored(opens_detail.id)
    assert after.page_parameters == raw_before.page_parameters
    assert after.query_parameters == raw_before.query_parameters


@pytest.mark.django_db
def test_notification_values_can_be_sent_back_to_update_action(builder_ctx, titled):
    before = listed(builder_ctx, titled.id)

    update(builder_ctx, titled.id, title=before["title"], description="Same")
    update(builder_ctx, titled.id, description=before["description"])

    assert listed(builder_ctx, titled.id)["title"] == before["title"]
    assert stored(titled.id).title["formula"] == "'Old'"
    assert stored(titled.id).description["formula"] == "'Text'"


# ---------------------------------------------------------------------------
# Page parameters of an open_page update
# ---------------------------------------------------------------------------


@pytest.fixture
def two_parameter_page(data_fixture, builder_ctx):
    return data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Two",
        path="/d/:id/:slug",
        path_params=[
            {"name": "id", "type": "text"},
            {"name": "slug", "type": "text"},
        ],
    )


@pytest.fixture
def opens_two(builder_ctx, two_parameter_page):
    return saved(
        create(
            builder_ctx,
            ActionCreate(
                type="open_page",
                element=builder_ctx["button"].id,
                navigate_to_page_id=two_parameter_page.id,
                page_parameters=[
                    {"name": "id", "value": "A"},
                    {"name": "slug", "value": "B"},
                ],
            ),
        )
    )


def _parameter_names(action_id):
    return [p["name"] for p in stored(action_id).page_parameters]


@pytest.mark.django_db
def test_update_action_refuses_a_partial_parameter_list(builder_ctx, opens_two):
    with pytest.raises(ToolInputError, match="slug") as error:
        update(
            builder_ctx,
            opens_two.id,
            page_parameters=[{"name": "id", "value": "New"}],
            target="blank",
        )

    assert "missing" in str(error.value).lower()
    assert _parameter_names(opens_two.id) == ["id", "slug"]
    assert stored(opens_two.id).target == opens_two.target
    assert stored(opens_two.id).page_parameters[0]["value"]["formula"] == "'A'"


@pytest.mark.django_db
def test_update_action_refuses_an_unknown_parameter_name(builder_ctx, opens_two):
    with pytest.raises(ToolInputError, match="nosuch") as error:
        update(
            builder_ctx,
            opens_two.id,
            page_parameters=[
                {"name": "id", "value": "A"},
                {"name": "slug", "value": "B"},
                {"name": "nosuch", "value": "x"},
            ],
        )

    assert "unknown" in str(error.value).lower()
    assert _parameter_names(opens_two.id) == ["id", "slug"]


@pytest.mark.django_db
def test_update_action_refuses_a_new_target_with_other_parameters(
    data_fixture, builder_ctx, opens_two
):
    other = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        path="/o/:code",
        path_params=[{"name": "code", "type": "text"}],
    )

    with pytest.raises(ToolInputError, match="code"):
        update(builder_ctx, opens_two.id, navigate_to_page_id=other.id)

    action = stored(opens_two.id)
    assert action.navigate_to_page_id == opens_two.navigate_to_page_id
    assert _parameter_names(opens_two.id) == ["id", "slug"]


@pytest.mark.django_db
def test_update_action_accepts_a_new_target_with_its_parameters(
    data_fixture, builder_ctx, opens_two
):
    other = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        path="/o/:code",
        path_params=[{"name": "code", "type": "text"}],
    )

    result = update(
        builder_ctx,
        opens_two.id,
        navigate_to_page_id=other.id,
        page_parameters=[{"name": "code", "value": "C"}],
    )

    assert "formula_errors" not in result
    assert _parameter_names(opens_two.id) == ["code"]
    assert stored(opens_two.id).navigate_to_page_id == other.id


@pytest.mark.django_db
def test_update_action_accepts_a_complete_list_in_any_order(builder_ctx, opens_two):
    update(
        builder_ctx,
        opens_two.id,
        page_parameters=[
            {"name": "slug", "value": "S"},
            {"name": "id", "value": "I"},
        ],
    )

    assert sorted(_parameter_names(opens_two.id)) == ["id", "slug"]


FUNCTION_CALLS = [
    "generate_uuid()",
    "upper('abc')",
    "random_int(1, 10)",
    "add(1, 2)",
]
TEXTS = ["Hello (world)", "foo(bar)", "'upper(x)'", "add(1", "add(1, 2) trailing"]


def _store_title(action, formula):
    action.title = {"formula": formula, "mode": BASEROW_FORMULA_MODE_ADVANCED}
    action.save()


@pytest.mark.django_db
@pytest.mark.parametrize("formula", FUNCTION_CALLS)
def test_a_function_call_in_a_title_survives_a_round_trip(builder_ctx, titled, formula):
    _store_title(stored(titled.id), formula)
    before = listed(builder_ctx, titled.id)
    assert before["title"] == formula

    result = update(builder_ctx, titled.id, title=before["title"])

    assert "formula_errors" not in result
    assert stored(titled.id).title["formula"] == formula
    assert listed(builder_ctx, titled.id)["title"] == formula


@pytest.mark.django_db
@pytest.mark.parametrize("formula", FUNCTION_CALLS)
def test_a_function_call_in_a_parameter_survives_a_round_trip(
    builder_ctx, opens_detail, formula
):
    action = stored(opens_detail.id)
    action.page_parameters = [
        {
            "name": "id",
            "value": {"formula": formula, "mode": BASEROW_FORMULA_MODE_ADVANCED},
        }
    ]
    action.save()
    before = listed(builder_ctx, opens_detail.id)

    result = update(
        builder_ctx, opens_detail.id, page_parameters=before["page_parameters"]
    )

    assert "formula_errors" not in result
    assert stored(opens_detail.id).page_parameters[0]["value"]["formula"] == formula


@pytest.mark.django_db
@pytest.mark.parametrize("text", TEXTS)
def test_text_that_is_not_a_function_call_stays_text(builder_ctx, titled, text):
    result = update(builder_ctx, titled.id, title=text)

    assert "formula_errors" not in result
    assert stored(titled.id).title["formula"] == wrap_static_string(text)


@pytest.mark.django_db
@pytest.mark.parametrize("text", TEXTS)
def test_parameter_text_that_is_not_a_function_call_stays_text(
    builder_ctx, opens_detail, text
):
    update(
        builder_ctx, opens_detail.id, page_parameters=[{"name": "id", "value": text}]
    )

    value = stored(opens_detail.id).page_parameters[0]["value"]["formula"]
    assert value == wrap_static_string(text)


@pytest.mark.django_db
def test_a_function_call_that_is_not_valid_here_keeps_the_old_title(
    builder_ctx, titled
):
    result = update(
        builder_ctx, titled.id, title="add(1, get('page_parameter.nosuch'))"
    )

    assert result["formula_errors"][0]["field"] == "title"
    assert stored(titled.id).title["formula"] == "'Old'"


@pytest.mark.django_db
def test_a_custom_navigation_action_is_not_checked_against_its_old_page(
    builder_ctx, opens_two
):
    action = stored(opens_two.id)
    action.navigation_type = "custom"
    action.save()

    update(builder_ctx, opens_two.id, page_parameters=[])

    assert stored(opens_two.id).page_parameters == []


# ---------------------------------------------------------------------------
# Empty field values, and the table_id warning
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_action_with_only_an_empty_field_value_list_is_refused(
    builder_ctx, row_action_with_mapping
):
    action, _table, field = row_action_with_mapping

    with pytest.raises(ToolInputError, match="field_values"):
        update(builder_ctx, action.id, field_values=[])

    assert _mappings(action.id) == {field.id: "'x'"}


@pytest.mark.django_db
def test_an_empty_field_value_list_with_another_change_is_not_refused(
    builder_ctx, row_action_with_mapping
):
    action, table, field = row_action_with_mapping

    update(builder_ctx, action.id, field_values=[], table_id=table.id)

    assert _mappings(action.id) == {field.id: "'x'"}


def test_table_id_says_what_moving_to_another_table_does():
    description = ActionChanges.model_fields["table_id"].description

    assert "cleared" in description
    assert "row_id" in description
    assert "new table" in description
    assert "row_id" in actions.update_action.__doc__
    assert "clears the field values" in actions.update_action.__doc__


# ---------------------------------------------------------------------------
# Field values of a new row action
# ---------------------------------------------------------------------------


def _create_row_with(builder_ctx, value):
    table = builder_ctx["data_source"].service.specific.table
    field = table.field_set.first()
    result = actions.create_actions(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ActionCreate(
                type="create_row",
                element=builder_ctx["button"].id,
                event="click",
                table_id=table.id,
                field_values=[{"field_id": str(field.id), "value": value}],
            )
        ],
    )
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    return result, field, action.service.specific.field_mappings.get().value["formula"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    ["nosuchfn('x')", "get('current_record.id')"],
    ids=["unknown-function", "not-in-a-collection"],
)
def test_a_new_row_actions_invalid_field_value_is_left_empty_and_listed(
    builder_ctx, value
):
    result, field, stored = _create_row_with(builder_ctx, value)

    assert [e["field"] for e in result["formula_errors"]] == [f"field_{field.id}"]
    assert stored == "''"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, expected",
    [
        ("Alice", "'Alice'"),
        ("Hello (world)", "'Hello (world)'"),
        ("O'Brien", "'O\\'Brien'"),
        ("not a formula", "'not a formula'"),
    ],
)
def test_a_new_row_actions_plain_field_value_is_stored_as_fixed_text(
    builder_ctx, value, expected
):
    result, _field, stored = _create_row_with(builder_ctx, value)

    assert "formula_errors" not in result
    assert stored == expected


@pytest.mark.django_db
def test_a_new_row_actions_field_id_may_have_spaces_around_it(builder_ctx):
    table = builder_ctx["data_source"].service.specific.table
    field = table.field_set.first()
    result = actions.create_actions(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ActionCreate(
                type="create_row",
                element=builder_ctx["button"].id,
                event="click",
                table_id=table.id,
                field_values=[{"field_id": f" {field.id} ", "value": "'x'"}],
            )
        ],
    )

    assert "formula_errors" not in result
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    assert action.service.specific.field_mappings.get().value["formula"] == "'x'"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value", ["'fixed'", "7", "upper('abc')", "get('user.id')", "$formula: 'fixed'"]
)
def test_a_new_row_actions_valid_field_value_is_stored(builder_ctx, value):
    result, _field, stored = _create_row_with(builder_ctx, value)

    assert "formula_errors" not in result
    assert stored == value.removeprefix("$formula: ")
