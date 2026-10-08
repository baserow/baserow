import re
from unittest.mock import Mock, patch

from django.core.exceptions import FieldDoesNotExist
from django.db import OperationalError, connection
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.dependencies.handler import (
    FieldDependencyHandler,
)
from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.formula import FormulaHandler
from baserow.contrib.database.formula.migrations.handler import (
    MAX_BATCH_RETRIES,
    FormulaMigrationHandler,
)
from baserow.contrib.database.formula.migrations.migrations import (
    ALL_FORMULAS,
    BASEROW_FORMULA_VERSION,
    FORMULA_MIGRATIONS,
    FORMULAS_USING_INDEX,
    NO_FORMULAS,
    FormulaMigration,
    FormulaMigrations,
    SelectedOncePerRun,
    formula_ids_with_stale_field_references,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewFilter, ViewGroupBy
from baserow.core.exceptions import DeadlockException
from baserow.core.psycopg import errors


def assert_all_rows_are_none(data_fixture, field):
    for i, row in enumerate(data_fixture.get_rows([field])):
        assert row[0] is None, "Row {i} was not None however we expected it to be none"


def assert_all_rows_are_not_none(data_fixture, field):
    for i, row in enumerate(data_fixture.get_rows([field])):
        assert row[0] is not None, (
            "Row {i} was None however we expected it to be not None"
        )


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


@pytest.mark.django_db
def test_migration_recalculates_cell_values_without_jit(data_fixture):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[], []])
    formula_field = data_fixture.create_formula_field(
        table=table, formula="1", calculate_cell_values=False
    )
    FormulaField.objects.update(version=1)
    jit_per_update = []

    def record_jit(execute, sql, params, many, context):
        if isinstance(sql, str) and sql.startswith(
            f'UPDATE "database_table_{table.id}" SET "{formula_field.db_column}"'
        ):
            with context["connection"].connection.cursor() as cursor:
                cursor.execute("SHOW jit")
                jit_per_update.append(cursor.fetchone()[0])
        return execute(sql, params, many, context)

    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL jit = on")
    with connection.execute_wrapper(record_jit):
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
                        recalculate_cell_values_for=ALL_FORMULAS,
                        force_recreate_formula_columns_for=NO_FORMULAS,
                    ),
                ]
            )
        )

    assert jit_per_update == ["off"]
    assert_all_rows_are_not_none(data_fixture, formula_field)


def _lookup_of_a_link_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    linked = data_fixture.create_database_table(database=database)
    further = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True)
    data_fixture.create_text_field(table=linked, primary=True)
    old_primary = data_fixture.create_text_field(table=further, primary=True)
    new_primary = data_fixture.create_text_field(table=further)
    link = FieldHandler().create_field(
        user, table, "link_row", link_row_table=linked, name="link"
    )
    link_of_link = FieldHandler().create_field(
        user, linked, "link_row", link_row_table=further, name="link_of_link"
    )
    lookup = FieldHandler().create_field(
        user,
        table,
        "lookup",
        name="lookup",
        through_field_id=link.id,
        target_field_id=link_of_link.id,
    )
    further_row = RowHandler().create_row(
        user,
        further,
        {old_primary.db_column: "old", new_primary.db_column: "new"},
    )
    linked_row = RowHandler().create_row(
        user, linked, {link_of_link.db_column: [further_row.id]}
    )
    row = RowHandler().create_row(user, table, {link.db_column: [linked_row.id]})
    return user, table, lookup, row, further_row, old_primary, new_primary


def _cell(table, row, field):
    return str(getattr(table.get_model().objects.get(id=row.id), field.db_column))


