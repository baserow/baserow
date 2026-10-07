# Shared CRUD tables

`CrudTable` renders service-backed lists with search, sorting, pagination, empty
states and optional row details. Explore its states in Storybook under
**Baserow / CrudTable**. Existing callers do not need to enable expansion.

## Expandable rows

Providing `expanded-row` enables expansion. The slot renders inside a separate
`tbody` and must contain one or more `tr` elements. Use normal table cells to
align details with the parent columns, including `colspan` when a detail spans
multiple columns. Reuse the `data-table__table-row`, `data-table__table-cell` and
`data-table__table-cell-content` classes for the shared styling.

For a free-form block spanning the entire table:

```vue
<CrudTable :service="service" :columns="columns" row-id-key="id">
  <template #title="{ count }">{{ count }} items</template>
  <template #expanded-row="{ row, columns }">
    <tr>
      <td :colspan="columns.length" class="data-table__expanded-content">
        <ItemDetails :item="row" />
      </td>
    </tr>
  </template>
</CrudTable>
```

- `rowExpandable(row)` optionally limits which rows can expand. Without this
  predicate, every row is expandable when the slot is present.
- `expandColumnKey` places the toggle beside the contents of a chosen column.
  By default, it appears in the first column.
- `row-expansion-toggle`, scoped to `{ row, expanded }`, adds content beside the
  chevron. The table owns the accessible button, keyboard behavior and ARIA state.
- `row-toggle` emits `{ row, expanded }` after a user toggles a row.
- `expanded-row` also receives `updateRow`, `deleteRow` and `refresh` callbacks,
  as do the `rows` and `menus` slots.

Rows start collapsed and can be opened independently. Clicking non-interactive
row content or the disclosure button toggles expansion. Cell controls retain
their own behavior. For a custom interactive target without native semantics,
use `data-prevent-row-toggle` to opt out of row clicks.

Expansion is keyed by `rowIdKey`. Changing page, search or filters clears it.
Sorting or refreshing the same page preserves expansion for rows still present
and eligible. Expanded content is unmounted when collapsed or while fetching;
keep any draft state that must survive outside the slot content.

The legacy `rows` slot replaces the entire body, including the default row
renderer and expansion. Callers using it own their row interactions.

## Header and narrow layouts

The `title` slot receives `{ count, loading }`, where `count` is the service's
total result count (or the array length for non-paginated services). Search and
`header-right-side` controls remain visible when the table is empty. Put the
view's main creation or invitation button in `primary-action`: it appears in
the header and below the unfiltered empty-state content, with the same event
handlers and permission checks. Keep other controls in `header-right-side`.
Use `search-placeholder` for a contextual search prompt (for example, "Search
members"); omitting it keeps the shared search label.
The `empty` slot supplies the unfiltered empty-state content; do not repeat the
primary action there. Unmatched search and filters show the shared no-results
message instead, with the primary action available in the header.
If the current page becomes empty while other results remain, the table shows
a page-empty message and keeps pagination available instead of showing the
collection's onboarding content.

Columns scroll horizontally rather than disappearing. Mark row action columns
with `stickyRight` in their `CrudTableColumn` definition so their controls stay
accessible while scrolling. Keep the same sticky class on any expanded action
cells, as demonstrated by the expandable Storybook story.

The **Expandable Rows** and **Narrow Viewport** stories demonstrate member
role details for Arlene, Sam and Robin, with three, two and one assignments
respectively. Expand several members at once; Charlie has no assignments and
cannot be expanded. The examples include Projects (database), Tasks (table)
and Kanban - Q3 (view). The role selectors are interactive; edits stay in the
story's in-memory fixtures. This is a reusable component example, not a members
page or a backend integration. Storybook contains UI components rather than
management-page previews.
