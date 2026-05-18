# Baserow formula technical guide

This is the engineer's view of the database formula system — the one that
powers the `formula`, `lookup`, `rollup`, and `count` field types in user
tables. For the user-facing explanation see
[understanding Baserow formulas](../tutorials/understanding-baserow-formulas.md).

> **Not this doc:** there is a *separate* "runtime formula" system under
> `backend/src/baserow/core/formula/` used by the application builder
> (`get('current_user.email')`, `concat('Hello ', name)`, etc.). It shares
> the grammar but nothing else — no typing, no materialisation, no
> dependency graph. If you're touching the builder, that's a different
> codebase that happens to live next door.

## The one thing to internalise: formulas are materialised

A Baserow formula is **not** evaluated at query time. Every formula field
is backed by a real Postgres column on the user table. The cell value you
see in a grid view is just `SELECT formula_column FROM ...` — there is no
expression to evaluate. What the formula machinery actually does is
produce, on every change, a Django ORM expression that gets fed to a bulk
`UPDATE` over that column.

This shapes the whole architecture and is the answer to most "wait, how
does this work?" questions:

- **Why so much code on the write path?** Because we pay the formula cost
  on write, not on read. Reads are cheap.
- **Why a typing pass?** Because we need to pick the right Postgres column
  type up front (`numeric`, `text`, `jsonb`, …) and choose the right
  ORM expression for the cast.
- **Why a dependency graph?** Because if A depends on B, an update to B
  must re-`UPDATE` A's column. We need to know what to recompute and in
  what order.
- **Why can formula fields reuse formula fields?** Because every
  intermediate is itself a materialised column. A formula referencing
  another formula is just `F("field_123")` — no inlining, no exponential
  expression bloat, no recompilation cascade.

The corollary: **changing a formula or its dependencies rewrites column
data, not just metadata.** A `formula` field is closer to a generated
column than to a Django `@property`.

## The pipeline

A user types a string. By the time it hits a row's column, six things
have happened.

```
formula string
   │  parser/parser.py — ANTLR4
   ▼
ANTLR parse tree
   │  parser/ast_mapper.py — BaserowFormulaToBaserowASTMapper
   ▼
untyped BaserowExpression (AST)
   │  types/typer.py + types/visitors.py:FormulaTypingVisitor
   ▼
typed BaserowExpression (every node has a BaserowFormulaType)
   │  expression_generator/generator.py
   ▼
Django ORM Expression
   │  handler.py:recalculate_formula_and_get_update_expression
   ▼
Bulk UPDATE on the user table's formula column
```

### 1. Grammar and parser

ANTLR4. Grammar at `formula/BaserowFormula.g4` and
`formula/BaserowFormulaLexer.g4` in the repo root. Generated Python parser
under `backend/src/baserow/core/formula/parser/generated/`. Entry point:
`baserow.core.formula.parser.parser.get_parse_tree_for_formula`. The
generated code lives in `core/` rather than `contrib/database/` because
both formula systems (database and builder) share the grammar.

### 2. Parse tree → Python AST

`backend/src/baserow/contrib/database/formula/parser/ast_mapper.py`. The
`BaserowFormulaToBaserowASTMapper` (line 54) is the ANTLR visitor that
walks the parse tree and emits `BaserowExpression` nodes. Entry point:
`raw_formula_to_untyped_expression()` (line 32).

The AST nodes live in
`backend/src/baserow/contrib/database/formula/ast/tree.py`:

- `BaserowExpression[A]` — generic base; `A` is the type parameter (`UnTyped`
  before typing, a concrete `BaserowFormulaType` after).
- `BaserowFunctionCall[A]` — a function applied to args. Holds a
  `BaserowFunctionDefinition`.
- `BaserowFieldReference[A]` — refers to another field by name. After
  typing this is rewritten to reference by ID (see "internal formula").
- `BaserowStringLiteral` / `BaserowIntegerLiteral` / `BaserowDecimalLiteral`
  / `BaserowBooleanLiteral`.

Every node has `.accept(visitor)`. All the rest of the pipeline is visitors.

### 3. Type resolution

`backend/src/baserow/contrib/database/formula/types/typer.py:12` —
`calculate_typed_expression`. Walks the untyped AST with
`FormulaTypingVisitor` (`types/visitors.py:220`), assigning a
`BaserowFormulaType` to each node bottom-up. The result is a fully typed
AST or — if anything failed — a tree whose root is wrapped in
`BaserowFormulaInvalidType` carrying an error message.

