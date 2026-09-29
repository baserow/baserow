from unittest.mock import patch

from django.db import connection
from django.db.models import Q

import pytest

from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.formula.migrations.handler import FormulaMigrationHandler
from baserow.contrib.database.formula.migrations.migrations import (
    ALL_FORMULAS,
    BASEROW_FORMULA_VERSION,
    FORMULA_MIGRATIONS,
    FORMULAS_USING_INDEX,
    NO_FORMULAS,
    FormulaMigration,
    FormulaMigrations,
)
from baserow.contrib.database.rows.handler import RowHandler


def assert_all_rows_are_none(data_fixture, field):
    for i, row in enumerate(data_fixture.get_rows([field])):
        assert row[0] is None, "Row {i} was not None however we expected it to be none"


def assert_all_rows_are_not_none(data_fixture, field):
    for i, row in enumerate(data_fixture.get_rows([field])):
        assert (
            row[0] is not None
        ), "Row {i} was None however we expected it to be not None"


def assert_when_updating_formula_versions(
    data_fixture,
    given_formulas_with_version_in_the_db,
    when_the_migrations_are,
    then_formula_cell_values_are_recalculated,
    given_the_formula_is="1",
    given_the_formula_field_is=None,
):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[], []])
    if given_the_formula_field_is is None:
        formula_field = data_fixture.create_formula_field(
            formula=given_the_formula_is, calculate_cell_values=False
        )
    else:
        formula_field = given_the_formula_field_is

    FormulaField.objects.update(version=given_formulas_with_version_in_the_db)
    assert_all_rows_are_none(data_fixture, formula_field)

    FormulaMigrationHandler.migrate_formulas(when_the_migrations_are)
    if then_formula_cell_values_are_recalculated:
        assert_all_rows_are_not_none(data_fixture, formula_field)
    else:
        assert_all_rows_are_none(data_fixture, formula_field)


@pytest.mark.django_db
def test_assert_migrations_are_valid():
    # Migrations should be ascending order starting from 1 and always incrementing only
    # by 1.
    for i, migration in enumerate(FORMULA_MIGRATIONS):
        assert migration.version == i + 1


@pytest.mark.django_db
def test_migration_including_field_which_should_recalculate_its_attributes(
    data_fixture,
):
    previous_internal_formula_value = "'some old formula'"
    formula_field = data_fixture.create_formula_field(
        formula="1",
        internal_formula=previous_internal_formula_value,
        version=1,
        recalculate=False,
    )
    assert formula_field.internal_formula == previous_internal_formula_value

    data_fixture.create_rows_in_table(formula_field.table, [[], []])

    FormulaField.objects.update(version=1)
    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    # Assert the internal fields were recalculated by the migration
    formula_field.refresh_from_db()
    assert formula_field.internal_formula != previous_internal_formula_value


@pytest.mark.django_db
def test_migration_excluding_field_which_shouldnt_recalculate_its_attributes(
    data_fixture,
):
    previous_internal_formula_value = "'some old formula'"
    formula_field = data_fixture.create_formula_field(
        formula="1",
        internal_formula=previous_internal_formula_value,
        version=1,
        recalculate=False,
    )
    assert formula_field.internal_formula == previous_internal_formula_value

    data_fixture.create_rows_in_table(formula_field.table, [[], []])

    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    # Assert the internal fields were not recalculated by the migration.
    formula_field.refresh_from_db()
    assert formula_field.internal_formula == previous_internal_formula_value


@pytest.mark.django_db
def test_migration_excluding_field_which_shouldnt_recalculate_its_attributes_from(
    data_fixture,
):
    previous_internal_formula_value = "'some old formula'"
    formula_field = data_fixture.create_formula_field(
        formula="1",
        internal_formula=previous_internal_formula_value,
        version=1,
        recalculate=False,
    )
    assert formula_field.internal_formula == previous_internal_formula_value

    data_fixture.create_rows_in_table(formula_field.table, [[], []])

    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    # Assert the internal fields were not recalculated by the migration.
    formula_field.refresh_from_db()
    assert formula_field.internal_formula == previous_internal_formula_value


