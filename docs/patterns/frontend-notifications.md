# Frontend notifications

This page covers the web-frontend half of in-product notifications: the
panel, Vuex store, realtime updates, and `notification` registry. For the
backend model and `NotificationType` implementation, see
[Notification system](../technical/notification-system.md).

Notifications are not toasts. A toast is transient feedback for the
current action. A notification is inbox-like state the user can read
later, mark as read, and receive by email when the backend type supports
it.

## Moving parts

| Piece | File | Role |
|---|---|---|
| Panel | `modules/core/components/NotificationPanel.vue` | Renders the bell panel, infinite scroll, unread state, mark-read actions. |
| Store | `modules/core/store/notification.js` | Holds current workspace, notification list, unread counts, loading state. |
| Service | `modules/core/services/notification.js` | Calls `/notifications/{workspaceId}/...`. |
| Type base | `modules/core/notificationTypes.js` | Frontend registry class for icon, content, and route. |
| Realtime | `modules/core/plugins/realTimeHandler.js` | Applies `notifications_created`, fetch-required, read, and clear events. |

Feature modules register their frontend notification types in `plugin.js`.
For example, database notification types live in
`web-frontend/modules/database/notificationTypes.js` and are registered in
`web-frontend/modules/database/plugin.js`.

## Frontend `NotificationType`

Each backend notification type that appears in the panel needs a matching
frontend type:

```javascript
export class WebhookDeactivatedNotificationType extends NotificationType {
  static getType() {
    return 'webhook_deactivated'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return WebhookDeactivatedNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(
      this.app.$router,
      {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
      },
      'database-table-open-webhooks'
    )
  }
}
```

Register it:

```javascript
$registry.register('notification', new WebhookDeactivatedNotificationType(context))
```

`getType()` must match the backend type string exactly.

## Content components

Notification content components receive `notification` and usually mix in
`modules/core/mixins/notificationContent.js`. The mixin provides:

- `sender` formatting.
- `route` from the registered frontend type.
- `markAsReadAndHandleClick`, which marks the notification read before
  running the component's `handleClick`.

Most clickable content wraps its title in `<nuxt-link :to="route">` and
emits `close-panel` after click.

## Realtime flow

The backend can push:

- `notifications_created` — contains full notifications; the store inserts
  visible ones and updates unread counts.
- `notifications_fetch_required` — contains counts only; the store marks
  itself stale so the panel shows a refresh hint when open.
- `notification_marked_as_read` — updates one notification.
- `all_notifications_marked_as_read` and `all_notifications_cleared` —
  update bulk panel state.

The panel uses offset pagination because new realtime notifications can
arrive while the user is scrolling.

## Anti-patterns

- **Using a notification for immediate operation feedback.** Use a toast.
- **Adding backend type only.** Without the frontend registry entry and
  content component, the panel cannot render the notification.
- **Hardcoding route construction in the component.** Put route logic in
  `NotificationType.getRoute(notification.data)`.
- **Skipping `notificationContent`.** You will likely miss mark-as-read or
  close-panel behaviour.
- **Forgetting workspace scope.** The store separates current-workspace
  unread counts from user-level notifications and other-workspace badges.

## Related

- [Notification system](../technical/notification-system.md).
- [Frontend registries](frontend-registries.md).
- [Alerts and toasts](alerts-and-toasts.md).
