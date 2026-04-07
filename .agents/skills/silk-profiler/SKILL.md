---
name: silk-profiler
description: Investigate backend performance using Django Silk profiling data. Use when investigating a slow endpoint, a potential bottleneck, N+1 queries, or understanding query patterns for a specific request.
---

# Investigate Backend Performance with Silk

Use this skill to investigate a slow endpoint or a potential bottleneck. Django Silk (enabled by default in dev via `BASEROW_ENABLE_SILK` in `dev.py`) records every HTTP request, its SQL queries, and full Python stack traces into PostgreSQL. The user may provide a Silk request URL, a request ID, or just describe which endpoint is slow.

## Prerequisites

- Silk must be enabled (default in dev: `BASEROW_ENABLE_SILK=on` in `dev.py`)
- The slow operation must have been performed recently so Silk has captured it
- The dev database must be accessible (usually via `docker exec` into the `baserow-db-1` container)

## Connecting to the Database

Read the `DATABASES` setting in `backend/src/baserow/config/settings/base.py` (and `dev.py` which imports it) to find the connection credentials. Env vars may override the defaults.

The database usually runs in a Docker container. Try `docker exec` first:

```bash
docker exec <db-container> psql -U <user> -d <database> -c "<SQL>"
```

To find the container name:

```bash
docker ps --format '{{.Names}}' | grep -i "db\|postgres"
```

If `psql` is available locally, connect directly using the host/port from the settings. **Try connecting first, only ask the user if it fails.**

## Handling User Input

The user may provide:

- **A Silk URL** like `http://localhost:8000/silk/request/<uuid>/sql/` — extract the UUID between `/request/` and the next `/` as the request ID.
- **A request ID** (UUID) directly.
- **An endpoint path** like `/api/database/tables/123/` — search for it in `silk_request`.
- **A description** like "deleting a table is slow" — search by path pattern and sort by time.

## Workflow

### Step 1: Find the Request

If you already have a request ID, skip to Step 2.

```sql
-- Search by path pattern
SELECT id, path, method, round(time_taken::numeric, 0) AS ms,
       num_sql_queries AS queries, start_time
FROM silk_request
WHERE path LIKE '%/api/PATTERN/%'
ORDER BY start_time DESC
LIMIT 10;
```

```sql
-- Slowest requests overall
SELECT id, path, method, round(time_taken::numeric, 0) AS ms,
       num_sql_queries AS queries, start_time
FROM silk_request
ORDER BY time_taken DESC
LIMIT 10;
```

```sql
-- Requests with the most SQL queries (likely N+1)
SELECT id, path, method, num_sql_queries AS queries,
       round(time_taken::numeric, 0) AS ms, start_time
FROM silk_request
ORDER BY num_sql_queries DESC
LIMIT 10;
```

### Step 2: Analyze Where Time Is Spent

`meta_time_spent_queries` is usually NULL, so compute query time from `silk_sqlquery`:

```sql
SELECT r.path, r.method,
       round(r.time_taken::numeric, 0) AS total_ms,
       r.num_sql_queries,
       round(q.query_ms::numeric, 0) AS query_ms,
       round((r.time_taken - q.query_ms)::numeric, 0) AS python_ms
FROM silk_request r
JOIN (
    SELECT request_id, SUM(time_taken) AS query_ms
    FROM silk_sqlquery GROUP BY request_id
) q ON q.request_id = r.id
WHERE r.id = '<request_id>';
```

If `query_ms` dominates, the problem is database queries. If `python_ms` is high, the bottleneck is in Python code.

### Step 3: Detect N+1 Query Patterns

Group by **normalized** query text (string literals and integer params replaced with `?`) to catch N+1 patterns where the same query runs with different IDs:

```sql
SELECT COUNT(*) AS count,
       round(SUM(time_taken)::numeric, 1) AS total_ms,
       LEFT(regexp_replace(
         regexp_replace(query, '''[^'']*''', '''?''', 'g'),
         '= \d+', '= ?', 'g'
       ), 200) AS normalized
FROM silk_sqlquery
WHERE request_id = '<request_id>'
GROUP BY regexp_replace(
  regexp_replace(query, '''[^'']*''', '''?''', 'g'),
  '= \d+', '= ?', 'g'
)
ORDER BY count DESC
LIMIT 15;
```