@pytest.mark.django_db
def test_migration_including_field_for_dep_recalc_recalcs_its_deps(
    data_fixture,
):
    previous_internal_formula_value = "'some old formula'"
    other_formula_field = data_fixture.create_formula_field(
        formula="1",
        internal_formula=previous_internal_formula_value,
    )
    formula_with_dependency_to_be_recalced = data_fixture.create_formula_field(
        table=other_formula_field.table,
        formula=f"field('{other_formula_field.name}')",
        internal_formula=previous_internal_formula_value,
    )
    formula_with_dependency_not_to_be_recalced = data_fixture.create_formula_field(
        table=other_formula_field.table,
        formula=f"field('{other_formula_field.name}')",
        internal_formula=previous_internal_formula_value,
    )
    assert formula_with_dependency_to_be_recalced.dependencies.count() == 1
    assert formula_with_dependency_not_to_be_recalced.dependencies.count() == 1

    FieldDependency.objects.all().delete()

    data_fixture.create_rows_in_table(
        formula_with_dependency_to_be_recalced.table, [[], []]
    )

    FormulaField.objects.update(version=1)
    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=Q(
                        id=formula_with_dependency_to_be_recalced.id
                    ),
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    # Formula field was recalculated as migration v2 matches it
    assert formula_with_dependency_to_be_recalced.dependencies.count() == 1
    # The other one didn't match the migration so its deleted deps weren't rebuilt
    assert formula_with_dependency_not_to_be_recalced.dependencies.count() == 0


@pytest.mark.django_db
def test_downgrade_recalculates_attributes_and_graph_but_not_cell_values(
    data_fixture,
):
    previous_internal_formula_value = "'some old formula'"
    other_field = data_fixture.create_text_field()

    data_fixture.create_rows_in_table(other_field.table, [[], []])

    formula_field = data_fixture.create_formula_field(
        table=other_field.table,
        formula=f"field('{other_field.name}')",
        internal_formula=previous_internal_formula_value,
        version=10,
        recalculate=False,
        calculate_cell_values=False,
        setup_dependencies=False,
    )
    assert formula_field.internal_formula == previous_internal_formula_value
    assert formula_field.dependencies.count() == 0

    assert_all_rows_are_none(data_fixture, formula_field)

    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    formula_field.refresh_from_db()
    assert formula_field.internal_formula != previous_internal_formula_value
    assert formula_field.dependencies.count() == 1
    # The downgrade didn't recalc cell values
    assert_all_rows_are_none(data_fixture, formula_field)


@pytest.mark.django_db
def test_recalculate_formulas_according_to_version_needing_full_refresh(
    data_fixture,
):
    # Passing over a version that needs recalculation of cells does it
    assert_when_updating_formula_versions(
        data_fixture,
        given_formulas_with_version_in_the_db=0,
        when_the_migrations_are=FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=ALL_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=3,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        ),
        then_formula_cell_values_are_recalculated=True,
    )
    # Going to the refresh version works
    assert_when_updating_formula_versions(
        data_fixture,
        given_formulas_with_version_in_the_db=0,
        when_the_migrations_are=FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=3,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=ALL_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        ),
        then_formula_cell_values_are_recalculated=True,
    )

    # Upgrading from the latest version that needs a refresh doesn't refresh cells
    assert_when_updating_formula_versions(
        data_fixture,
        given_formulas_with_version_in_the_db=0,
        when_the_migrations_are=FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        ),
        then_formula_cell_values_are_recalculated=False,
    )


