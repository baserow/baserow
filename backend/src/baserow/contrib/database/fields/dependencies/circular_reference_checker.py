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
from django.db.models.expressions import RawSQL

from baserow.contrib.database.fields.dependencies.models import FieldDependency

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


def will_cause_circular_dep(from_field, to_field):
    return from_field.id in get_all_field_dependencies(to_field)


def get_all_field_dependencies(field: "Field") -> set[int]:
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
        traverse(id, depth, path) AS (
            SELECT first.dependency_id, 1, ARRAY[first.dependant_id, first.dependency_id]
                FROM dependencies AS first
                LEFT OUTER JOIN dependencies AS second
                ON first.dependency_id = second.dependant_id
            WHERE first.dependant_id = %s
        UNION
            SELECT DISTINCT dependency_id, traverse.depth + 1, path || d.dependency_id
                FROM traverse
                INNER JOIN dependencies d
                ON d.dependant_id = traverse.id
            WHERE NOT d.dependency_id = ANY(path)  -- Avoid cycles
        )
        SELECT id FROM traverse
        WHERE depth <= %s
        GROUP BY id
        ORDER BY MAX(depth) DESC, id ASC
        """  # nosec b608
    )
    # fmt: on

    dependencies_field_ids = RawSQL(
        raw_query, (*params, field.pk, settings.MAX_FIELD_REFERENCE_DEPTH)
    )  # nosec B611
    pks = Field.objects.filter(id__in=dependencies_field_ids).values_list(
        "pk", flat=True
    )
    return set(pks)
