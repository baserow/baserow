# Notification system

Notifications are the in-product way Baserow tells a user something happened
that they care about: a collaborator was added to a row, a form was submitted,
a webhook was deactivated, an automation workflow failed. Each notification can
also be sent by email (instantly, daily, or weekly digest) depending on the
user's preferences and the notification type's configuration.

Entry point: `baserow.core.notifications.handler.NotificationHandler`.

## Data model

Two models in `baserow.core.notifications.models`:

- **`Notification`** — one row per notification *event*. Holds the type, the
  workspace, the params data (JSON), broadcast flag, and creation/scheduling
  metadata.
- **`NotificationRecipient`** — many-to-many between `Notification` and `User`.
  Holds per-user state: `read`, `email_scheduled`, `queued`, and (for broadcast
  notifications) the marker that this specific user has seen it.

The model split exists because some notifications target many users (workspace
admins, all workspace members, a broadcast to every user) and we want one
`Notification` row + one recipient row per user rather than duplicating data.

## `NotificationType` — the registry

Each notification kind is a `NotificationType` subclass registered in
`notification_type_registry` (see
`backend/src/baserow/core/notifications/registries.py`).
The type owns:

- **Recipient resolution** — given the params, which users should receive this?
- **Formatting** — what does the title/body look like in the UI?
- **Email integration** — does this type emit emails too, and what does the
  email look like? (`EmailNotificationTypeMixin`.)
- **Web frontend URL** (optional) — a deep link the user clicks to take action.

Built-in registrations (non-exhaustive):

| Type | Registered in |
|---|---|
| `WorkspaceInvitationCreatedNotificationType`, `WorkspaceInvitationAcceptedNotificationType`, `WorkspaceInvitationRejectedNotificationType`, `BaserowVersionUpgradeNotificationType` | `baserow.core.apps` |
| `CollaboratorAddedToRowNotificationType`, `UserMentionInRichTextFieldNotificationType`, `FormSubmittedNotificationType`, `WebhookDeactivatedNotificationType`, `WebhookPayloadTooLargeNotificationType` | `baserow.contrib.database.apps` |
| `WorkflowDisabledNotificationType` | `baserow.contrib.automation.apps` |

Premium/enterprise plugins register their own types in their respective `apps.py`.

## Creating a notification

A typical call from a handler looks like:

```python
NotificationHandler.create_direct_notification_for_users(
    notification_type=CollaboratorAddedToRowNotificationType.type,
    recipients=[user_a, user_b],
    data={"row_id": row.id, "field_id": field.id},
    sender=requesting_user,
    workspace=table.database.workspace,
)
```

`NotificationHandler` also has helpers for **broadcast** notifications
(`create_broadcast_notification`) where the notification is created once and
every user can see it until they've marked it read, and for sending the same
notification to a specific set of recipients
(`create_direct_notification_for_users` — used to target, for example, every
user in a workspace by passing the workspace's user list).

Three signals fire from the handler:

- `notification_created` — receivers in `baserow.ws.*` translate this into a
  realtime push to connected clients.
- `notification_marked_as_read` — pushes a marker so the unread counter updates
  in the user's UI.
- `all_notifications_cleared` / `all_notifications_marked_as_read` — bulk
  variants.

## Reading and marking read

The frontend fetches notifications via the notifications API, displays them in
the panel, and tracks unread count by querying `NotificationRecipient` filtered
by `read=False` for the current user. Marking read flips `read=True` and emits
the corresponding signal.

## Email delivery

`EmailNotificationTypeMixin` is the opt-in. A type that inherits from it must
implement:

- `get_notification_title_for_email(notification, context)` — the email subject.
- `get_notification_description_for_email(notification, context)` — the body.
- Optionally set `has_web_frontend_route = True` to make the email clickable.

Users choose their email cadence (instant, daily digest, weekly digest, or
never) in their profile.

Three Celery beat schedules in `baserow.config.settings.base` drive delivery:

| Cadence | Env crontab var | Default |
|---|---|---|
| Instant | `BASEROW_EMAIL_NOTIFICATIONS_INSTANT_CRONTAB` | `* * * * *` (every minute) |
| Daily | `BASEROW_EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY` | hour `0` |
| Weekly | `BASEROW_EMAIL_NOTIFICATIONS_WEEKLY_*` | configurable |

Per-task batch caps (`BASEROW_EMAIL_NOTIFICATIONS_LIMIT_INSTANT/_DAILY/_WEEKLY`,
defaults 50 / 1000 / 5000) prevent runaway email blasts and split work across
multiple task runs.

The send path is `send_queued_notifications_to_users` in
`baserow.core.notifications.tasks`. It pulls users with scheduled+unread+queued
notifications and renders a `NotificationsSummaryEmail` (defined in
`baserow.core.emails`) per user.

`EMAIL_NOTIFICATIONS_ENABLED` (env `BASEROW_EMAIL_NOTIFICATIONS_ENABLED`, default
true) is the global kill switch. Set to false to disable all email sending.

## Adding a new notification type

1. Subclass `NotificationType` (and `EmailNotificationTypeMixin` if you want
   emails). Add `CliNotificationTypeMixin` if you want a `manage.py` command to
   create one for testing.
2. Define the `type` string and any params your formatting needs.
3. Implement `get_notification_title_for_email` / `get_notification_description_for_email`
   if applicable.
4. Register the type from the relevant `apps.py` `ready()` method.
5. Add the API serializer if the params surface in the API response.
6. Wire the trigger — typically a signal receiver or a call from a handler that
   creates the notification.

## Gotchas

- **`create_direct_notification_for_users` vs `create_broadcast_notification`.**
  Direct creates one `Notification` and one `NotificationRecipient` per user
  (you can mark per-user state). Broadcast creates one `Notification` with no
  per-user rows — users get a "seen" recipient row the first time they mark it
  read.
- **The signal-versus-handler split.** Notifications are often emitted from
  signal receivers, not from the handler that did the work, because the
  notification depends on context that's only available after the action is
  complete. Look at `baserow.contrib.database.fields.notification_types` for
  representative examples.
- **Email send is async.** Sending an email is a Celery task triggered by beat,
  not by the request that created the notification. A user that creates a
  notification and then immediately checks their inbox will not see it yet.
- **Workspace inference.** Many types require the workspace to scope visibility
  and email routing. If you write a new type and forget the `workspace`
  parameter, the notification will be created but won't be discoverable by
  workspace-scoped queries.

## Related

- [Systems overview — Notification system](systems-overview.md#notification-system).
- [Frontend notifications](../patterns/frontend-notifications.md) — the panel,
  store, realtime updates, and frontend registry.
- [Email pattern](../patterns/emails.md) — how email rendering works generally.