Any query appearing more than a handful of times is likely an N+1 problem.

### Step 4: Examine Slow Individual Queries

```sql
SELECT id, round(time_taken::numeric, 1) AS ms, LEFT(query, 300) AS query_preview
FROM silk_sqlquery
WHERE request_id = '<request_id>'
ORDER BY time_taken DESC
LIMIT 10;
```

```sql
-- Full query text for a specific slow query
SELECT query FROM silk_sqlquery WHERE id = <query_id>;
```

### Step 5: Analyze Query Plans

Silk runs `EXPLAIN` on every captured query and stores the plan in the `analysis` column of `silk_sqlquery`. This is always available — no extra configuration needed.

```sql
SELECT id, round(time_taken::numeric, 1) AS ms, analysis
FROM silk_sqlquery
WHERE request_id = '<request_id>'
ORDER BY time_taken DESC
LIMIT 5;
```

These are estimated plans (no actual execution stats). If you need actual row counts and timings, run `EXPLAIN ANALYZE` manually on a specific query:

```sql
EXPLAIN ANALYZE <paste query from silk_sqlquery here>;
```

**What to look for:**

- **Seq Scan on large tables** — a sequential scan on a table that could grow large (e.g. rows, fields, workspaces) means a missing or unused index. Small config tables are fine.
- **Missing indexes** — if a WHERE or JOIN condition filters on a column without an index, the planner falls back to sequential scans. Fix with `db_index=True` on the model field or a migration with `AddIndex`.
- **Existing indexes not being used** — an index may exist but the planner ignores it (wrong column order in composite index, type mismatch, function wrapping the column, etc.). Check whether the index is used by *any* query in the codebase — if not, it's dead weight and should be removed.
- **Nested Loop with high row estimates** — often a sign of missing `select_related` or a missing index on the join column.

> **Do not enable `SILKY_ANALYZE_QUERIES`** (`BASEROW_DANGEROUS_SILKY_ANALYZE_QUERIES`) to upgrade to EXPLAIN ANALYZE globally. It re-executes every UPDATE and breaks data integrity. The default EXPLAIN plans in the `analysis` column are sufficient for most investigations — run `EXPLAIN ANALYZE` manually only on specific queries when needed.

### Step 6: Read Stack Traces

Stack traces are stored reversed: the **top** is ORM/Silk internals, the **middle** contains Baserow application frames (paths containing `baserow/src/baserow/`), and the **bottom** is Django server/threading boilerplate. Scan for the Baserow frames in the middle — those are the ones that matter.

```sql
SELECT traceback FROM silk_sqlquery WHERE id = <query_id>;
```

To get traces for the most repeated query pattern:

```sql
SELECT id, traceback
FROM silk_sqlquery
WHERE request_id = '<request_id>'
  AND regexp_replace(
    regexp_replace(query, '''[^'']*''', '''?''', 'g'),
    '= \d+', '= ?', 'g'
  ) = (
    SELECT regexp_replace(
      regexp_replace(query, '''[^'']*''', '''?''', 'g'),
      '= \d+', '= ?', 'g'
    )
    FROM silk_sqlquery
    WHERE request_id = '<request_id>'
    GROUP BY regexp_replace(
      regexp_replace(query, '''[^'']*''', '''?''', 'g'),
      '= \d+', '= ?', 'g'
    )
    ORDER BY COUNT(*) DESC LIMIT 1
  )
LIMIT 3;
```

### Step 7: Trace to Code and Propose Fixes

Once you've identified the problematic query and its origin in the stack trace:

1. Read the source file and function that triggered the query
2. Understand the data access pattern
3. Propose a fix based on the patterns below

## Common Patterns and Fixes

### N+1 Queries — Missing `select_related()` / `prefetch_related()`

**Symptom:** The same SELECT appears dozens/hundreds of times, each with a different WHERE id = value.

