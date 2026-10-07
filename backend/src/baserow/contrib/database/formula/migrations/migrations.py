import dataclasses
from typing import Callable, Set, Union

from django.db import connection
from django.db.models import Q, QuerySet

from baserow.core.formula import BaserowFormulaException

NO_FORMULAS = Q(pk__in=[])
ALL_FORMULAS = ~NO_FORMULAS

FORMULAS_USING_INDEX = Q(internal_formula__contains="index(")


@dataclasses.dataclass(frozen=True)
class SelectedOncePerRun:
    """
    Selects formulas with one query over all formulas, made once at the start of a
    migration run instead of once per batch.
    """

    select_formula_ids: Callable[[], Set[int]]


FormulaMigrationSelector = Union[Q, Callable[[QuerySet], Q], SelectedOncePerRun]


@dataclasses.dataclass
class FormulaMigration:
    """
    Represents how to migrate to a particular version of the Baserow formula language.
    """

    """
    The formula version id.
    """
    version: int

    """
    If this version requires formulas from older versions to have their FormulaField
    attributes to be recalculated set the filter which matches FormulaField's here.

    Normally for most formula upgrades this should be ALL_FORMULAS (see

    Specifically this will control which FormulaField's have `.save(recalculate=True)`
    called on them (which recalculates their attributes given the current formula
    version)
    """
    recalculate_formula_attributes_for: FormulaMigrationSelector

    """
    If this version requires formulas from older versions to have their field
    dependencies recalculated using FieldDependencyHandler.rebuild_dependencies then
    provide a filter here matching the formula fields that should have this done.

    Most

    This will be done prior to any attribute or cell value recalculation in the
    migration.
    """
    recalculate_field_dependencies_for: FormulaMigrationSelector

    """
    If this version requires formulas from older versions to have their actual cell
    values to be recalculated then provide a filter here matching the formula fields
    that should have this done.
    """
    recalculate_cell_values_for: FormulaMigrationSelector

    """
    If this version requires formulas from older versions to have their entire columns
    recreated from scratch and repopulated with cell values then provide a filter here
    matching the formula fields that should have this done.
    """
    force_recreate_formula_columns_for: FormulaMigrationSelector


class FormulaMigrations(list):
    def get_latest_version(self) -> int:
        return super().__getitem__(-1).version


def formula_ids_with_stale_field_references() -> Set[int]:
    """
    Returns the ids of the formulas whose internal formula references a field that
    is trashed or deleted, or reaches through a link field to a field that is no
    longer the primary field of the linked table.
    """

    from baserow.contrib.database.fields.models import (
        Field,
        FormulaField,
        LinkRowField,
    )

    # Field ids are capped at 18 digits so that they always fit in a bigint.
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT reference.formula_id
            FROM (
                SELECT
                    formula.field_ptr_id AS formula_id,
                    found[1]::bigint AS field_id,
                    found[2]::bigint AS primary_field_id
                FROM {FormulaField._meta.db_table} formula
                CROSS JOIN LATERAL regexp_matches(
                    formula.internal_formula,
                    'field_(\\d{{1,18}})(?:__field_(\\d{{1,18}}))?',
                    'g'
                ) AS found
            ) reference
            LEFT JOIN {Field._meta.db_table} field
                ON field.id = reference.field_id AND NOT field.trashed
            LEFT JOIN {LinkRowField._meta.db_table} link
                ON link.field_ptr_id = reference.field_id
            LEFT JOIN {Field._meta.db_table} primary_field
                ON primary_field.table_id = link.link_row_table_id
                AND primary_field."primary"
                AND NOT primary_field.trashed
            WHERE field.id IS NULL
                OR (
                    reference.primary_field_id IS NOT NULL
                    AND primary_field.id IS DISTINCT FROM reference.primary_field_id
                )
            """  # noqa: S608
        )
        return {row[0] for row in cursor.fetchall()}


FORMULAS_WITH_STALE_FIELD_REFERENCES = SelectedOncePerRun(
    formula_ids_with_stale_field_references
)


def all_aggregate_formulas(formulas: QuerySet) -> Q:
    aggregate_formula_ids = []
    for f in formulas:
        try:
            if f.cached_untyped_expression.aggregate:
                aggregate_formula_ids.append(f.id)
        except BaserowFormulaException:
            continue
    return Q(id__in=aggregate_formula_ids)


# A list containing all Baserow formula versions and how to migrate to them. The last
# item in the last is always the latest formula version. The versions in this list
# must increment by one per version.
#
# When migrating from one version to another the FormulaMigrationHandler will use this
# list to calculate which formulas to recalculate attributes/cell values/
# field dependencies for. It will OR together all Q filters in the versions being
# updated through/to.
FORMULA_MIGRATIONS = FormulaMigrations(
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
        FormulaMigration(
            version=3,
            recalculate_formula_attributes_for=ALL_FORMULAS,
            # v3 fixes various dep graph issues.
            recalculate_field_dependencies_for=ALL_FORMULAS,
            # v3 fixes a bug where a date cell could contain a BC date unsupported by
            # python.
            recalculate_cell_values_for=(
                Q(formula_type="date") | Q(array_formula_type="date")
            ),
            force_recreate_formula_columns_for=NO_FORMULAS,
        ),
        FormulaMigration(
            version=4,
            # v4 makes some previously incorrectly valid formulas invalid now as they
            # should have always been invalid e.g. sum(1).
            recalculate_formula_attributes_for=ALL_FORMULAS,
            recalculate_field_dependencies_for=NO_FORMULAS,
            recalculate_cell_values_for=NO_FORMULAS,
            force_recreate_formula_columns_for=NO_FORMULAS,
        ),
        FormulaMigration(
            version=5,
            # v5 Fixes formulas that reference other aggregate formulas.
            recalculate_formula_attributes_for=NO_FORMULAS,
            recalculate_field_dependencies_for=NO_FORMULAS,
            recalculate_cell_values_for=NO_FORMULAS,
            force_recreate_formula_columns_for=all_aggregate_formulas,
        ),
        FormulaMigration(
            version=6,
            # v6 drops index()'s 4th argument, so any internal formula still
            # carrying one has to be regenerated, and its cells recomputed since
            # the values they hold were produced by the older expression.
            recalculate_formula_attributes_for=FORMULAS_USING_INDEX,
            recalculate_field_dependencies_for=NO_FORMULAS,
            recalculate_cell_values_for=FORMULAS_USING_INDEX,
            force_recreate_formula_columns_for=NO_FORMULAS,
        ),
        FormulaMigration(
            version=7,
            # v7 recalculates formulas with stale field references, see
            # `formula_ids_with_stale_field_references`.
            recalculate_formula_attributes_for=NO_FORMULAS,
            recalculate_field_dependencies_for=FORMULAS_WITH_STALE_FIELD_REFERENCES,
            recalculate_cell_values_for=FORMULAS_WITH_STALE_FIELD_REFERENCES,
            force_recreate_formula_columns_for=NO_FORMULAS,
        ),
    ]
)
# The current version is the last migration.
BASEROW_FORMULA_VERSION = FORMULA_MIGRATIONS.get_latest_version()
