# CRUD tables

Use `CrudTable` for admin-style tables that list objects from a service
and need search, sorting, pagination, row updates, or row action menus.

Core files:

- `web-frontend/modules/core/components/crudTable/CrudTable.vue`.
- `web-frontend/modules/core/components/crudTable/CrudTableSearch.vue`.
- `web-frontend/modules/core/crudTable/crudTableColumn.js`.

Good examples include enterprise audit log and members pages.

## Service contract

Most callers use `web-frontend/modules/core/crudTable/baseService.js`.
`CrudTable` receives a service object with a `fetch` method:

```javascript
service.fetch(baseUrl, page, searchQuery, columnSorts, filters, options)
```

For paginated endpoints, return:

```javascript
{
  data: {
    count: 120,
    results: [{ id: 1, name: 'Ada' }],
  },
}
```

For non-paginated endpoints, create the base service with
`isPaginated = false`; the component then accepts an array response.
`service.options.baseUrl` can be a string or a function of
`service.options.urlParams`.

## Columns

Columns are `CrudTableColumn` instances:

```javascript
new CrudTableColumn(
  'email',
  this.$t('members.email'),
  MemberEmailCell,
  true,   // sortable
  false,  // stickyLeft
  false,  // stickyRight
  {},
  25,     // width percentage
  this.$t('members.emailHelp')
)
```

The column key must exist on every returned row. `cellComponent` receives
`row` and `column`, plus any listeners added to `<CrudTable>`.

## Slots

| Slot | Use |
|---|---|
| `title` | Table heading. |
| `header-right-side` | Buttons such as "Invite" or "Export". |
| `header-filters` | Dropdown filters above the table body. |
| `empty` | Empty state shown only when there are no rows, no search, and no filters. |
| `menus` | Context menus and modals. Receives `update-row` and `delete-row`. |

The `menus` slot is where row action contexts belong. Keep them outside
individual cells so they can update table state through the slot props.

## Row updates

Cell components can emit:

- `row-update` with the full updated row.
- `row-delete` with the row id.
- `refresh` to refetch the current page.
- `row-context` to let the parent open a context menu for a cell / row.

`CrudTable` mutates the current `rows` array for updates and deletions.
For creates, call the component's `upsertRow(row)` through a ref or refetch
the table after the modal closes.

## Search and sort

`CrudTableSearch` debounces typing and emits `search-changed`. Submitting
the search form runs immediately. Sortable headers cycle through
descending, ascending, and no sort. Multi-column sort order is preserved
in the `columnSorts` array sent to the service.

## Anti-patterns

- **Using `CrudTable` for user data grids.** Database table rows have their
  own grid/view system.
- **Returning rows without `rowIdKey`.** Updates and deletes cannot find
  the row to patch.
- **Putting row menus inside every cell.** Put shared contexts in the
  `menus` slot and pass row data through `row-context`.
- **Ignoring filters in the service.** The component refetches when the
  `filters` object changes; the service owns translating those filters to
  query parameters.

## Related

- [Context menus](context-menus.md).
- [Dropdowns](dropdowns.md).
- [Frontend architecture](frontend-architecture.md).
