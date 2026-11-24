"""
Tests for applying and validating filter operations on a Local Baserow service.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from baserow.contrib.integrations.local_baserow.service_filters.registries import (
    service_filter_target_type_registry,
)
from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterOperation,
    FilterState,
    FilterValidationContext,
    ServiceFilterValidationError,
    StateFilter,
    StateGroup,
    apply_operations,
    get_compatible_filter_types,
)
from baserow.core.formula.types import BaserowFormulaObject


@dataclass
class BuilderSetup:
    user: Any
    workspace: Any
    table: Any
    name: Any
    status: Any
    amount: Any
    due: Any
    done_option: Any
    todo_option: Any
    data_source: Any


@pytest.fixture
def builder_setup(data_fixture) -> BuilderSetup:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    status = data_fixture.create_single_select_field(table=table, name="Status")
    done_option = data_fixture.create_select_option(field=status, value="Done")
    todo_option = data_fixture.create_select_option(field=status, value="Todo")
    amount = data_fixture.create_number_field(table=table, name="Amount")
    due = data_fixture.create_date_field(table=table, name="Due")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder,
        name="Task",
        path="/task/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, name="Tasks", table=table, integration=integration
    )
    return BuilderSetup(
        user,
        workspace,
        table,
        name,
        status,
        amount,
        due,
        done_option,
        todo_option,
        data_source,
    )


def validation_context(setup: BuilderSetup, check_formula=None):
    fields = {f.id: f.specific for f in setup.table.field_set.all()}
    return FilterValidationContext(
        fields=fields,
        compatible_types={
            field_id: get_compatible_filter_types(field)
            for field_id, field in fields.items()
        },
        select_options={
            setup.status.id: {
                setup.done_option.id: "Done",
                setup.todo_option.id: "Todo",
            }
        },
        check_formula=check_formula,
    )


def builder_formula_check(setup: BuilderSetup):
    return service_filter_target_type_registry.get(
        "builder_data_source"
    ).get_formula_check(setup.user, setup.data_source)


def raw(value: str) -> dict:
    return dict(BaserowFormulaObject.create(formula=value, mode="raw"))


def add_filter(**kwargs) -> FilterOperation:
    return FilterOperation(op="add_filter", **kwargs)


@pytest.mark.django_db
def test_compatible_filter_types_exclude_deprecated_date_filters(builder_setup):
    due_types = get_compatible_filter_types(builder_setup.due.specific)

    assert "date_is" in due_types
    assert "date_equals_day_of_month" in due_types
    assert "date_equal" not in due_types
    assert "date_equals_today" not in due_types
    assert "single_select_equal" in get_compatible_filter_types(
        builder_setup.status.specific
    )


@pytest.mark.django_db
def test_apply_operations_adds_groups_and_filters(builder_setup):
    s = builder_setup
    state = FilterState("AND", (), ())

    new_state = apply_operations(
        state,
        [
            add_filter(field_id=s.amount.id, type="higher_than", value="10"),
            FilterOperation(op="add_group", group_id="g1", filter_type="OR"),
            add_filter(
                field_id=s.status.id,
                type="single_select_equal",
                value=str(s.done_option.id),
                group="g1",
            ),
            add_filter(
                field_id=s.due.id,
                type="date_is",
                value="UTC??today",
                group="g1",
            ),
        ],
        validation_context(s),
    )

    assert new_state.filter_type == "AND"
    assert [g.id for g in new_state.groups] == ["g1"]
    assert [(f.type, f.group) for f in new_state.filters] == [
        ("higher_than", None),
        ("single_select_equal", "g1"),
        ("date_is", "g1"),
    ]
    assert new_state.filters[0].value == raw("10")


@pytest.mark.django_db
def test_apply_operations_updates_and_deletes_keeping_other_filters_untouched(
    builder_setup,
):
    s = builder_setup
    untouched = {"formula": "get('page_parameter.id')", "mode": "advanced"}
    state = FilterState(
        "AND",
        (
            # A value as stored, without a version: it must be kept as it is.
            _filter("1", s.name.id, "equal", untouched),
            _filter("2", s.amount.id, "higher_than", raw("5")),
            _filter("3", s.amount.id, "lower_than", raw("100")),
        ),
        (),
    )

    new_state = apply_operations(
        state,
        [
            FilterOperation(op="update_filter", filter_id="2", value="50"),
            FilterOperation(op="delete_filter", filter_id="3"),
            FilterOperation(op="set_filter_type", filter_type="OR"),
        ],
        validation_context(s),
    )

    assert new_state.filter_type == "OR"
    assert [f.id for f in new_state.filters] == ["1", "2"]
    assert new_state.filters[0].value is untouched
    assert new_state.filters[1].value == raw("50")


@pytest.mark.django_db
def test_apply_operations_delete_group_cascades(builder_setup):
    s = builder_setup
    state = FilterState(
        "AND",
        (
            _filter("1", s.amount.id, "higher_than", raw("5"), group="10"),
            _filter("2", s.amount.id, "lower_than", raw("9"), group="11"),
            _filter("3", s.name.id, "contains", raw("a")),
        ),
        (
            _group("10", "OR"),
            _group("11", "AND", parent="10"),
        ),
    )

    new_state = apply_operations(
        state,
        [FilterOperation(op="delete_group", group_id="10")],
        validation_context(s),
    )

    assert new_state.groups == ()
    assert [f.id for f in new_state.filters] == ["3"]


@pytest.mark.django_db
def test_apply_operations_keeps_hidden_filters_and_refuses_to_touch_them(
    builder_setup,
):
    s = builder_setup
    hidden = _filter("1", s.amount.id, "higher_than", raw("5"), hidden=True)
    state = FilterState("AND", (hidden,), ())

    with pytest.raises(ServiceFilterValidationError):
        apply_operations(
            state,
            [FilterOperation(op="delete_filter", filter_id="1")],
            validation_context(s),
        )

    new_state = apply_operations(
        state,
        [add_filter(field_id=s.name.id, type="contains", value="a")],
        validation_context(s),
    )
    assert new_state.filters[0] is hidden


@pytest.mark.django_db
def test_apply_operations_reports_every_invalid_filter(builder_setup, data_fixture):
    s = builder_setup
    other_field = data_fixture.create_text_field(name="Elsewhere")

    with pytest.raises(ServiceFilterValidationError) as exc:
        apply_operations(
            FilterState("AND", (), ()),
            [
                add_filter(field_id=other_field.id, type="equal", value="a"),
                add_filter(field_id=s.name.id, type="higher_than", value="1"),
                add_filter(
                    field_id=s.status.id, type="single_select_equal", value="Done"
                ),
                add_filter(field_id=s.due.id, type="date_is", value="2024-05-01"),
                add_filter(field_id=s.amount.id, type="lower_than", value="ten"),
                FilterOperation(op="add_group", group_id="empty", filter_type="OR"),
                FilterOperation(op="update_filter", filter_id="404", value="x"),
            ],
            validation_context(s),
        )

    errors = "\n".join(exc.value.errors)
    assert "doesn't exist in the table" in errors
    assert "'higher_than' can't be used on field 'Name'" in errors
    assert "invalid select option id(s)" in errors
    assert "invalid date filter value '2024-05-01'" in errors
    assert "'ten' is not a number" in errors
    assert "Group 'empty' was added without any filter" in errors
    assert "filter '404' doesn't exist" in errors


@pytest.mark.django_db
def test_apply_operations_validates_builder_formula_values(builder_setup):
    s = builder_setup
    ctx = validation_context(s, builder_formula_check(s))

    new_state = apply_operations(
        FilterState("AND", (), ()),
        [
            add_filter(
                field_id=s.name.id,
                type="equal",
                value="get('page_parameter.id')",
                value_is_formula=True,
            )
        ],
        ctx,
    )
    assert new_state.filters[0].value["formula"] == "get('page_parameter.id')"
    assert new_state.filters[0].value["mode"] == "advanced"

    for formula in (
        "get('page_parameter.slug')",
        "get('form_data.12')",
        f"get('data_source.{s.data_source.id}.0.id')",
        "get('page_parameter.id'",
    ):
        with pytest.raises(ServiceFilterValidationError) as exc:
            apply_operations(
                FilterState("AND", (), ()),
                [
                    add_filter(
                        field_id=s.name.id,
                        type="equal",
                        value=formula,
                        value_is_formula=True,
                    )
                ],
                ctx,
            )
        assert "invalid formula" in exc.value.errors[0], formula


@pytest.mark.django_db
def test_apply_operations_refuses_formula_values_without_formula_data(
    builder_setup,
):
    s = builder_setup

    with pytest.raises(ServiceFilterValidationError) as exc:
        apply_operations(
            FilterState("AND", (), ()),
            [
                add_filter(
                    field_id=s.name.id,
                    type="equal",
                    value="get('page_parameter.id')",
                    value_is_formula=True,
                )
            ],
            validation_context(s, check_formula=None),
        )

    assert "formula values can't be used here" in exc.value.errors[0]


@pytest.mark.django_db
def test_apply_operations_refuses_groups_when_not_supported(builder_setup):
    s = builder_setup
    ctx = validation_context(s)
    ctx.allow_filter_groups = False

    with pytest.raises(ServiceFilterValidationError) as exc:
        apply_operations(
            FilterState("AND", (), ()),
            [
                FilterOperation(op="add_group", group_id="g1", filter_type="OR"),
                add_filter(field_id=s.name.id, type="contains", value="a", group="g1"),
            ],
            ctx,
        )

    assert "filter groups can't be used here" in exc.value.errors[0]


def test_operation_requires_its_arguments():
    with pytest.raises(ValueError, match="add_filter requires: field_id"):
        FilterOperation(op="add_filter", type="equal")


def _filter(id, field_id, type, value, group=None, hidden=False):
    return StateFilter(
        id=id, field_id=field_id, type=type, value=value, group=group, hidden=hidden
    )


def _group(id, filter_type, parent=None):
    return StateGroup(id=id, filter_type=filter_type, parent_group=parent)


@pytest.mark.django_db
@pytest.mark.parametrize("filter_type", ["empty", "not_empty", "is_even_and_whole"])
def test_valueless_filters_reject_formulas(builder_setup, filter_type):
    """Keep raw valueless filters valid, but reject formulas they cannot consume."""
    s = builder_setup
    ctx = validation_context(s, lambda formula: None)
    operation = dict(field_id=s.amount.id, type=filter_type)
    result = apply_operations(
        FilterState("AND", (), ()),
        [FilterOperation(op="add_filter", **operation, value="")],
        ctx,
    )
    assert result.filters[0].type == filter_type
    with pytest.raises(ServiceFilterValidationError, match="doesn't take a value"):
        apply_operations(
            FilterState("AND", (), ()),
            [
                FilterOperation(
                    op="add_filter",
                    **operation,
                    value="1",
                    value_is_formula=True,
                )
            ],
            ctx,
        )


@pytest.mark.django_db
def test_custom_filter_inherits_value_requirement(builder_setup):
    """New filter types inherit validation behavior without adding their name to a list."""
    from baserow.contrib.database.views.registries import view_filter_type_registry
    from baserow.contrib.database.views.view_filters import IsEvenAndWholeViewFilterType

    class CustomEvenFilter(IsEvenAndWholeViewFilterType):
        type = "custom_even_filter"

    view_filter_type_registry.register(CustomEvenFilter())
    try:
        s = builder_setup
        ctx = validation_context(s, lambda formula: None)
        with pytest.raises(ServiceFilterValidationError, match="doesn't take a value"):
            apply_operations(
                FilterState("AND", (), ()),
                [
                    FilterOperation(
                        op="add_filter",
                        field_id=s.amount.id,
                        type="custom_even_filter",
                        value="1",
                        value_is_formula=True,
                    )
                ],
                ctx,
            )
    finally:
        view_filter_type_registry.unregister("custom_even_filter")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "base_name, field_name, value, expected_error",
    [
        ("higher_than", "amount", "not-a-number", "is not a number"),
        ("single_select_equal", "status", "999999999", "invalid select option"),
    ],
)
def test_custom_filter_inherits_raw_value_validation(
    builder_setup, base_name, field_name, value, expected_error
):
    """New numeric and select subtypes use their parent's validation automatically."""
    from baserow.contrib.database.views.registries import view_filter_type_registry

    base = type(view_filter_type_registry.get(base_name))
    custom_type = type("CustomFilter", (base,), {"type": "custom_value_filter"})
    view_filter_type_registry.register(custom_type())
    try:
        s = builder_setup
        ctx = validation_context(s)
        with pytest.raises(ServiceFilterValidationError, match=expected_error):
            apply_operations(
                FilterState("AND", (), ()),
                [
                    FilterOperation(
                        op="add_filter",
                        field_id=getattr(s, field_name).id,
                        type="custom_value_filter",
                        value=value,
                    )
                ],
                ctx,
            )
    finally:
        view_filter_type_registry.unregister("custom_value_filter")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [
        "1",
        "0",
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        "checked",
        "unchecked",
        "TRUE",
        "FALSE",
        "invalid",
    ],
)
def test_boolean_filters_use_shared_boolean_values(data_fixture, builder_setup, value):
    """Accept the field's boolean spellings while rejecting invalid filter values."""
    s = builder_setup
    field = data_fixture.create_boolean_field(table=s.table)
    ctx = validation_context(s)
    operation = FilterOperation(
        op="add_filter", field_id=field.id, type="boolean", value=value
    )
    if value == "invalid":
        with pytest.raises(ServiceFilterValidationError, match="invalid boolean value"):
            apply_operations(FilterState("AND", (), ()), [operation], ctx)
    else:
        result = apply_operations(FilterState("AND", (), ()), [operation], ctx)
        assert result.filters[0].value == raw(value)


@pytest.mark.django_db
@pytest.mark.parametrize("deprecated", [True, False])
def test_custom_filter_deprecation_controls_availability(builder_setup, deprecated):
    """Filter availability uses registered metadata rather than concrete classes."""
    from baserow.contrib.database.views.registries import view_filter_type_registry
    from baserow.contrib.database.views.view_filters import HigherThanViewFilterType

    custom = type(
        "CustomFilter",
        (HigherThanViewFilterType,),
        {
            "type": "custom_deprecated_filter",
            "deprecated": deprecated,
        },
    )
    view_filter_type_registry.register(custom())
    try:
        available = get_compatible_filter_types(builder_setup.amount.specific)
        assert ("custom_deprecated_filter" in available) is not deprecated
    finally:
        view_filter_type_registry.unregister("custom_deprecated_filter")
