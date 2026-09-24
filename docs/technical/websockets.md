# Working with websockets

Baserow uses [Django Channels](https://channels.readthedocs.io/en/latest/) library to handle websocket connections.

## Consumers

The communication between connected clients (like the Baserow web-frontend) and Baserow backend is done through Django Channels [consumers](https://channels.readthedocs.io/en/latest/topics/consumers.html). A consumer is akin to a Django view. It can receive payloads from a client and send payloads to the client. The difference is that consumers are stateful and handle communication back and forth for the whole duration of a websocket connection.

Similarly to Django views, consumers are hooked to a particular URL, see this excerpt from `backend/src/baserow/ws/routing.py` on how the `CoreConsumer` is routed:

```python
websocket_urlpatterns = [re_path(r"^ws/core/", CoreConsumer.as_asgi())]
```

The above example shows that any client that wants to establish a websocket connection using the `ws/core/` URL (with ws protocol) will be handled by the `CoreConsumer`.

Each consumer has access to the connection’s [scope](https://channels.readthedocs.io/en/latest/topics/consumers.html#scope) which is like the `request` object in traditional views, holding various information about the connection.

### AsyncJsonWebsocketConsumer

We use [`AsyncJsonWebsocketConsumer`](https://channels.readthedocs.io/en/latest/topics/consumers.html#asyncjsonwebsocketconsumer) from the Django Channels library as the base for our consumers since we want to exchange JSON payloads. These consumers typically have three main event handlers: `connect` (for setting up the connection or revoking the connection), `disconnect` (for cleanup), and `receive_json` (for reacting to client's messages).

In each AsyncJsonWebsocketConsumer, we will typically want to:

- React to client's messages in `receive_json`
- Send messages back to the connected client via `self.send_json(..)`
- React to custom events by implementing our own event handlers as class methods, e.g. `async def react_to_custom_event(self, event):`. Custom events are for handeling messages coming from other consumers or other backend code as opposed to handeling messages from clients.
- Join channel layer groups via `self.channel_layer.group_add(..)` to subscribe clients to additional events (more on that below).

Let's have a look at a simple consumer:

```python
class MyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

        # We can access the scope object holding connection's information
        # In this case Django Channels will provide
        # authenticated user
        user = self.scope["user"]

        if not user:
            # We don't have to allow the connection to
            # be established.
            await self.close()
            return

        # Join every new connection to the "users" channel group
        # that can be used to later broadcast messages to everyone
        await self.channel_layer.group_add("users", self.channel_name)

    async def disconnect(self, message):
        # Remove the connection from a channel group
        await self.channel_layer.group_discard("users", self.channel_name)

    async def receive_json(self, content, **parameters):
        # Process a message from a client

        # If client sends "Hi", say Hello back
        if "hi" in content:
          await self.send_json({"message": "Hello back!"})

    # Event handlers

    async def react_to_custom_event(self, event):
        # To invoke this event we will need to manually
        # send a message to channel layer with this event name
        ...
```

### CoreConsumer

The main Baserow consumer is `CoreConsumer` (from `backend/src/baserow/ws/consumers.py`). It currently handles all web-frontend connections, all backend events and exchange of all messages between clients and the backend.

### Concurrency and database access

Keep consumer handlers nonblocking. Synchronous database, network, or expensive CPU
work on the event loop delays every connection served by that loop. Channels processes
messages sequentially within each consumer; awaiting a replay or permission check
delays later messages on that socket, while other consumers can continue.

ORM calls must use `run_database_sync` from `baserow.ws.telemetry`, or Channels'
`database_sync_to_async`. In ordinary WebSocket scopes these calls share one
thread-sensitive executor thread per ASGI process. Cold authentication, page
permission checks, and presence-space resolution use this executor. Anonymous and
valid cached-user authentication avoid it. Slow shared operations can still delay
other operations using that thread; adding ASGI workers does not increase the
concurrency within one worker.

`CoreConsumer.dispatch` does not submit database cleanup before every message.
Database-free handshakes and live, presence, and control delivery therefore avoid
waiting behind unrelated shared-thread work. Each ORM adapter cleans connections
before and after its operation on the connection-owning thread, including on error.
Channels also retains its final disconnect cleanup after presence and group teardown.
That final cleanup can wait for the shared thread before the application terminates.
Do not move connection cleanup to an arbitrary thread or create a thread per socket.

Use [WebSocket telemetry](../installation/monitoring.md#websocket-and-realtime-metrics)
to distinguish executor queueing, database execution, and event-loop delays.

## Channel Layer and Channel Groups

In essense, a [channel layer](https://channels.readthedocs.io/en/latest/topics/channel_layers.html) facilitates cross-process communication like the communication between consumers themselves or between consumers and any other backend code that needs to send messages to connected clients. Baserow uses [RedisChannelLayer](https://github.com/django/channels_redis/) for this purpose.

Each consumer has a unique *channel name* (the `self.channel_name` in the example above), and can join arbitrary-named groups, allowing both point-to-point and broadcast messaging.

Currently, `CoreConsumer`s use these channel groups for broadcasts:

- `users` for all connected clients (includes anonymous users)
- page groups representing "table", "view", or "row" pages that have been originally created for people browsing these pages to receive real-time updates
- permission-oriented groups to track consumers that need to listen to permission updates and be able to disconnect from channel groups that they shouldn't be a part of anymore

## Pages and Subscriptions

`CoreConsumer` has a concept of *pages* that a client can subscribe to in order to receive messages targeting specific pages. Clients have to manually request to be subscribed with a special payload. The consumer can then check if the client has the permissions necessary to receive these page updates and if so, add itself to the particular channel group representing the page.

For example, users can subscribe to receive updates to a particular Baserow table. If the request is permitted, the consumer handling the connection will join `table-{id}` channel group and start receiving messages related to the table page with the particular id.

Each page that can be subscribed is implemented as a `PageType` and registered in `page_registry` so it is possible to implement new page types without making changes to the consumer itself. See `backend/src/baserow/ws/registries.py` for details.

## Message Broadcasting

Often we need to notify connected clients about something. For example, clients subscribed to a table page need real-time updates about created or updated rows.

The main method to send a message to all consumers (all clients) in a particular channel group is through `send_message_to_channel_group()` function in `backend/src/baserow/ws/tasks.py`. The `message` parameter should contain the `type` parameter referring to the event handler that will be invoked on each consumer:

```python
from baserow.ws.tasks import send_message_to_channel_group
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

channel_layer = get_channel_layer()

message = {
  "type": "react_to_custom_event",
  # ...event payload
}

group = "table-2"

async_to_sync(send_message_to_channel_group)(channel_layer, group, message)
```

## Front-end

Websocket connections are automatically established for each user, including anonymous users, in the main page layout `web-frontend/modules/core/layouts/app.vue` when the Baserow web-frontend is loaded. Interacting with the backend using websocket connections is abstracted in `RealTimeHandler` class which is available in Vue components under `this.$realtime` property.

Consult client-side documentation in `docs/apis/web-socket-api.md` for implementing webscocket clients for Baserow.

## Web Socket ID

The **web socket id** is a UUID generated once at application boot and stored in the auth store. The client sends it as a query parameter on the WebSocket URL and as a `WebSocketId` HTTP header on REST API requests. The backend uses it to exclude the originating client from the broadcast of its own mutations, so a client never receives an echo of a change it just made.

The ID persists across reconnects within the same page load. A new tab or page refresh generates a fresh UUID.

## Reliability and Event Replay

WebSocket connections drop, and when they do, a client may miss broadcasts sent while it was offline. The reliability layer exists to detect that gap and either fill it (replay the missed events) or flag it (tell the client to refresh).

### Persisted Events

When replay recording is enabled, replayable broadcasts sent through `send_messages_to_channel_group` are **persisted** to the database before being sent. Direct channel-layer messages, including ephemeral presence updates, bypass recording. This creates a replay log keyed by channel group in the `ws_realtime_events` table:

| Field | Type | Purpose |
|---|---|---|
| `id` | `BigAutoField` | Sequential, monotonically increasing. Sent to clients as `_event_id`. |
| `channel_group` | `TextField` | Which channel group this event targeted (e.g., `table-42`, `users`). |
| `payload` | `JSONField` | The full broadcast message including type, user filters, and inner payload. |
| `created_at` | `DateTimeField` | When the event was recorded. Used for retention cleanup. |
| `target_user_ids` | `ArrayField(IntegerField)` | Recipients of users-channel events, derived by the database from the envelope. |
| `all_users` | `BooleanField` | Whether a users-channel event targets every user. Derived by the database. |

The `id` returned on insert is injected into the payload as `_event_id` before the message is sent.

The table is created as a PostgreSQL `UNLOGGED` table. This skips write-ahead log (WAL) entries, significantly reducing write overhead for high-throughput event recording. The trade-offs are that contents are lost on unclean shutdown (acceptable — events are ephemeral and clients handle the can't-replay path gracefully) and that the table is invisible to streaming replication, so the database router routes all reads of unlogged models to the primary database. Any new unlogged model should follow the same convention.

Recipient selection uses the small `target_user_ids` array and `all_users` flag,
rather than searching every user's individual JSON payload map. A GIN index covers
recipient arrays on the `users` channel, and a partial ID index covers broadcasts
to all users. Page messages use the `(channel_group, id)` index. Full business
payloads are not indexed.

The `ws_realtime_event_targets_before_write` trigger calls
`ws_set_realtime_event_targets()` to derive both columns before insertion
and when `payload` or `channel_group` changes. This also covers old workers that
insert only the original columns during deployment. It reads routing metadata for
users-channel events; page messages need no payload traversal. Live delivery and
replay must continue to agree on recipient selection.

Migration `ws.0002` resets this disposable buffer with `TRUNCATE ... CONTINUE
IDENTITY` before installing the columns, trigger and replacement indexes. It does
not backfill old payloads. The reset and schema changes commit together, with
indexes built while the table is empty and locked. Lock waits are capped at one
second and statements at three seconds, preserving stricter existing limits;
failure rolls the reset back. The event sequence is kept LOGGED and is never
restarted, so pre-reset cursors cannot match unrelated new events.

Apply the migration before deploying new workers. Clients whose cursor was
cleared must refresh their data. Older workers remain write-compatible through
the trigger, but older readers still filter JSON without the previous payload
index and can be slower during rollout. If replay is disabled in production,
leave it disabled until all workers are updated. Reversing this migration also
resets the buffer before restoring its old indexes; neither direction restores
discarded history. These resets affect only realtime replay, not the underlying
user data.

Migration `ws.0003` adds separate unlogged history-summary and history-state tables;
it preserves the existing event table and indexes. Before migration, pause and
drain the old cleanup task. Update all replay readers before enabling the new
cleanup, because older readers cannot use the summaries. Initial activation
establishes a conservative history floor from the logged event sequence. Cursors
below that floor refresh. After an unlogged-table reset, initialization takes the
same boundary while briefly blocking inserts, preserving the sequence's `CACHE 1`
requirement. Before rolling back, disable replay and establish fresh client
baselines; removing the summaries cannot restore compacted payloads.

### Last Seen Event ID

During normal delivery, the frontend advances its cursor to the highest `_event_id`
it has processed. The IDs come from a single database sequence. The cursor persists
across workspace and page changes within a page load. During recovery, the client
pins the original cursor and buffers persisted updates until replay completes.

### Replay on Reconnect

When a client reconnects, it re-authenticates, restores its page subscriptions, and
sends a `replay_events` message carrying its last seen event ID as `last_seen_id`.
The server uses that cursor and those subscriptions to decide whether recovery is
possible, with these completed outcomes:

1. **Nothing missed** — No relevant event follows the client's `last_seen_id`, in either full events or expired-history summaries. The client is already up to date for the channel groups being restored, even if the acknowledged event itself has been removed.
2. **Events replayed** — The server fetches the missed events for the client's page channel groups and implicit `users` group, filters out the client's own broadcasts (via its web socket id) and any events not relevant to that user, and re-invokes them through the consumer's handlers in order — exactly as if they had arrived live. The client catches up without a page reload.
3. **Can't replay** — A relevant missed event has expired, the cursor predates known history or is ahead of the recorded high-water mark, too many events were missed (more than `BASEROW_REALTIME_REPLAY_MAX_EVENTS`), or the server finds a persisted event it cannot safely re-deliver through a websocket broadcast handler. The server responds with `force_refresh=true` and the client shows a "workspace data is outdated" toast with a refresh action.

Every `replay_events_result` with `force_refresh=false` includes `latest_event_id`, the latest event ID the server can safely acknowledge for that replay decision. A fresh page load receives the recorded high-water mark, including compacted history, as its baseline. When replay succeeds, `latest_event_id` is the last replayed event, or the original cursor when nothing relevant changed. It can be lower than the global high-water mark when newer events were irrelevant. Full events, expired summaries and the known-history floor are checked in one database snapshot, so cleanup cannot expose a gap between deleting an event and recording its expired history. If `force_refresh=true`, `latest_event_id` is not meaningful and the client should refresh instead.

### Replay resource limits and retries

Replay reads use a separate executor with two active jobs and up to eight FIFO
waiters per ASGI process. A request has a three-second budget for queueing,
connection setup, and execution. PostgreSQL receives a transaction-local statement
timeout using the remaining budget without relaxing a stricter database timeout.
These are internal constants in `backend/src/baserow/ws/replay.py`; they do not
limit event-recording writes. A small result limit alone does not bound how many
irrelevant rows a query may scan.

Queued cancellations remove their waiter. Once a job is submitted, cancellation or
a caller deadline retains its slot until the thread and its connection cleanup
finish. Replay connections close after each job. Configure the database driver's
connection timeout as well: an async deadline cannot stop a blocked synchronous
connection attempt.

For overload, timeouts, and database failures, clients advertising
`supports_retry=true` receive `replay_events_retry` and retry on the same socket
with backoff and jitter. Older clients receive the existing refresh fallback.
Expired relevant history, an excessive event gap, or disabled recording requires a
refresh when recovering missed updates.

The frontend keeps one replay request or retry timer active and holds the original
cursor across retries. It buffers persisted updates up to 1,000 event IDs and an
estimated 5 MiB, then delivers recovered updates in event-ID order with duplicates
removed. Ephemeral presence and control messages bypass this buffer. A fresh
baseline preserves buffered live updates. Buffer overflow, or a disconnect before
the first baseline was established, requires a refresh because recovery can no
longer be verified. An unrecoverable gap stays marked outdated across reconnects.

### Event Cleanup

A periodic Celery task compacts events older than `BASEROW_REALTIME_REPLAY_RETENTION_HOURS` (24 hours by default), independently of JWT refresh-token lifetime. It runs every ten minutes, including when recording is disabled, with a 240-second work budget and at most 5,000 events per committed batch. Each statement has a three-second timeout and a 250 ms lock timeout, tightened to the remaining budget without relaxing stricter database settings. Locked rows are left for a later run.

Each exact audience gets a separate summary containing routing metadata and the
newest expired event IDs, without full business payloads. The summary keeps the
newest event and the newest event with a different ignored socket: any client
excludes at most one socket, so these two entries preserve its latest relevant
expired event. New browser sessions therefore do not create new summary rows for
an otherwise identical audience. Distinct audiences can still accumulate; summary
storage has no fixed size bound or expiry. Row-scoped channel groups such as
`table-<id>-row-<id>` give one summary per edited row rather than per table, so
size this against row volume.

Summary updates, deletion of all selected full events, and advancement of the
compacted high-water mark commit together. Each batch commits separately, so
earlier progress survives a later failure. Ordinary replay reads remain available
while a batch is uncommitted. A scheduled run skips cleanup while another task owns
the nonblocking 330-second lease. The retention target is not a hard maximum row
age: locked rows or a sustained cleanup backlog can remain until a later run.

Replay also checks the age of relevant full events left behind by cleanup, so
locked rows or cleanup lag cannot make expired payloads replayable. Increasing the
retention window cannot restore already compacted payloads. Deleting events or
summaries outside this cleanup is unsupported without explicitly invalidating
existing replay cursors.

The existing `(created_at, id)` index supports bounded expiration scans; no second
age index is added. Since expired originals are removed, retained summaries do not
accumulate in that scan. Recipient indexes are restricted to the shared `users`
channel; page events retain the
`(channel_group, id)` index. Cleanup makes storage reusable through PostgreSQL
vacuum; it does not normally shrink the table's allocated files. Monitor recording
rate, committed cleanup progress, and database vacuum activity together; see
[Monitoring](../installation/monitoring.md#websocket-and-realtime-metrics).

The replay table uses the same autovacuum thresholds as the pending search values table:
analyze threshold `2000` with scale factor `0.002`, and both update/delete and
insert-triggered vacuum thresholds `5000` with scale factor `0.01`. For example,
autoanalyze becomes eligible after approximately `2000 + 0.002 × estimated rows`
changes. These settings affect eligibility; background-worker scheduling and
available I/O still determine when maintenance runs. The migration does not run
an immediate `ANALYZE`.

### Configuration

| Setting | Default | Purpose |
|---|---|---|
| `BASEROW_REALTIME_REPLAY_MAX_EVENTS` | 200 | Maximum number of missed events the server will replay. Beyond this, the client is told to refresh. Set to `0` to disable event recording and replay; retention cleanup continues. Clients learn replay availability during authentication and use refresh when missed events cannot be recovered. |
| `BASEROW_REALTIME_REPLAY_RETENTION_HOURS` | 24 | Maximum age in hours of full events available for replay. Must be a positive integer. Older relevant missed history requires a refresh; increasing the window cannot restore compacted payloads. |

See [configuration.md](../installation/configuration.md) for the full settings reference.
