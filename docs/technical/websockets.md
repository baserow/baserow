# Working with WebSockets

Baserow uses [Django Channels](https://channels.readthedocs.io/en/latest/)
to handle WebSocket connections.

## Consumers

Connected clients, such as the Baserow web frontend, communicate with the
backend through Django Channels
[consumers](https://channels.readthedocs.io/en/latest/topics/consumers.html).
A consumer is similar to a Django view: it receives payloads from a client
and sends payloads back. The difference is that consumers are stateful for
the whole WebSocket connection.

Like Django views, consumers are mounted on URLs. `CoreConsumer` is routed
from `backend/src/baserow/ws/routing.py` like this:

```python
websocket_urlpatterns = [re_path(r"^ws/core/", CoreConsumer.as_asgi())]
```

Any client that opens a WebSocket connection to `ws/core/` is handled by
`CoreConsumer`.

Each consumer has access to the connection's
[scope](https://channels.readthedocs.io/en/latest/topics/consumers.html#scope),
which is the WebSocket equivalent of a traditional request object.

### AsyncJsonWebsocketConsumer

We use
[`AsyncJsonWebsocketConsumer`](https://channels.readthedocs.io/en/latest/topics/consumers.html#asyncjsonwebsocketconsumer)
as the base class because Baserow exchanges JSON payloads. These consumers
usually implement three main handlers: `connect` (accept or reject the
connection), `disconnect` (cleanup), and `receive_json` (client messages).

In each AsyncJsonWebsocketConsumer, we will typically want to:

- React to client messages in `receive_json`
- Send messages back to the connected client via `self.send_json(..)`
- React to custom events by implementing class methods such as
  `async def react_to_custom_event(self, event):`. Custom events handle
  messages from other consumers or backend code, not from clients.
- Join channel-layer groups via `self.channel_layer.group_add(..)` to
  subscribe clients to additional events.

Let's have a look at a simple consumer:

```python
class MyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

        # The scope contains connection information. In this case, Django
        # Channels provides the authenticated user.
        user = self.scope["user"]

        if not user:
            # We don't have to allow the connection to be established.
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

The main Baserow consumer is `CoreConsumer`
(`backend/src/baserow/ws/consumers.py`). It handles all web-frontend
connections and all messages exchanged between clients and backend events.

## Channel Layer and Channel Groups

A [channel layer](https://channels.readthedocs.io/en/latest/topics/channel_layers.html)
handles cross-process communication between consumers, or between consumers
and backend code that needs to send messages to connected clients. Baserow
uses [RedisChannelLayer](https://github.com/django/channels_redis/) for
this purpose.

Each consumer has a unique *channel name* (`self.channel_name` in the
example above) and can join arbitrary groups. This supports both
point-to-point and broadcast messaging.

Currently, `CoreConsumer`s use these channel groups for broadcasts:

- `users` for all connected clients, including anonymous users.
- Page groups for "table", "view", or "row" pages, so users browsing those
  pages receive realtime updates.
- Permission-oriented groups for consumers that need to receive permission
  updates and leave channel groups they can no longer access.

## Pages and Subscriptions

`CoreConsumer` has a concept of *pages* that clients can subscribe to.
Clients request a subscription with a special payload. The consumer checks
whether the client may receive updates for that page and, if so, joins the
channel group that represents it.

For example, users can subscribe to updates for a Baserow table. If the
request is permitted, the consumer joins the `table-{id}` channel group and
starts receiving messages for that table.

Each subscribable page is implemented as a `PageType` and registered in
`page_registry`, so new page types do not require changes to the consumer
itself. See `backend/src/baserow/ws/registries.py`.

## Message Broadcasting

Connected clients often need to be notified after backend writes. For
example, clients subscribed to a table page need realtime updates for
created or updated rows.

Use `send_message_to_channel_group()` in `backend/src/baserow/ws/tasks.py`
to send a message to every consumer in a channel group. The `message`
payload must include `type`, which names the event handler invoked on each
consumer:

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

### Broadcasts run on Celery, not the request thread

**Broadcasting is never synchronous from the request's perspective.** Every
broadcast goes through a Celery task in `backend/src/baserow/ws/tasks.py` and is
enqueued from `transaction.on_commit(...)` in the relevant signal handler.
Three reasons matter:

1. The user who made the change doesn't wait for fan-out — the HTTP
   response returns as soon as the write commits.
2. Broadcast work can be substantial (permission checks across every
   workspace member, per-user serialisation, multi-group sends), so we
   keep it off the request-handling gunicorn process. The docstring on
  `broadcast_application_created` (`backend/src/baserow/ws/tasks.py:336`) calls this out
   explicitly: "calculating the individual payloads can take a lot of
   computational power and should therefore not run on a gunicorn worker."
3. Enqueuing from `on_commit` guarantees the broadcast worker can't see
   an uncommitted row.

Signals typically call `PageType.broadcast(payload, ...)`
(`backend/src/baserow/ws/registries.py`), which in turn delegates to
`broadcast_to_channel_group.delay(...)`. Direct calls to the lower-level
`broadcast_to_*` tasks also exist for special cases (workspace-wide
sends, per-user payloads, permission-filtered sends). The full menu in
`backend/src/baserow/ws/tasks.py`:

| Task | Audience |
|---|---|
| `broadcast_to_channel_group` | Everyone subscribed to a named channel group (a page). |
| `broadcast_to_group` | All users in a workspace (resolves `WorkspaceUser`, then delegates). |
| `broadcast_to_groups` | All users across multiple workspaces. |
| `broadcast_to_users` | A specific list of user ids. |
| `broadcast_to_users_individual_payloads` | A per-user payload map (different message per recipient). |
| `broadcast_to_permitted_users` | Users in a workspace who pass a given `operation_type` permission check against a scope. |
| `broadcast_application_created` | Specialised: serialises the new application per-user (visibility-filtered) and sends individual payloads. |
| `force_disconnect_users` | Boots specific user ids off the socket (used after permission revocation). |

### Work happens regardless of who's listening

A subtle thing worth knowing: **the broadcast task does all its work
before — and independently of — whether anyone is subscribed to the
target group.** For `broadcast_to_permitted_users` that means fetching
the workspace, every `WorkspaceUser`, the scope object, and running
`check_permission_for_multiple_actors` against every member of the
workspace; for `broadcast_application_created` it means serialising the
application once per visible user. Only then is the message handed to
`channel_layer.group_send`, which delivers it to whoever happens to be
in the group — or drops it on the floor if the group is empty.

This is a consequence of how Django Channels works: the Redis-backed
channel layer is fire-and-forget. There's no API to ask "is anyone in
this group right now?" before doing the work. Group membership lives in
Redis keys maintained by the consumers themselves on `connect` /
`disconnect`, but the channel layer doesn't surface a count.

**Possible future optimisation.** If we maintained our own subscriber
count per page in Redis (kept in sync via the consumer's `subscribe` /
`unsubscribe` handlers in `CoreConsumer`), the signal — or the task body
— could short-circuit when the count is zero and skip the heavy
serialisation / permission work entirely. The hard part is consistency:
worker crashes, network blips, and double-disconnects could leave the
count out of sync with reality, and false negatives would silently drop
legitimate updates. Until that's resolved, the simple "always do the
work" path is the safe default.

## Frontend

WebSocket connections are opened automatically for every user, including
anonymous users, from
`web-frontend/modules/core/layouts/app.vue`. Frontend code uses
`RealTimeHandler`, available in Vue components as `this.$realtime`, rather
than talking to the socket directly.

See [WebSocket API](../apis/web-socket-api.md) for the client-facing
protocol.
