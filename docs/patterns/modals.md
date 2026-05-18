# Modals

`<Modal>` is Baserow's page-blocking overlay primitive. Use it when the
user needs to focus on one flow: creating or editing an object, confirming
a destructive action, configuring settings, selecting files, or opening a
row detail view.

The component lives in `web-frontend/modules/core/components/Modal.vue`
and is backed by `modules/core/mixins/baseModal.js`.

## Basic shape

```html
<Modal ref="modal" small>
  <h2>{{ $t('confirmDelete.title') }}</h2>
  <p>{{ $t('confirmDelete.message') }}</p>
  <Button type="danger" @click="confirm">
    {{ $t('action.delete') }}
  </Button>
</Modal>
```

```javascript
methods: {
  open() {
    this.$refs.modal.show()
  },
  confirm() {
    // Do the work in the parent or store, then close.
    this.$refs.modal.hide()
  },
}
```

## Props

| Prop | Use |
|---|---|
| `tiny`, `small`, `wide`, `fullScreen` | Size variants. Default is medium. |
| `right` | Right-side drawer instead of centred dialog. |
| `leftSidebar`, `rightSidebar` | Reserve modal sidebar space. |
| `closeButton` | Show the close button. Default `true`. |
| `fullHeight` | Stretch content to the modal's full height. |
| `contentScrollable` | Scroll inside the modal instead of overflowing the page. |
| `contentPadding`, `boxPadding` | Toggle inner / outer padding. |
| `collapsibleRightSidebar` | Show a right-sidebar collapse toggle. |

## Methods and events

- `show()` opens and emits `show`.
- `hide(emit = true)` closes and emits `hidden` unless suppressed.
- `toggle(value)` shows, hides, or toggles when `value` is omitted.

Use `@hidden` for cleanup: reset form data, clear selection, or drop
temporary state. Suppressing the `hidden` event is rare and usually only
needed when a parent modal is closing nested modal state itself.

## Global close

`this.$bus.$emit('close-modals')` closes all open modals. It is used for
session expiry, logout, and context-changing navigation. If a modal should
survive that event, be very explicit in the component; most modals should
close.

## Choosing the primitive

Use a modal when the user must complete or dismiss a focused flow. Use a
[context menu](context-menus.md) when the UI is a quick anchored choice,
such as a row action menu, dropdown-like picker, or right-click menu.

| User need | Primitive |
|---|---|
| Page should be blocked | `<Modal>` |
| Backdrop should darken the page | `<Modal>` |
| Long form or settings flow | `<Modal>` or a dedicated page |
| Three row actions | `<Context>` |
| Anchored quick choice | `<Context>` |

## Accessibility

- `<Modal>` traps focus while open and restores focus on close.
- Keep `closeButton` enabled unless there is another clear keyboard path
  out of the modal.
- Icon-only buttons inside a modal need text or an `aria-label`.
- Do not open a modal from SSR or `asyncData`; open it from user
  interaction or client-side state.

## Anti-patterns

- **Nested modals.** They break focus management and the global close
  event. Prefer one modal with steps, or separate pages.
- **DOM-query opening.** `document.querySelector(...).show()` bypasses
  Vue state. Use `$refs`.
- **Business logic in the modal component.** The modal renders and emits;
  the parent, store, or service does the work.
- **Modal for tiny action menus.** Use a context menu anchored to the
  object the action affects.

## Related

- [Context menus](context-menus.md).
- [Forms](forms.md).
- [Frontend architecture](frontend-architecture.md).
