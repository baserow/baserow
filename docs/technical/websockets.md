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
          self.send_json({"message": "Hello back!"})

    # Event handlers

    async def react_to_custom_event(self, event):
        # To invoke this event we will need to manually
        # send a message to channel layer with this event name
        ...
```

### CoreConsumer

The main Baserow consumer is `CoreConsumer` (from `backend/src/baserow/ws/consumers.py`). It currently handles all web-frontend connections, all backend events and exchange of all messages between clients and the backend.

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

Every broadcast that goes through the channel layer is **persisted** to the database before being sent. This creates a sequential log of all events, keyed by channel group, stored in the `ws_realtime_events` table:

| Field | Type | Purpose |
|---|---|---|
| `id` | `BigAutoField` | Sequential, monotonically increasing. Sent to clients as `_event_id`. |
| `channel_group` | `TextField` | Which channel group this event targeted (e.g., `table-42`, `users`). |
| `payload` | `JSONField` | The full broadcast message including type, user filters, and inner payload. |
| `created_at` | `DateTimeField` | When the event was recorded. Used for retention cleanup. |

The `id` returned on insert is injected into the payload as `_event_id` before the message is sent.

The table is created as a PostgreSQL `UNLOGGED` table. This skips write-ahead log (WAL) entries, significantly reducing write overhead for high-throughput event recording. The trade-offs are that contents are lost on unclean shutdown (acceptable — events are ephemeral and clients handle the can't-replay path gracefully) and that the table is invisible to streaming replication, so the database router routes all reads of unlogged models to the primary database. Any new unlogged model should follow the same convention.

### Last Seen Event ID

The frontend tracks the highest `_event_id` it has observed and advances it on every incoming message. This value is global and monotonic because event IDs come from a single database sequence. It persists continuously across the page load and is not reset on workspace or page changes.

### Replay on Reconnect

When a client reconnects, it re-authenticates, sends a `replay_events` message carrying its last seen event ID as `last_seen_id`, and re-subscribes to the pages it was tracking. The `last_seen_id` tells the server "I've seen everything up to this point", and the server responds with one of three outcomes:

1. **Nothing missed** — The replay window contains only the client's `last_seen_id`. The client is already up to date for the channel groups being restored.
2. **Events replayed** — The server fetches the missed events for the client's page channel groups and implicit `users` group, filters out the client's own broadcasts (via its web socket id) and any events not relevant to that user, and re-invokes them through the consumer's handlers in order — exactly as if they had arrived live. The client catches up without a page reload.
3. **Can't replay** — Either too many events were missed (more than `BASEROW_REALTIME_REPLAY_MAX_EVENTS`), the client's `last_seen_id` has already been cleaned up by retention, or the server finds a persisted event it cannot safely re-deliver through a websocket broadcast handler. The server responds with `force_refresh=true` and the client shows a "workspace data is outdated" toast with a refresh action.

Every `replay_events_result` with `force_refresh=false` includes `latest_event_id`, the latest event ID the server can safely acknowledge for that replay decision. If a client connects without a `last_seen_id` (a fresh page load), the server returns the latest persisted event ID as the new baseline because there is nothing to replay. When replay succeeds, `latest_event_id` is the last event in the replay window and might be lower than the global latest persisted ID if newer events were irrelevant to that client. If the server responds with `force_refresh=true`, `latest_event_id` is not meaningful and the client should refresh instead.

### Event Cleanup

A periodic Celery task removes events older than the retention window every 60 minutes. Retention is coupled to `REFRESH_TOKEN_LIFETIME` (default 7 days): clients with tokens older than that will re-authenticate and receive fresh state anyway, so their replay baseline is never needed.

### Configuration

| Setting | Default | Purpose |
|---|---|---|
| `BASEROW_REALTIME_REPLAY_MAX_EVENTS` | 0 (disabled) | Maximum number of missed events the server will replay. Beyond this, the client is told to refresh. Set to `0` to disable event recording and replay entirely; clients that request replay while replay is disabled are told to refresh because the server cannot verify or fill missed events. |

See [configuration.md](../installation/configuration.md) for the full settings reference.
