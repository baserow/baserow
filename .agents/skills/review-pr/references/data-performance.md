# Data access and scale review

Use this reference when query shape or frequency changes, work grows with a
collection, or the diff touches indexes, caches, search/filter/order/aggregation,
bulk work, tasks, realtime fan-out, generated SQL, payload size, or a performance
claim. Load `external-io.md` when the fan-out leaves Baserow.

## Establish the scale model

Record what initiates the operation and which dimensions multiply its cost: users,
workspaces, applications, tables, rows, fields, views, dependencies, actions,
recipients, events, pages, jobs, and concurrent requests. Take expected and high-end
values from product limits, settings, the issue, or production evidence. If none
exist, state the assumed envelope rather than silently testing a two-object fixture.

Estimate the complete cost at that envelope:

- SQL statements, rows scanned/locked/written, and generated-query complexity;
- CPU and memory per request or worker;
- response, cache, broker, and websocket bytes;
- tasks or broadcasts produced and their concurrency;
- latency and resource lifetime across every phase.

An `O(users × workspaces × fields)` path must be evaluated as the product, not as
three individually small loops.

## Trace and measure database work

- Follow the real entry point through permission managers, model properties,
  handlers, serializers, signals, registry hooks, websocket construction, and task
  enqueueing. Lazy ORM evaluation can move the query far from its definition.
- Compare query growth between a small and representative case in the same cache
  state. Use `CaptureQueriesContext` around the end-to-end operation; prefer an
  assertion that query count is constant with cardinality when an exact count would
  be brittle.
- Inspect the SQL produced by complex queryset, formula, aggregation, and generated
  table-model paths. Independent many-to-many aggregations can multiply rows through
  join fan-out even when the ORM looks compact.
- Look for `.specific`, permission resolution, `table.get_model()`, serializer
  fields, and registry hooks inside loops. Use the established select/prefetch,
  `specific_iterator`, request-local cache, and bulk paths where applicable.
- Prefer set-based writes and bounded batches. Flag full materialization before a
  limit, per-object writes/tasks, unbounded dependency traversal, and `count()` or
  `exists()` followed by the same fetch when `limit + 1` answers both questions.

## Verify indexes with the planner

An index declaration is not evidence that PostgreSQL will use it. Populate realistic
volume and selectivity, refresh statistics when needed, and inspect the production
query using `QuerySet.explain(format="json")`, a stored Silk plan, or read-only
`EXPLAIN (ANALYZE, BUFFERS)` in a disposable database.

Check that:

- filters, joins, and ordering can use the intended index;
- composite column order and partial predicates match the real query;
- casts, functions, widening, nullable conditions, or an `OR` do not defeat it;
- estimated and actual rows are close enough for a sensible plan;
- scan rows, nested-loop count, sort method/size, and buffers remain reasonable.

A sequential scan on a small or low-selectivity table is not itself a finding. An
unused index adds write and storage cost. Ground either conclusion in the plan and
expected frequency. Normal metadata indexes follow the concurrent zero-downtime
migration pattern; generated user-table indexes use the existing lazy runtime path
rather than iterating all user tables in a migration.

## Caches, locks, and payloads

- A cache key includes tenant/permission scope, resource identity, version, and every
  input that changes the result. Exercise cold, warm, changed-input, permission-change,
  negative-entry, and invalidation paths; prevent miss stampedes.
- Invalidation is narrow and complete across every mutation path. Never clear the
  generated-model cache globally at runtime.
- Transactions and locks cover the invariant, not slow serialization or remote work.
  Inspect lock order, number of locked rows, contention on shared tenant keys, and
  deadlock retry behavior.
- Bounds apply before or during allocation: paginate and stream instead of buffering,
  cap graph/dependency depth and task fan-out, and measure serialized payloads rather
  than only Python objects.
- Performance claims use production-like settings and data distribution. Include
  cold and warm behavior when caching materially changes the result.

## Evidence

Leave the smallest decisive artifact: a small-versus-large query-growth test, the
relevant SQL and plan, a representative benchmark, or explicit fan-out/payload
arithmetic. When captured request data exists, Silk can connect repeated SQL to its
Baserow stack frame; never enable an option that re-executes possibly mutating
queries merely to obtain a plan.