**Fix:** Add `select_related('relation')` for ForeignKey/OneToOne, or `prefetch_related('relation')` for reverse FK/M2M, on the queryset that feeds the loop or serializer.

### Queries in Loops That Could Be Batched

**Symptom:** Queries inside a Python for-loop that could be replaced with a single bulk operation.

**Fix:** Collect IDs first, do a single bulk query, then map results back. Common in Baserow: `break_dependencies_for_field` called per-field instead of batching, `FieldCache.reset_cache()` called inside loops invalidating cached data.

### `specific_iterator` or `specific_queryset` / `.specific` Overhead

**Symptom:** Many SELECT queries fetching from different field type tables (`database_textfield`, `database_numberfield`, etc.) one at a time.

**Fix:** Use `specific_iterator()` with a batch of fields rather than calling `.specific` per field in a loop. Or ensure `FieldCache` is populated before the loop and not reset mid-iteration.

### `get_model()` Called Repeatedly

**Symptom:** Repeated queries to `database_field` and `django_content_type` tables to rebuild the same table model.

**Fix:** Cache the model result or pass it as a parameter instead of calling `table.get_model()` multiple times.

### Duplicate Queries Across Serializer Fields

**Symptom:** Multiple serializer fields each trigger the same query independently.

**Fix:** Use `prefetch_related` with a `Prefetch` object on the view's queryset, or add a `@cached_property` on the model.

### Missing Database Indexes

**Symptom:** A single query takes a very long time (>100ms). The query filters on a column that isn't indexed.

**Fix:** Add `db_index=True` to the model field or create a migration with `AddIndex`.

## Silk Table Schema Reference

### silk_request
| Column | Type | Notes |
|---|---|---|
| id | CharField(36) | UUID primary key |
| path | CharField(190) | Request URL path |
| method | CharField(10) | HTTP method |
| start_time | DateTimeField | Request start |
| time_taken | FloatField | Total time (ms) |
| num_sql_queries | IntegerField | SQL query count |
| meta_time_spent_queries | FloatField | **Usually NULL** — compute from silk_sqlquery instead |
| view_name | CharField(190) | Django view name (usually populated) |

### silk_sqlquery
| Column | Type | Notes |
|---|---|---|
| id | IntegerField | Auto PK |
| query | TextField | Full SQL text |
| start_time | DateTimeField | Query start |
| end_time | DateTimeField | Query end |
| time_taken | FloatField | Execution time (ms) |
| request_id | FK | Links to silk_request |
| traceback | TextField | Python stack trace (reversed — ORM at top, Baserow in middle, server at bottom) |
| analysis | TextField | EXPLAIN output (always populated). With `SILKY_ANALYZE_QUERIES` enabled, contains EXPLAIN ANALYZE instead. |

### silk_profile
| Column | Type | Notes |
|---|---|---|
| id | IntegerField | Auto PK |
| name | CharField(300) | Profile name |
| time_taken | FloatField | Duration (ms) |
| request_id | FK | Links to silk_request |
| file_path | CharField(300) | Source file |
| line_num | IntegerField | Start line |
| func_name | CharField(300) | Function name |

## Guardrails

- **Use read-only queries only.** Never run INSERT, UPDATE, DELETE, or DDL on any table.
- **Never enable `SILKY_ANALYZE_QUERIES`** (`BASEROW_DANGEROUS_SILKY_ANALYZE_QUERIES`). It runs every UPDATE twice and breaks data integrity.
- **Do not truncate Silk tables** without asking the user first.
- **Ground every claim in data.** Always quote the specific evidence (EXPLAIN output, stack trace lines, source code with file path and line number) when making a diagnosis. Never state that a query is slow, an index is missing, or a `select_related` is needed without showing the data that supports it.
- When proposing fixes, always read the actual source code first — don't guess from the query text alone.
- **Confirm findings with the user.** When a user describes a problem without a Silk URL or request ID, confirm the matching request was found and provide its Silk URL (e.g. `http://localhost:8000/silk/request/<uuid>/`) so the user can verify before proceeding.
