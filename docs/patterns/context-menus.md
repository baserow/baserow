# Context menus

`<Context>` is Baserow's anchored popover primitive. Use it for action
menus, right-click menus, inline pickers, and dropdown-like UI that should
close when the user clicks away.

The component lives in `web-frontend/modules/core/components/Context.vue`
and is backed by the `context` mixin.

## Basic shape

A context menu is anchored to a trigger element. The parent calls
`toggle(triggerEl)` on the context ref:

```html
<a ref="actions" @click="$refs.menu.toggle($refs.actions)">
  <i class="iconoir-more-horiz" />
</a>

<Context ref="menu">
  <ul class="context__menu">
    <li><a @click="rename">{{ $t('action.rename') }}</a></li>
    <li><a @click="deleteItem">{{ $t('action.delete') }}</a></li>
  </ul>
</Context>
```

The mixin handles positioning, outside clicks, scroll, and resize.

## Props

| Prop | Use |
|---|---|
| `hideOnClickOutside` | Close on outside click. Default `true`. |
| `hideOnScroll` | Close when the page scrolls. Default `true`. |
| `hideOnResize` | Close when the window resizes. Default `true`. |
| `overflowScroll` | Let the context content scroll. |
| `maxHeightIfOutsideViewport` | Cap height (computed from viewport) when the content would otherwise overflow. |

## Methods and events

- `toggle(triggerEl, vertical, horizontal, verticalOffset, horizontalOffset, value)`
  opens or closes (pass an explicit `value` boolean to force a state).
- `show(triggerEl, vertical, horizontal, verticalOffset, horizontalOffset)` opens.
- `hide()` closes.
- `@shown` fires after positioning and DOM placement.
- `@hidden` fires after close.

`vertical` and `horizontal` accept alignment strings such as `top`,
`bottom`, `left`, `right`, and `auto`.

## Common patterns

**Action menu:** use a three-dot trigger, an icon button, or another
small target next to the object being acted on.

**Right-click menu:** call `show(event)` from `@contextmenu.prevent`.

```html
<div @contextmenu.prevent="$refs.menu.show($event)">...</div>
```

**Filtering picker:** put a search input and list inside `<Context>`,
then set `overflowScroll` and `maxHeightIfOutsideViewport` for long lists.

## Context vs dropdown

Use [Dropdowns](dropdowns.md) when the UI is a form value with selected
state, keyboard selection, search, and `v-model` / `@input` semantics.
Use `<Context>` when the UI is an anchored surface that contains arbitrary
actions or custom content.

## Accessibility

`<Context>` does not trap focus. That is intentional: the user can dismiss
it by clicking away, scrolling, resizing, or pressing a parent-level
shortcut. Do not add focus traps to context menus.

## Anti-patterns

- **New floating primitives.** Compose `<Context>` or `<Modal>` instead.
- **Unanchored contexts.** If there is no trigger or cursor position, the
  user probably expects a modal or a normal page section.
- **Long workflows in a context menu.** Use a modal or page once the user
  needs to read, validate, or submit several fields.

## Related

- [Modals](modals.md).
- [Dropdowns](dropdowns.md).
- [Frontend architecture](frontend-architecture.md).
