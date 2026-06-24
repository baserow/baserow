# Grid View Test Plan

Browser coverage for the grid view lives in `e2e-tests/tests/database/grid/`.

This plan defines the expected visible behavior and maps it to e2e coverage,
organized by numbering rules, a coverage matrix, and scenario expectations.

Expected sequences are intentionally repetitive. Use the same sentence for the
same visible side effect whenever a test is added or changed.

`TODO` marks an expected visible detail that the current e2e tests do not
verify. Keep those details in the plan so future tests know the intended
behavior.

## Numbering Convention

Test IDs use `bucket.group.scenario` plus an optional letter suffix for closely
related variants, for example `1.2.1b`.

The first number identifies the domain:

| Bucket | Domain |
|---|---|
| 1 | Row creation |
| 2 | Row updates |
| 3 | Row deletion |
| 4 | Clipboard and multi-cell edits |
| 5 | Filters |
| 6 | Sorts |
| 7 | Search |
| 8 | View display options |
| 9 | Cell selection |
| 10 | Keyboard navigation |
| 11 | Row hover and context menus |
| 12 | Checkbox selection and bulk actions |
| 13 | Row expand modal |
| 14 | Public shared grid |
| 15 | Realtime row events |
| 16 | Realtime metadata and presence |
| 17 | Data-sync read-only mode |

Within each bucket, groups start at `.1` and increase by topic. In covered
create, update, and clipboard sections, `.2` is filter-affecting behavior and
`.3` is sort-affecting behavior. Specs may group setup-heavy blocks out of
numeric order when that keeps related fixtures together. Uncovered group-by
paths are listed in TODO coverage instead of reserving empty groups. Letter
suffixes (`a`, `b`, `c`) are timing or selection variants of the same scenario.

## Coverage Matrix

Maps `operation × active constraints × timing` to the test section that covers
it. `TODO` = uncovered. `—` = not applicable.

**Optimistic (✓):** every active constraint is on a regular field the frontend
can evaluate locally — warnings appear immediately and the row moves or hides
without waiting for the backend.

**Deferred (✗):** at least one active constraint involves a formula field the
frontend cannot evaluate — warnings and row changes for that constraint are
deferred until the backend responds. Escape before the backend responds is `—`
because no warning has appeared yet for the deferred constraint.

**Backend error column:** the backend returns a 5xx error. The optimistic value
(always applied immediately for field edits) must be rolled back. For optimistic
constraints the warning also disappears on rollback; for deferred constraints no
warning appeared so only the value rollback matters. Error toasts are asserted
for covered row CRUD backend-error cases.

When multiple constraints are active and only some involve formula fields, the
row can show an immediate warning for the optimistic constraints while still
waiting on the deferred ones. The "Constraint fields" column records which
constraint fields are regular vs. formula; for combined rows "all regular" and
"any formula" are used since every combined cell is TODO and the specific
field-type breakdown belongs in the scenario description when the test is
written.

