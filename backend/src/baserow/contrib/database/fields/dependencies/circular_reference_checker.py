#
# Copyright 2020, Jack Linke
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# Copyright (c) 2019-present Baserow B.V.
#    Modifications licensed according to the LICENSE file in the root of this
#    repository.
#
# This file contains modified Apache 2.0 licensed code from the highly useful
# https://github.com/OmenApps/django-postgresql-dag/ project. Specifically the
# Recursive CTE used to search for circular references. The modifications made change
# this query so it works with our own database models and structure.
#

from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection

from baserow.contrib.database.fields.dependencies.exceptions import (
    CircularFieldDependencyError,
)
from baserow.contrib.database.fields.dependencies.models import FieldDependency

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


def will_cause_circular_dep(from_field, to_field):
    return from_field.id in get_all_field_dependencies(to_field)


def get_all_field_dependencies(field: "Field") -> set[int]:
    """
    Get all field dependencies for a field. This includes all fields that the given
    field depends on, directly or indirectly, even if the field have been trashed. For
    example, if the given field is a formula that references another formula which in
    turn references a text field, both the intermediate formula and the text field will
    be returned as dependencies.

    This function uses a recursive CTE to traverse the field dependency graph and return
    all field ids that are reachable from the given field id. If a circular dependency
    is detected, a CircularFieldDependencyError is raised.

    :param field: The field to get dependencies for.
    :return: A set of field ids that the given field depends on.
    :raises CircularFieldDependencyError: If a circular dependency is detected.
    """

    from baserow.contrib.database.fields.models import Field

    filtered_field_dependencies = FieldDependency.objects.filter(
        dependant_id__table__database_id=Field.objects_and_trash.filter(pk=field.pk)
        .order_by()
        .values("table__database_id")[:1]
    )
    sql, params = filtered_field_dependencies.query.get_compiler(
        connection=connection
    ).as_sql()

    # Only pk_name and a table name get formatted in, no user controllable input, safe.
    # fmt: off
    raw_query = (
        f"""
        WITH RECURSIVE dependencies AS ({sql}),
        traverse(id, depth, path, is_circular) AS (
            SELECT
                dependency_id,
                1,
                ARRAY[dependant_id, dependency_id],
                FALSE
            FROM dependencies
            WHERE dependant_id = %s

            UNION ALL

            SELECT
                d.dependency_id,
                traverse.depth + 1,
                path || d.dependency_id,
                d.dependency_id = ANY(path) OR traverse.is_circular -- detect circularity
            FROM traverse
            INNER JOIN dependencies d ON d.dependant_id = traverse.id
            WHERE NOT traverse.is_circular -- stop recursion when a cycle is found
        )
        SELECT id, is_circular
        FROM (
            SELECT
                id,
                is_circular,
                MAX(depth) AS max_depth
            FROM traverse
            WHERE depth <= %s
            GROUP BY id, is_circular
        ) sub
        ORDER BY max_depth DESC, id ASC;
        """  # nosec b608
    )
    # fmt: on

    dep_ids = set()
    with connection.cursor() as cursor:
        cursor.execute(
            raw_query, (*params, field.pk, settings.MAX_FIELD_REFERENCE_DEPTH)
        )
        results = cursor.fetchall()
        for dep_id, is_circular in results:
            if is_circular:
                raise CircularFieldDependencyError()
            elif dep_id is not None:  # Avoid broken references
                dep_ids.add(dep_id)

    return dep_ids
