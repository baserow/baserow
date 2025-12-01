from baserow.core.psycopg import sql


class NoValueSentinel:
    """
    Helper class to mark missing values.
    """


NO_VALUE = NoValueSentinel()

START_DATE_FIELD = "start_date"
END_DATE_FIELD = "end_date"
DURATION_FIELD = "duration"


# The query builds a list of rows belonging to the graph. Each row contains
# its path from the root, depth level and a shortcut information if it's a root,
# intermediate node or a leaf (ending) of a path. Also, each row contains
# start/end dates and duration to be able to calculate new values.
# Note: One row can belong to multiple paths, and there may be multiple paths
# in the graph (one row can have multiple parents and one parent can have
# multiple children).
ROW_DEPENDENCY_GRAPH_QUERY = sql.SQL(
    """
    WITH RECURSIVE
        updated AS
                (SELECT unnest(ARRAY [{value}]) AS updated_id),
        ancestors AS (select u.updated_id         AS id,
                             u.updated_id         AS original_id,
                             0                    AS level,
                             ARRAY [u.updated_id] AS path
                      FROM updated u
                      JOIN {table_name} t ON t.id = u.updated_id AND NOT t.trashed
                      UNION ALL
                      -- Recursively find parents
                      SELECT ip.{to_field_name} AS parent_id
                , a.original_id
                , a.level - 1 AS level
                , ip.{to_field_name} || a.path AS path
                      FROM ancestors a
                          JOIN {relation_table_name} ip
                      ON ip.{from_field_name} = a.id
                      JOIN {table_name} t ON t.id = a.id AND NOT t.trashed
                      WHERE NOT (ip.{to_field_name} = ANY (a.path)) -- Prevent cycles
        ),
        -- one starting row can have multiple roots
        roots AS (SELECT a.id as root_id,
                         a.id,
                         a.original_id
                  FROM ancestors a
                           LEFT OUTER JOIN {relation_table_name} ip
                  ON ip.{from_field_name} = a.id
                 JOIN {table_name} t ON t.id = a.id AND NOT t.trashed
                  WHERE ip.id IS NULL
                  ORDER BY original_id, level ASC),
        -- Find all descendants starting from roots
        descendants AS (
            -- Start with root nodes
            SELECT r.root_id,
                   r.root_id         AS id,
                   r.original_id,
                   0                 AS level,
                   ARRAY [r.root_id] AS path
            FROM roots r
                JOIN {table_name} t ON t.id = r.root_id AND NOT t.trashed
            UNION ALL
            -- Recursively find children
            SELECT d.root_id,
                   ip.{from_field_name} AS  id,
                d.original_id,
                d.level + 1 AS  level,
                d.path || ip.{from_field_name} AS  path
            FROM descendants d
                JOIN {relation_table_name} ip
            ON ip.{to_field_name} = d.id
            JOIN {table_name} t ON t.id = d.id AND NOT t.trashed
            WHERE NOT (ip.{from_field_name} = ANY (d.path)) -- Prevent cycles
        ),
-- Combine all nodes in the dependency trees
        complete_tree AS (SELECT DISTINCT d.id,
                                          d.original_id,
                                          r.root_id,
                                          d.level,
                                          d.path
                          FROM descendants d
                                   JOIN roots r ON r.root_id = d.root_id)
-- Final result with item details
    SELECT ct.id,
           i.{start_date_field},
    i.{end_date_field},
    i.{duration_field},
    ct.root_id,
    ct.level,
    ct.path,
    ct.original_id AS triggered_by_update_of,
    CASE
        WHEN ct.id = ct.root_id THEN 'ROOT'
        WHEN NOT EXISTS (SELECT 1 FROM {relation_table_name} WHERE {to_field_name} = ct.id) THEN 'LEAF'
        ELSE 'INTERMEDIATE'
    END AS  node_type

FROM complete_tree ct
JOIN {table_name} i ON i.id = ct.id AND NOT i.trashed
ORDER BY ct.original_id, ct.level desc, ct.id;
    """
)  # noqa STR100