@pytest.mark.django_db
@pytest.mark.parametrize("old_primary_state", ["deleted", "trashed", "kept"])
def test_v7_recalculates_a_lookup_of_a_link_field_with_an_outdated_primary_field(
    data_fixture, old_primary_state
):
    (
        user,
        table,
        lookup,
        row,
        further_row,
        old_primary,
        new_primary,
    ) = _lookup_of_a_link_field(data_fixture)
    stale_internal_formula = lookup.internal_formula
    assert old_primary.db_column in stale_internal_formula

    FieldHandler().change_primary_field(user, new_primary.table, new_primary)
    old_primary.refresh_from_db()
    if old_primary_state == "deleted":
        old_primary.delete()
    elif old_primary_state == "trashed":
        FieldHandler().delete_field(user, old_primary)
    FormulaField.objects.update(version=6)
    FormulaField.objects.filter(id=lookup.id).update(
        internal_formula=stale_internal_formula
    )
    invalidate_table_in_model_cache(table.id)
    if old_primary_state == "deleted":
        with pytest.raises(FieldDoesNotExist, match=old_primary.db_column):
            RowHandler().create_row(user, table, {})
    elif old_primary_state == "trashed":
        with pytest.raises(ValueError, match=old_primary.db_column):
            RowHandler().create_row(user, table, {})
    else:
        RowHandler().update_row_by_id(
            user, new_primary.table, further_row.id, {new_primary.db_column: "new"}
        )
        assert "old" in _cell(table, row, lookup)

    FormulaMigrationHandler.migrate_formulas_to_latest_version()

    lookup.refresh_from_db()
    assert new_primary.db_column in lookup.internal_formula
    assert lookup.formula_type == "array"
    assert lookup.version == BASEROW_FORMULA_VERSION
    assert "new" in _cell(table, row, lookup)
    assert "old" not in _cell(table, row, lookup)
    RowHandler().create_row(user, table, {})


@pytest.mark.django_db
def test_v7_marks_a_formula_inlining_a_deleted_link_field_as_invalid(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    linked = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True)
    data_fixture.create_text_field(table=linked, primary=True, name="name")
    link = FieldHandler().create_field(
        user, table, "link_row", link_row_table=linked, name="link"
    )
    lookup = FieldHandler().create_field(
        user,
        table,
        "lookup",
        name="lookup",
        through_field_id=link.id,
        target_field_name="name",
    )
    count = FieldHandler().create_field(
        user, table, "formula", name="count", formula="count(field('lookup'))"
    )
    assert link.db_column in count.internal_formula

    # The link field is deleted without its dependants being updated.
    link.link_row_related_field.delete()
    link.delete()
    FormulaField.objects.update(version=6)
    invalidate_table_in_model_cache(table.id)
    with pytest.raises(FieldDoesNotExist, match=link.db_column):
        RowHandler().create_row(user, table, {})

    FormulaMigrationHandler.migrate_formulas_to_latest_version()

    lookup.refresh_from_db()
    count.refresh_from_db()
    assert lookup.formula_type == "invalid"
    assert count.formula_type == "invalid"
    assert FieldDependency.objects.filter(
        dependant=lookup, broken_reference_field_name="link"
    ).exists()
    RowHandler().create_row(user, table, {})


@pytest.mark.django_db
def test_v7_selector_matches_formulas_with_stale_field_references_only(
    data_fixture,
):
    user, table, lookup, _, _, old_primary, _ = _lookup_of_a_link_field(data_fixture)
    healthy = FieldHandler().create_field(
        user, table, "formula", name="healthy", formula="lookup('link', 'link_of_link')"
    )
    unrelated = FieldHandler().create_field(
        user, table, "formula", name="unrelated", formula="'a' + 'b'"
    )
    long_literal = FieldHandler().create_field(
        user, table, "formula", name="long_literal", formula=f"'field_{'1' * 4301}'"
    )
    FormulaField.objects.filter(id=lookup.id).update(
        internal_formula=lookup.internal_formula.replace(
            old_primary.db_column, "field_999999999"
        )
    )

    selected = formula_ids_with_stale_field_references()

    assert lookup.id in selected
    assert healthy.id not in selected
    assert unrelated.id not in selected
    # A literal that looks like a reference only costs a needless recalculation.
    assert long_literal.id in selected


