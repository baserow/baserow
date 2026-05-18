# Dropdowns

Dropdowns are for choosing a value. They are not generic popovers; use
[context menus](context-menus.md) for arbitrary action surfaces.

Core components:

- `web-frontend/modules/core/components/Dropdown.vue`.
- `web-frontend/modules/core/components/DropdownItem.vue`.
- `web-frontend/modules/core/components/DropdownSection.vue`.
- `web-frontend/modules/core/components/PaginatedDropdown.vue`.

## Static options

```html
<Dropdown
  v-model="form.role"
  :placeholder="$t('memberRole.placeholder')"
>
  <DropdownItem
    v-for="role in roles"
    :key="role.uid"
    :name="role.name"
    :value="role.uid"
  />
</Dropdown>
```

Use `DropdownItem` for every selectable value. It registers itself with
the parent dropdown, which is how selected labels, keyboard navigation,
and search stay in sync.

## Props worth knowing

| Prop | Use |
|---|---|
| `v-model` / `modelValue` | Current value. `value` is still supported for older code. |
| `multiple` | Emits an array and renders checkboxes in items. |
| `clearable` | Selecting the current single value emits `null`. |
| `showSearch` | Enables the built-in search input. Default `true`. |
| `showInput` | Shows the selected-value control. Set false for floating lists. |
| `fixedItems` | Positions the options with `position: fixed` for overflow containers. |
| `beforeShow` | Async hook for lazy option setup. |
| `error`, `disabled`, `size` | Standard field states. |

Search matches `name` and optional `alias` on each `DropdownItem`.

## Paginated options

Use `<PaginatedDropdown>` when options come from an API or the list can be
large.

```html
<PaginatedDropdown
  v-model="selectedUserId"
  :fetch-page="fetchUsers"
  value-name="name"
  :fetch-on-open="true"
/>
```

`fetchPage(page, search)` must return the normal paginated API shape:

```javascript
{
  data: {
    count: 42,
    results: [{ id: 1, value: 'Ada' }],
  },
}
```

The mixin debounces search, appends more rows near the scroll bottom,
and avoids duplicate ids when loading later pages. Use
`inMemoryPaginatedDropdown` when the source list is local but should
behave like paginated data.

## Grid-cell dropdowns

Database grid cells use
`web-frontend/modules/database/mixins/selectDropdown.js` to integrate dropdowns
with cell selection:

- Enter, F2, or printable characters open the dropdown.
- Escape closes it.
- Arrow keys and Tab remain owned by grid navigation.
- Space still opens the row edit modal.

If you create a new selectable grid field, copy that mixin's shape rather
than attaching document-level keyboard listeners ad hoc.

## Anti-patterns

- **Using `<Dropdown>` as an action menu.** Use `<Context>`.
- **Rendering custom selectable elements without `DropdownItem`.** The
  parent will not know what can be searched, highlighted, or displayed.
- **Eager API loading for large option sets.** Use `PaginatedDropdown`
  with `fetchOnOpen`.
- **Putting business logic in item components.** Items select values;
  parent components react to `v-model`, `input`, or `change`.

## Related

- [Context menus](context-menus.md).
- [Forms](forms.md).
- [Frontend architecture](frontend-architecture.md).
