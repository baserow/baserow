# Signals and `transaction.on_commit`

Two backend rules prevent many subtle bugs:

1. Use signals only for real fanout.
2. Run externally visible side effects after the database transaction commits.

For a complete realtime example, see [Realtime end-to-end](realtime-end-to-end.md).

## Signals

A signal is a publish/subscribe boundary. Use one when the emitter should not
know which subsystems react.

Good reasons to emit a signal:

- Multiple subsystems react to the same state change.
- Premium, enterprise, plugins, telemetry, or future code may react.
- The emitter and receiver sit across an import boundary.
- The event is a stable domain event, such as `rows_created` or
  `field_updated`.

Prefer a direct call when there is exactly one local receiver and no credible
extension point. A signal of one is usually just hidden control flow.

## `transaction.on_commit`

Any side effect with external visibility must run after commit:

```python
from django.db import transaction

transaction.on_commit(lambda: my_task.delay(row.id))
```

Use it for:

- Celery tasks.
- Websocket broadcasts.
- Emails.
- Webhooks or external HTTP.
- Cross-process cache invalidation.

Without it, a side effect can describe data that later rolls back.

## Ownership

Put `on_commit` in the receiver or side-effect owner, not at the signal emit
site. The emitter knows that something happened; the receiver knows whether its
reaction is externally visible.

```python
@receiver(row_signals.rows_created)
def rows_created(sender, rows, user, table, **kwargs):
    transaction.on_commit(
        lambda: page_registry.get("table").broadcast(
            RealtimeRowMessages.rows_created(...),
            getattr(user, "web_socket_id", None),
            table_id=table.id,
        )
    )
```

## Common Patterns

```python
# Wrong: worker may read before commit.
my_task.delay(row.id)

# Correct.
transaction.on_commit(lambda: my_task.delay(row.id))
```

```python
# Better than N callbacks in a loop.
transaction.on_commit(lambda: my_task.delay([row.id for row in rows]))
```

If a callback does slow work, queue a Celery task from `on_commit`; do not do the
slow work inside the callback. `on_commit` callbacks run synchronously during
commit.

## Adding a Signal

1. Confirm there is fanout or a real extension point.
2. Emit from the handler that owns the state change.
3. Name it in the past tense: `thing_created`, `thing_updated`.
4. Pass stable context in kwargs; adding kwargs later is safe, removing them is
   not.
5. Keep receivers short and side-effect focused.
6. Wrap external side effects in `transaction.on_commit`.
7. Test at least one receiver and the rollback case when the side effect matters.

## Anti-Patterns

- Emitting a signal and also doing the same side effect inline.
- Adding a signal only to avoid a normal function call.
- Calling `on_commit` outside any transaction and assuming it defers work; in
  autocommit mode it runs immediately.
- Mixing `on_commit(do_it)` in one branch and `do_it()` in another for the same
  side effect.
- Emitting long chains of signals from receivers unless the chain is short,
  intentional, and tested.

## Debugging

Find receivers with `rg`:

```bash
rg "@receiver\\(.*rows_created|@receiver\\(rows_created|@receiver\\(row_signals.rows_created" \
  backend/src/baserow premium/backend enterprise/backend
```

Repeat with the signal name you care about. Receivers are top-level functions
decorated with `@receiver`.

## Related

- [Realtime end-to-end](realtime-end-to-end.md).
- [Celery](../technical/celery.md).
- [Caching](../technical/caching.md).
- [Notification system](../technical/notification-system.md).
- [Action system](../technical/action-system.md).