`BaserowFormulaType` lives in
`backend/src/baserow/contrib/database/formula/types/formula_type.py:66`.
Concrete types are in `types/formula_types.py`:
`BaserowFormulaTextType`, `BaserowFormulaNumberType`,
`BaserowFormulaBooleanType`, `BaserowFormulaDateType`,
`BaserowFormulaDurationType`, `BaserowFormulaSingleSelectType`,
`BaserowFormulaMultipleSelectType`, `BaserowFormulaArrayType`,
`BaserowFormulaURLType`, etc. The special `BaserowFormulaInvalidType`
lives next to the base class in `types/formula_type.py:570`. The concrete
types are discovered through the `BASEROW_FORMULA_TYPES` module-level list
at `formula_types.py:1984`.

Each `BaserowFormulaType` answers two questions:

- **What Django field stores my value?** — via `get_model_field(...)` and
  `db_column_fields`. This is where the storage-format mismatch lives
  (see below).
- **What's the "compatible" Baserow field type for filters/sorts?** —
  via `baserow_field_type` (e.g. `"text"`, `"number"`). The view filter
  registry uses this to decide which filters apply to a formula column.

### 4. AST → Django expression

`backend/src/baserow/contrib/database/formula/expression_generator/generator.py`.
The `BaserowExpressionToDjangoExpressionGenerator` walks a typed AST and
emits Django ORM `Expression` objects (`F`, `Func`, `Cast`, `Subquery`,
…). Three public entry points:

- `baserow_expression_to_update_django_expression` (line 40) — for bulk
  `UPDATE` over an existing column.
- `baserow_expression_to_insert_django_expression` (line 56) — for
  `INSERT`. Different because aggregate-style sub-expressions can't run
  on a row that doesn't have an id yet.
- `baserow_expression_to_single_row_update_django_expression` (line 47)
  — single-row variant used when one row needs to refresh.

### 5. Persistence — the materialised column

`FormulaHandler.recalculate_formula_and_get_update_expression`
(`handler.py:399`) is what `FieldHandler` calls when a formula field is
created, the formula text changes, or a dependency changes. It:

1. Saves the recalculated `FormulaField` metadata.
2. Calls `recreate_formula_field_if_needed(...)` to **drop and recreate
   the Postgres column** if the formula type changed (e.g. number → text).
   This is real DDL.
3. Returns the Django UPDATE expression that the caller runs to
   re-populate the column.

That last step is the materialisation: `model.objects.update(field_X=expr)`.

### 6. Recompute on dependency change

When field B (which A depends on) changes, the field dependency graph
identifies A as needing a refresh, and the same expression-generation
machinery emits a new UPDATE. The handler-level walkthrough is in
[field-system.md](../patterns/field-system.md). Topological order means
chains of formula-of-formula resolve in a single pass.

## The dependency graph

`backend/src/baserow/contrib/database/fields/dependencies/`. Three things
to know:

- **Storage** — `FieldDependency` rows
  (`dependencies/models.py:4`): `dependant` FK → `dependency` FK, optional
  `via` (LinkRowField), optional `broken_reference_field_name`. The
  graph is real data, not a runtime computation.
- **Build** —
  `dependencies/dependency_rebuilder.py:rebuild_fields_dependencies`. For
  a formula field, it asks the typed AST for the fields it references
  (`BaserowFieldReferenceVisitor` in
  `formula/parser/ast_mapper.py`), then writes `FieldDependency` rows.
- **Walk** — `FieldDependencyHandler._get_all_dependent_fields`
  (`dependencies/handler.py:80`) uses `graphlib.TopologicalSorter` to
  return dependants in order. A change to one field triggers refresh of
  every dependant in topological order, each one a single bulk UPDATE.

The graph encodes link-row hops, so a formula `lookup("Friends", "Name")`
adds an edge "this field → friends.name via the Friends link row".
Changes on either side trigger the right recompute.

## Internal formula vs user formula

`FormulaField` (in `fields/models.py:626`) has two text columns:

- **`formula`** — the user's input verbatim, with field references by
  *name*: `field('Total') * 2`. This is what the UI shows.
- **`internal_formula`** — a normalised form with field references by
  *id*: `field_by_id(123) * 2`. This is what we parse and type.

The split matters because **renaming a field doesn't change the formulas
that reference it.** The id-keyed `internal_formula` is stable; only the
user-facing `formula` text needs to update its quoted name. Renaming a
field walks every formula in the table, regenerates the user-facing
`formula` string from the unchanged `internal_formula`, and sends it
back. No re-parse, no re-type.

The same column also lets us detect when *deleting* a field would
silently break a formula — we know which ids the formula references
without reparsing.

## Formula types and storage formats

This is a real footgun. A formula's storage column **does not always
match the column format of the underlying field type with the same name.**

The mismatches:

| `BaserowFormulaType` | `baserow_field_type` (filter compat) | Actual storage |
|---|---|---|
| `BaserowFormulaTextType` | `text` | `text` column |
| `BaserowFormulaNumberType` | `number` | `numeric` column |
| `BaserowFormulaSingleSelectType` | (none) | `JSONField` — stores `{"id": ..., "value": ..., "color": ...}` |
| `BaserowFormulaMultipleSelectType` | (none) | `JSONField` (array of objects) |
| `BaserowFormulaArrayType` | (none) | `JSONField` (array of element-typed objects) |
| `BaserowFormulaLinkType` | (none) | `JSONField` — stores `{"label": ..., "url": ...}` |

The reason: a formula returning a single-select isn't a real
`SelectOption` FK. There's no parent option row to point at — the formula
*computes* the option. So we store a denormalised JSON snapshot of what
the option looks like *at recompute time*.

Consequences for anyone writing code against formula columns:

- **Don't `F("formula_field_id") == single_select_id`.** It's not a FK;
  it's JSON.
- **Filters know this** because they go through `baserow_field_type`. If
  you're writing a new filter on a select field that should also work
  on a formula returning a select, route via the formula type's
  `baserow_field_type`, not the raw model field.
- **If the upstream select option's name or colour changes, the
  formula's snapshot is stale until the next recompute.** That recompute
  is scheduled by the dependency graph, so this is usually fine — but
  bulk imports / direct DB edits can leave snapshots out of date.

## Functions

A function is a `BaserowFunctionDefinition` subclass
(`formula/ast/tree.py:408`) registered in `formula_function_registry`
(`formula/registries.py:10`). A function decides:

- **What arguments it accepts** — fixed count, range, or unlimited
  (`FixedNumOfArgs`, `NumOfArgsGreaterThan`, `NumOfArgsBetween`).
- **What types it accepts and returns** — `type_function(args)` runs at
  typing time; it can reject mismatches, *or* it can rewrite the AST
  (e.g. `concat(date, bool)` wraps both args in `toText(...)` calls).
  This is how implicit coercion works.
- **How to emit Django** — `to_django_expression_given_args(args)`.

Most function definitions inherit from the arity helpers
(`ZeroArgumentBaserowFunction`, `OneArgumentBaserowFunction`, etc., in
the same file) which collapse the boilerplate.

Operators (`+`, `*`, `==`, …) are not a separate concept — the parser
maps them to function calls. `+` is `BaserowAdd`, `==` is
`BaserowEqual`, etc. Precedence comes from the grammar's rule ordering
in `BaserowFormula.g4`. Operator "overloading" (`'a' + 'b'` vs `1 + 2`)
is just a function whose `type_function` returns different output types
based on its arguments.

## Lookup, rollup, count — formulas in disguise

`CountField`, `RollupField`, and `LookupField` (all in `fields/models.py`,
each subclassing `FormulaField`) are not separate concepts. They're
formulas with their `formula` text generated internally from a few
parameters:

- `CountField(through_field=Friends)` → `count(field('Friends'))`.
- `RollupField(through_field=Friends, target_field=Score, rollup_function=sum)`
  → `sum(lookup('Friends', 'Score'))`.
- `LookupField(through_field=Friends, target_field=Name)`
  → `lookup('Friends', 'Name')`.

`FormulaFieldType` (`fields/field_types.py`) handles all four. The
lookup/rollup/count UI builds the formula string under the hood and the
rest of the pipeline runs exactly the same.

This is why all four go through the same dependency graph, the same
typing pass, and the same materialised column. Once you understand
formulas, you understand lookup/rollup/count for free.

## Formula language versioning

The formula language grows over time — new functions, fixed type
inference bugs, changed semantics. We don't want to break user formulas
in long-lived workspaces. The solution:

- `BASEROW_FORMULA_VERSION` (currently `5`) is the language version this
  build of Baserow understands.
- `FormulaField.version` records the version a given formula was last
  recalculated under.
- `formula/migrations/migrations.py` defines `FORMULA_MIGRATIONS` — one
  entry per version with what work needs doing to bring a formula from
  `version=N-1` up to `version=N` (recalculate attributes, rebuild
  dependencies, recompute cell values, force-recreate columns).

A Baserow deployment startup runs the formula migration runner and
catches up any out-of-date formulas. Adding a function that doesn't
change existing semantics doesn't need a new version; changing typing
rules or fixing a bug whose old behaviour was observable does. The
existing entries are a good reference for what counts as which.

## Invalid type — graceful failure

When typing fails (referenced field deleted, type mismatch, parse
error), we don't crash. The whole expression is wrapped in
`BaserowFormulaInvalidType(error)` and the column's storage type
collapses to text. The error message lives on `FormulaField.error`. The
UI shows it in the formula configuration drawer.

What makes this safe:

- The "invalid" column is still a real Postgres column — queries don't
  fail.
