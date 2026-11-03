from django.db.models import F, JSONField, Value

import pytest

from baserow.contrib.database.api.fields.serializers import CollaboratorSerializer
from baserow.contrib.database.fields.field_filters import FilterBuilder
from baserow.contrib.database.formula.ast.function_defs import (
    BaserowStringAggCollaboratorValues,
)
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaMultipleCollaboratorsType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.agents.handler import AgentHandler
from baserow.core.models import SubjectRollout


@pytest.mark.django_db
def test_new_collaborator_formula_values_only_store_name(data_fixture):
    """New formula JSON uses canonical Subject names for humans and Agents alike."""
    user = data_fixture.create_user(first_name="Canonical")
    table = data_fixture.create_database_table(user=user)
    collaborators = data_fixture.create_multiple_collaborators_field(
        table=table, name="People"
    )
    formula = data_fixture.create_formula_field(table=table, formula="field('People')")
    agent = AgentHandler().create_agent(table.database.workspace, name="Assistant")
    SubjectRollout.objects.create(pk=1, agent_references_enabled=True)
    row = RowHandler().force_create_row(
        user, table, {collaborators.db_column: [user.id, agent.subject_id]}
    )
    value = getattr(row, formula.db_column)
    assert value == [
        {"id": user.id, "name": "Canonical", "type": "auth.User"},
        {"id": agent.subject_id, "name": "Assistant", "type": "core.Agent"},
    ]
    assert CollaboratorSerializer(value, many=True).data == value


@pytest.mark.django_db
@pytest.mark.parametrize("nested", [False, True])
def test_legacy_and_canonical_names_search_filter_and_stringify(data_fixture, nested):
    """Stored legacy names remain readable and canonical keys take precedence."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_multiple_collaborators_field(table=table, name="People")
    formula = data_fixture.create_formula_field(table=table, formula="field('People')")
    row = RowHandler().force_create_row(user, table, {})
    names = [
        {"id": 1, "first_name": "Legacy Alice"},
        {"id": 2, "name": "Canonical Bob", "first_name": "Stale ignored"},
        {"id": 3, "name": "New Carol", "type": "core.Agent"},
    ]
    model = table.get_model()
    model.objects.filter(pk=row.pk).update(
        **{
            formula.db_column: Value(
                [{"id": 1, "value": names}] if nested else names,
                output_field=JSONField(),
            )
        }
    )
    formula_type = BaserowFormulaMultipleCollaboratorsType()
    if nested:
        search = formula_type.get_search_expression_in_array(
            formula, model.objects.all()
        )
    else:
        search = formula_type.get_search_expression(formula, model.objects.all())
    assert (
        model.objects.annotate(names=search).values_list("names", flat=True).get()
        == "Legacy Alice Canonical Bob New Carol"
    )
    if not nested:
        serializer = formula_type.get_response_serializer_field(formula)
        assert [v["name"] for v in serializer.to_representation(names)] == [
            "Legacy Alice",
            "Canonical Bob",
            "New Carol",
        ]
        assert (
            "name" not in names[0]
        )  # Reading must not mutate stored legacy dictionaries.
        # Exercise the actual SQL expression used by totext(), preserving array order.
        expression = BaserowStringAggCollaboratorValues().to_django_expression(
            F(formula.db_column)
        )
        assert list(
            model.objects.annotate(label=expression).values_list("label", flat=True)
        ) == ["Legacy Alice", "Canonical Bob", "New Carol"]
    else:
        model_field = model._meta.get_field(formula.db_column)
        for method in (
            formula_type.get_in_array_contains_query,
            formula_type.get_in_array_contains_word_query,
        ):
            for text in ("Alice", "Bob", "Carol"):
                condition = method(formula.db_column, text, model_field, formula)
                assert (
                    FilterBuilder()
                    .filter(condition)
                    .apply_to_queryset(model.objects.all())
                    .exists()
                )
            condition = method(formula.db_column, "Stale", model_field, formula)
            assert (
                not FilterBuilder()
                .filter(condition)
                .apply_to_queryset(model.objects.all())
                .exists()
            )


@pytest.mark.django_db
@pytest.mark.parametrize("name_key", ["name", "first_name"])
def test_empty_collaborator_names_support_legacy_values(data_fixture, name_key):
    """Empty-name filters support both stored schemas without treating IDs as names."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_multiple_collaborators_field(table=table, name="People")
    formula = data_fixture.create_formula_field(table=table, formula="field('People')")
    row = RowHandler().force_create_row(user, table, {})
    model = table.get_model()
    formula_type = BaserowFormulaMultipleCollaboratorsType()
    model_field = model._meta.get_field(formula.db_column)
    for label, expected_empty in (("", True), ("Alice", False)):
        model.objects.filter(pk=row.pk).update(
            **{
                formula.db_column: Value(
                    [{"id": 1, name_key: label}], output_field=JSONField()
                )
            }
        )
        condition = formula_type.get_all_empty_query(
            formula.db_column, model_field, formula, in_array=False
        )
        assert (
            FilterBuilder()
            .filter(condition)
            .apply_to_queryset(model.objects.all())
            .exists()
            is expected_empty
        )