@pytest.mark.django_db
def test_v7_updates_the_formulas_depending_on_a_recalculated_formula(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    linked = data_fixture.create_database_table(database=database)
    further = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True)
    data_fixture.create_text_field(table=linked, primary=True)
    data_fixture.create_text_field(table=further, primary=True)
    number = data_fixture.create_number_field(table=further)
    link = FieldHandler().create_field(
        user, table, "link_row", link_row_table=linked, name="link"
    )
    FieldHandler().create_field(
        user, linked, "link_row", link_row_table=further, name="link_of_link"
    )
    first_val = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="first_val",
        formula="first(lookup('link', 'link_of_link'))",
    )
    shout = FieldHandler().create_field(
        user, table, "formula", name="shout", formula="upper(field('first_val'))"
    )
    lookup_in_linked_table = FieldHandler().create_field(
        user,
        linked,
        "lookup",
        name="lookup_of_first_val",
        through_field_id=link.link_row_related_field_id,
        target_field_id=first_val.id,
    )
    assert lookup_in_linked_table.array_formula_type == "text"
    # The primary field becomes a number while the formulas keep their text state.
    stale_state = {
        values.pop("field_ptr_id"): values
        for values in FormulaField.objects.filter(
            id__in=[first_val.id, shout.id, lookup_in_linked_table.id]
        ).values()
    }
    FieldHandler().change_primary_field(user, further, number)
    for field_id, values in stale_state.items():
        FormulaField.objects.filter(id=field_id).update(**values)
    FormulaField.objects.update(version=6)
    invalidate_table_in_model_cache(table.id)

    FormulaMigrationHandler.migrate_formulas_to_latest_version()

    first_val.refresh_from_db()
    shout.refresh_from_db()
    lookup_in_linked_table.refresh_from_db()
    assert first_val.formula_type == "number"
    assert shout.formula_type == "invalid"
    assert lookup_in_linked_table.array_formula_type == "number"
    RowHandler().create_row(user, table, {})
    RowHandler().create_row(user, linked, {})


def _migrate_with_a_failing_cell_update(side_effect):
    with (
        patch(
            "baserow.contrib.database.formula.migrations.handler.FormulaHandler"
            ".recalculate_formula_and_get_update_expression",
            side_effect=side_effect,
        ),
        patch("baserow.core.db.time.sleep"),
    ):
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
                        recalculate_cell_values_for=ALL_FORMULAS,
                        force_recreate_formula_columns_for=NO_FORMULAS,
                    ),
                ]
            )
        )


@pytest.mark.django_db
def test_migration_marks_a_formula_invalid_when_its_cell_update_fails(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_rows_in_table(table, [[]])
    failing = data_fixture.create_formula_field(table=table, formula="'a'")
    grid = data_fixture.create_grid_view(table=table)
    ViewHandler().create_filter(user, grid, failing, "equal", "a")
    ViewHandler().create_group_by(user, grid, failing, "ASC", 200)
    assert _cells(table, failing) == ["a"]
    FormulaField.objects.update(version=1)

    _migrate_with_a_failing_cell_update(
        side_effect=lambda *args, **kwargs: RawSQL("(1 / 0)::text", [])
    )

    failing.refresh_from_db()
    assert failing.formula_type == "invalid"
    assert failing.error == "Failed to recalculate cell values after formula update."
    assert failing.version == 2
    assert _cells(table, failing) == [None]
    assert not ViewFilter.objects.filter(field=failing).exists()
    assert not ViewGroupBy.objects.filter(field=failing).exists()


def _cells(table, field):
    return [
        getattr(row, field.db_column)
        for row in table.get_model().objects_and_trash.order_by("id")
    ]


TRANSIENT_ERRORS = [
    errors.DeadlockDetected,
    errors.LockNotAvailable,
    errors.QueryCanceled,
    errors.SerializationFailure,
]


def _transient_error(error_class):
    error = OperationalError(error_class.__name__)
    error.__cause__ = error_class(error_class.__name__)
    return error


@pytest.mark.django_db
@pytest.mark.parametrize("error_class", TRANSIENT_ERRORS)
def test_migration_retries_a_batch_after_a_transient_error(data_fixture, error_class):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[]])
    formula = data_fixture.create_formula_field(
        table=table, formula="'a'", calculate_cell_values=False
    )
    FormulaField.objects.update(version=1)

    recalculate = FormulaHandler.recalculate_formula_and_get_update_expression
    calls = []

    def fail_once(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise _transient_error(error_class)
        return recalculate(*args, **kwargs)

    _migrate_with_a_failing_cell_update(side_effect=fail_once)

    formula.refresh_from_db()
    assert len(calls) == 2
    assert formula.formula_type == "text"
    assert formula.error is None
    assert formula.version == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error_class,expected_exception",
    [
        (errors.DeadlockDetected, DeadlockException),
        (errors.LockNotAvailable, OperationalError),
        (errors.QueryCanceled, OperationalError),
        (errors.SerializationFailure, OperationalError),
    ],
)
def test_migration_raises_when_a_transient_error_keeps_failing(
    data_fixture, error_class, expected_exception
):
    table = data_fixture.create_database_table()
    formula = data_fixture.create_formula_field(table=table, formula="'a'")
    FormulaField.objects.update(version=1)
    recalculate = Mock(side_effect=_transient_error(error_class))

    with pytest.raises(expected_exception):
        _migrate_with_a_failing_cell_update(side_effect=recalculate)

    assert recalculate.call_count == MAX_BATCH_RETRIES + 1

    formula.refresh_from_db()
    assert formula.formula_type == "text"
    assert formula.version == 1


