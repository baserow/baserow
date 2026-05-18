# Alerts and toasts

Baserow uses two small feedback primitives:

- **`<Alert>`** for inline or fixed messages that belong to the current
  screen.
- **Toasts** for transient global feedback, dispatched through the Vuex
  `toast` store and rendered by `<Toasts>`.

Use an alert when the message should remain visible near the affected UI.
Use a toast when the user triggered an operation and needs short-lived
feedback from anywhere in the app.

## Alerts

`web-frontend/modules/core/components/Alert.vue` renders the standard
alert surface.

```html
<Alert type="warning" close-button @close="dismissed = true">
  <template #title>{{ $t('billing.warningTitle') }}</template>
  {{ $t('billing.warningBody') }}
  <template #actions>
    <Button type="secondary">{{ $t('action.fix') }}</Button>
  </template>
</Alert>
```

Supported `type` values:

| Type | Use |
|---|---|
| `info-neutral` | Low-emphasis information. |
| `info-primary` | Important information. |
| `warning` | Risky but not failed state. |
| `error` | Blocking or failed state. |
| `success` | Completed state that should stay visible. |
| `blank` | Custom content without a status icon. |

`position="top"` or `position="bottom"` turns an alert into a fixed
banner. Use `loading` when the alert is the visible state of an ongoing
operation.

## Toasts

Global toasts live in `web-frontend/modules/core/store/toast.js` and are
rendered by `web-frontend/modules/core/components/toasts/Toasts.vue`.
Dispatch through the store:

```javascript
await this.$store.dispatch('toast/success', {
  title: this.$t('settings.savedTitle'),
  message: this.$t('settings.savedMessage'),
})
```

Available general actions are `toast/info`, `toast/success`,
`toast/warning`, and `toast/error`. They create normal top toasts that
auto-close after five seconds.

Special toasts such as connection state, undo/redo, copy/paste/clear,
restore, session expiry, authorization error, and permissions update have
dedicated store flags or actions. Use those existing paths instead of
adding another generic toast with similar text.

## Choosing

| Need | Use |
|---|---|
| Validation or setup problem in a form / panel | `<Alert>` |
| Persistent warning inside settings | `<Alert>` |
| Save succeeded | Toast |
| Background operation started / failed | Toast |
| Undoable restore | Existing restore toast |
| Something the user must act on later | [Frontend notifications](frontend-notifications.md) |

## Anti-patterns

- **Toast for required action.** A toast disappears; use an alert, modal,
  or notification.
- **Alert for routine success.** Inline success messages add clutter; use
  a toast unless the success state belongs to the screen.
- **Manual timers around `<Alert>`.** If it should auto-close, it is
  usually a toast.
- **New bespoke toast containers.** Add a store flag and component to
  `<Toasts>` only when the feedback has special behaviour.

## Related

- [Frontend notifications](frontend-notifications.md).
- [Optimistic updates](optimistic-updates.md).
- [Loading animations](loading-animations.md).
