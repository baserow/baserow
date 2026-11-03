"""
The shared action tools store the formulas they are given and report the rest,
without a model. The conftest of this folder fails any model call.
"""

import pytest

from baserow.api.sessions import set_untrusted_client_session_id
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
from baserow_enterprise.builder.tools.types import ActionCreate


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
def test_known_refs_reach_the_action(builder_ctx):
    result = actions.create_actions_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            notification("button"),
            ActionCreate(
                type="refresh_data_source",
                element="button",
                data_source="products",
            ),
        ],
        BuilderWriteOptions(
            known_refs={"button": builder_ctx["button"].id},
            known_data_source_refs={"products": builder_ctx["data_source"].id},
        ),
    )

    assert "errors" not in result
    assert saved(result, 1).data_source_id == builder_ctx["data_source"].id


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