def _migrate_with_a_selector(selector, batch_size):
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
                    recalculate_field_dependencies_for=selector,
                    recalculate_cell_values_for=selector,
                    force_recreate_formula_columns_for=NO_FORMULAS,
                ),
            ]
        ),
        batch_size=batch_size,
    )


@pytest.mark.django_db
def test_migration_selects_once_per_run_across_batches(data_fixture):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[]])
    formulas = [
        data_fixture.create_formula_field(
            table=table, formula=f"'{i}'", calculate_cell_values=False
        )
        for i in range(3)
    ]
    FormulaField.objects.update(version=1)
    select_formula_ids = Mock(return_value={formulas[1].id})

    _migrate_with_a_selector(SelectedOncePerRun(select_formula_ids), batch_size=1)

    select_formula_ids.assert_called_once()
    assert [_cells(table, formula) for formula in formulas] == [[None], ["1"], [None]]
    assert set(FormulaField.objects.values_list("version", flat=True)) == {2}


@pytest.mark.django_db
def test_migration_locks_only_the_formulas_it_recalculates(data_fixture):
    table = data_fixture.create_database_table()
    formulas = [
        data_fixture.create_formula_field(table=table, formula=f"'{i}'")
        for i in range(3)
    ]
    FormulaField.objects.update(version=1)

    with CaptureQueriesContext(connection) as queries:
        _migrate_with_a_selector(
            SelectedOncePerRun(lambda: {formulas[1].id}), batch_size=10
        )

    locking_queries = [q["sql"] for q in queries if "FOR UPDATE" in q["sql"]]
    assert len(locking_queries) == 1
    locked_ids = re.search(r"IN \(([^)]*)\)", locking_queries[0]).group(1)
    assert locked_ids.replace(" ", "").split(",") == [str(formulas[1].id)]