- The dependency graph still tracks the broken reference (the
  `broken_reference_field_name` column on `FieldDependency`).
- The moment the broken reference becomes resolvable again — a deleted
  field is restored, a new field with the right name is created — the
  formula re-types automatically and the column is repopulated.

## Aggregates and the post-insert refresh

Aggregate formulas (sum, count, every, …) cannot be evaluated inside
the same `INSERT` that creates the row — at INSERT time the new row has
no id yet, so the subqueries that would walk to linked rows have
nothing to bind. The flag
`FormulaField.requires_refresh_after_insert` records this; row creation
runs an `UPDATE` immediately after the `INSERT` to populate aggregate
columns.

There's a similar
`needs_periodic_update` for formulas containing time-sensitive functions
(`now()`, `today()`) — Celery refreshes these on a schedule.

`FormulaHandler._expression_requires_refresh_after_insert` carries this
warning in a comment:

> WARNING: This function is directly used by migration code. Please
> ensure backwards compatibility when adding fields etc.

That's because the cached flag is computed during formula migrations.
Changing what `_expression_requires_refresh_after_insert` returns can
quietly invalidate stored data on the next migration run.

## Frontend

The frontend has its own ANTLR-generated parser
(`web-frontend/modules/core/formula/parser/`) used purely for **client-side
validation, syntax highlighting, and autocomplete** in the formula input.
It does not type-check or evaluate — only the backend is authoritative.

The grammar is shared (one `.g4` source, two generators). When you
change the grammar, regenerate both via `formula/build.sh`. The
backend parser is regenerated under
`backend/src/baserow/core/formula/parser/generated/`; the frontend's
counterpart is under `web-frontend/modules/core/formula/parser/`.

## Visitors worth knowing

Spread across a few modules under
`backend/src/baserow/contrib/database/formula/`:

- `FormulaTypingVisitor` (`types/visitors.py:220`) — untyped → typed.
- `BaserowExpressionToDjangoExpressionGenerator`
  (`expression_generator/generator.py`) — typed → Django ORM.
- `BaserowFieldReferenceVisitor` (`parser/ast_mapper.py:188`) — collects
  referenced field ids. Used by the dependency rebuilder and by
  rename/delete logic.
- `FunctionsUsedVisitor` (`types/visitors.py:39`) — list of function names
  in the expression. Used to compute `needs_periodic_update`.
- `BaserowFormulaASTVisitor[Y, X]` (`ast/visitors.py:10`, the base) —
  generic visitor base class; `Y` is input type-parameter, `X` is the
  return type.

Writing a new pass over the AST is almost always "subclass
`BaserowFormulaASTVisitor`".

## Where to grep when debugging

| Symptom | Look at |
|---|---|
| "Formula doesn't recompute when X changes" | `dependencies/dependency_rebuilder.py`, `BaserowFieldReferenceVisitor` |
| "Formula returns wrong type" | `types/visitors.py:FormulaTypingVisitor`, the function's `type_function` |
| "Formula returns right type but wrong value" | `expression_generator/generator.py`, the function's `to_django_expression_given_args` |
| "Formula column got dropped/recreated" | `handler.py:recalculate_formula_and_get_update_expression`, `recreate_formula_field_if_needed` |
| "Filter on formula column doesn't work" | `BaserowFormulaType.baserow_field_type`, the field-type's filter list |
| "After deploy, lots of formulas need recompute" | `formula/migrations/migrations.py`, `BASEROW_FORMULA_VERSION` |
| "Aggregate formula shows null after insert" | `requires_refresh_after_insert` flag, the post-insert UPDATE in `RowHandler` |

## Tests

- `backend/tests/baserow/contrib/database/formula/` — type system,
  function-by-function semantics, AST round-trips.
- `backend/tests/baserow/contrib/database/field/` — `LookupField`,
  `RollupField`, `CountField` behaviour.
- `backend/tests/baserow/core/formula/` — parser, runtime formula
  (builder) execution.
- `web-frontend/test/unit/formula/` — frontend parser, validator,
  autocomplete.

## Related

- [Field system](../patterns/field-system.md) — where formula fields
  hang off the broader field/handler architecture and dependency cascade.
- [Dynamic models](dynamic-models.md) — why dropping and recreating a
  formula column requires invalidating the generated-model cache.
- [Table rows full-text search](table-rows-search.md) — how the formula
  type's resolved `baserow_field_type` decides how the formula's value
  enters the search index.
- [PostgreSQL locks](postgresql-locks.md) — formula recompute holds row
  locks during the UPDATE; matters when a wide table has many
  formula-of-formula dependencies.
- [Understanding Baserow formulas](../tutorials/understanding-baserow-formulas.md)
  — user-facing tutorial.