@pytest.mark.django_db
def test_recalculate_formula_that_is_broken_marks_it_as_invalid(
    data_fixture,
):
    formula_that_raises_when_deps_recalculated = data_fixture.create_formula_field(
        formula="invalid syntax",
        formula_type="number",
        requires_refresh_after_insert=True,
        name="needs_refresh",
        setup_dependencies=False,
        calculate_cell_values=False,
    )
    other_formula = data_fixture.create_formula_field(
        table=formula_that_raises_when_deps_recalculated.table,
        formula=f"1+1",
        name="other_formula",
        calculate_cell_values=False,
    )
    formula_that_raises_when_deps_recalculated.formula_type = "text"
    formula_that_raises_when_deps_recalculated.error = None
    formula_that_raises_when_deps_recalculated.save(recalculate=False)
    formula_that_raises_when_deps_recalculated.refresh_from_db()
    assert formula_that_raises_when_deps_recalculated.error is None

    FormulaField.objects.update(version=1)
    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=ALL_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    formula_that_raises_when_deps_recalculated.refresh_from_db()
    assert formula_that_raises_when_deps_recalculated.error is not None
    assert formula_that_raises_when_deps_recalculated.formula_type == "invalid"


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.database.formula.FormulaHandler.baserow_expression_to_update_django_expression",
)
def test_formula_migration_failing_when_refreshing_cell_values_marks_as_invalid(
    mock_generator_func,
    data_fixture,
):
    mock_generator_func.side_effect = Exception(
        "Make this formula crash on SQL generation"
    )
    table = data_fixture.create_database_table()
    model = table.get_model()
    row = model.objects.create()
    formula_that_raises_when_refreshed = data_fixture.create_formula_field(
        formula="0",
        internal_formula="0",
        formula_type="number",
        number_decimal_places=1,
        name="needs_refresh",
        table=table,
        recalculate=False,
        setup_dependencies=False,
        calculate_cell_values=False,
        version=1,
    )

    FormulaField.objects.update(version=1)
    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=ALL_FORMULAS,
                    recalculate_cell_values_for=ALL_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    formula_that_raises_when_refreshed.refresh_from_db()
    assert formula_that_raises_when_refreshed.error is not None
    assert formula_that_raises_when_refreshed.formula_type == "invalid"


@pytest.mark.django_db
def test_recalculate_formulas_according_to_version(
    data_fixture,
):
    old_version = 0
    version_to_update_to = 1

    formula_with_default_internal_field = data_fixture.create_formula_field(
        formula="1",
        internal_formula="",
        requires_refresh_after_insert=False,
        name="a",
        version=old_version,
        recalculate=False,
        create_field=False,
    )
    formula_that_needs_refresh = data_fixture.create_formula_field(
        formula="row_id()",
        internal_formula="",
        formula_type="number",
        requires_refresh_after_insert=False,
        name="b",
        version=old_version,
        recalculate=False,
        create_field=False,
    )
    broken_reference_formula = data_fixture.create_formula_field(
        formula="field('unknown')",
        internal_formula="",
        requires_refresh_after_insert=False,
        name="c",
        version=old_version,
        recalculate=False,
        create_field=False,
    )
    dependant_formula = data_fixture.create_formula_field(
        table=formula_that_needs_refresh.table,
        formula="field('b')",
        internal_formula="",
        requires_refresh_after_insert=False,
        name="d",
        version=old_version,
        recalculate=False,
        create_field=False,
    )
    upto_date_formula_depending_on_old_version = data_fixture.create_formula_field(
        table=dependant_formula.table,
        formula=f"field('{dependant_formula.name}')",
        internal_formula="",
        requires_refresh_after_insert=False,
        name="f",
        version=version_to_update_to,
        recalculate=False,
        create_field=False,
    )
    assert dependant_formula.version == old_version

    FormulaField.objects.update(version=old_version)

    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        )
    )

    formula_with_default_internal_field.refresh_from_db()
    assert formula_with_default_internal_field.internal_formula == "error_to_nan(1)"
    assert not formula_with_default_internal_field.requires_refresh_after_insert

    formula_that_needs_refresh.refresh_from_db()
    assert formula_that_needs_refresh.internal_formula == "error_to_nan(row_id())"
    assert formula_that_needs_refresh.requires_refresh_after_insert

    broken_reference_formula.refresh_from_db()
    assert broken_reference_formula.internal_formula == "field('unknown')"
    assert broken_reference_formula.formula_type == "invalid"
    assert not broken_reference_formula.requires_refresh_after_insert

    dependant_formula.refresh_from_db()
    assert (
        dependant_formula.internal_formula
        == f"error_to_nan(field('{formula_that_needs_refresh.db_column}'))"
    )

    upto_date_formula_depending_on_old_version.refresh_from_db()
    assert (
        upto_date_formula_depending_on_old_version.field_dependencies.get().specific
        == dependant_formula
    )
    assert (
        upto_date_formula_depending_on_old_version.internal_formula
        == f"error_to_nan(field('{dependant_formula.db_column}'))"
    )


