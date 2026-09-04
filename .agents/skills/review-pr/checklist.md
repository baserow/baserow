# Review checklist

Companion to `SKILL.md`. Each line is a rule of this repo or something the maintainers have asked for repeatedly in past reviews (PR numbers in parentheses point to the discussion). Check each line against the diff; report only lines that are actually broken, with the file and line.

## Problem and scope

- The PR description states the issue, the approach, and how to test. Numbers and claims in it are verified, not trusted. (#5928)
- The fix addresses the root cause, not the symptom: no existence checks or `?.` added to make a crash go away. (#4842)
- The fix has an observable effect; check what Caddy, uvicorn, or Django already do before accepting a duplicate mechanism. (#4327)
- Only the capabilities the issue asks for; extra powers that expose data or change links are questioned.
- Bugs sharing a root cause are fixed together; unrelated fixes, refactors, reformatting, and dependency bumps are split out or annotated inline. (#5775)
- Nothing added for a later PR: no unused parameters, always-empty plumbing, or speculative abstractions. (#5399)
- No leftovers: `console.log`, commented code, TODOs without an owner, test-time constants, dead helpers and their tests, duplicate lines from a rebase, stale references to a replaced dependency.

## Functional

### Happy path and failure paths

- Every transient state (generating, pending, locked) has an exit path on timeout, cancellation, error, and lost websocket message. (#4200)
- A mid-way failure leaves no orphaned state: `transaction.atomic` kept, one `try/finally`, side effects ordered after the durable write, cleanup consistent with what peers already saw. (#5399, #5570)
- Read-modify-write on shared state is atomic: `select_for_update`, JSONB merge, Redis Lua, `cache.lock()`. Never get-then-write. (#4200, #5666)
- Invalid or missing input fails explicitly. No silent fallback, coercion, or drop: an empty id turning update into create, a malformed param widening to all fields. (#5786)
- Only the exact exception is caught, around the exact call. `SoftTimeLimitExceeded` is re-raised in Celery loops. The original exception mapping is preserved. (#5020, #5775)
- Derived state follows its input: previews reset on importer switch, cached schemas cleared when the request changes, metadata built from the effective override. (#5968)
- User edits are never dropped: debounced inputs flushed before save, dirty state guarded against late fetches, editor kept open on failed save. (#5786)
- Truthiness is not a contract: `Number.isInteger`, `!== ''`, `Array.isArray`, explicit sentinels. `bool("false")` is `True`. (#4838, #5570)

### Lifecycle and intersections

For every new model field, field type, view option, or concept, check each path below and that a test exists for each one that applies:

- duplicate (field, table, database, application)
- export/import, including `export_serialized`, templates, Airtable import, and id remapping
- trash and restore, kept symmetric: purge related data only on permanent delete (#4200)
- undo/redo: action type registered, retry paths join the original action group
- snapshots
- field type conversion, both directions
- user deletion and workspace deletion
- row history, webhooks, automation triggers, notifications, and search index, whenever the value they receive changes (#5775)
- public and restricted views: separate endpoints, footers, broadcast paths, and serializers (#5341)
- every view type (grid, gallery, kanban, calendar, form) and the row edit modal, not only grid (#5470)
- every field type, including premium `AIFieldType` delegating to its underlying type (#5624)
- every grid mode: group by, read-only, public, row coloring, multi-row create, keyboard navigation (#5470)
- feature flag on and off: gate only user-initiated creation, keep existing objects editable, exportable, and importable (#5767)
- premium and enterprise: grep the whole monorepo for every usage of a changed component, mixin, helper, or error path (#4872)
- workspace storage usage when new user-file references are introduced

### Realtime and concurrency

- Broadcasts are gated: skipped when nobody else listens, throttled for high-frequency events, re-sent only when the output can change. (#5570)
- Realtime updates go through the regular store update path (`viewType.rowUpdated`), not per-field loops.
- Ephemeral Redis state has a TTL refreshed on every write path. Disconnect handlers are not the only cleanup. (#5399)
- Every realtime payload passes the recipient permission filter, including clear and null payloads. (#5399)
- Reconnect logic resets when the tab becomes visible or the browser is back online.
- Periodic and fan-out tasks are bounded: run lock before the scan, capped fan-out via env var, no DB spikes, lock TTL refreshed inside the loop. (#5666)
- A new `@app.task` name or a changed task signature is dropped or rejected by old workers during a rolling deploy. The effect is stated in the PR description. (#5666)
- Telemetry and log lines record one execution mode. A flag that changes what a task does must not share a histogram or counter with the other mode. (#5666)
- Splitting a priority-ordered list into parallel batches strides it (`ids[i::n]`) so workers keep processing oldest first. (#5666)
- Tests run Celery eagerly (`CELERY_TASK_ALWAYS_EAGER`), so enqueue-time behaviour (queued duplicates, backlog growth) is shown by patching `.delay`, and named in residual uncertainty when it cannot be.

## Backend code

### Placement and layers

- Data access and business logic live in a handler. Views call handlers. User-owned data mutates through an `ActionType` so the audit log and undo see it. (#4886)
- Validation and cross-cutting behaviour are enforced once, at the layer every entry point passes through (`prepare_values`, `prepare_value_for_db`, middleware), never per view. (#5716)
- Generic handlers and components stay free of type-specific branches. Add a hook with a default on the base registry type instead of `hasattr` probes. (#4119)
- A subsystem's logic stays in its own handler: `FieldHandler` calls `on_field_updated` style hooks rather than knowing about metadata or tables. (#4200)
- Registries in `registries.py`, type subclasses in `*_types.py`, serializers in `serializers.py`, actions in `actions.py`, handlers in `handler.py`, new helpers in the module that already owns the concern.
- Premium and enterprise settings live in `baserow_premium/config/settings/settings.py` and `baserow_enterprise/config/settings/settings.py`, never in core `base.py`. (#5489)
- A new field or view type mirrors its siblings: same hooks (`prepare_value_for_db`, `get_visible_field_options_in_order`), same API format, same tests. (#5775, #5973)
- One general bulk-capable handler method. Single-item helpers are thin shortcuts, not second implementations. (#4200)
- IDs identifying a resource go in the URL path. An invalid or not accessible IDs is 404; 401 is only for credentials.

### Reuse and simplicity

- Library primitives before hand-rolled ones: Celery retry, celery-singleton (`base=Singleton`, `unique_on`), `SingletonAutoRescheduleFlag`, `concurrent.futures.wait`, `schema_editor.add_index`, Sentry `ignoreErrors`. (#5666)
- Existing helpers before new ones: `str_to_bool`, `field.db_column`, `BigAutoFieldMixin`, `order_objects`, `local_cache`, `table.get_model()` (cached per request).
- No new setting when an existing one covers the concern. A value's presence can enable a feature instead of an `_ENABLED` flag. (#5112)
- No checks, filters, or `transaction.atomic()` that the callee, the default manager (`trashed=False`), or an earlier return already guarantees. (#4072, #4886)
- No object state that is read once (`notification_sent` flags, error dicts). Use a local or raise. (#4263)
- Raise a domain exception when a contract cannot be fulfilled. Never return status booleans, `None`, or a degraded flag.
- Prefer required inputs and an explicit object over optional parameters that switch behaviour.
- Imports at module top. A function-local import only breaks a cycle, and says so. (#5205)
- Schema-editor operations execute and catch already-exists. No pre-check query. (#4200)

### Naming, types, docstrings, comments

- Names say what a thing does or contains: no hidden side effects, no `enhance` or `mark_as_processed` for multi-step work, `get_` for value-returning methods, `_` only for module- or class-private helpers. (#4263, #4886)
- One term per concept across model, module, payload keys, params, and frontend state. Existing terms (`worker`, `notification`, `workspace`, `session_id`, `snapshot`, `order`) are not reused for new concepts. (#4263, #5355)
- No redundant qualifiers and no new vocabulary (`degraded`, `staleness`) that renames an existing concept. (#5355)
- Settings and cache keys are named for what they govern and prefixed by feature (`BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS`); time values carry their unit. (#4263, #5541)
- Type hints on every new or touched function, precise to runtime values: `int | None`, `UUID`, `Callable[[...], None]`. Structured data is a `TypedDict` or dataclass, never a plain `dict`. (#5399, #5507)
- Docstrings use reST `:param`, `:return`, `:raises` (only where the exception is raised, not where it propagates), are accurate on every path, and never restate method inventories, default values that `base.py` owns, or env-var explanations that `configuration.md` owns. (#5355, #4200, #5489)
- Comments: at most two lines, only a non-obvious why (magic threshold, intentional asymmetry, fragile third-party assumption). Wrong, stale, or narrating comments are findings. Existing why-comments stay while their reason holds. (#4263, #5264)
- Assumptions stated in comments are enforced in code or types.

### Performance

- No query per object: prefetch for reads, set-based `UPDATE` and `DELETE` for writes, especially in loops, migrations, and tasks. (#5136)
- No extra round trips: fetch `limit + 1` instead of `exists()` or `count()` with the same filter. (#5355)
- Model properties and serializer fields never query or parse per access. Cache per request. (#5716)
- No database transaction held across external network I/O. No `@transaction.atomic` on read-only views. (#5972)
- Large sets in bounded batches: `.iterator(chunk_size=...)`, 100 to 200 rows per task, remainder rescheduled. (#4378)
- One statement instead of select-then-write: `bulk_create(update_conflicts=True)`, `Case`/`When` reorders. Skip the write when the value is unchanged.
- Indexes match the hot queries and are checked with the planner at realistic volume. No index for a rare cleanup task. (#4298)
- Websocket and ASGI code uses `redis.asyncio` natively. `database_sync_to_async` wraps only ORM calls. (#5399)
- Generated-model cache invalidated narrowly. Never `clear_generated_model_cache()` at runtime.
- Performance claims are measured on wide or large tables in production mode. (#5551)

### Settings, logging, operability

- Numeric env vars parse with `int(os.getenv(X) or default)` so an empty string does not crash startup. Booleans use `str_to_bool`. (#5666, #5205)
- Django settings are never read in a function default argument. Default to `None` and resolve inside so `override_settings` works. Module-level constants computed from settings at import follow the existing pattern and are fine. (#5666)
- Log level tracks impact: dropped work is `warning` or higher, harmless skips lower, no `INFO` per processed item. A skip error names the setting a self-hoster should tune. (#4263, #5666)
- No `logger.exception` around external-request failures: loguru's `diagnose` prints frame locals, including resolved URLs and headers. Log ids and the exception class.
- User-facing errors describe the real state and every cause the caught exception covers. Env-var advice belongs in docs, not in messages. (#5489)

## Migrations and compatibility

- Zero downtime: the previous version keeps running against the new schema without Django ORM errors (unknown column, null violation, missing table). New fields have `db_default`. Nothing is renamed or dropped; removal is state-only via `SeparateDatabaseAndState` and the column is dropped next release behind a `# TODO ZDM` marker. A feature flag does not make a migration zero-downtime. (#4200)
- Per-row `db_default` values use DB functions (`RandomUUID`). No null-as-sentinel, no Python backfill hooks. (#4200)
- Never iterate user tables in a migration. Add columns and indexes lazily at runtime (`view_loaded_create_indexes_and_columns`) and create indexes concurrently.
- Data migrations are justified in the PR with a realistic scenario, idempotent and set-based, safe against concurrent writes, explicit about failure, and covered by a historical migration test over all stored value shapes. They are skipped when existing data already works.
- `preserve_default=False` for one-off defaults, `UniqueConstraint` over `unique_together`, integer fields sized to their real range, no unrelated column type changes.
- One migration file per branch: merge into the existing one instead of adding another.
- Rolling deploy: new Celery task names are dropped by old workers, cache keys are `VERSION`-scoped, old frontends tolerate new backend payloads and new frontends old backends, stale browser tabs do not 404 on renamed URLs. Effects are stated in the PR description. (#5972)
- Public API contract: URLs used from users' scripts, serializer fields, and query params are kept, or deprecated with an alias and a notice. A changed contract gets an explicit marker (`truncated`) and a docs update.
- Import/export and parsing formats round-trip existing stored values. A/B against `develop` before changing a serializer.
- Existing capabilities are not removed (public-view group by, unsaved field reorder). Inputs are restricted instead.
- New security guards or punitive defaults on existing self-hosted features default to off, with a tracked follow-up to flip them. A `breaking_change` changelog entry accompanies any default that changes behaviour. (#5489)
- Frontend and backend semantics are identical (`isEmpty` for link rows, `max_length` on the same stripped value). (#5469)

## Boundaries

Strict, true in the codebase today:

- `backend/src/baserow` never imports `baserow_premium` or `baserow_enterprise` outside `if TYPE_CHECKING:`.
- `baserow_premium` never imports `baserow_enterprise`.
- `contrib/database` never imports `builder`, `automation`, or `dashboard`. `builder` and `automation` never import each other.
- `web-frontend/modules/core` never imports from premium or enterprise modules.

Soft, question any deviation:

- One authoritative copy of each piece of frontend state. No mirrored copies or store-then-fallback lookups.
- Mixins declare their own props and never read `$parent`. No coupling to another store's mutation names. Public methods on the owning component instead of `$refs` or `$el` reach-ins. `this.$realtime`, not `this.$nuxt.$realtime`. (#4200, #4872)
- `GridView` stays unaware of public versus authenticated context. The page component passes normalized capabilities such as `readOnly`.
- Local stores or composables for component-bound state with in-flight async actions.

## Frontend

- Copy only in `en.json`. Type classes return text via `this.app.i18n.t()`. No dynamic `$t` keys built from a prefix. No copy for functionality not yet delivered.
- SCSS: dedicated file imported via the bundle, BEM, `$palette-*`, explicit classes over `:last-child`, one component per file, dead rules removed, no reuse of a grid `::before` or `::after` already used by sorted, filtered, or grouped states.
- Buttons inside grid cells use `@mousedown.prevent.stop`. Keys in editing mode act on the input, not on grid navigation.
- Forms: errors inline with `<Alert>` beside the inputs, full text wrapped, no toasts. Lazy validation (pristine until Save), first collapsed section with errors expanded on submit. (#4171)
- Pending background updates and failed actions are visible. An optimistic value never hides a delayed warning. A newer error replaces a stale one. (#5956)
- Row values interpolated into URLs are encoded individually. Composite values (select, link row, file) are refused.
- Routes by name via `router.js`, not hard-coded paths.
- The frontend never hides an action the backend allows and never shows one it forbids. Data providers fail on the same missing path segments the backend does.
- In-flight requests are managed: no repeated rows request while one is pending, outdated ones aborted. Tested with a throttled network.
- No needless recomputation: never spread an injected reactive context inside `provide` or `computed`. Memoize per-cell contexts.
- `yarn.lock` is updated by `yarn install` after any dependency change, never by hand.
- Manual UI test matrix: matches Figma exactly (screenshots of every deviation); long names, 100 users, adjacent selections, wide tables, every row height, mobile layout, Safari for drag and drop; a 1M-row staging table for grid or virtual-scroll changes; framework migrations compared against the previous version. (#5399, #5570, #4918)

## Security

- Any URL the server fetches (data sync, SSO, webhooks, AI providers, integrations, previews) goes through advocate. A host-safety check covers loopback, link-local, CGNAT, mapped and 6to4 IPv6, and the host's own addresses, not just `ip.is_private`. DNS is resolved once and the validated IP is used for the connection. (#5489)
- Connections to user-chosen hosts set connect and statement timeouts. Outbound responses are bounded while streaming, with a decompression-aware ceiling.
- Enterprise egress proxies: advocate rejects `HTTP_PROXY`. Check the impact before guarding an existing flow.
- Nothing rendered from user input is unescaped (`v-html`, markdown, rich text). Rich-text image nodes reference an existing `UserFile`, never an external URL.
- Secrets are write-only serializer fields, masked in responses, and redacted from exports, snapshots, templates, AI prompts, and logs (`sensitive_fields` on service types). Example secrets in env templates visibly say they must change. Password hashes and other write-only values never reach data providers.
- Every endpoint checks permission with the right operation type on the right context. Ids are derived server-side from the authoritative object (`view.table_id`), never trusted from the client. User lookups in auth paths filter `is_active=True`.
- Restricting access through a view covers every path: single-row GET, search, list, aggregations, realtime. Restricted-view users never receive full-access users' ids. (#4072, #5399)
- Public views exclude fields carrying formulas or hidden field ids. Public serializers leak nothing beyond the visible payload.
- Actions triggered by a user run as, and are attributed to, that user, never the field or integration creator. Low-permission clickers never receive raw external responses or headers. (#5755)
- Client input is validated with allowlists and bounds before use in paths, regexes, or `open()`. `\d+` accepts Unicode digits and unbounded length.
- Workspace import extracts only zip members listed in the signed manifest.
- A disabled feature is enforced server-side at the ingest or emission point, not only by filtering recipients, with a regression test.
- A security fix protects existing accounts, cannot lock users out without admin recovery, and matches the real threat. (#5907)

## Tests

- Every fix and every edge case raised in review has a regression test at the layer it lives, and it fails on the old code. (#5951)
- Assertions prove the named behaviour with a case the broken implementation would fail: rendered output, order, values, a guarded call not invoked. Not prop values, counts, or "code ran". (#5571)
- Setup through `data_fixture`, handlers, and shared fixtures, not mocks or manual model mutation. Failure paths are driven with real failing input, never a mocked exception the code never raises. (#4119)
- Guards are exercised, not bypassed: a private-IP test on a blocked port never reaches the IP check; an autouse patch that serialises an executor means no test covers concurrency. (#4263, #5489)
- Existing assertions are never loosened or removed during a refactor without evidence. A "flaky" claim needs a failing run.
- Tests do not lock in wrong behaviour (tolerating inconsistent data, or the old behaviour the PR replaces).
- Deterministic: no timing-based sync, no colliding random values, per-run unique ids, cleanup in `finally`, assertions never gated behind a runtime condition.
- Lean: parametrize variants, extract repeated setup into a local fixture, drop tests implied by others, minor edges in unit tests rather than e2e.
- A new type has the tests its siblings have (action signals, import/export, duplication, id remapping).
- Permission-gated UI, per role: click the visible button and verify success; when hidden, assert the API rejects with a permission error. (#5805)
- e2e drives the real UI flow (same session, two windows for realtime), never state created through the API. Ports come from the stack env, not hard-coded.
- Field-dependent features are tested against the "All field types" template.

## Docs and process

- Every new `BASEROW_*` env var has a row in `docs/installation/configuration.md` (correct default, empty-value semantics, what it disables), a line in `.env.example`, and an entry in every docker-compose file. Follow the `add-django-config-env-var` skill.
- Docs match the code: real identifiers, no invented numbers, no removed dependencies. Technical docs describe concepts, models, and fields, not method names. (#5355)
- A subsystem with new concepts gets a `docs/technical/` doc defining terms and relationships. A decision that deviates from an ADR amends it in the same PR. (#5973)
- Admin-facing trust assumptions (the IdP verifies emails) are documented in setup docs and the settings UI.
- Changelog via `just changelog add`: a user-facing sentence, correct type and domain, bare issue number, no bullet points. One entry when a flagged feature ships, not per slice. `breaking_change` when a default changes. (#5197, #5055)
- Backend translatable strings changed: `just b make-translations` was run and the `.po` files are committed.
- Stacked PRs target the parent branch. The parent is not merged alone when it depends on the child's fix.
- Every deferred item has a follow-up issue before approval.
- Review feedback lands as new commits, not rewritten history.
- The original author or owning team (grid view, rich text, builder) is tagged for delicate code.
- External PRs touching `premium/` or `enterprise/` cannot be accepted for license reasons. Thank and close.
