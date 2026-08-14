import dataclasses
from typing import Callable, Union

from django.db.models import Q, QuerySet

from baserow.core.formula import BaserowFormulaException

NO_FORMULAS = Q(pk__in=[])
ALL_FORMULAS = ~NO_FORMULAS

FORMULAS_USING_INDEX = Q(internal_formula__contains="index(")


FormulaMigrationSelector = Union[Q, Callable[[QuerySet], Q]]


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
    ]
)
# The current version is the last migration.
BASEROW_FORMULA_VERSION = FORMULA_MIGRATIONS.get_latest_version()
