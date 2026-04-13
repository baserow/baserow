---
name: Create In-App Notification
description: Create or update a Baserow in-app notification for an event. Use when adding a backend `NotificationType`, wiring frontend notification rendering and routing, defining the notification target, or preventing duplicate notifications for the same event object.
---

# Create Baserow In-App Notifications

Use this skill when a task is to add or update an in-app notification shown in Baserow's notification center.

Do not invent a new notification architecture. This repo already has established backend and frontend patterns. Start from the closest existing notification type in the same product area: core, database, builder, automation, integration, premium, or enterprise.

## First Step

Before editing, identify which shape best matches the event:

1. One event sends one notification to one or more explicit users.
2. One event fans out to many users and should be grouped or queued efficiently.
3. One event is instance-wide and should be a broadcast notification.
4. The event should update or reuse an existing notification instead of creating another one.

Then inspect the closest example before editing.

Useful starting points:

- Core notification types: `backend/src/baserow/core/notification_types.py`
- Database notification types: `backend/src/baserow/contrib/database/fields/notification_types.py`
- Premium notification types: `premium/backend/src/baserow_premium/row_comments/notification_types.py`
- Enterprise notification types: `enterprise/backend/src/baserow_enterprise/data_scanner/notification_types.py`
- Backend notification APIs: `backend/src/baserow/core/notifications/handler.py`
- Backend notification base classes: `backend/src/baserow/core/notifications/registries.py`
- Frontend base notification type: `web-frontend/modules/core/notificationTypes.js`

## What A Complete Notification Usually Needs

Most new notifications touch both sides:

1. Backend `NotificationType` subclass and event hook.
2. Backend registration in the relevant app `ready()` method.
3. Frontend `NotificationType` class.
4. Frontend content component used in the notification list.
5. Frontend registration in the relevant `plugin.js`.
6. Targeted backend tests, and frontend tests if the route or rendering logic is non-trivial.

## Backend Pattern

Follow the existing backend shape:

1. Add a typed payload container, usually a dataclass, with the minimal stable fields needed by the UI and routing.
2. Implement a `NotificationType` subclass.
3. Add a helper like `create_notification`, `notify_*`, or `construct_notification`.
4. Call `NotificationHandler.create_direct_notification_for_users(...)` for direct notifications.
5. Use `NotificationHandler.construct_notification(...)` plus `UserNotificationsGrouper` when batching many notifications.
6. Use `NotificationHandler.create_broadcast_notification(...)` only for true broadcast events.
7. Register the notification type in the matching backend app.

Common backend registration points:

- `backend/src/baserow/core/apps.py`
- `backend/src/baserow/contrib/database/apps.py`
- `premium/backend/src/baserow_premium/apps.py`
- `enterprise/backend/src/baserow_enterprise/apps.py`

## Frontend Pattern

If the notification must render inside the app, add the frontend type too:

1. Create a frontend `NotificationType` subclass with the same `type` string.
2. Return the appropriate icon component.
3. Return a content component that renders the notification text.
4. Implement `getRoute(notificationData)` when the notification should be clickable.
5. Register the type in the relevant frontend `plugin.js`.

Common frontend registration points:

- `web-frontend/modules/core/plugin.js`
- `web-frontend/modules/database/plugin.js`
- `premium/web-frontend/modules/baserow_premium/plugin.js`
- `enterprise/web-frontend/modules/baserow_enterprise/plugin.js`

## Define The Target Clearly

Every notification should have a clear target: what object or page the user should land on when they click it.

Prefer storing stable identifiers in `notification.data`, not display-only values. Usually that means IDs plus enough names to render a readable message.

Good target payload examples:

- Row or field event: `database_id`, `table_id`, `row_id`, `field_id`
- Comment event: `comment_id`, `table_id`, `row_id`
- Workspace-scoped event: `workspace_id` or object IDs resolvable within the workspace
- Admin or global event: IDs and query parameters needed for an admin route

Use these rules:

1. Include the smallest set of IDs required to reconstruct the target route.
2. Include names only for display or email text.
3. Keep the target stable even if labels change later.
4. Use `workspace=None` only when the event is truly user-global or instance-global.
5. If the backend email link should point to the same place, keep the backend and frontend route assumptions aligned.

There are two target implementations to consider:

1. Backend `get_web_frontend_url(...)`
   Use this when the notification is emailed and should link into the app.
   `EmailNotificationTypeMixin` already provides the default `/notification/<workspace_id>/<notification_id>` route when `has_web_frontend_route = True`.
   Override it only when the target route cannot be expressed through that default flow.
