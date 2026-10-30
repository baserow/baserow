from io import BytesIO

from django.db import transaction

import pytest

from baserow.contrib.database.fields.models import MultipleCollaboratorsField
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaMultipleCollaboratorsType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewDefaultValue
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same_workspace", [True, False])
def test_agent_assignments_defaults_and_filters_import_only_into_its_workspace(
    data_fixture, same_workspace
):
    user = data_fixture.create_user(first_name="Member")
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent(workspace=workspace, name="Ops")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_multiple_collaborators_field(table=table, name="Owners")
    view = data_fixture.create_grid_view(table=table)
    audit_field = data_fixture.create_created_by_field(table=table)
    values = [{"id": user.id}, {"id": agent.user_id}]
    RowHandler().create_row(user, table, {field.id: values})
    data_fixture.create_view_filter(
        view=view,
        field=field,
        type="multiple_collaborators_has",
        value=str(agent.user_id),
    )
    data_fixture.create_view_filter(
        view=view, field=audit_field, type="user_is", value=str(agent.user_id)
    )
    with transaction.atomic():
        ViewHandler().update_view_default_values(
            user, view, [{"field": field.id, "enabled": True, "value": values}]
        )

    target = workspace if same_workspace else data_fixture.create_workspace(user=user)
    config = ImportExportConfig(include_permission_data=False)
    exported = CoreHandler().export_workspace_applications(workspace, BytesIO(), config)
    applications, _ = CoreHandler().import_applications_to_workspace(
        target, exported, BytesIO(), config, None
    )
    imported_table = applications[0].table_set.get()
    imported_field = MultipleCollaboratorsField.objects.get(table=imported_table)
    imported_view = imported_table.view_set.get()
    imported_row = imported_table.get_model().objects.get()
    expected_ids = {user.id, agent.user_id} if same_workspace else {user.id}
    assert (
        set(
            getattr(imported_row, imported_field.db_column).values_list("id", flat=True)
        )
        == expected_ids
    )
    default = ViewDefaultValue.objects.get(view=imported_view, field=imported_field)
    assert {collaborator["id"] for collaborator in default.value} == expected_ids
    expected_filter_value = str(agent.user_id) if same_workspace else ""
    assert dict(imported_view.viewfilter_set.values_list("type", "value")) == {
        "multiple_collaborators_has": expected_filter_value,
        "user_is": expected_filter_value,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("unavailable_agent", [False, True])
def test_collaborator_formula_export_skips_unavailable_users(
    data_fixture, unavailable_agent
):
    user = data_fixture.create_user(first_name="Member")
    table = data_fixture.create_database_table(user=user)
    workspace = table.database.workspace
    agent = data_fixture.create_agent(workspace=workspace, name="Ops")
    unavailable = (
        data_fixture.create_agent(workspace=workspace).user
        if unavailable_agent
        else data_fixture.create_user()
    )
    if unavailable_agent:
        Agent.objects.filter(user=unavailable).update(trashed=True)
    data_fixture.create_multiple_collaborators_field(table=table, name="Owners")
    formula = data_fixture.create_formula_field(table=table, formula="field('Owners')")

    result = BaserowFormulaMultipleCollaboratorsType().get_export_value(
        [{"id": user.id}, {"id": agent.user_id}, {"id": unavailable.id}],
        {"name": formula.db_column, "formula_field": formula},
        rich_value=True,
    )

    assert result == [
        f"Member <{user.email}>",
        f"Ops <{agent.user.email}>",
    ]
