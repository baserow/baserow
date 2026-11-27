from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

import pytest

from baserow.contrib.database.tools.view_config import ViewSortItem
from baserow.contrib.database.tools.views import ViewFilterItemCreate, ViewItemCreate
from baserow.contrib.database.views.models import View, ViewFilter
from baserow_enterprise.assistant.editor_generation import (
    FilterChanges,
    FilterEdit,
    InstructionDraft,
    NewView,
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

    def post(action, **parameters):
        return api_client.post(
            reverse("assistant:actions"),
            {
                "action": action,
                "prompt": "Please make this change",
                "parameters": parameters,
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
    assert generate.call_args.kwargs == {"current": "Be brief."}


@pytest.mark.parametrize(
    "formula, valid", [("upper(field('Title'))", True), ("field('Missing')", False)]
)
def test_validates_formula_in_its_target_table(editor, formula, valid):
    table, _, _, post = editor
    output = SimpleNamespace(table_id=table.id, formula=formula, is_formula_valid=True)
    with patch(
        f"{MODULE}.run_formula_generation", return_value=SimpleNamespace(output=output)
    ):
        response = post(
            "generate_formula", table_id=table.id, field_name="Label", current=""
        )
    if valid:
        assert response.status_code == 200, response.data
        assert response.data["result"] == {"formula": formula}
    else:
        assert response.status_code == 400
    assert list(table.field_set.values_list("name", flat=True)) == ["Title"]


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
