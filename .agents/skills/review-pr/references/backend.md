# Backend and API review

Use this reference for production Python, Django models, API views, handlers,
actions, services, registries, and settings. Load the security, data-performance,
or state-compatibility references as well when their triggers apply.

## Domain boundaries

- When a change crosses model, handler, service, action, or API boundaries, consult
  [manage-backend-layers](../../manage-backend-layers/SKILL.md) for the owning layer
  and nearby patterns. Use it to evaluate the change against its contract; do not
  run its implementation workflow as part of the review.
- Views authenticate, parse, call the domain layer, and serialize. Querying and
  persistence belong in handlers; services coordinate permission-aware domain work.
  Mutations that participate in action history and undo go through an `ActionType`;
  follow the owning module's contract for internal or non-undoable operations.
- Enforce an invariant at the lowest shared boundary every entry point crosses.
  Avoid repeating validation or permissions in individual views, serializers, bulk
  paths, imports, or tasks.
- Extend generic behavior through the owning registry hook with a safe default. Do
  not add type-specific branches or `hasattr` probes to generic handlers.
- Keep one bulk-capable implementation. Single-item helpers should delegate rather
  than become a second behavior path.
- Keep the dependency direction one-way: core should not import `contrib`, premium, or
  enterprise at all, not even under `TYPE_CHECKING`, but it's allowed to name the implementation in a comment if adds clarity. Premium should not import enterprise. One contrib should import another only when strictly needed; prefer lifting the shared piece into core. Develop still breaks this, so report only what a diff adds or widens.
- Keep serializers in `serializers.py`, actions in `actions.py`, registries in
  `registries.py`, type subclasses in `*_types.py`, and domain work in `handler.py`.
  Premium and enterprise settings stay in their own config packages.

## Contracts and Django behavior

- Resolve the authoritative resource first, then derive workspace/parent ids and
  permissions from it. Resource ids belong in URL paths. Preserve the endpoint's
  established missing-resource and permission-denied contract: the shared
  [`map_exceptions`](../../../../backend/src/baserow/api/decorators.py) mapping uses
  [`ERROR_PERMISSION_DENIED`](../../../../backend/src/baserow/api/errors.py) (401)
  for `PermissionException`, while specific endpoints may deliberately use 404.
  Trace the actual exception mapping and tests before proposing a status change.
- Return a typed domain result when the read shape differs from the model. Do not
  monkey-patch transient attributes onto ORM instances or encode alternate outcomes
  in a plain dict, bool, or `None`.
- Catch only the exception whose behavior changes, around the call that raises it.
  Preserve the established API error mapping and re-raise `SoftTimeLimitExceeded` in
  Celery loops.
- Keep transactions around the invariant and durable writes, not read-only requests,
  serialization, or external I/O. Re-read mutable state under the appropriate lock
  when the decision depends on freshness.
- When a mutation schedules tasks, broadcasts, or other external effects, apply the
  [commit and rollback checks](state-compatibility.md#commit-and-rollback-effects).
- Resolve Django settings inside the function when tests may override them. Avoid
  reading a setting in a default argument.
- Reuse a setting only when it governs the same resource, unit, valid range,
  consumers, operational effect, and security policy. A similar value type is not a
  shared policy boundary.
- Search for the established subsystem primitive before adding a second mechanism,
  especially `local_cache`, `table.get_model()`, `order_objects`, `str_to_bool`,
  celery-singleton helpers, advocate, and schema-editor operations.

## Repository-specific completion

- New and touched functions follow the repository's precise type-hint and reST
  docstring conventions where the contract is not already self-evident from an
  override or tiny helper.
- Backend translatable strings require `just b make-translations` and the generated
  catalog changes.
- A new environment setting must reach the settings layer, `.env.example`, every
  applicable Compose/Helm/runtime consumer, env remapping, and the installation
  configuration docs. Verify that the process which uses it actually receives it.
- Tests use shared fixtures and handlers rather than constructing impossible model
  states or mocking exceptions the real path cannot raise.
