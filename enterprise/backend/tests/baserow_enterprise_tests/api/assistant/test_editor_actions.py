from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

import pytest
from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart
from pydantic_ai.models.function import FunctionModel

from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools.tables import TableItemCreate
from baserow.contrib.database.tools.view_config import ViewSortItem
from baserow.contrib.database.tools.views import ViewFilterItemCreate, ViewItemCreate
from baserow.contrib.database.views.models import View, ViewFilter
from baserow_enterprise.assistant.editor_generation import (
    AIFieldPromptDraft,
    DatabaseDesign,
    FilterChanges,
    FilterEdit,
    InstructionDraft,
    NewView,
    RowColorRule,
)

MODULE = "baserow_enterprise.assistant.editor_generation"
VIEWS = "baserow_enterprise.api.assistant.views"
pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(enterprise_data_fixture, api_client):
    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)
    field = enterprise_data_fixture.create_text_field(
        table=table, name="Title", primary=True
    )
    view = enterprise_data_fixture.create_grid_view(table=table)

    def post(
        action,
        *,
        scope_workspace_id=None,
        prompt="Please make this change",
        **parameters,
    ):
        return api_client.post(
            reverse("assistant:actions"),
            {
                "action": action,
                "prompt": prompt,
                "parameters": parameters,
                **(
                    {"workspace_id": scope_workspace_id}
                    if scope_workspace_id is not None
                    else {}
                ),
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    with (
        override_settings(DEBUG=True),
        patch(f"{VIEWS}.resolve_assistant_model"),
        patch(f"{VIEWS}.check_lm_ready_or_raise"),
    ):
        yield table, field, view, post


def test_generates_instruction_draft_without_creating_agent(editor):
    table, _, _, post = editor
    with patch(
        f"{MODULE}._generate",
        return_value=InstructionDraft(instructions="Reply in German."),
    ) as generate:
        response = post(
            "generate_agent_instructions",
            workspace_id=table.database.workspace_id,
            current="Be brief.",
        )
    assert response.status_code == 200, response.data
    assert response.data == {
        "changed": False,
        "summary": "",
        "result": {"instructions": "Reply in German."},
    }
    assert generate.call_args.kwargs == {"current": "Be brief.", "agent_name": ""}


@pytest.mark.parametrize("can_repair", [True, False])
def test_formula_editor_validates_and_retries_in_the_open_field(
    editor, enterprise_data_fixture, can_repair
):
    table, title, _, post = editor
    title.primary = False
    title.save()
    enterprise_data_fixture.create_formula_field(
        table=table, name="Name", primary=True, formula="field('Title')"
    )
    original = "length(field('Title')) > 5"
    target = enterprise_data_fixture.create_formula_field(
        table=table, name="Formula", formula=original
    )
    expected = "contains(lower(field('Name')), 'propose')"
    retries = []

    def respond(messages, info):
        assert not info.function_tools and not info.output_tools
        latest = messages[-1].parts[0]
        if isinstance(latest, RetryPromptPart):
            assert "Missing" in latest.content
            retries.append(latest)
        return ModelResponse(
            parts=[TextPart(expected if can_repair and retries else "field('Missing')")]
        )

    with patch(f"{VIEWS}.resolve_assistant_model") as resolve:
        profile = resolve.return_value
        profile.create_model.return_value = FunctionModel(respond)
        profile.get_settings.return_value = {}
        response = post(
            "generate_formula",
            table_id=table.id,
            field_name=target.name,
            current=original,
            prompt="name contains propose",
        )

    assert retries
    if can_repair:
        assert response.status_code == 200, response.data
        assert response.data == {
            "result": {"formula": expected},
            "changed": False,
            "summary": "",
        }
    else:
        assert response.status_code == 400
    target.refresh_from_db()
    assert target.formula == original


def test_create_then_edit_view_filters(editor):
    table, field, _, post = editor
    condition = ViewFilterItemCreate(
        field_id=field.id, type="text", operator="contains", value="red"
    )
    plan = NewView(
        view=ViewItemCreate(type="grid", name="Red items"),
        filters=[condition],
        sorts=[ViewSortItem(field_id=field.id, order="DESC")],
    )
    with patch(f"{MODULE}._generate", return_value=plan):
        response = post("create_view", table_id=table.id)
    assert response.status_code == 200, response.data
    view = View.objects.get(id=response.data["result"]["view_id"], table=table)
    assert view.viewsort_set.get().order == "DESC"
    row_filter = ViewFilter.objects.get(view=view, field=field, value="red")
    edit = FilterEdit(
        filter_id=row_filter.id,
        condition=condition.model_copy(update={"value": "green"}),
    )
    for changes in [
        FilterChanges(update=[edit], summary="Updated."),
        FilterChanges(remove=[row_filter.id], summary="Removed."),
    ]:
        with patch(f"{MODULE}._generate", return_value=changes):
            response = post("edit_view_filters", view_id=view.id)
        assert response.status_code == 200, response.data
        assert response.data["changed"]
        if changes.update:
            row_filter.refresh_from_db()
            assert row_filter.value == "green"
    assert not ViewFilter.objects.filter(view=view).exists()


def test_edit_blank_filter_on_a_text_formula(editor, enterprise_data_fixture):
    table, title, view, post = editor
    title.primary = False
    title.save()
    name = enterprise_data_fixture.create_formula_field(
        table=table, name="Name", primary=True, formula="field('Title')"
    )
    existing = enterprise_data_fixture.create_view_filter(
        view=view, field=name, type="equal", value=""
    )
    edit = FilterEdit(
        filter_id=existing.id,
        condition=ViewFilterItemCreate(
            field_id=name.id, type="text", operator="contains", value="propose"
        ),
    )
    with patch(
        f"{MODULE}._generate",
        return_value=FilterChanges(update=[edit], summary="Updated."),
    ):
        response = post(
            "edit_view_filters", view_id=view.id, prompt="name containing propose"
        )
    assert response.status_code == 200, response.data
    saved = ViewFilter.objects.get(view=view)
    assert (saved.id, saved.field_id, saved.type, saved.value) == (
        existing.id,
        name.id,
        "contains",
        "propose",
    )


def test_invalid_condition_rolls_back_view_and_earlier_condition(editor):
    table, field, _, post = editor
    ok = ViewFilterItemCreate(
        field_id=field.id, type="text", operator="contains", value="text"
    )
    plan = NewView(
        view=ViewItemCreate(type="grid", name="Invalid"),
        filters=[ok, ok.model_copy(update={"field_id": -1})],
        sorts=[],
    )
    with patch(f"{MODULE}._generate", return_value=plan):
        response = post("create_view", table_id=table.id)
    assert response.status_code == 400
    assert not View.objects.filter(table=table, name="Invalid").exists()
    assert not ViewFilter.objects.filter(field=field).exists()


def test_rejects_edit_if_filters_changed_during_generation(
    editor, enterprise_data_fixture
):
    _, field, view, post = editor
    existing = enterprise_data_fixture.create_view_filter(
        view=view, field=field, value="old"
    )

    def generate(*args, **kwargs):
        ViewFilter.objects.filter(pk=existing.pk).update(value="manual edit")
        return FilterChanges(remove=[existing.pk], summary="Removed.")

    with patch(f"{MODULE}._generate", side_effect=generate):
        response = post("edit_view_filters", view_id=view.id)
    assert response.status_code == 400
    existing.refresh_from_db()
    assert existing.value == "manual edit"


def test_cannot_generate_for_another_workspace(editor, enterprise_data_fixture):
    _, _, _, post = editor
    other = enterprise_data_fixture.create_database_table()
    with patch(f"{MODULE}._generate") as generate:
        response = post("create_view", table_id=other.id)
    assert response.status_code in (400, 403)
    generate.assert_not_called()


def test_scoped_editor_rejects_mismatch_before_resolving_model(editor):
    table, _, _, post = editor
    with patch(f"{VIEWS}.resolve_assistant_model") as resolve:
        response = post(
            "create_view",
            scope_workspace_id=table.database.workspace_id + 1,
            table_id=table.id,
        )
    assert response.status_code == 400
    resolve.assert_not_called()


def test_scoped_agent_draft_includes_its_name(editor):
    table, _, _, post = editor
    workspace_id = table.database.workspace_id
    with patch(
        f"{MODULE}._generate",
        return_value=InstructionDraft(instructions="Summarize releases."),
    ) as generate:
        response = post(
            "generate_agent_instructions",
            scope_workspace_id=workspace_id,
            workspace_id=workspace_id,
            agent_name="Release helper",
            current="Be brief.",
        )
    assert response.status_code == 200
    assert generate.call_args.kwargs == {
        "agent_name": "Release helper",
        "current": "Be brief.",
    }


@pytest.mark.parametrize("action", ["create_table", "create_database"])
def test_generated_structure_is_openable_in_its_target(editor, action):
    table, _, _, post = editor
    layout = TableItemCreate(
        name="Projects",
        primary_field_name="Project",
        fields=[{"name": "Budget", "type": "number"}],
    )
    if action == "create_database":
        params = {"workspace_id": table.database.workspace_id}
        design = DatabaseDesign(
            name="Studio",
            tables=[
                layout,
                TableItemCreate(name="People", primary_field_name="Name", fields=[]),
            ],
        )
    else:
        params = {"database_id": table.database_id}
        design = layout
    with patch(f"{MODULE}._generate", return_value=design):
        response = post(action, name="My choice", **params)
    assert response.status_code == 200, response.data
    result = response.data["result"]
    created = Table.objects.get(
        pk=result["table_id"], database_id=result["database_id"]
    )
    assert created.database.workspace_id == table.database.workspace_id
    assert created.get_primary_field().name == "Project"
    assert created.field_set.get(name="Budget").get_type().type == "number"
    if action == "create_database":
        assert created.database.name == "My choice"
        assert set(
            Table.objects.filter(database=created.database).values_list(
                "name", flat=True
            )
        ) == {"Projects", "People"}
    else:
        assert created.database_id == table.database_id and created.name == "My choice"


def test_create_database_rolls_back_invalid_fields(editor):
    table, _, _, post = editor
    design = DatabaseDesign(
        name="Invalid design",
        tables=[
            TableItemCreate(
                name="Tasks",
                primary_field_name="Name",
                fields=[
                    {"name": "Broken", "type": "formula", "formula": "field('Missing')"}
                ],
            )
        ],
    )
    with patch(f"{MODULE}._generate", return_value=design):
        response = post("create_database", workspace_id=table.database.workspace_id)
    assert response.status_code == 400
    assert not table.database.__class__.objects.filter(name="Invalid design").exists()


def test_ai_field_prompt_uses_only_other_fields_of_its_table(editor):
    table, field, _, post = editor
    draft = AIFieldPromptDraft(parts=["Summarize this customer's request: ", field.id])
    with patch(f"{MODULE}._generate", return_value=draft):
        params = {"table_id": table.id, "current": "", "output_type": "text"}
        response = post("generate_ai_field_prompt", **params)
        assert response.status_code == 200, response.data
        formula = response.data["result"]["ai_prompt"]
        assert f"get('fields.field_{field.id}')" in formula
        assert not response.data["changed"]
        assert (
            post("generate_ai_field_prompt", field_id=field.id, **params).status_code
            == 400
        )


def test_new_table_cannot_target_a_database_in_another_workspace(
    editor, enterprise_data_fixture
):
    table, _, _, post = editor
    other = enterprise_data_fixture.create_database_table()
    with patch(f"{MODULE}._generate") as generate:
        response = post(
            "create_table",
            scope_workspace_id=table.database.workspace_id,
            database_id=other.database_id,
        )
    assert response.status_code in (400, 403)
    generate.assert_not_called()


def test_row_color_uses_current_views_fields_without_filtering_its_rows(editor):
    _, field, view, post = editor
    design = RowColorRule(
        color="red",
        filters=[
            ViewFilterItemCreate(
                field_id=field.id, type="text", operator="contains", value="urgent"
            )
        ],
    )
    with patch(f"{MODULE}._generate", return_value=design):
        response = post("add_row_color", view_id=view.id)
    assert response.status_code == 200, response.data
    rule = response.data["result"]["color_rule"]
    assert rule["color"] == "red"
    (condition,) = rule["filters"]
    assert (condition["field"], condition["type"], condition["value"]) == (
        field.id,
        "contains",
        "urgent",
    )
    assert not ViewFilter.objects.filter(view=view).exists()