@pytest.mark.django_db
def test_complex_set_of_migrations_with_different_filters(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user)
    previous_internal_formula_value = "'some old formula'"

    data_fixture.create_rows_in_table(table, [[], []])
    other_formula_field = data_fixture.create_formula_field(
        formula="1", internal_formula=previous_internal_formula_value, table=table
    )
    formula_with_dependency_to_be_recalced = data_fixture.create_formula_field(
        table=table,
        formula=f"field('{other_formula_field.name}')",
        internal_formula=previous_internal_formula_value,
    )
    formula_with_dependency_not_to_be_recalced = data_fixture.create_formula_field(
        table=table,
        formula=f"field('{other_formula_field.name}')",
        internal_formula=previous_internal_formula_value,
    )
    assert formula_with_dependency_to_be_recalced.dependencies.count() == 1
    assert formula_with_dependency_not_to_be_recalced.dependencies.count() == 1

    previous_text_formula = "'old'"
    previous_bool_formula = "false"
    previous_num_formula = "2"
    formula_of_type_text_to_be_refreshed = data_fixture.create_formula_field(
        table=table,
        formula=f"'a'",
        internal_formula=previous_text_formula,
        calculate_cell_values=False,
    )
    formula_of_type_bool_to_only_recalc_attrs = data_fixture.create_formula_field(
        table=table,
        formula=f"true",
        internal_formula=previous_bool_formula,
        calculate_cell_values=False,
    )
    formula_of_type_number_to_recreate_col = data_fixture.create_formula_field(
        table=table,
        formula=f"1",
        internal_formula=previous_num_formula,
        calculate_cell_values=False,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table.get_database_table_name()} ALTER COLUMN "
            f"{formula_of_type_number_to_recreate_col.db_column} TYPE text USING "
            f"{formula_of_type_number_to_recreate_col.db_column}::text;"
        )
    assert_all_rows_are_none(data_fixture, formula_of_type_text_to_be_refreshed)
    assert_all_rows_are_none(data_fixture, formula_of_type_bool_to_only_recalc_attrs)
    assert_all_rows_are_none(data_fixture, formula_of_type_number_to_recreate_col)

    FieldDependency.objects.all().delete()

    FormulaField.objects.update(version=1)
    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=ALL_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=2,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=Q(
                        id=formula_with_dependency_to_be_recalced.id
                    ),
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=3,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=NO_FORMULAS,
                    recalculate_cell_values_for=Q(formula_type="text"),
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
                FormulaMigration(
                    version=4,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=Q(formula_type="bool"),
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=Q(formula_type="number"),
                ),
            ]
        )
    )

    # Formula field was recalculated as migration v2 matches it
    assert formula_with_dependency_to_be_recalced.dependencies.count() == 1
    # The other one didn't match the migration so its deleted deps weren't rebuilt
    assert formula_with_dependency_not_to_be_recalced.dependencies.count() == 0

    formula_of_type_text_to_be_refreshed.refresh_from_db()
    assert_all_rows_are_not_none(data_fixture, formula_of_type_text_to_be_refreshed)
    assert (
        formula_of_type_text_to_be_refreshed.internal_formula
        != previous_internal_formula_value
    )

    formula_of_type_bool_to_only_recalc_attrs.refresh_from_db()
    assert_all_rows_are_none(data_fixture, formula_of_type_bool_to_only_recalc_attrs)
    assert (
        formula_of_type_bool_to_only_recalc_attrs.internal_formula
        != previous_bool_formula
    )

    formula_of_type_number_to_recreate_col.refresh_from_db()
    assert_all_rows_are_not_none(data_fixture, formula_of_type_number_to_recreate_col)
    assert (
        formula_of_type_number_to_recreate_col.internal_formula != previous_num_formula
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"select data_type from "
            f"information_schema.columns where table_name = '"
            f"{table.get_database_table_name()}' and column_name = '"
            f"{formula_of_type_number_to_recreate_col.db_column}'"
        )
        assert [r[0] for r in cursor.fetchall()] == ["numeric"]


