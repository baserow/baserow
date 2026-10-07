import time
import traceback
import typing
from copy import deepcopy
from typing import Dict, List, Set

from django.db import OperationalError, transaction
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
    SelectedOncePerRun,
)
from baserow.core.db import jit_disabled
from baserow.core.psycopg import is_transient_error
from baserow.core.utils import ChildProgressBuilder, Progress

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


DEFAULT_FORMULA_MIGRATION_BATCH_SIZE = 100
MAX_BATCH_ATTEMPTS = 3
BATCH_RETRY_BACKOFF_SECONDS = 1.0


def _recalculate_formula_metadata_dependencies_first_order(
    field: "Field",
    field_cache: FieldCache,
    recalculate_cell_values: bool,
    force_recreate_columns: bool,
    already_recalculated: Set[int],
    update_dependants: bool = False,
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
    :param update_dependants: Whether to update the fields depending on the provided
        field after its cell values are recalculated, like a field update does.
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
                # The savepoint lets the formula be marked as invalid below when a
                # query fails, instead of aborting the whole batch.
                with transaction.atomic():
                    model = field_cache.get_model(field.table)
                    expr = FormulaHandler.recalculate_formula_and_get_update_expression(
                        field,
                        old_field,
                        field_cache,
                        force_recreate_column=force_recreate_columns,
                    )
                    with jit_disabled():
                        model.objects_and_trash.all().update(
                            **{f"{field.db_column}": expr}
                        )
            except Exception as e:
                if is_transient_error(e):
                    raise
                field.mark_as_invalid_and_save(
                    "Failed to recalculate cell values after formula update."
                )
                logger.warning(
                    f"""During formula update change failed to recalculate formula
{field.name} with id {field.id} in {field.table.name} with id {field.table.id} with
formula {field.formula}. Marking the formula as invalid. The error was caused by:
{traceback.format_exception_only(type(e), e)}"""
                )
            _after_formula_recalculated(field)
            if update_dependants:
                _update_dependants(field, old_field, field_cache)
        already_recalculated.add(field.id)


def _after_formula_recalculated(field: "Field"):
    """
    Removes the view filters, sorts and group bys that the formula's type no longer
    supports, like a field update does.
    """

    from baserow.contrib.database.views.handler import ViewHandler

    fields_type_changed.send(
        _recalculate_formula_metadata_dependencies_first_order, fields=[field]
    )
    ViewHandler().field_updated(field)


def _update_dependants(field: "Field", old_field: "Field", field_cache: FieldCache):
    from baserow.contrib.database.fields.dependencies.update_collector import (
        FieldUpdateCollector,
    )
    from baserow.contrib.database.fields.handler import FieldHandler

    try:
        with transaction.atomic():
            FieldHandler().update_dependencies_of_field_updated(
                field, old_field, FieldUpdateCollector(field.table), field_cache
            )
    except Exception as e:
        if is_transient_error(e):
            raise
        logger.warning(
            f"Failed to update the fields depending on formula {field.name} with id "
            f"{field.id} in {field.table.name} with id {field.table.id}. The error "
            f"was caused by: {traceback.format_exception_only(type(e), e)}"
        )


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

        out_of_date_formulas = FormulaField.objects.filter(
            ~Q(version=migrations.get_latest_version())
        )
        total_out_of_date_formulas = out_of_date_formulas.count()
        if total_out_of_date_formulas == 0:
            return

        oldest_version_in_db_currently = FormulaField.objects.aggregate(
            min=Min("version")
        )["min"]
        selected_once_per_run = cls._select_once_per_run(
            oldest_version_in_db_currently, migrations
        )

        logger.info(
            f"Found {total_out_of_date_formulas} formulas to migrate "
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

            # Batches walk the formulas by id, so each one starts after the previous
            # one instead of scanning past all the formulas already migrated.
            last_id = 0
            while True:
                current_batch += 1
                batch_ids = cls._migrate_batch_with_retries(
                    out_of_date_formulas.filter(id__gt=last_id),
                    batch_size,
                    oldest_version_in_db_currently,
                    migrations,
                    selected_once_per_run,
                    progress,
                )
                if not batch_ids:
                    break
                last_id = batch_ids[-1]
            progress_bar.set_description("Finished migrating formulas")

    @classmethod
    def _select_once_per_run(
        cls, current_version: int, migrations: FormulaMigrations
    ) -> Dict[SelectedOncePerRun, Set[int]]:
        latest_version = migrations.get_latest_version()
        if current_version > latest_version:
            return {}

        selected = {}
        for m in migrations[current_version:latest_version]:
            for selector in (
                m.recalculate_formula_attributes_for,
                m.recalculate_field_dependencies_for,
                m.recalculate_cell_values_for,
                m.force_recreate_formula_columns_for,
            ):
                if (
                    isinstance(selector, SelectedOncePerRun)
                    and selector not in selected
                ):
                    selected[selector] = selector.select_formula_ids()
        return selected

    @classmethod
    def _migrate_batch_with_retries(
        cls,
        remaining_formulas: QuerySet,
        batch_size: int,
        current_version: int,
        migrations: FormulaMigrations,
        selected_once_per_run: Dict[SelectedOncePerRun, Set[int]],
        progress: Progress,
    ) -> List[int]:
        """
        Migrates the next batch of formulas in its own transaction, so a run never
        locks too many tables at once and hits the "out of shared memory" error. The
        batch is retried when it fails on contention or a timeout.

        :return: The ids of the formulas in the batch, empty when none are left.
        """

        for attempt in range(1, MAX_BATCH_ATTEMPTS + 1):
            try:
                with transaction.atomic():
                    batch_ids = list(
                        remaining_formulas.order_by("id").values_list("id", flat=True)[
                            :batch_size
                        ]
                    )
                    if batch_ids:
                        cls._update_formulas(
                            batch_ids,
                            current_version,
                            migrations,
                            selected_once_per_run,
                            progress.create_child_builder(
                                represents_progress=len(batch_ids)
                            ),
                        )
                    return batch_ids
            except OperationalError as e:
                if not is_transient_error(e) or attempt == MAX_BATCH_ATTEMPTS:
                    raise
                logger.warning(
                    f"Retrying a formula migration batch after a transient error: {e}"
                )
                time.sleep(BATCH_RETRY_BACKOFF_SECONDS * attempt)

    @classmethod
    def _update_formulas(
        cls,
        batch_ids: List[int],
        current_version: int,
        migrations: FormulaMigrations,
        selected_once_per_run: Dict[SelectedOncePerRun, Set[int]],
        child_progress_builder: ChildProgressBuilder,
    ):
        from baserow.contrib.database.fields.models import FormulaField

        latest_version = migrations.get_latest_version()
        batch = FormulaField.objects.filter(id__in=batch_ids)
        querysets, affected_filter = cls._get_formula_querysets(
            batch, set(batch_ids), current_version, migrations, selected_once_per_run
        )
        affected_ids = list(batch.filter(affected_filter).values_list("id", flat=True))

        if affected_ids:
            # Only the formulas that are recalculated are locked, so a concurrent run
            # waits for them and then skips them as they're already migrated.
            locked_ids = list(
                FormulaField.objects.filter(id__in=affected_ids)
                .exclude(version=latest_version)
                .select_for_update()
                .values_list("id", flat=True)
            )
            cls._do_formula_migration_operations(
                *[queryset.filter(id__in=locked_ids) for queryset in querysets],
                child_progress_builder,
            )

        batch.exclude(version=latest_version).update(version=latest_version)

    @classmethod
    def _get_formula_querysets(
        cls,
        batch: QuerySet,
        batch_ids: Set[int],
        current_version,
        migrations: FormulaMigrations,
        selected_once_per_run: Dict[SelectedOncePerRun, Set[int]],
    ):
        """
        Given a list of migrations, figures out the current version and constructs
        the querysets of formulas onto which the different migration operations will
        be run respectively, and a filter matching any formula they contain.

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

            def get_q(selector: FormulaMigrationSelector):
                if isinstance(selector, SelectedOncePerRun):
                    return Q(id__in=selected_once_per_run[selector] & batch_ids)
                elif isinstance(selector, typing.Callable):
                    return selector(batch)
                else:
                    return selector

            for m in relevant_migrations:
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
            batch.filter(attribute_filter)
            .exclude(recalculate_cell_values_filter)
            .exclude(force_recreate_columns_filter)
        )
        formulas_to_rebuild_dependencies_for = batch.filter(rebuild_dependencies_filter)
        formulas_to_recalculate_cell_values_for = batch.filter(
            recalculate_cell_values_filter
        ).exclude(force_recreate_columns_filter)
        formulas_to_force_recreate_columns_for = batch.filter(
            force_recreate_columns_filter
        )
        affected_filter = (
            attribute_filter
            | rebuild_dependencies_filter
            | recalculate_cell_values_filter
            | force_recreate_columns_filter
        )
        return (
            formulas_to_rebuild_dependencies_for,
            formulas_to_recalculate_cell_values_for,
            formulas_to_only_update_attributes_for,
            formulas_to_force_recreate_columns_for,
        ), affected_filter

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
                update_dependants=True,
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