2. Frontend `getRoute(notificationData)`
   Return the real in-app route object based on the IDs stored in `notification.data`.

If the notification redirects through the generic notification route, verify the frontend route can still resolve the final location from the stored data.

## Prevent Duplicate Notifications

Do not blindly create a new notification every time a signal fires. First decide whether repeated events should:

1. Create a new notification every time.
2. Reuse one existing unread notification for the same object.
3. Suppress re-creation while a tracking record still exists.
4. Mark an existing notification as read instead of creating a new one.

The repo uses several duplicate-prevention patterns already:

### Pattern 1: Query for an existing active notification

Use this when the event has a natural unique object, such as an invitation, comment, sync, or scan.

Typical lookup shape:

```python
NotificationHandler.get_notification_by(
    user,
    notificationrecipient__read=False,
    data__contains={"some_object_id": obj.id},
)
```

Use this when you want at most one active notification per recipient and per object. If one already exists, do not create another. Depending on the behavior, you can:

- return early
- update the existing notification data
- mark the existing notification as read as part of a follow-up action

Choose `data` keys that uniquely identify the event target. If multiple objects can share the same notification type, the dedupe key must include all IDs needed to distinguish them.

### Pattern 2: Persist or reuse an event-tracking row

Use this when the same source content may be removed and re-added quickly, and a raw notification query is not enough.

The rich text mention flow uses `RichTextFieldMention` rows to track mention existence and avoid duplicate notifications when content is briefly undone and redone. Follow that approach when the event source has lifecycle state that should outlive a single signal call.

### Pattern 3: Group creation before writing recipients

Use `UserNotificationsGrouper` when one operation can generate many notifications across many users. This reduces fan-out overhead and avoids ad hoc per-user creation loops.

### Pattern 4: Update or mark read instead of inserting

If the event resolves a prior notification, prefer updating state over inserting another notification. For example, invitation follow-up flows mark the original invitation notification as read.

## Choosing A Dedupe Key

A dedupe key is usually an implicit tuple made from:

1. notification `type`
2. recipient user
3. active state, usually unread and uncleared
4. one or more stable object IDs stored in `data`

Examples:

- One notification per invitation per user:
  `type + recipient + data.invitation_id`
- One notification per row comment mention per user:
  `type + recipient + data.comment_id`
- One notification per row-field mention per user:
  `type + recipient + data.field_id + data.row_id`

Do not dedupe on mutable names or message text.

## Implementation Checklist

When adding a new notification, verify all of these:

1. The `type` string is unique and stable.
2. The payload contains stable target IDs.
3. The workspace is correct for permission-scoped listing.
4. The sender is correct, or `None` if there is no meaningful sender.
5. Duplicate creation behavior is explicit.
6. Backend registration is present.
7. Frontend registration is present if the notification appears in-app.
8. The route works for the intended target.
9. Tests cover both creation and duplicate prevention behavior.

## Testing Expectations

Add the narrowest backend tests that prove:

1. The right recipients are selected.
2. The notification payload contains the target IDs.
3. The notification is workspace-scoped correctly.
4. A duplicate event does not create an extra active notification when dedupe is required.
5. The route-related data needed by the frontend is present.

Useful existing tests:

- `premium/backend/tests/baserow_premium_tests/row_comments/test_row_comments_notification_types.py`
- `enterprise/backend/tests/baserow_enterprise_tests/data_scanner/test_data_scanner_notification_types.py`

If you add custom frontend routing or rendering logic, add or update a focused frontend unit test near the notification type or component.

## Search Patterns

Use these searches to move quickly:

- `rg -n "class .*NotificationType" backend/src premium/backend/src enterprise/backend/src`
- `rg -n "notification_type_registry.register" backend/src premium/backend/src enterprise/backend/src`
- `rg -n "new .*NotificationType\\(context\\)" web-frontend premium/web-frontend enterprise/web-frontend`
- `rg -n "NotificationHandler\\.create_direct_notification_for_users|UserNotificationsGrouper|create_broadcast_notification" backend/src premium/backend/src enterprise/backend/src`
- `rg -n "data__contains=.*_id|get_notification_by\\(" backend/src premium/backend/src enterprise/backend/src`

## Guardrails

- Do not create a new notification type without checking whether an existing one should be reused or updated.
- Do not store only display text if the notification needs to link back to an object.
- Do not dedupe on mutable fields like names or messages.
- Do not use broadcasts for ordinary per-user events.
- Do not skip frontend registration when the notification must render in-app.
- Do not create duplicate unread notifications for the same object unless that is explicitly the desired product behavior.