@pytest.mark.django_db
def test_can_force_recalculate_for_formulas_with_invalid_syntax_or_of_error_type(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user)

    data_fixture.create_rows_in_table(table, [[], []])

    data_fixture.create_formula_field(
        table=table,
        formula=f"field('invalid')",
        formula_type="error",
        error="Missing field",
        calculate_cell_values=False,
    )
    data_fixture.create_formula_field(
        table=table,
        formula=f"invalid syntax",
        formula_type="error",
        error="Missing field",
        calculate_cell_values=False,
        setup_dependencies=False,
    )
    previous_num_formula = "2"
    formula_of_type_number_to_recreate_col = data_fixture.create_formula_field(
        table=table,
        formula=f"1",
        internal_formula=previous_num_formula,
        calculate_cell_values=False,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table.get_database_table_name()} ALTER COLUMN "
            f"{formula_of_type_number_to_recreate_col.db_column} TYPE text USING "
            f"{formula_of_type_number_to_recreate_col.db_column}::text;"
        )
    assert_all_rows_are_none(data_fixture, formula_of_type_number_to_recreate_col)

    FormulaField.objects.update(version=0)
    FormulaMigrationHandler.migrate_formulas(
        FormulaMigrations(
            [
                FormulaMigration(
                    version=1,
                    recalculate_formula_attributes_for=NO_FORMULAS,
                    recalculate_field_dependencies_for=Q(formula_type="bool"),
                    recalculate_cell_values_for=NO_FORMULAS,
                    force_recreate_formula_columns_for=Q(formula_type="number"),
                ),
            ]
        )
    )

    formula_of_type_number_to_recreate_col.refresh_from_db()
    assert_all_rows_are_not_none(data_fixture, formula_of_type_number_to_recreate_col)
    assert (
        formula_of_type_number_to_recreate_col.internal_formula != previous_num_formula
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"select data_type from "
            f"information_schema.columns where table_name = '"
            f"{table.get_database_table_name()}' and column_name = '"
            f"{formula_of_type_number_to_recreate_col.db_column}'"
        )
        assert [r[0] for r in cursor.fetchall()] == ["numeric"]


# v6 stopped writing index()'s 4th argument. These cover upgrading an instance
# whose stored internal formulas still carry one of the older shapes.


def _index_formula_on_a_file_field(data_fixture, formula, name="idx"):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_file_field(table=table, name="Files", primary=True)
    RowHandler().create_rows(user, table, [{}])
    field = FieldHandler().create_field(
        user, table, "formula", name=name, formula=formula
    )
    return user, table, field


@pytest.mark.django_db
def test_v6_rewrites_a_legacy_four_argument_internal_formula(data_fixture):
    _, _, field = _index_formula_on_a_file_field(
        data_fixture, "index(field('Files'), 0)"
    )

    legacy = field.internal_formula[:-1] + ",'{elem}')"
    FormulaField.objects.filter(id=field.id).update(internal_formula=legacy, version=5)

    FormulaMigrationHandler.migrate_formulas_to_latest_version()

    field.refresh_from_db()
    assert "{elem}" not in field.internal_formula
    assert field.version == BASEROW_FORMULA_VERSION


@pytest.mark.django_db
def test_v6_rewrites_a_legacy_two_argument_internal_formula(data_fixture):
    """Pre-2.2.0 rows carry no mode and evaluate as text, breaking jsonb callers."""

    _, _, field = _index_formula_on_a_file_field(
        data_fixture, "get_file_visible_name(index(field('Files'),0))"
    )

    legacy = field.internal_formula.replace(",'single_file')", ")")
    assert legacy != field.internal_formula
    FormulaField.objects.filter(id=field.id).update(internal_formula=legacy, version=5)

    FormulaMigrationHandler.migrate_formulas_to_latest_version()

    field.refresh_from_db()
    assert "'single_file'" in field.internal_formula
    assert field.version == BASEROW_FORMULA_VERSION


@pytest.mark.django_db
def test_v6_selector_matches_index_formulas_only(data_fixture):
    user, table, indexed = _index_formula_on_a_file_field(
        data_fixture, "index(field('Files'), 0)", name="indexed"
    )
    shortcut = FieldHandler().create_field(
        user, table, "formula", name="shortcut", formula="first(field('Files'))"
    )
    unrelated = FieldHandler().create_field(
        user, table, "formula", name="unrelated", formula="'a' + 'b'"
    )

    matched = set(
        FormulaField.objects.filter(FORMULAS_USING_INDEX).values_list("id", flat=True)
    )

    assert indexed.id in matched
    assert shortcut.id in matched, "first()/last() expand to index() internally"
    assert unrelated.id not in matched
