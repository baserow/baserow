from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet

from baserow.contrib.database.fields.dependencies.dependency_rebuilder import (
    break_dependencies_for_field,
    rebuild_fields_dependencies,
    update_fields_with_broken_references,
)
from baserow.contrib.database.fields.dependencies.exceptions import (
    CircularFieldDependencyError,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.fields.registries import FieldType, field_type_registry
from baserow.contrib.database.table.models import Table
from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.types import PermissionCheck

from .models import FieldDependency

FieldDependants = List[Tuple[Field, FieldType, List[LinkRowField]]]


class FieldDependencyHandler:
    @classmethod
    def get_same_table_dependencies(cls, field: Field) -> List[Field]:
        """
        Returns the list of fields that the provided field directly depends on which
        are in the same table.

        :param field: The field to get dependencies for.
        :return: A list of specific field instances.
        """

        return [
            dep.specific for dep in field.field_dependencies.filter(table=field.table)
        ] + [
            dep.via.specific
            for dep in field.dependencies.filter(via__table=field.table)
        ]

    @classmethod
    def rebuild_dependencies(
        cls, fields, field_cache: FieldCache
    ) -> List[FieldDependency]:
        """
        Rebuilds this fields dependencies based off field_type.get_field_dependencies.

        :param fields: The fields to rebuild its field dependencies for.
        :param field_cache: A field cache which will be used to lookup fields.
        :return: Any new dependencies created by the rebuild.
        """

        update_fields_with_broken_references(fields)
        return rebuild_fields_dependencies(fields, field_cache)

    @classmethod
    def break_dependencies_delete_dependants(cls, field):
        """
        Breaks any dependant relationships to the field.

        :param field: The field to break all dependant relations onto the field and all
           dependencies
        """

        break_dependencies_for_field(field)

    @classmethod
    def _get_all_dependent_fields(
        cls,
        table_id: int,
        field_ids: Iterable[int],
        field_cache: FieldCache,
        associated_relations_changed: bool,
        database_id_prefilter=None,
    ) -> Tuple[QuerySet[FieldDependency], Dict[int, Field]]:
        """
        Recursively fetches field dependants and retrieves specific field types in a
        query-efficient and performant manner.

        :param table_id: The table that the provided field_ids are all part of.
        :param field_ids: The field ids for which we need to find the dependent fields,
            they must all be in the same table as specified by the table_id param.
        :field_cache: A field cache used to find and store the specific object of the
            dependant.
        :param associated_relations_changed: If true any relations associated with any
           provided field ids will be treated as having changed also and dependants on
           the relations themselves will be additionally returned.
        :param database_id_prefilter: Optionally prefilter the dependencies for a
            specific database. Providing it brings a significant performance
            improvement but limits dependencies to the database. This can only be done
            if all the provided fields are in the same database.
        :return: A tuple containing the queryset of the dependencies and a dictionary of
            the specific fields.
        """

        if len(field_ids) == 0:
            return []

        query_parameters = {
            "pks": list(field_ids),
            "max_depth": settings.MAX_FIELD_REFERENCE_DEPTH,
            "table_id": table_id,
            "database_id": database_id_prefilter,
        }
        relationship_table = FieldDependency._meta.db_table
        linkrowfield_table = LinkRowField._meta.db_table
        fields_db_table_name = Field._meta.db_table
        tables_db_table_name = Table._meta.db_table

        if associated_relations_changed:
            associated_relations_changed_query = f"""
                OR (
                    first.via_id = ANY(%(pks)s)
                    OR linkrowfield.link_row_related_field_id = ANY(%(pks)s)
                )
                AND NOT (
                    first.dependant_id = ANY(%(pks)s)
                )
            """
        else:
            associated_relations_changed_query = ""

        if database_id_prefilter:
            # Filters tbe dependencies to only include fields in the provided database.
            # This will significantly speed up performance because it doesn't need to
            # filter through all the dependencies. This improvement is noticeable on
            # large Baserow instances with many users.
            database_prefilter_query = f"""
                INNER JOIN {fields_db_table_name}
                    ON ( {relationship_table}.dependant_id = {fields_db_table_name}.id )
                INNER JOIN {tables_db_table_name}
                    ON ( {fields_db_table_name}.table_id = {tables_db_table_name}.id )
                WHERE  {tables_db_table_name}.database_id = %(database_id)s
            """
        else:
            database_prefilter_query = ""

        relationship_table_cte = f"""
            SELECT  {relationship_table}.id,
                    {relationship_table}.dependant_id,
                    {relationship_table}.dependency_id,
                    {relationship_table}.via_id
            FROM {relationship_table} {database_prefilter_query}
        """  # nosec b608

        # Raw query that traverses through the dependencies, and will find the
        # dependants of the provided fields ids recursively.
        raw_query = f"""
            WITH RECURSIVE traverse(id, dependency_ids, via_ids, depth) AS (
              WITH relationship_table_cte AS ( {relationship_table_cte} )
                SELECT
                    first.dependant_id,
                    first.dependency_id::text,
                    /*
                    We only want to add via's to the path which are valid joins
                    required to get from the dependant cell to the dependency. The
                    queryset can return dependencies with via's for dependants in the
                    same row, which don't need a join, so we filter those out here.
                    */
                    CASE
                        WHEN (
                            first.via_id IS DISTINCT FROM NULL
                            AND (
                                dependant.table_id != %(table_id)s
                                OR dependency.table_id = %(table_id)s
                            )
                        ) THEN first.via_id::text
                        ELSE ''
                    END as via_id,
                    1
                FROM relationship_table_cte AS first
                LEFT OUTER JOIN relationship_table_cte AS second
                    ON first.dependant_id = second.dependency_id
                LEFT OUTER JOIN {linkrowfield_table} as linkrowfield
                    ON first.via_id = linkrowfield.field_ptr_id
                LEFT OUTER JOIN {fields_db_table_name} as dependant
                    ON first.dependant_id = dependant.id
                LEFT OUTER JOIN {fields_db_table_name} as dependency
                    ON first.dependency_id = dependency.id
                WHERE
                    first.dependency_id = ANY(%(pks)s)
                    {associated_relations_changed_query}
                -- LIMITING_FK_EDGES_CLAUSE_1
                -- DISALLOWED_ANCESTORS_NODES_CLAUSE_1
                -- ALLOWED_ANCESTORS_NODES_CLAUSE_1
                UNION
                SELECT DISTINCT
                    dependant_id,
                    coalesce(concat_ws('|', dependency_ids::text, dependency_id::text), ''),
                    coalesce(concat_ws('|', via_ids::text, via_id::text), ''),
                    traverse.depth + 1
                FROM traverse
                INNER JOIN relationship_table_cte
                    ON relationship_table_cte.dependency_id = traverse.id
                WHERE 1 = 1
                -- LIMITING_FK_EDGES_CLAUSE_2
                -- DISALLOWED_ANCESTORS_NODES_CLAUSE_2
                -- ALLOWED_ANCESTORS_NODES_CLAUSE_2
            )
            SELECT
                traverse.id,
                STRING_AGG(traverse.dependency_ids, '|') AS dependency_ids,
                traverse.via_ids,
                field.content_type_id,
                field.name,
                field.table_id,
                MAX(depth) as depth
            FROM traverse
            LEFT OUTER JOIN {fields_db_table_name} as field
                ON traverse.id = field.id
            WHERE depth <= %(max_depth)s
            GROUP BY traverse.id, traverse.via_ids, field.content_type_id, field.name, field.table_id
            ORDER BY MAX(depth) ASC, id ASC
        """  # nosec b608

        queryset = FieldDependency.objects.raw(raw_query, query_parameters)
        link_row_field_content_type = ContentType.objects.get_for_model(LinkRowField)
        fields_to_fetch = set()
        fields_in_cache = {}

        # Unpacks the dependant field id, the link row via fields, and adds them to the
        # `fields_to_fetch` list, so that we can later query efficiently fetch the
        # specific objects.
        for dependency in queryset:
            if dependency.via_ids:
                dependency.via_ids = [
                    int(v) for v in dependency.via_ids.split("|") if v
                ]
            else:
                dependency.via_ids = []

            if dependency.dependency_ids:
                dependency.dependency_ids = [
                    int(v) for v in dependency.dependency_ids.split("|") if v
                ]
            else:
                dependency.dependency_ids = []

            field = Field(
                id=dependency.id,
                content_type_id=dependency.content_type_id,
                table_id=dependency.table_id,
                name=dependency.name,
            )

            if field not in fields_to_fetch:
                cached_field = field_cache.lookup_specific(
                    field, fetch_if_missing=False
                )
                if cached_field is not None:
                    fields_in_cache[cached_field.id] = cached_field
                else:
                    fields_to_fetch.add(field)

            for via_id in dependency.via_ids:
                link_row_field = Field(
                    id=via_id, content_type_id=link_row_field_content_type.id
                )
                if link_row_field not in fields_to_fetch:
                    fields_to_fetch.add(link_row_field)

        # This hook is called for every unique field type in the specific_iterator of
        # the fields. The `table` and `link_row_table` references are later needed,
        # so we're prefetching them here based on the type.
        from baserow.contrib.database.fields.field_types import LinkRowFieldType

        link_row_field_model = field_type_registry.get(
            LinkRowFieldType.type
        ).model_class

        def queryset_hook(model, queryset):
            queryset = queryset.select_related("table")
            if model == link_row_field_model:
                queryset = queryset.select_related("link_row_table")
            return queryset

        # Creates an object of specific field types, so that we don't have to execute
        # unnecessary queries later on.
        specific_fields = {}
        if fields_to_fetch:
            specific_fields = {
                field.id: field
                for field in specific_iterator(
                    fields_to_fetch,
                    base_model=Field,
                    per_content_type_queryset_hook=queryset_hook,
                )
            }

        return queryset, {**specific_fields, **fields_in_cache}

    @classmethod
    def group_dependencies_by_level(
        cls, dependencies: Dict[int | str, Set[int | str]]
    ) -> List[List[int | str]]:
        """
        Groups the given dependencies into levels based on their dependency order using
        a topological sort. This method organizes items (identified by integers or
        strings) into levels where each level contains items that do not depend on each
        other and can be processed concurrently. An item at level N can only be
        processed after all items in levels 0 to N-1 have been processed, ensuring that
        dependencies are respected. The `dependencies` parameter is a dictionary where
        each key is an item and its value is a set of items that it depends on. The
        method returns a list of lists, where each sublist represents a level in the
        dependency hierarchy.

        Example: >>> dependencies = {
        ...     'A': set(),
        ...     'B': {'A'},
        ...     'C': {'B'},
        ...     'D': {'B'},
        ...     'E': {'C', 'D'}
        ... }
        >>> cls.group_dependencies_by_level(dependencies)
        ...     [['A'], ['B'], ['C', 'D'], ['E']]

        In this example, 'A' has no dependencies and is placed at the first level. 'B'
        depends on 'A' and is placed at the next level. Both 'C' and 'D' depend on 'B'
        but not on each other, so they are grouped together in the third level. Finally,
        'E' depends on both 'C' and 'D' and is placed in the fourth level.

        :param dependencies: A dictionary mapping each item to a set of items it
            depends on.
        :return: A list of lists, where each sublist contains items that can be
            processed at the same level.
        :raises CircularFieldDependencyError: If the dependencies contain a cycle,
            a CircularFieldDependencyError is raised.
        """

        ts = TopologicalSorter(dependencies)

        try:
            ts.prepare()
        except CycleError:
            raise CircularFieldDependencyError()

        levels = []

        while ts.is_active():
            ready_nodes = ts.get_ready()
            level = [node for node in ready_nodes]
            ts.done(*ready_nodes)
            levels.append(level)

        return levels

    @classmethod
    def group_all_dependent_fields_by_level_from_fields(
        cls,
        fields: Iterable[Field],
        field_cache: FieldCache,
        associated_relations_changed: bool,
        database_id_prefilter=None,
    ) -> List[List[Tuple[int, Field]]]:
        """
        Given a list of fields, even from different tables, this method will return a
        list of lists where each list contains the fields than can be updated at the
        same time. The dependants are grouped by their level, so all formulas can be
        updated in the correct order updating one level at a time as they are returned.
        Every tuple in the list contains the id of the starting table of the dependency
        (used to identify the proper update collector) and the field instance to update.

        :param fields: A list of fields for which we need to find the dependent fields.
        :param field_cache: A field cache used to find and store the specific object of
            the dependant.
        :param associated_relations_changed: If true any relations associated with any
            provided field ids will be treated as having changed also and dependants on
            the relations themselves will be additionally returned.
        :param database_id_prefilter: Optionally prefilter the dependencies for a
            specific database. Providing it brings a significant performance
            improvement but limits dependencies to the database. This can only be done
            if all the provided fields are in the same database.
        :return: An iterable of lists where each list represents all the fields that can
            be updated together.
        """

        tables = defaultdict(set)
        for field in fields:
            tables[field.table_id].add(field.id)

        dependencies = defaultdict(set)

        # Contains a map between the field id and the information needed to update it.
        dependency_map = defaultdict(list)

        for starting_table_id, field_ids in tables.items():
            if len(field_ids) == 0:
                continue

            dependencies_queryset, specific_fields = cls._get_all_dependent_fields(
                starting_table_id,
                field_ids,
                field_cache,
                associated_relations_changed,
                database_id_prefilter=database_id_prefilter,
            )

            for dependency in dependencies_queryset:
                dependant_field = specific_fields[dependency.id]
                if field_cache.lookup_specific(dependant_field) is None:
                    # If somehow the dependant is trashed it will be None. We can't
                    # really trigger any updates for it so ignore it.
                    continue
                # The first raw query has constructed a path of link row fields that
                # lead back to the original table so that we can later efficiently
                # update the correct rows.
                #
                # We only want to add via's to the path which are valid joins required
                # to get from the dependant cell to the dependency. The queryset can
                # return dependencies with via's for dependants in the same row, which
                # don't need a join, so we filter those out here.
                via_path_to_starting_table = [
                    field_cache.lookup_specific(specific_fields[via_id])
                    for via_id in dependency.via_ids
                ] or None
                dependency_map[dependant_field.id].append(
                    (starting_table_id, dependant_field, via_path_to_starting_table)
                )
                dependencies[dependant_field.id] = set(dependency.dependency_ids)

        dependencies_gouped_by_level = cls.group_dependencies_by_level(dependencies)

        # For every dependency, return the starting table id and the field instance.
        dependent_fields_by_level = []
        for group_of_depdencies in dependencies_gouped_by_level:
            level = []
            for field_id in group_of_depdencies:
                if field_id in dependency_map:
                    level.extend(dependency_map[field_id])
            if level:
                dependent_fields_by_level.append(level)

        return dependent_fields_by_level

    @classmethod
    def group_all_dependent_fields_by_level(
        cls,
        table_id: int,
        field_ids: Iterable[int],
        field_cache: FieldCache,
        associated_relations_changed: bool,
        database_id_prefilter=None,
    ) -> List[FieldDependants]:
        """
        Recursively fetches field dependants, and fetches the specific types in a query
        efficient and performant manner. The dependants are grouped by their depth,
        so all formulas can be updated in the correct order.

        :param table_id: The table that the provided field_ids are all part of.
        :param field_ids: The field ids for which we need to find the dependent fields,
            they must all be in the same table as specified by the table_id param.
        :param field_cache: A field cache used to find and store the specific object
            of the dependant.
        :param associated_relations_changed: If true any relations associated
           with any provided field ids will be treated as having changed also and
           dependants on the relations themselves will be additionally returned.
        :param database_id_prefilter: Optionally prefilter the dependencies for a
            specific database. Providing it brings a significant performance
            improvement but limits dependencies to the database. This can only be done
            if all the provided fields are in the same database.
        :return: A list for every depth containing the dependant fields, their field
            type and the path to starting table.
        """

        if len(field_ids) == 0:
            return []

        dependencies_queryset, specific_fields = cls._get_all_dependent_fields(
            table_id,
            field_ids,
            field_cache,
            associated_relations_changed,
            database_id_prefilter=database_id_prefilter,
        )

        dependencies = defaultdict(set)
        # Contains a map between the field id and the information needed to update it.
        dependency_map = defaultdict(list)

        for dependency in dependencies_queryset:
            dependant_field = specific_fields[dependency.id]
            if field_cache.lookup_specific(dependant_field) is None:
                # If somehow the dependant is trashed it will be None. We can't really
                # trigger any updates for it so ignore it.
                continue

            # The first raw query has constructed a path of link row fields that lead
            # back to the original table so that we can later efficiently update the
            # correct rows.
            #
            # We only want to add via's to the path which are valid joins required to
            # get from the dependant cell to the dependency. The queryset can return
            # dependencies with via's for dependants in the same row, which don't need
            # a join, so we filter those out here.
            via_path_to_starting_table = [
                field_cache.lookup_specific(specific_fields[via_id])
                for via_id in dependency.via_ids
            ] or None
            dependant_field_type = field_type_registry.get_by_model(dependant_field)

            dependency_map[dependant_field.id].append(
                (
                    dependant_field,
                    dependant_field_type,
                    via_path_to_starting_table,
                )
            )

            dependencies[dependant_field.id] = set(dependency.dependency_ids)

        dependencies_gouped_by_level = cls.group_dependencies_by_level(dependencies)

        dependent_fields_by_level = []
        for group_of_depdencies in dependencies_gouped_by_level:
            level = []
            for field_id in group_of_depdencies:
                if field_id in dependency_map:
                    level.extend(dependency_map[field_id])
            if level:
                dependent_fields_by_level.append(level)

        return dependent_fields_by_level

    @classmethod
    def get_all_dependent_fields_with_type(
        cls,
        table_id: int,
        field_ids: Iterable[int],
        field_cache: FieldCache,
        associated_relations_changed: bool,
        database_id_prefilter=None,
    ) -> FieldDependants:
        """
        Fetches field dependants recursive, and fetches the specific types in a query
        efficient and performant manner.

        :param table_id: The table that the provided field_ids are all part of.
        :param field_ids: The field ids for which we need to find the dependent fields,
            they must all be in the same table as specified by the table_id param.
        :param field_cache: A field cache used to find and store the specific object
            of the dependant.
        :param associated_relations_changed: If true any relations associated
           with any provided field ids will be treated as having changed also and
           dependants on the relations themselves will be additionally returned.
        :param database_id_prefilter: Optionally prefilter the dependencies for a
            specific database. Providing it brings a significant performance
            improvement but limits dependencies to the database. This can only be done
            if all the provided fields are in the same database.
        :return: A list containing the dependant fields, their field type and the
            path to starting table.
        """

        if len(field_ids) == 0:
            return []

        dependencies, specific_fields = cls._get_all_dependent_fields(
            table_id,
            field_ids,
            field_cache,
            associated_relations_changed,
            database_id_prefilter=database_id_prefilter,
        )

        result: FieldDependants = []
        for dependency in dependencies:
            dependant = specific_fields[dependency.id]
            dependant_field = field_cache.lookup_specific(dependant)
            if dependant_field is None:
                # If somehow the dependant is trashed it will be None. We can't really
                # trigger any updates for it so ignore it.
                continue
            dependant_field_type = field_type_registry.get_by_model(dependant_field)

            # The first raw query has constructed a path of link row fields that lead
            # back to the original table so that we can later efficiently update the
            # correct rows.
            #
            # We only want to add via's to the path which are valid joins required to
            # get from the dependant cell to the dependency. The queryset can return
            # dependencies with via's for dependants in the same row, which don't need
            # a join, so we filter those out here.
            via_path_to_starting_table = [
                field_cache.lookup_specific(specific_fields[via_id])
                for via_id in dependency.via_ids
            ] or None

            result.append(
                (dependant_field, dependant_field_type, via_path_to_starting_table)
            )

        return result

    @classmethod
    def get_dependant_fields_with_type(
        cls,
        table_id: int,
        field_ids: Iterable[int],
        associated_relations_changed: bool,
        field_cache: FieldCache,
        starting_via_path_to_starting_table: Optional[str] = None,
    ) -> FieldDependants:
        """
        Finds the unique dependant fields of the provided field ids efficiently with the
        least amount of queries. These provided field ids must all be for fields in the
        same table.

        :param table_id: The table that the provided field_ids are all part of.
        :param field_ids: The field ids for which we need to find the dependent fields,
            they must all be in the same table as specified by the table_id param.
        :param associated_relations_changed: If true any relations associated
            with any provided field ids will be treated as having changed also and
            dependants on the relations themselves will be additionally returned.
        :param field_cache: A field cache used to find and store the specific object
            of the dependant.
        :param starting_via_path_to_starting_table: The starting of the dependant
            fields.
        :return: A list containing the dependant fields, their field type and the
            path to starting table.
        """

        if not field_ids:
            return []

        dependant_filter = Q(dependency_id__in=field_ids)
        if associated_relations_changed:
            # Any m2m relationships associated with the provided field_ids have changed.
            # So we want to lookup all fields which are dependant via these link row
            # m2m relationships to properly update them also.
            dependant_filter |= (
                Q(via_id__in=field_ids)
                | Q(via__link_row_related_field_id__in=field_ids)
            ) & ~Q(dependant_id__in=field_ids)
        queryset = (
            FieldDependency.objects.filter(dependant_filter)
            .select_related(
                "dependant",
                "dependant__table",
                "dependency",
                "via",
                "via__table",
                "via__link_row_table",
            )
            .order_by("id")
        )

        # Creates an object of specific field types, so that we don't have to execute
        # unnecessary queries later on.
        specific_dependants = {
            field.id: field
            for field in specific_iterator(
                [dependency.dependant for dependency in queryset],
                base_model=Field,
                select_related=["table"],
            )
        }

        result: FieldDependants = []
        for field_dependency in queryset:
            dependant = specific_dependants[field_dependency.dependant_id]
            dependant_field = field_cache.lookup_specific(dependant)
            if dependant_field is None:
                # If somehow the dependant is trashed it will be None. We can't really
                # trigger any updates for it so ignore it.
                continue
            dependant_field_type = field_type_registry.get_by_model(dependant_field)

            # We only want to add via's to the path which are valid joins required to
            # get from the dependant cell to the dependency. The queryset can return
            # dependencies with via's for dependants in the same row, which don't need
            # a join, so we filter those out here.
            if field_dependency.via is not None and (
                dependant.table_id != table_id
                or (
                    field_dependency.dependency
                    and field_dependency.dependency.table_id == table_id
                )
            ):
                via_path_to_starting_table = (
                    starting_via_path_to_starting_table or []
                ) + [field_dependency.via]
            else:
                via_path_to_starting_table = starting_via_path_to_starting_table

            result.append(
                (dependant_field, dependant_field_type, via_path_to_starting_table)
            )
        return result

    @classmethod
    def get_via_dependants_of_link_field(cls, field: "LinkRowField") -> FieldDependants:
        broken_via_dep_filter = Q(via_id=field.id) & ~Q(dependant_id=field.id)

        related_field_id = field.link_row_related_field_id
        if related_field_id:
            # We also have a related link row field, which is about to get deleted due
            # to the type change also. Find all of it's via deps also excluding its self
            # via dependency.
            broken_via_dep_filter |= Q(via_id=related_field_id) & ~Q(
                dependant_id=related_field_id
            )

        dependants = []
        for via_dep in FieldDependency.objects.filter(broken_via_dep_filter):
            dependant_field = via_dep.dependant.specific
            dependant_field_type = field_type_registry.get_by_model(dependant_field)
            field_dep_tuple = (
                dependant_field,
                dependant_field_type,
                # Don't set any via path as the m2m is being deleted due to the
                # type change and won't be usable.
                [],
            )
            dependants.append(field_dep_tuple)
        return dependants

    @classmethod
    def rebuild_or_raise_if_user_doesnt_have_permissions_after(
        cls,
        workspace: Workspace,
        user: AbstractUser,
        field: Field,
        field_cache: FieldCache,
        field_operation_name: str,
    ):
        new_dependencies = FieldDependencyHandler.rebuild_dependencies(
            [field], field_cache
        )
        FieldDependencyHandler.raise_if_user_doesnt_have_operation_on_dependencies_in_other_tables(
            workspace, user, field, new_dependencies, field_operation_name
        )

    @classmethod
    def raise_if_user_doesnt_have_operation_on_dependencies_in_other_tables(
        cls,
        workspace: Workspace,
        user: AbstractUser,
        field: Field,
        dependencies: List[FieldDependency],
        field_operation_name: str,
    ):
        """
        For a list of dependencies checks the provided user has the provided operation
        on each of the dependency fields raising if they do not. It skips any
        dependencies that point at the same table assuming the user already has rights
        on fields in the table `field` is in.

        :param workspace: The workspace.
        :param user: The user.
        :param field: The field.
        :param dependencies: The dependencies.
        :param field_operation_name: The field operation name.
        """

        perm_checks = []
        for dep in dependencies:
            dependency_field = dep.dependency
            if dependency_field.table_id != field.table_id:
                perm_checks.append(
                    PermissionCheck(
                        user,
                        field_operation_name,
                        dependency_field,
                    )
                )

        changed_field_type = field_type_registry.get_by_model(field)
        for (
            check,
            result,
        ) in (
            CoreHandler().check_multiple_permissions(perm_checks, workspace).items()
        ):
            if not result:
                raise changed_field_type.get_permission_error_when_user_changes_field_to_depend_on_forbidden_field(
                    check.actor, field, check.context
                )
