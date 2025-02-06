import math
import traceback
import typing
from copy import deepcopy
from typing import Set

from django.db import transaction
from django.db.models import Min, Q, QuerySet

from loguru import logger
from tqdm import tqdm

from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.signals import fields_type_changed
from baserow.contrib.database.formula import FormulaHandler
from baserow.contrib.database.formula.migrations.migrations import (
    ALL_FORMULAS,
    FORMULA_MIGRATIONS,
    NO_FORMULAS,
    FormulaMigrations,
    FormulaMigrationSelector,
)
from baserow.core.utils import ChildProgressBuilder, Progress

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


DEFAULT_FORMULA_MIGRATION_BATCH_SIZE = 100


def _recalculate_formula_metadata_dependencies_first_order(
    field: "Field",
    field_cache: FieldCache,
    recalculate_cell_values: bool,
    force_recreate_columns: bool,
    already_recalculated: Set[int],
):
    """
    Initially follows the field dependency tree recursively from the provided field
    and recalculates all the fields dependencies first before recalculating the provided
    field.

    :param field: The field to recalculate its metadata and/or cell values for.
    :param field_cache: A cache using to stored queried fields.
    :param recalculate_cell_values: Whether to recalculate the cell values of the
        fields also and not just their metadata.
    :param already_recalculated: A set of field ids which have already been recalculated
        which will used to skip recalculating them again if encountered again.
    """

    from baserow.contrib.database.fields.models import FormulaField

    if field.id in already_recalculated:
        return True

    for dep in field.field_dependencies.all():
        _recalculate_formula_metadata_dependencies_first_order(
            dep,
            field_cache,
            recalculate_cell_values,
            force_recreate_columns,
            already_recalculated,
        )

    field = field_cache.lookup_specific(field)

    if isinstance(field, FormulaField):
        old_field = deepcopy(field)
        field.save(field_cache=field_cache, raise_if_invalid=False)
        if recalculate_cell_values or force_recreate_columns:
            try:
                model = field_cache.get_model(field.table)
                expr = FormulaHandler.recalculate_formula_and_get_update_expression(
                    field,
                    old_field,
                    field_cache,
                    force_recreate_column=force_recreate_columns,
                )
                model.objects_and_trash.all().update(**{f"{field.db_column}": expr})
                fields_type_changed.send(
                    _recalculate_formula_metadata_dependencies_first_order,
                    fields=[field]
                )
            except Exception as e:
                field.mark_as_invalid_and_save(
                    "Failed to recalculate cell values after formula update."
                )
                logger.warning(
                    f"""During formula update change failed to recalculate formula
{field.name} with id {field.id} in {field.table.name} with id {field.table.id} with
formula {field.formula}. Marking the formula as invalid. The error was caused by:
{traceback.format_exception_only(type(e), e)}"""
                )
        already_recalculated.add(field.id)


