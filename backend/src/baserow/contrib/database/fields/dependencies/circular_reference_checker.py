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

from django.conf import settings


def will_cause_circular_dep(from_field, to_field):
    return from_field.id in get_all_field_dependencies(to_field)


def get_all_field_dependencies(field):
    from baserow.contrib.database.fields.models import Field

    query_parameters = {
        "pk": field.pk,
        "max_depth": settings.MAX_FIELD_REFERENCE_DEPTH,
    }

    # Only pk_name and a table name get formatted in, no user controllable input, safe.
    # fmt: off
    raw_query = (
        f"""
        WITH RECURSIVE dependencies AS MATERIALIZED (
            SELECT dd.id, dependant_id, dependency_id
            FROM database_fielddependency dd
            INNER JOIN database_field df ON dd.dependant_id = df.id
            INNER JOIN database_table dt ON dt.id = df.table_id
            WHERE dt.database_id = (
                SELECT database_id
                FROM database_field df
                INNER JOIN database_table dt ON df.table_id = dt.id
                WHERE df.id = %(pk)s
                LIMIT 1
            )
        ),
        traverse(id, depth) AS (
            SELECT first.dependency_id, 1
                FROM dependencies AS first
                LEFT OUTER JOIN dependencies AS second
                ON first.dependency_id = second.dependant_id
            WHERE first.dependant_id = %(pk)s
        UNION
            SELECT DISTINCT dependency_id, traverse.depth + 1
                FROM traverse
                INNER JOIN dependencies
                ON dependencies.dependant_id = traverse.id
            WHERE 1 = 1
        )
        SELECT id FROM traverse
        WHERE depth <= %(max_depth)s
        GROUP BY id
        ORDER BY MAX(depth) DESC, id ASC
        """  # nosec b608
    )
    # fmt: on
    pks = Field.objects.raw(raw_query, query_parameters)
    return {item.pk for item in pks}
