from collections import defaultdict
from typing import TYPE_CHECKING, List

from django.db.models import Q

if TYPE_CHECKING:
    from baserow.contrib.database.fields import models as field_models

from baserow.contrib.database.fields.dependencies.circular_reference_checker import (
    will_cause_circular_dep,
)
from baserow.contrib.database.fields.dependencies.exceptions import (
    CircularFieldDependencyError,
)
from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.field_cache import FieldCache


def break_dependencies_for_field(field):
    """
    Given a specific field ensures no fields depend on it any more, and if they do
    those dependencies are set to be broken and only reference the field name.

    :param field: The field whose dependants will have their relationships broken for.
    """

    from baserow.contrib.database.fields.models import LinkRowField

    FieldDependency.objects.filter(dependant=field).delete()
    field.dependants.update(dependency=None, broken_reference_field_name=field.name)
    if isinstance(field, LinkRowField):
        field.vias.all().delete()


def update_fields_with_broken_references(fields: List["field_models.Field"]):
    """
    Checks to see if there are any fields which should now depend on `field` if it's
    name has changed to match a broken reference.

    :param fields: The field that has potentially just been renamed.
    :return: True if some fields were found which now depend on field, False otherwise.
    """

    if len(fields) == 0:
        return False

    # Create a map so that we can later get the right field based on the table id and
    # field name to set the correct dependency.
    table_field_map = {}
    field_names_per_table = defaultdict(list)
    for field in fields:
        table_field_map[(field.table_id, field.name)] = field
        field_names_per_table[field.table_id].append(field.name)

    # We need to fetch the broken dependencies for all the provided in one query, so we
    # can chain a big or statement to fetch them all.
    q = Q()
    for table_id, field_names in field_names_per_table.items():
        q |= Q(
            dependant__table_id=table_id,
            broken_reference_field_name__in=field_names,
        )
        q |= Q(
            via__link_row_table_id=table_id,
            broken_reference_field_name__in=field_names,
        )

    broken_dependencies = FieldDependency.objects.filter(q).select_related(
        "dependant", "via"
    )
    updated_deps = []
    for dep in broken_dependencies:
        key = (dep.dependant.table_id, dep.broken_reference_field_name)
        field = table_field_map.get(key)
        if not field:
            key = (dep.via.link_row_table_id, dep.broken_reference_field_name)
            field = table_field_map.get(key)
        if not field:
            raise ValueError("Field matching broken dependencies not found.")
        # Unfortunately, the `will_cause_circular_dep` still causes N number of
        # queries, but that's only if broken dependencies have been found.
        if not will_cause_circular_dep(dep.dependant, field):
            dep.dependency = field
            dep.broken_reference_field_name = None
            updated_deps.append(dep)

    if updated_deps:
        FieldDependency.objects.bulk_update(
            updated_deps, ["dependency", "broken_reference_field_name"]
        )

    return len(updated_deps) > 0


def rebuild_fields_dependencies(
    field_instances,
    field_cache: FieldCache,
) -> List[FieldDependency]:
    """
    Deletes all existing dependencies a field has and resets them to the ones
    defined by the field_instances FieldType.get_field_dependencies. Does not
    affect any dependencies from other fields to this field.

    :param field_instances: The field whose dependencies to change.
    :param field_cache: A cache which will be used to lookup the actual
        fields referenced by any provided field dependencies.
    :return: Any new dependencies created by the rebuild.
    """

    from baserow.contrib.database.fields.registries import field_type_registry

    all_new_dependencies_to_create = []
    all_deleted_dependency_ids = []
    all_current_dependencies = FieldDependency.objects.filter(
        dependant_id__in=[f.id for f in field_instances]
    )

    for field_instance in field_instances:
        field_type = field_type_registry.get_by_model(field_instance)
        new_dependencies = field_type.get_field_dependencies(
            field_instance, field_cache
        )
        current_dependencies = [
            dependency
            for dependency in all_current_dependencies
            if dependency.dependant_id == field_instance.id
        ]

        # The str of a dependency can be used to compare two dependencies to see if they
        # are functionally the same.
        current_deps_by_str = {str(dep): dep for dep in current_dependencies}
        new_deps_by_str = {str(dep): dep for dep in new_dependencies}
        new_dependencies_to_create = []

        for new_dep_str, new_dep in new_deps_by_str.items():
            try:
                # By removing from current_deps_by_str once we have finished the loop
                # it will contain all the old dependencies we need to delete.
                current_deps_by_str.pop(new_dep_str)
            except KeyError:
                # The new dependency does not exist in the current dependencies so we
                # must create it.
                new_dependencies_to_create.append(new_dep)

        for dep in new_dependencies_to_create:
            # Unfortunately, the `will_cause_circular_dep` still causes N number of
            # queries, but that's only if new dependencies must be created.
            if dep.dependency is not None and will_cause_circular_dep(
                field_instance, dep.dependency
            ):
                raise CircularFieldDependencyError()

        all_new_dependencies_to_create += new_dependencies_to_create

        # All new dependencies will have been removed from current_deps_by_str and so
        # any remaining ones are old dependencies which should no longer exist.
        # Delete them.
        all_deleted_dependency_ids += [dep.id for dep in current_deps_by_str.values()]

    if all_new_dependencies_to_create:
        new_dependencies = FieldDependency.objects.bulk_create(
            all_new_dependencies_to_create
        )

    if len(all_deleted_dependency_ids) > 0:
        FieldDependency.objects.filter(pk__in=all_deleted_dependency_ids).delete()

    return new_dependencies