class FormulaMigrationHandler:
    @classmethod
    def migrate_formulas_to_latest_version(
        cls, batch_size: int = DEFAULT_FORMULA_MIGRATION_BATCH_SIZE
    ):
        """
        Migrates all formulas found in the database to the latest formula version.
        A formula migration is not like a normal database migration. A formula migration
        consists of the following steps:

        1. Find the oldest formula version in the db currently, stored in the
           FormulaField.version column.
        2. Get the list of migrations to get to the latest formula version.
        3. Loop over the list of migrations. Each migration specifies Q filter
           for each of the three "migration operations" that will be performed
           at the end. The Q filter says "to migrate past this version, this
           migration operation must be applied to these formulas".
        4. Now we have 3 querysets of formulas to apply the following operations
           too to actually perform the migration:
            1. Rebuild the formula's field dependencies.
            2. Recalculate the formula's internal attributes: re-type it, transform it,
               save the results onto the FormulaField model.
            3. Recalculate the formula's cell values given its recalculated attributes.
        5. Finally once we've applied the operations above to the relevant formulas we
           update their FormulaField.version column to the latest version.

        We don't perform a normal database migration to do this because:
        A Django migration cannot rely on code outside of it's file which might
        change. The formula code is large and complex, we can't copy it into each
        migration to ensure the migration will always work.

        Instead a formula migration is set of recalculations/updates per formula in the
        db given the current state of the code.
        """

        cls.migrate_formulas(FORMULA_MIGRATIONS, batch_size)

    @classmethod
    def migrate_formulas(
        cls,
        migrations: FormulaMigrations,
        batch_size: int = DEFAULT_FORMULA_MIGRATION_BATCH_SIZE,
    ):
        from baserow.contrib.database.fields.models import FormulaField

        oldest_version_in_db_currently = FormulaField.objects.aggregate(
            min=Min("version")
        )["min"]

        total_out_of_date_formulas = FormulaField.objects.filter(
            ~Q(version=migrations.get_latest_version())
        ).count()
        max_number_of_batches = math.ceil(total_out_of_date_formulas / batch_size)

        def get_locked_formula_batch_to_update() -> typing.Optional[QuerySet]:
            # In-case there is another concurrent formula migration is running we
            # want to lock the formulas we want to update. This effectively
            # serializes formula migrations running concurrently, but this is desirable
            # as otherwise they will often cause each other to crash due to deadlocks
            # if actually running concurrently.
            locked_formula_ids = (
                FormulaField.objects.filter(~Q(version=migrations[-1].version))
                .order_by("id")
                .select_for_update()[0:batch_size]
            )
            # Force the evaluation of the queryset so we know exactly what formulas
            # we have locked and future usages of the queryset won't lock another random
            # batch of formula fields.
            locked_formula_ids = [f.id for f in locked_formula_ids]
            if len(locked_formula_ids) == 0:
                return None
            else:
                return FormulaField.objects.filter(id__in=locked_formula_ids)

        logger.info(
            f"Found {max_number_of_batches} batches of formulas to migrate "
            f"from version {oldest_version_in_db_currently} to "
            f"{migrations.get_latest_version()}."
        )

        with tqdm(total=total_out_of_date_formulas) as progress_bar:
            current_batch = 0

            def progress_updated(percentage, state):
                progress_bar.set_description(f"Batch {current_batch}: " + (state or ""))
                progress_bar.update(progress.progress - progress_bar.n)

            progress = Progress(progress_bar.total)
            progress.register_updated_event(progress_updated)

            for _ in range(max_number_of_batches):
                current_batch += 1
                # We need to run formula migrations in batches, each in a separate
                # transaction to ensure we never hit the "out of shared memory" psql
                # error due to attempting to lock too many tables in the same
                # transaction.
                with transaction.atomic():
                    locked_formula_batch = get_locked_formula_batch_to_update()
                    if locked_formula_batch is None:
                        # We ran out of formulas to update, this should only happen
                        # if some concurrent other formula migration is updating at
                        # the same time.
                        progress.increment(
                            progress.total - progress.progress,
                            "Finished early due to another formula "
                            "migration running concurrently and updating batches "
                            "itself.",
                        )
                        return
                    else:
                        cls._update_formulas(
                            locked_formula_batch,
                            oldest_version_in_db_currently,
                            migrations,
                            progress.create_child_builder(
                                represents_progress=batch_size
                            ),
                        )
            progress_bar.set_description("Finished migrating formulas")

    @classmethod
    def _update_formulas(
        cls,
        locked_formula_batch: QuerySet,
        current_version: int,
        migrations: FormulaMigrations,
        child_progress_builder: ChildProgressBuilder,
    ):
        (
            formulas_to_rebuild_dependencies_for,
            formulas_to_recalculate_attributes_and_cell_values_for,
            formulas_to_only_update_attributes_for,
            formulas_to_force_recreate_columns_for,
        ) = cls._get_formula_querysets(
            locked_formula_batch, current_version, migrations
        )

        cls._do_formula_migration_operations(
            formulas_to_rebuild_dependencies_for,
            formulas_to_recalculate_attributes_and_cell_values_for,
            formulas_to_only_update_attributes_for,
            formulas_to_force_recreate_columns_for,
            child_progress_builder,
        )

        locked_formula_batch.update(version=migrations.get_latest_version())

    @classmethod
    def _get_formula_querysets(
        cls,
        locked_formula_batch: QuerySet,
        current_version,
        migrations: FormulaMigrations,
    ):
        """
        Given a list of migrations, figures out the current version and constructs
        the three querysets of formulas onto which the three different migration
        operations will be run respectively.

        :param migrations: All migrations available.
        """

        latest_version = migrations.get_latest_version()
        if current_version > latest_version:
            # When downgrading only recalculate the attributes and the graph.
            # Don't bother recalculating the cell values as it's very, very slow and
            # only likely to introduce back bugs that were fixed in newer versions.

            attribute_filter = ALL_FORMULAS
            rebuild_dependencies_filter = ALL_FORMULAS
            recalculate_cell_values_filter = NO_FORMULAS
            force_recreate_columns_filter = NO_FORMULAS
        else:
            relevant_migrations = migrations[current_version:latest_version]
            attribute_filter = NO_FORMULAS
            rebuild_dependencies_filter = NO_FORMULAS
            recalculate_cell_values_filter = NO_FORMULAS
            force_recreate_columns_filter = NO_FORMULAS
            for m in relevant_migrations:

                def get_q(selector: FormulaMigrationSelector):
                    if isinstance(selector, typing.Callable):
                        return selector(locked_formula_batch)
                    else:
                        return selector

                attribute_filter |= get_q(m.recalculate_formula_attributes_for)
                rebuild_dependencies_filter |= get_q(
                    m.recalculate_field_dependencies_for
                )
                recalculate_cell_values_filter |= get_q(m.recalculate_cell_values_for)
                force_recreate_columns_filter |= get_q(
                    m.force_recreate_formula_columns_for
                )

        # We will also recalculate the attributes when refreshing cell values,
        # no need to update attributes twice, so we exclude.
        formulas_to_only_update_attributes_for = (
            locked_formula_batch.filter(attribute_filter)
            .exclude(recalculate_cell_values_filter)
            .exclude(force_recreate_columns_filter)
        )
        formulas_to_rebuild_dependencies_for = locked_formula_batch.filter(
            rebuild_dependencies_filter
        )
        formulas_to_recalculate_cell_values_for = locked_formula_batch.filter(
            recalculate_cell_values_filter
        ).exclude(force_recreate_columns_filter)
        formulas_to_force_recreate_columns_for = locked_formula_batch.filter(
            force_recreate_columns_filter
        )
        return (
            formulas_to_rebuild_dependencies_for,
            formulas_to_recalculate_cell_values_for,
            formulas_to_only_update_attributes_for,
            formulas_to_force_recreate_columns_for,
        )

    @classmethod
    def _do_formula_migration_operations(
        cls,
        formulas_to_rebuild_dependencies_for: QuerySet,
        formulas_to_both_calc_attrs_and_refresh_cell_values_for: QuerySet,
        formulas_to_only_recalculate_attributes_for: QuerySet,
        formulas_to_force_recreate_columns_for: QuerySet,
        child_progress_builder: ChildProgressBuilder,
    ):
        from baserow.contrib.database.fields.dependencies.handler import (
            FieldDependencyHandler,
        )

        total_migration_operations = (
            formulas_to_rebuild_dependencies_for.count()
            + formulas_to_both_calc_attrs_and_refresh_cell_values_for.count()
            + formulas_to_only_recalculate_attributes_for.count()
            + formulas_to_force_recreate_columns_for.count()
        )
        progress = ChildProgressBuilder.build(
            child_progress_builder,
            total_migration_operations,
        )

        field_cache = FieldCache()
        already_recalculated = set()

        # First recalculate all formula dependencies to ensure they are correct and
        # upto date. This is needed because the new version might calculate
        # dependencies differently than the old version.

        for field in formulas_to_rebuild_dependencies_for.iterator():
            try:
                FieldDependencyHandler.rebuild_dependencies([field], field_cache)
            except Exception as e:
                logger.warning(
                    f"Failed to recalculate dependencies for field: "
                    f"{field.name}({field.id}) in {field.table.name}({field.table.id}) "
                    f"with formula {field.formula}. Skipping as we will later mark "
                    f"this formula as invalid when we recalculate its metadata. "
                    f"The error was caused by: "
                    f"{traceback.format_exception_only(type(e), e)}"
                )
            progress.increment(1, "Rebuilding field dependencies")

        # Now the dependency graph is correct we can starting from the dependencies
        # recalculate the formula metadata and cell values across the entire
        # dependency tree.

        for field in formulas_to_both_calc_attrs_and_refresh_cell_values_for.iterator():
            _recalculate_formula_metadata_dependencies_first_order(
                field,
                field_cache,
                recalculate_cell_values=True,
                force_recreate_columns=False,
                already_recalculated=already_recalculated,
            )
            progress.increment(1, "Recalculating metadata and data")

        for field in formulas_to_only_recalculate_attributes_for.iterator():
            _recalculate_formula_metadata_dependencies_first_order(
                field,
                field_cache,
                recalculate_cell_values=False,
                force_recreate_columns=False,
                already_recalculated=already_recalculated,
            )
            progress.increment(1, "Recalculating only metadata")

        for field in formulas_to_force_recreate_columns_for.iterator():
            _recalculate_formula_metadata_dependencies_first_order(
                field,
                field_cache,
                recalculate_cell_values=False,
                force_recreate_columns=True,
                already_recalculated=set(),
            )
            progress.increment(1, "Fully recreating formulas")
