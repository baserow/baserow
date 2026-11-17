import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_filter_type_registry

OPERATORS = [
    ("single_select", "single_select_equal", False),
    ("single_select", "single_select_not_equal", True),
    ("single_select", "single_select_is_any_of", False),
    ("single_select", "single_select_is_none_of", True),
    ("multiple_select", "multiple_select_has", False),
    ("multiple_select", "multiple_select_has_not", True),
]


@pytest.mark.django_db
@pytest.mark.parametrize("field_type,operator,negated", OPERATORS)
@pytest.mark.parametrize("formula", [False, True])
@pytest.mark.parametrize("case", ["label", "id", "comma", "unknown", "mixed"])
def test_selection_filters_accept_ids_and_exact_labels(
    data_fixture, field_type, operator, negated, formula, case
):
    """Exercise SQL filtering, including JSON formulas, duplicate labels and empty rows."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(
        user,
        table,
        field_type,
        name="Selection",
        select_options=[
            {"value": "Alpha", "color": "blue"},
            {"value": "Beta", "color": "green"},
            {"value": 'Fruit, "Fresh"', "color": "red"},
        ],
    )
    alpha, beta, comma = field.select_options.order_by("id")
    duplicate = data_fixture.create_select_option(
        field=field, value="Alpha", color="orange"
    )
    numeric = data_fixture.create_select_option(
        field=field, value=str(alpha.id), color="purple"
    )
    target = (
        FieldHandler().create_field(
            user, table, "formula", name="Computed", formula="field('Selection')"
        )
        if formula
        else field
    )
    assignments = [[alpha.id], [beta.id], [comma.id], [duplicate.id], [numeric.id], []]
    if field_type == "multiple_select":
        assignments.append([alpha.id, beta.id])
    created = (
        RowHandler()
        .create_rows(
            user,
            table,
            [
                {
                    field.db_column: values
                    if field_type == "multiple_select"
                    else (values[0] if values else None)
                }
                for values in assignments
            ],
        )
        .created_rows
    )
    kind = view_filter_type_registry.get(operator)
    if case == "label":
        value = "Alpha"
        matching = {alpha.id, duplicate.id}
    elif case == "id":
        # A label containing the same digits must not override the existing ID.
        value = str(alpha.id)
        matching = {alpha.id}
    elif case == "comma":
        value = (
            kind.prepare_value(['Fruit, "Fresh"'])
            if kind.accepts_multiple_values
            else 'Fruit, "Fresh"'
        )
        matching = {comma.id}
    elif case == "unknown":
        value = "missing label"
        matching = set()
    else:
        value = (
            kind.prepare_value([str(alpha.id), "Beta"])
            if kind.accepts_multiple_values
            else "Beta"
        )
        matching = {alpha.id, beta.id} if kind.accepts_multiple_values else {beta.id}
    expected = {
        row.id
        for row, values in zip(created, assignments)
        if bool(matching.intersection(values)) != negated
    }
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(view=view, field=target, type=operator, value=value)
    result = list(
        ViewHandler()
        .apply_filters(view, table.get_model().objects.all())
        .values_list("id", flat=True)
    )
    assert set(result) == expected
    assert len(result) == len(expected)


@pytest.mark.parametrize("operator", [item[1] for item in OPERATORS])
def test_selection_filter_import_preserves_labels_and_remaps_ids(operator):
    kind = view_filter_type_registry.get(operator)
    mapping = {"database_field_select_options": {12: 112}}
    assert kind.set_import_serialized_value("Alpha", mapping) == "Alpha"
    assert kind.set_import_serialized_value("12", mapping) == "112"
    label = 'Fruit, "Fresh"'
    original = (
        kind.prepare_value(["12", label]) if kind.accepts_multiple_values else label
    )
    expected = (
        kind.prepare_value(["112", label]) if kind.accepts_multiple_values else label
    )
    assert kind.set_import_serialized_value(original, mapping) == expected


@pytest.mark.django_db
@pytest.mark.parametrize("operator", ["multiple_select_has", "multiple_select_has_not"])
def test_multiple_select_label_ignores_unused_and_foreign_options(
    data_fixture, operator
):
    """Labels of unused options, here or in another table, must not change results."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(
        user,
        table,
        "multiple_select",
        name="Tags",
        select_options=[
            {"value": "Foo", "color": "blue"},
            {"value": "Bar", "color": "green"},
        ],
    )
    foo, bar = field.select_options.order_by("id")
    # An unused option with the same label in this field, and one in another table.
    data_fixture.create_select_option(field=field, value="Foo", color="red")
    other = data_fixture.create_multiple_select_field(user=user)
    data_fixture.create_select_option(field=other, value="Foo")
    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            [
                {field.db_column: [foo.id]},
                {field.db_column: [bar.id]},
                {field.db_column: []},
            ],
        )
        .created_rows
    )
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(view=view, field=field, type=operator, value="Foo")

    result = set(
        ViewHandler()
        .apply_filters(view, table.get_model().objects.all())
        .values_list("id", flat=True)
    )

    if operator == "multiple_select_has":
        assert result == {rows[0].id}
    else:
        assert result == {rows[1].id, rows[2].id}