| Operation | Constraint | Constraint field | Optimistic | Keep selected | Deselect after confirm | Deselect before confirm | Backend error | Escape |
|---|---|---|:---:|---|---|---|---|---|
| Create | — | — | ✓ | [1.1.1](#111-backend-confirmation-for-a-new-row) | — | — | [1.1.3](#113-failed-create-is-rolled-back-and-the-optimistic-row-disappears) | — |
| Create | filter | regular | ✓ | [1.2.1a](#121a-add-row-that-does-not-match-an-active-simple-field-filter-and-keep-it-selected) | [1.2.1a](#121a-add-row-that-does-not-match-an-active-simple-field-filter-and-keep-it-selected) | [1.2.1b](#121b-deselect-newly-added-filter-mismatched-row-before-backend-confirmation) | [1.2.1d](#121d-backend-returns-500-on-filter-affected-create) | — |
| Create | filter | formula | ✗ | [1.2.2a](#122a-create-row-with-formula-field-filter-active--no-warning-until-backend-responds) | [1.2.2a](#122a-create-row-with-formula-field-filter-active--no-warning-until-backend-responds) | [1.2.2b](#122b-deselect-newly-added-formula-filtered-row-before-backend-confirmation) | [1.2.2c](#122c-backend-returns-500-on-formula-filter-affected-create) | — |
| Create | sort | regular | ✓ | [1.3.1a](#131a-add-row-with-simple-field-sort-asc-and-keep-it-selected) | [1.3.1a](#131a-add-row-with-simple-field-sort-asc-and-keep-it-selected) | [1.3.1b](#131b-add-row-with-simple-field-sort-asc-then-deselect-before-backend-confirmation) | [1.3.1c](#131c-backend-returns-500-on-sort-affected-create) | — |
| Create | sort | formula | ✗ | [1.3.2a](#132a-add-row-with-formula-field-sort-active--no-move-warning-until-backend-responds) | [1.3.2a](#132a-add-row-with-formula-field-sort-active--no-move-warning-until-backend-responds) | [1.3.2b](#132b-add-row-with-formula-field-sort-active-then-deselect-before-backend-confirmation) | [1.3.2c](#132c-backend-returns-500-on-formula-sort-affected-create) | — |
| Create | group-by | regular | ✓ | TODO | TODO | TODO | TODO | — |
| Create | group-by | formula | ✗ | TODO | TODO | TODO | TODO | — |
| Update | — | — | ✓ | [2.1.1](#211-edit-primary-field-and-press-enter) | — | — | [2.1.3](#213-backend-returns-500-on-update) | [2.1.4](#214-press-escape-while-editing) |
| Update | filter | regular | ✓ | [2.2.1a](#221a-edit-filtered-row-to-non-matching-value-and-keep-it-selected) | [2.2.1a](#221a-edit-filtered-row-to-non-matching-value-and-keep-it-selected) | [2.2.1b](#221b-deselect-filter-mismatched-row-before-backend-confirmation) | [2.2.2](#222-backend-returns-500-on-filter-affecting-update) | [2.2.4](#224-press-escape-during-filter-mismatched-edit) |
| Update | filter | formula | ✗ | [2.2.5a](#225a-edit-with-formula-field-filter-active--no-warning-until-backend-responds) | [2.2.5b](#225b-deselect-formula-filtered-row-after-backend-confirmation) | [2.2.5c](#225c-deselect-formula-filtered-row-before-backend-confirmation) | [2.2.5d](#225d-backend-returns-500-on-formula-filter-affecting-update) | — |
| Update | sort | regular | ✓ | [2.3.1a](#231a-edit-sorted-row-so-it-should-move-and-keep-it-selected) | [2.3.1a](#231a-edit-sorted-row-so-it-should-move-and-keep-it-selected) | [2.3.1b](#231b-deselect-sort-mismatched-row-before-backend-confirmation) | [2.3.2](#232-backend-returns-500-on-sort-affecting-update) | [2.3.3](#233-press-escape-during-sort-mismatched-edit) |
| Update | sort | formula | ✗ | [2.3.4a](#234a-edit-with-formula-field-sort-active--no-move-warning-until-backend-responds) | [2.3.4a](#234a-edit-with-formula-field-sort-active--no-move-warning-until-backend-responds) | [2.3.4b](#234b-deselect-formula-sorted-row-before-backend-confirmation) | [2.3.4c](#234c-backend-returns-500-on-formula-sort-affecting-update) | — |
| Update | group-by | regular | ✓ | TODO | TODO | TODO | TODO | TODO |
| Update | group-by | formula | ✗ | TODO | TODO | TODO | TODO | — |
| Paste | — | — | ✓ | TODO | — | — | TODO | — |
| Paste | filter | regular | ✓ | [4.2.1a](#421a-paste-value-that-breaks-active-filter-then-deselect) | [4.2.1a](#421a-paste-value-that-breaks-active-filter-then-deselect) | [4.2.1b](#421b-filter-breaking-paste-deselected-before-backend-confirmation) | TODO | — |
| Paste | filter | formula | ✗ | TODO | TODO | TODO | TODO | — |
| Paste | sort | regular | ✓ | [4.3.1a](#431a-sort-affecting-paste-shows-row-has-moved-warning-then-moves-row-on-deselect) | [4.3.1a](#431a-sort-affecting-paste-shows-row-has-moved-warning-then-moves-row-on-deselect) | [4.3.1b](#431b-sort-affecting-paste-deselected-before-backend-confirmation-moves-row-immediately) | TODO | — |
| Paste | sort | formula | ✗ | TODO | TODO | TODO | TODO | — |
| Paste | group-by | regular | ✓ | TODO | TODO | TODO | TODO | — |
| Paste | group-by | formula | ✗ | TODO | TODO | TODO | TODO | — |

### Combined constraints (TODO)

All combinations of two or more active constraints (filter + sort, filter +
group-by, sort + group-by, filter + sort + group-by) are uncovered for every
operation and timing variant. Each combination should be tested in both the
all-regular (fully optimistic) and any-formula (partially or fully deferred)
configurations. When added, expand this section into a table following the same
structure as the single-constraint table above.

## Row Creation

### 1.1.1 Backend confirmation for a new row

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- Row count increments.
- Empty row stays at the bottom after backend confirmation.
- Row loading spinner is hidden after backend confirmation.

### 1.1.2 Primary field is selected after adding a row

- Empty row is appended at the bottom.
- Row count increments.
- New row primary cell is selected after backend confirmation.

### 1.1.3 Failed create is rolled back and the optimistic row disappears

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- POST request returns 500.
- Optimistic row is removed from the visible grid after the error.
- Row count returns to its original value.
- Error toast is visible.

### 1.2.1a Add row that does not match an active simple-field filter and keep it selected

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- Row remains visible while selected.
- "Row does not match filters" remains visible while the row is selected.
- Row loading spinner is hidden after backend confirmation.
- "Row does not match filters" remains visible while the row is selected after
  backend confirmation.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.

### 1.2.1b Deselect newly added filter-mismatched row before backend confirmation

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- After deselect while the create request is pending, the row is removed from the
  visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row stays hidden after backend confirmation.

### 1.2.1c Enter a value that makes the newly added row match the active filter

- With a filter such as "Name is not empty", empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- Typed value is visible immediately.
- "Row does not match filters" is hidden after the value matches the filter.
- Row remains visible.

### 1.2.1d Backend returns 500 on filter-affected create

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- POST request returns 500.
- Optimistic row is removed from the visible grid after the error.
- "Row does not match filters" is hidden after the error.
- Row count returns to its original value.
- Error toast is visible.

### 1.2.2a Create row with formula-field filter active — no warning until backend responds

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is hidden while the create request is pending
  because the frontend cannot evaluate the formula filter.
- Row loading spinner is hidden after backend confirmation.
- "Row does not match filters" is visible after backend confirmation while the
  row is selected.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.

### 1.2.2b Deselect newly added formula-filtered row before backend confirmation

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is hidden while the create request is pending.
- After deselect while the create request is pending, the row remains visible
  because the frontend has not yet received the formula result from the backend.
- After the create request completes, the row is removed from the visible grid.

### 1.2.2c Backend returns 500 on formula-filter-affected create

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is hidden while the create request is pending
  because the frontend cannot evaluate the formula filter.
- POST request returns 500.
- Optimistic row is removed from the visible grid after the error.
- Row count returns to its original value.
- Error toast is visible.

### 1.3.1a Add row with simple-field sort ASC and keep it selected

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- Row loading spinner is hidden after backend confirmation.
- "Row has moved" remains visible while the row is selected.
- After deselect, the row moves to the first sorted position.
- After deselect, "Row has moved" is hidden.

### 1.3.1b Add row with simple-field sort ASC, then deselect before backend confirmation

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- After deselect while the create request is pending, the row moves to the first
  sorted position.
- Row loading spinner is visible while the create request is pending.
- After deselect, "Row has moved" is hidden.
- Empty row stays in the first sorted position after backend confirmation.
- Row loading spinner is hidden after backend confirmation.
- No warning is visible after backend confirmation.

### 1.3.1c Backend returns 500 on sort-affected create

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- POST request returns 500.
- Optimistic row is removed from the visible grid after the error.
- "Row has moved" is hidden after the error.
- Row count returns to its original value.
- Remaining rows are visible in their original sorted order.
- Error toast is visible.

### 1.3.2a Add row with formula-field sort active — no move warning until backend responds

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is hidden while the create request is pending because the
  frontend cannot evaluate the formula sort.
- Row loading spinner is hidden after backend confirmation.
- "Row has moved" is visible after backend confirmation while the row is selected.
- After deselect, the row moves to its sorted position.
- After deselect, "Row has moved" is hidden.

### 1.3.2b Add row with formula-field sort active, then deselect before backend confirmation

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is hidden while the create request is pending.
- After deselect while the create request is pending, the row stays at the bottom
  because the frontend has not yet received the backend-computed sort value.
- After the create request completes, the row moves to its sorted position.
- No warning is visible after the row moves.

### 1.3.2c Backend returns 500 on formula-sort-affected create

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is hidden while the create request is pending because the
  frontend cannot evaluate the formula sort.
- POST request returns 500.
- Optimistic row is removed from the visible grid after the error.
- Row count returns to its original value.
- Error toast is visible.

### 1.4.1 Edit a field while create is pending

- Empty row is appended at the bottom.
- Row loading spinner is visible while the create request is pending.
- Typed value in a field of the pending row is visible immediately.
- After the create request completes, the queued PATCH fires and the value is
  confirmed.
- No error is shown.

### 1.4.2 PATCH is not sent to the network until the create request completes

- Empty row is appended at the bottom.
- Field in the pending row is edited and confirmed.
- No PATCH request reaches the network while the POST is still in-flight.
- After the POST completes, the queued PATCH fires with the real row ID.
- Field value is saved correctly.

## Row Updates

### 2.1.1 Edit primary field and press Enter

- Typed value is visible immediately.
- Typed value is submitted.
- Original value is no longer visible.
- No row loading spinner is shown for this optimistic text update.

### 2.1.4 Press Escape while editing

- Typed draft is discarded.
- Original value is visible again.
- No save transition is shown.

### 2.1.2 Click outside edited cell

- Typed value is visible immediately.
- Typed value is submitted by blur.
- No row loading spinner is shown for this optimistic text update.

### 2.1.3 Backend returns 500 on update

- Typed value is submitted.
- PATCH request returns 500.
- Grid remains rendered with both rows.
- Typed value is rolled back to the original value.
- Error toast is visible.

### 2.1.5 Invalid email value shows validation UI

- Invalid typed value is visible in the editor.
- Field validation error is visible.
- Pressing Enter keeps the editor open.
- Field validation error remains visible.

### 2.2.1a Edit filtered row to non-matching value and keep it selected

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row does not match filters" is visible immediately for simple-field filters.
- Row remains visible while selected.
- "Row does not match filters" remains visible after backend confirmation.

### 2.2.1b Deselect filter-mismatched row before backend confirmation

- "Row does not match filters" is visible before deselect.
- After deselect while the update request is pending, the row is removed from the
  visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row count decrements.
- Row stays hidden after backend confirmation.

### 2.2.4 Press Escape during filter-mismatched edit

- Typed draft is discarded.
- Original matching value is visible again.
- "Row does not match filters" is hidden.
- Row remains visible.
- Row count is unchanged.

### 2.2.3 Save the same matching value

- Typed value is visible immediately.
- Row remains visible.
- No warning is visible.
- Row count is unchanged.
- No row loading spinner is expected because no visible value transition is
  needed.

### 2.2.2 Backend returns 500 on filter-affecting update

- Typed value is submitted.
- PATCH request returns 500.
- Filtered grid remains rendered.
- Typed value is rolled back to the original value.
- "Row does not match filters" is hidden after rollback.
- Error toast is visible.

### 2.2.5a Edit with formula-field filter active — no warning until backend responds

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row does not match filters" is hidden while the update request is pending
  because the frontend cannot evaluate the formula filter.
- "Row does not match filters" is visible after backend confirmation.
- Row remains visible while selected.

### 2.2.5b Deselect formula-filtered row after backend confirmation

- "Row does not match filters" is visible while the row is selected.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row count decrements.

### 2.2.5c Deselect formula-filtered row before backend confirmation

- Typed value is visible immediately.
- "Row does not match filters" is hidden while the update request is pending.
- After deselect while the update request is pending, the row remains visible
  because the frontend has not yet received the formula result from the backend.
- After the update request completes, the row is removed from the visible grid.

### 2.2.5d Backend returns 500 on formula-filter-affecting update

- Typed value is visible immediately.
- "Row does not match filters" is hidden while the update request is pending
  because the frontend cannot evaluate the formula filter.
- PATCH request returns 500.
- Typed value is rolled back to the original value.
- Row remains visible.
- Error toast is visible.

### 2.3.1a Edit sorted row so it should move and keep it selected

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row has moved" is visible immediately for simple-field sorts.
- Row stays in its current visible position while selected.
- "Row has moved" remains visible after backend confirmation.

### 2.3.1b Deselect sort-mismatched row before backend confirmation

- "Row has moved" is visible before deselect.
- After deselect while the update request is pending, the row moves to its sorted
  position.
- After deselect, "Row has moved" is hidden.
- Row stays in its sorted position after backend confirmation.
- No warning is visible after backend confirmation.

### 2.3.2 Backend returns 500 on sort-affecting update

- Typed value is visible immediately.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- PATCH request returns 500.
- Typed value is rolled back to the original value.
- "Row has moved" is hidden after rollback.
- Row stays in its original position.
- Error toast is visible.

### 2.3.3 Press Escape during sort-mismatched edit

- Typed draft is discarded.
- Original value is visible again.
- "Row has moved" is hidden.
- Row stays in its original position.

### 2.3.4a Edit with formula-field sort active — no move warning until backend responds

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row has moved" is hidden while the update request is pending because the
  frontend cannot evaluate the formula sort.
- "Row has moved" is visible after backend confirmation.
- Row stays in its current visible position while selected.
- After deselect, the row moves to its sorted position.
- After deselect, "Row has moved" is hidden.

### 2.3.4b Deselect formula-sorted row before backend confirmation

- Typed value is visible immediately.
- "Row has moved" is hidden while the update request is pending.
- After deselect while the update request is pending, the row stays in its
  current position because the frontend has not yet received the
  backend-computed sort value.
- After the update request completes, the row moves to its sorted position
  without showing a warning.

### 2.3.4c Backend returns 500 on formula-sort-affecting update

- Typed value is visible immediately.
- "Row has moved" is hidden while the update request is pending because the
  frontend cannot evaluate the formula sort.
- PATCH request returns 500.
- Typed value is rolled back to the original value.
- Row stays in its current position.
- Error toast is visible.

## Row Deletion

### 3.1.1 Right-click row and choose "Delete row"

- Row is removed from the visible grid immediately.
- Row count decrements.
- The next row remains visible.
- Pending DELETE spinner is TODO.

### 3.1.2 Backend returns 500 on delete

- DELETE request returns 500.
- Deleted row is restored after rollback.
- Grid remains rendered with both rows.
- Error toast is visible.

## Clipboard And Multi-Cell Edits

### 4.1.1 Copy one cell and paste into another

- Clipboard receives copied value.
- Pasted value is visible immediately.
- No row loading spinner is shown for this optimistic text update.

### 4.1.2 Paste beyond the last row

- Existing last row is updated.
- Overflow row is created.
- Pasted values are visible immediately.
- Pasted field values are visible in both the updated row and overflow row.
- Create and update spinners are TODO.

### 4.2.1a Paste value that breaks active filter, then deselect

- Pasted value is visible immediately.
- "Row does not match filters" is visible immediately for simple-field filters.
- Row remains visible while selected.
- Row remains selected while warning is visible.
- "Row does not match filters" is visible before deselect.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row count decrements.

### 4.2.1b Filter-breaking paste deselected before backend confirmation

- Pasted value is visible immediately.
- "Row does not match filters" is visible immediately for simple-field filters.
- After deselect while the update request is pending, the row is removed from the
  visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row stays hidden after backend confirmation.

### 4.3.1a Sort-affecting paste shows Row has moved warning then moves row on deselect

- Pasted value is visible immediately.
- "Row has moved" is visible immediately for simple-field sorts.
- Row stays in its current visible position while selected.
- After deselect, the row moves to its sorted position.
- After deselect, "Row has moved" is hidden.

### 4.3.1b Sort-affecting paste deselected before backend confirmation moves row immediately

- Pasted value is visible immediately.
- "Row has moved" is visible immediately for simple-field sorts.
- After deselect while the update request is pending, the row moves to its sorted
  position.
- After deselect, "Row has moved" is hidden.
- Row stays in its sorted position after backend confirmation.
- No warning is visible after backend confirmation.

### 4.4.1 Delete clears selected cell range

- Rectangular multi-select range is visible.
- Pressing Delete clears every selected cell value.
- Non-selected cells are unchanged.

## Filters

### 5.1.1 Load view with API-created filter

- Grid opens with only matching rows visible.
- Non-matching rows are absent from the visible grid.

### 5.1.2 Load view with two AND filters

- Grid opens with only rows matching both filters visible.
- Rows matching only one condition are absent from the visible grid.

### 5.2.1 Use text contains filter

- Grid opens with every row containing the substring visible.
- Non-matching rows are absent from the visible grid.

## Sorts

### 6.1.1 Sort ASC

- Grid opens with rows visible in ascending order.

### 6.1.2 Sort DESC

- Grid opens with rows visible in descending order.

### 6.1.3 Sort by Name ASC and Score DESC

- Grid opens with primary sort applied first.
- Rows tied on Name are ordered by Score descending.

## Search

### 7.1.1 Search in highlight mode

- Search panel is open.
- Search is idle.
- Matching cells are highlighted.
- Non-matching rows remain visible.
- Non-matching cells are not highlighted.

### 7.1.2 Search with no matches in highlight mode

- Search panel is open.
- Search is idle.
- No cells are highlighted.
- All rows remain visible.

### 7.1.3 Clear search

- Existing highlights are hidden.
- All rows remain visible.

### 7.1.4 Search matches a non-primary field

- Matching non-primary cell is highlighted.
- Primary plus non-primary multi-field highlight in the same row is TODO.

### 7.2.1 Search in hide-not-matching mode

- Typing search hides non-matching rows.
- Matching rows remain visible.

### 7.2.2 Toggle hide-not-matching mode off

- Hidden rows become visible again.
- Matching cells remain highlighted.

## View Display Options

### 8.1.1 Row coloring from single-select color

- Grid opens with all rows loaded.
- Selected single-select values are visible.
- Row background uses the selected option color in the frozen-left section.
- Row background uses the selected option color in the scrollable-right section.
- No row loading spinner is shown because row coloring is loaded from the saved
  view decoration.

### 8.2.1 Hide and show a non-primary field

- Field header is initially visible.
- Field cells are initially visible.
- Hiding the field removes the field header immediately.
- Hiding the field removes the field cells immediately.
- Hidden state persists after reload.
- Row count is unchanged.
- Showing the field restores the field header.
- Showing the field restores the field cells with their values.
- Shown state persists after reload.

### 8.3.1 Change row height

- Grid opens at small row height.
- Values are visible.
- Selecting Medium changes visible rows to 55px.
- Values remain visible after changing row height.
- Selecting Large changes visible rows to 99px.
- Values remain visible after changing row height.
- Large row height persists after reload.
- No row loading spinner is shown.

### 8.4.1 Load view with frozen columns

- Saved frozen column count moves the first non-primary field into the frozen-left
  section.
- Frozen field header is absent from the scrollable-right section.
- Next non-primary field remains visible in the scrollable-right section.
- Frozen column layout persists after reload.

### 8.5.1 Count mode shows sequential row positions

- Row count column shows "1" for the first row, "2" for the second, and so on.
- Note: the backend default for a new view is `row_identifier_type = "id"`. Tests
  that verify count mode must explicitly set the view to count mode via API before
  navigating.

### 8.5.2 Switch to Row identifier and back to Count

- Clicking the dropdown icon in the row count header opens the identifier picker.
- Selecting "Row identifier" changes the count column to show actual backend row IDs.
- Sequential position values are no longer visible.
- Row identifier values persist after reload.
- Selecting "Count" restores sequential position values.
- Row identifier values are no longer visible.
- Count values persist after reload.

## Cell Selection

### 9.1.1 Click a cell

- Clicked cell becomes selected.
- No multi-select range is shown.

### 9.1.2 Shift-click another cell

- First selected cell remains the anchor.
- Rectangular multi-select range is shown between the anchor cell and clicked
  cell.

### 9.1.3 Drag across cells

- Rectangular multi-select range is shown during drag.
- Rectangular multi-select range remains visible after mouseup.

### 9.1.4 Press Escape

- Existing multi-select range is hidden.

### 9.1.5 Click outside the grid

- Existing multi-select range is hidden.

### 9.2.1 Shift+Arrow expands selected range

- Starting from one selected cell, Shift+ArrowRight expands the selected range
  to two cells.
- Shift+ArrowDown expands the selected range to a 2x2 area.

## Keyboard Navigation

### 10.1.1 Press Tab

- Selection moves to the next cell.
- Typing starts editing that cell.
- Typed value is visible immediately.

### 10.1.2 Press Enter on selected cell

- Editor appears in the selected cell.

### 10.1.3 Press Enter while editing

- Typed value is visible immediately.
- Selection moves down.
- Typing starts editing the row below.
- Second typed value is visible immediately.

### 10.1.4 Press Escape while editing

- Typed draft is discarded.
- Original value is visible again.
- Editor is closed.

### 10.1.5 Use arrow keys

- Selection moves to the target cell.
- No editor appears.

### 10.1.6 Type while a cell is selected

- Editor appears in the selected cell.
- Editor contains the typed characters.

## Row Hover Actions

### 11.1.1 Hover and unhover toggles checkbox and row count

- Row count is visible before hover.
- Hovering the row reveals the checkbox.
- Row count is hidden while the row is hovered.
- Checkbox is visible while hovering.
- Moving the mouse away hides the checkbox.
- Row count is visible again after unhover.

### 11.1.2 Drag handle present in unsorted view, absent when sort is active

- Drag handle element is present in a view with no active sort.
- Drag handle element is absent in a view where a sort controls row order.

### 11.2.1 Insert row below from context menu

- Context menu opens for a row.
- Selecting "Insert row below" creates an empty row directly below the selected
  row.
- Existing rows keep their relative order.

### 11.2.2 Duplicate row from context menu

- Context menu opens for a row.
- Selecting "Duplicate row" creates a copied row directly below the selected row.
- Duplicated row contains the copied primary and field values.

## Checkbox Selection

### 12.1.1 Checkbox selection clears active area selection

- Rectangular multi-select range is visible.
- Hovering a row reveals its checkbox.
- Clicking the row checkbox selects the row.
- Existing multi-select range is hidden.

## Row Expand Modal

### 13.1.1 Open row expand modal from context menu

- Context menu opens for a row.
- Selecting "Enlarge row" opens the row edit modal.
- Modal contains the selected row value.
- Closing the modal hides it.

## Public Shared Grid

### 14.1.1 Public grid renders rows without edit controls

- Public shared grid route renders without an authenticated session.
- Visible rows are loaded.
- Add row control is hidden.
- Row mutation context-menu actions are hidden.

## TODO Coverage

- 1.3.x: Sorted add where the correct destination is outside the current buffer.
- 1.5.x: Create rows with active group-by constraints.
- 2.3.5: Sort relocation outside the current buffer.
- 2.4.x: Update rows with active group-by constraints.
- 2.5.x: Editing fields that participate in formulas.
- 4.2.x: Filter-affecting paste with formula-field filter (deferred warning path).
- 4.3.x: Sort-affecting paste with formula-field sort (deferred move path).
- 4.4.x: Backspace clears all selected cell values while an area selection is active.
- 4.5.x: Larger multi-cell paste matrix.
- 4.6.x: Copy selected cells with column headers via the context menu option.
- 4.7.x: Paste with active group-by constraints.
- 5.3.x: OR filter combinations and filter groups.
- 8.1.x: Row coloring from a formula-based decoration (section 8.1 covers
  single-select only).
- 8.4.x: Freeze columns drag UI and limits.
    - Freeze handle is visible when there is enough horizontal space.
    - Freezing 3 columns moves 3 columns into the frozen-left section.
    - Freezing 4 columns moves 4 columns into the frozen-left section.
    - The scrollable-right section scrolls independently.
    - The UI does not allow freezing more than 4 columns.
    - The UI does not allow freezing more columns than can fit in the available
      width.
- 8.6.x: Drag-and-drop rows when no sort is applied.
    - Drop target is visible while dragging.
    - Dropped row moves to the new visual position.
    - Row order persists after reload.
- 8.7.x: Drag-and-drop fields.
    - Field-drag preview is visible while dragging a field header.
    - Target position is visible while dragging a field header.
    - Dropping reorders field headers.
    - Dropping reorders row cells to match the field headers.
    - Field order persists after reload.
- 11.2.x: Remaining single-row context menu actions beyond deletion, insert below,
  and duplicate (insert above, copy row URL).
- 12.2.x: Multi-row bulk actions on checkbox-selected rows.
- 13.2.x: Row expand modal deeper coverage — open via double-click, navigate
  prev/next rows, edit fields from inside the modal, filter re-check on modal
  close.
- 15.x: Realtime multi-user row events.
- 16.x: Realtime metadata and presence.
- 17.x: Data-sync read-only mode — add row button and delete row option are hidden
  when the table has a data sync without two-way sync enabled.