@pytest.mark.django_db
def test_v7_updates_the_dependants_of_a_formula_first_recalculated_as_dependency(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    linked = data_fixture.create_database_table(database=database)
    further = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(table=table, primary=True)
    data_fixture.create_text_field(table=linked, primary=True)
    data_fixture.create_text_field(table=further, primary=True)
    number = data_fixture.create_number_field(table=further)
    link = FieldHandler().create_field(
        user, table, "link_row", link_row_table=linked, name="link"
    )
    FieldHandler().create_field(
        user, linked, "link_row", link_row_table=further, name="link_of_link"
    )
    values = FieldHandler().create_field(
        user, table, "formula", name="values", formula="lookup('link', 'link_of_link')"
    )
    reader = FieldHandler().create_field(
        user,
        linked,
        "lookup",
        name="reader",
        through_field_id=link.link_row_related_field_id,
        target_field_id=values.id,
    )
    # The primary formula inlines `values`, so it's stale too and processed first.
    primary = FieldHandler().update_field(
        user, primary, "formula", formula="join(totext(field('values')), ',')"
    )
    stale_state = {
        state.pop("field_ptr_id"): state
        for state in FormulaField.objects.filter(
            id__in=[values.id, reader.id, primary.id]
        ).values()
    }
    FieldHandler().change_primary_field(user, further, number)
    for field_id, field_values in stale_state.items():
        FormulaField.objects.filter(id=field_id).update(**field_values)
    FormulaField.objects.update(version=6)
    invalidate_table_in_model_cache(table.id)
    invalidate_table_in_model_cache(linked.id)

    FormulaMigrationHandler.migrate_formulas_to_latest_version()

    reader.refresh_from_db()
    assert reader.array_formula_type == "number"
    RowHandler().create_row(user, linked, {})


@pytest.mark.django_db
def test_migration_retries_a_batch_after_a_transient_error_in_a_dependency_rebuild(
    data_fixture,
):
    table = data_fixture.create_database_table()
    formula = data_fixture.create_formula_field(table=table, formula="'a'")
    FormulaField.objects.update(version=1)
    deadlock = OperationalError("deadlock detected")
    deadlock.__cause__ = errors.DeadlockDetected("deadlock detected")
    rebuild = FieldDependencyHandler.rebuild_dependencies
    calls = []

    def deadlock_once(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise deadlock
        return rebuild(*args, **kwargs)

    with (
        patch(
            "baserow.contrib.database.fields.dependencies.handler"
            ".FieldDependencyHandler.rebuild_dependencies",
            side_effect=deadlock_once,
        ),
        patch("baserow.core.db.time.sleep"),
    ):
        _migrate_with_a_selector(
            SelectedOncePerRun(lambda: {formula.id}), batch_size=10
        )

    formula.refresh_from_db()
    assert len(calls) == 2
    assert formula.formula_type == "text"
    assert formula.version == 2


@pytest.mark.django_db
def test_migration_refreshes_dependants_of_recalculated_cells_with_the_same_type(
    data_fixture,
):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[]])
    formula = data_fixture.create_formula_field(table=table, name="f", formula="'a'")
    dependant = data_fixture.create_formula_field(
        table=table, name="g", formula="concat(field('f'), 'x')"
    )
    table.get_model().objects_and_trash.update(
        **{formula.db_column: None, dependant.db_column: None}
    )
    FormulaField.objects.update(version=1)

    with patch(
        "baserow.contrib.database.formula.migrations.handler.SearchHandler"
        ".schedule_update_search_data"
    ) as schedule_update_search_data:
        _migrate_with_a_selector(
            SelectedOncePerRun(lambda: {formula.id}), batch_size=10
        )

    assert _cells(table, formula) == ["a"]
    assert _cells(table, dependant) == ["ax"]
    scheduled_fields = [
        field
        for call in schedule_update_search_data.call_args_list
        for field in call.kwargs["fields"]
    ]
    assert formula.id in [field.id for field in scheduled_fields]


@pytest.mark.django_db
def test_migration_continues_when_updating_the_views_of_a_formula_fails(
    data_fixture,
):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[]])
    failing = data_fixture.create_formula_field(table=table, formula="'a'")
    FormulaField.objects.update(version=1)

    with patch(
        "baserow.contrib.database.views.handler.ViewHandler.field_updated",
        side_effect=ValueError("view hook failed"),
    ):
        _migrate_with_a_failing_cell_update(
            side_effect=lambda *args, **kwargs: RawSQL("(1 / 0)::text", [])
        )

    failing.refresh_from_db()
    assert failing.formula_type == "invalid"
    assert failing.version == 2


@pytest.mark.django_db
def test_migration_reports_a_failure_to_empty_the_cells_of_an_invalid_formula(
    data_fixture,
):
    table = data_fixture.create_database_table()
    data_fixture.create_rows_in_table(table, [[]])
    failing = data_fixture.create_formula_field(table=table, formula="'a'")
    FormulaField.objects.update(version=1)
    error = ValueError("recreate failed")

    with (
        patch(
            "baserow.contrib.database.formula.types.typer"
            ".recreate_formula_field_if_needed",
            side_effect=error,
        ),
        patch(
            "baserow.contrib.database.formula.migrations.handler.exception_capturer"
        ) as capturer,
    ):
        _migrate_with_a_failing_cell_update(
            side_effect=lambda *args, **kwargs: RawSQL("(1 / 0)::text", [])
        )

    failing.refresh_from_db()
    assert failing.formula_type == "invalid"
    capturer.assert_any_call(error)


@pytest.mark.django_db
def test_migration_skips_when_only_trashed_formulas_are_out_of_date(data_fixture):
    table = data_fixture.create_database_table()
    formula = data_fixture.create_formula_field(table=table, formula="'a'")
    FormulaField.objects_and_trash.filter(id=formula.id).update(trashed=True, version=1)

    with patch(
        "baserow.contrib.database.formula.migrations.handler.FormulaMigrationHandler"
        "._migrate_batch_with_retries"
    ) as migrate_batch:
        FormulaMigrationHandler.migrate_formulas(FORMULA_MIGRATIONS)

    migrate_batch.assert_not_called()
