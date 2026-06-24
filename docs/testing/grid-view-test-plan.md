# Grid View Flat Test Plan

Browser coverage for the flat (non-grouped) grid view lives in
`e2e-tests/tests/database/grid/`. Grouped grid and collapsible group-by behavior
are intentionally out of scope for this plan.

Expected sequences are intentionally repetitive. Use the same sentence for the
same visible side effect whenever a test is added or changed.

`TODO` marks an expected visible detail that the current e2e tests do not
verify. Keep those details in the plan so future tests know the intended
behavior.

## Row Creation

### 1.1.1 Click "+ Add row" with no filters/sorts

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row count increments.
- Row loading spinner is visible while the create request is pending.
  Covered by 1.1.2.
- Row loading spinner is hidden after backend confirmation.

### 1.1.2 Backend confirmation for a new row

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- Row count increments.
- Empty row stays at the bottom after backend confirmation.
- Row loading spinner is hidden after backend confirmation.

### 1.2.1a Add row with simple-field sort ASC and keep it selected

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- Row loading spinner is hidden after backend confirmation.
- "Row has moved" remains visible while the row is selected.
- After deselect, the row moves to the first sorted position.
- After deselect, "Row has moved" is hidden.

### 1.2.1b Add row with simple-field sort ASC, then deselect before backend confirmation

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

### 1.2.2a Edit Name under simple-field sort ASC and keep it selected

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- Row stays in its current visible position while selected.
- "Row has moved" remains visible while the row is selected after backend
  confirmation.
- After deselect, the row moves to its sorted position.
- After deselect, "Row has moved" is hidden.

### 1.2.2b Edit Name under simple-field sort ASC, then deselect before backend confirmation

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row has moved" is visible immediately because the frontend can evaluate the
  simple-field sort.
- After deselect while the update request is pending, the row moves to its sorted
  position.
- After deselect, "Row has moved" is hidden.
- Row stays in its sorted position after backend confirmation.
- No warning is visible after backend confirmation.

### 1.2.3 Deselect the sort-mismatched row after backend confirmation

- "Row has moved" is visible before deselect.
- After deselect, the row moves to its sorted position.
- After deselect, "Row has moved" is hidden.

### 1.2.4 Press Escape during sort mismatch

- Typed draft is discarded.
- Original value is visible again.
- "Row has moved" is hidden.
- Row stays in its original position.

### 1.3.1a Add row that does not match an active simple-field filter and keep it selected

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

### 1.3.1b Deselect newly added filter-mismatched row before backend confirmation

- Empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- Row loading spinner is visible while the create request is pending.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- After deselect while the create request is pending, the row is removed from the
  visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row stays hidden after backend confirmation.

### 1.3.1c Enter a value that makes the newly added row match the active filter

- With a filter such as "Name is not empty", empty row is appended at the bottom.
- Empty primary and field cells are visible immediately.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- Typed value is visible immediately.
- "Row does not match filters" is hidden after the value matches the filter.
- Row remains visible.
- This exact newly-created-row correction path is TODO.

### 1.3.1d Edit existing row to keep matching active filter

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- Row remains visible.
- No warning is visible.
- Row count is unchanged.

### 1.3.2a Type value that does not match a simple-field filter and keep it selected

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- Row remains visible while selected.
- "Row does not match filters" remains visible while the row is selected after
  backend confirmation.

### 1.3.2b Type value that does not match a simple-field filter, then deselect before backend confirmation

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row does not match filters" is visible immediately because the frontend can
  evaluate the simple-field filter.
- After deselect while the update request is pending, the row is removed from the
  visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row stays hidden after backend confirmation.

### 1.3.3 Deselect filter-mismatched row after backend confirmation

- "Row does not match filters" is visible before deselect.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row count decrements.

### 1.3.4 Press Escape during filter mismatch

- Typed draft is discarded.
- Original matching value is visible again.
- "Row does not match filters" is hidden.
- Row remains visible.
- Row count is unchanged.

## Row Editing

### 2.1.1 Edit primary field and press Enter

- Typed value is visible immediately.
- Typed value is submitted.
- Original value is no longer visible.
- No row loading spinner is shown for this optimistic text update.

### 2.1.2 Press Escape while editing

- Typed draft is discarded.
- Original value is visible again.
- No save transition is shown.

### 2.1.3 Click outside edited cell

- Typed value is visible immediately.
- Typed value is submitted by blur.
- No row loading spinner is shown for this optimistic text update.

### 2.1.4 Backend returns 500 on update

- Typed value is submitted.
- PATCH request returns 500.
- Grid remains rendered with both rows.
- Full rollback value and error-toast assertions are TODO.

### 2.3.1 Edit filtered row to non-matching value

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row does not match filters" is visible immediately for simple-field filters.
- Row remains visible while selected.
- Readonly/formula-filter deferral is TODO.

### 2.3.1b Deselect filter-mismatched row

- "Row does not match filters" is visible before deselect.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row count decrements.

### 2.3.2 Press Escape during filter-mismatched edit

- Typed draft is discarded.
- Original matching value is visible again.
- "Row does not match filters" is hidden.
- Row remains visible.
- Row count is unchanged.

### 2.3.3 Save the same matching value

- Typed value is visible immediately.
- Row remains visible.
- No warning is visible.
- Row count is unchanged.
- No row loading spinner is expected because no visible value transition is
  needed.

### 2.3.4 Backend returns 500 on filter-affecting update

- Typed value is submitted.
- PATCH request returns 500.
- Filtered grid remains rendered.
- Full rollback value and error-toast assertions are TODO.

### 2.5.1 Edit sorted row so it should move

- Typed value is visible immediately.
- No row loading spinner is shown for this optimistic text update.
- "Row has moved" is visible immediately for simple-field sorts.
- Row stays in its current visible position while selected.
- After deselect, the row moves to its sorted position.
- After deselect, "Row has moved" is hidden.
- Readonly/formula-sort deferral is TODO.

### 2.5.2 Press Escape during sort-mismatched edit

- Typed draft is discarded.
- Original value is visible again.
- "Row has moved" is hidden.
- Row stays in its original position.

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
- Error-toast assertion is TODO.

## View Options

### 4.1.1 Load view with API-created filter

- Grid opens with only matching rows visible.
- Non-matching rows are absent from the visible grid.

### 4.1.3 Load view with two AND filters

- Grid opens with only rows matching both filters visible.
- Rows matching only one condition are absent from the visible grid.

### 4.2.2 Use text contains filter

- Grid opens with every row containing the substring visible.
- Non-matching rows are absent from the visible grid.

### 5.1.1 Sort ASC

- Grid opens with rows visible in ascending order.

### 5.1.2 Sort DESC

- Grid opens with rows visible in descending order.

### 5.1.3 Sort by Name ASC and Score DESC

- Grid opens with primary sort applied first.
- Rows tied on Name are ordered by Score descending.

### 6.1.1 Search in highlight mode

- Search panel is open.
- Search is idle.
- Matching cells are highlighted.
- Non-matching rows remain visible.
- Non-matching cells are not highlighted.

### 6.1.2 Search with no matches in highlight mode

- Search panel is open.
- Search is idle.
- No cells are highlighted.
- All rows remain visible.

### 6.1.3 Clear search

- Existing highlights are hidden.
- All rows remain visible.

### 6.1.4 Search matches a non-primary field

- Matching non-primary cell is highlighted.
- Primary plus non-primary multi-field highlight in the same row is TODO.

### 6.2.1 Search in hide-not-matching mode

- Typing search hides non-matching rows.
- Matching rows remain visible.

### 6.2.2 Toggle hide-not-matching mode off

- Hidden rows become visible again.
- Matching cells remain highlighted.

### 7.1.1 Row coloring from single-select color

- Grid opens with all rows loaded.
- Selected single-select values are visible.
- Row background uses the selected option color in the frozen-left section.
- Row background uses the selected option color in the scrollable-right section.
- No row loading spinner is shown because row coloring is loaded from the saved
  view decoration.

### 7.2.1 Hide and show a non-primary field

- Field header is initially visible.
- Field cells are initially visible.
- Hiding the field removes the field header immediately.
- Hiding the field removes the field cells immediately.
- Row count is unchanged.
- Showing the field restores the field header.
- Showing the field restores the field cells with their values.

### 7.3.1 Change row height

- Grid opens at small row height.
- Values are visible.
- Selecting Medium changes visible rows to 55px.
- Values remain visible after changing row height.
- Selecting Large changes visible rows to 99px.
- Values remain visible after changing row height.
- No row loading spinner is shown.

### 7.7.1 Count mode shows sequential row positions

- Row count column shows "1" for the first row, "2" for the second, and so on.
- Note: the backend default for a new view is `row_identifier_type = "id"`. Tests
  that verify count mode must explicitly set the view to count mode via API before
  navigating.

### 7.7.2 Switch to Row identifier shows actual row IDs

- Clicking the dropdown icon in the row count header opens the identifier picker.
- Selecting "Row identifier" changes the count column to show actual backend row IDs.
- Sequential position values are no longer visible.

### 7.7.3 Switch back to Count restores sequential positions

- Selecting "Count" restores sequential position values.
- Row identifier values are no longer visible.

## Row Hover Actions

### 10.1.1 Hover shows checkbox and hides row count

- Row count is visible before hover.
- Hovering the row reveals the checkbox.
- Row count is hidden while the row is hovered.

### 10.1.2 Mouse-out restores row count and hides checkbox

- Checkbox is visible while hovering.
- Moving the mouse away hides the checkbox.
- Row count is visible again after unhover.

### 10.1.3 Drag handle present in unsorted view, absent when sort is active

- Drag handle element is present in a view with no active sort.
- Drag handle element is absent in a view where a sort controls row order.

## Selection, Paste, And Keyboard

### 8.1.1 Click a cell

- Clicked cell becomes selected.
- No multi-select range is shown.

### 8.1.2 Shift-click another cell

- First selected cell remains the anchor.
- Rectangular multi-select range is shown between the anchor cell and clicked
  cell.

### 8.1.3 Drag across cells

- Rectangular multi-select range is shown during drag.
- Rectangular multi-select range remains visible after mouseup.

### 8.1.4 Press Escape

- Existing multi-select range is hidden.

### 8.1.5 Click outside the grid

- Existing multi-select range is hidden.

### 8.3.1 Copy one cell and paste into another

- Clipboard receives copied value.
- Pasted value is visible immediately.
- No row loading spinner is shown for this optimistic text update.

### 8.3.4 Paste beyond the last row

- Existing last row is updated.
- Overflow row is created.
- Pasted values are visible immediately.
- Create and update spinners are TODO.

### 8.3.6 Paste value that breaks active filter

- Pasted value is visible immediately.
- "Row does not match filters" is visible immediately for simple-field filters.
- Row remains visible while selected.
- Pending update timing is TODO.

### 8.3.7 Deselect after filter-mismatching paste

- "Row does not match filters" is visible before deselect.
- After deselect, the row is removed from the visible grid.
- After deselect, "Row does not match filters" is hidden.
- Row count decrements.
- Deselecting before backend confirmation is TODO.

### 9.1 Press Tab

- Selection moves to the next cell.
- Typing starts editing that cell.
- Typed value is visible immediately.

### 9.3 Press Enter on selected cell

- Editor appears in the selected cell.

### 9.4 Press Enter while editing

- Typed value is visible immediately.
- Selection moves down.
- Typing starts editing the row below.
- Second typed value is visible immediately.

### 9.5 Press Escape while editing

- Typed draft is discarded.
- Original value is visible again.

### 9.6 Use arrow keys

- Selection moves to the target cell.
- No editor appears.

### 9.7 Type while a cell is selected

- Editor appears in the selected cell.
- Editor contains the typed characters.

## TODO Coverage

- 1.1.3: Full rollback assertions for failed row creation.
- 1.1.4: Primary field is selected immediately after adding a row.
- 1.2.x: Sorted add where the correct destination is outside the current buffer.
- 1.2.x: Sorted add on a readonly/formula field.
    - Empty row is appended at the bottom.
    - Row loading spinner is visible while the create request is pending.
    - "Row has moved" is hidden while the create request is pending because the
      frontend must wait for the backend-computed sort value.
    - After backend confirmation, "Row has moved" is visible while the row is
      selected.
    - If already deselected after backend confirmation, the row moves to its final
      position without showing the warning.
- 1.4.x: Create with an active formula-field filter.
- 2.1.5: Field validation error UI for invalid typed values.
- 2.2.x: Editing fields that participate in formulas.
- 2.4.x: Editing fields while a formula filter is active.
- 2.4.x: Editing a row where a readonly/formula-field filter cannot be evaluated
  by the frontend.
    - Typed value is visible immediately.
    - No row loading spinner is shown for this optimistic text update.
    - "Row does not match filters" is hidden while the update request is pending.
    - "Row does not match filters" is visible after backend confirmation.
    - Row is removed from the visible grid after backend confirmation if the row is
      not selected.
- 2.5.3: Failed sort-affecting update rollback.
- 2.5.4: Sort relocation outside the current buffer.
- 2.5.x: Editing a row where a readonly/formula-field sort cannot be evaluated
  by the frontend.
    - Typed value is visible immediately.
    - No row loading spinner is shown for this optimistic text update.
    - "Row has moved" is hidden while the update request is pending.
    - "Row has moved" is visible after backend confirmation if the row is still
      selected.
    - Row moves to its sorted position after backend confirmation if the row is not
      selected.
- 4.4.x: OR filter combinations and filter groups.
- 7.4.x: Drag-and-drop rows when no sort is applied.
    - Drop target is visible while dragging.
    - Dropped row moves to the new visual position.
    - Row order persists after reload.
- 7.5.x: Drag-and-drop fields.
    - Field-drag preview is visible while dragging a field header.
    - Target position is visible while dragging a field header.
    - Dropping reorders field headers.
    - Dropping reorders row cells to match the field headers.
    - Field order persists after reload.
- 7.6.x: Freeze columns.
    - Freeze handle is visible when there is enough horizontal space.
    - Freezing 1 column moves 1 column into the frozen-left section.
    - Freezing 2 columns moves 2 columns into the frozen-left section.
    - Freezing 3 columns moves 3 columns into the frozen-left section.
    - Freezing 4 columns moves 4 columns into the frozen-left section.
    - The scrollable-right section scrolls independently.
    - The UI does not allow freezing more than 4 columns.
    - The UI does not allow freezing more columns than can fit in the available
      width.
- 7.8.x: Row coloring from a formula-based decoration (section 7.1 covers
  single-select only).
- 8.2.x: Shift+Arrow expands the multi-select area from the keyboard.
- 8.4.x: Larger multi-cell paste matrix.
- 8.5.x: Filter-affecting paste where the row is deselected before backend
  confirmation.
    - For simple-field filters, pasted value is visible immediately.
    - For simple-field filters, "Row does not match filters" is visible
      immediately.
    - For simple-field filters, after deselect, the row is removed from the visible
      grid while the update request is pending.
    - For readonly/formula-field filters, pasted value is visible immediately.
    - For readonly/formula-field filters, "Row does not match filters" is hidden
      while the update request is pending.
    - For readonly/formula-field filters, row is removed from the visible grid
      after backend confirmation if the row is not selected.
- 8.6.x: Delete/Backspace clears all selected cell values while an area selection
  is active.
- 8.7.x: Copy selected cells with column headers via the context menu option.
- 10.2.x: Full single-row context menu matrix beyond deletion (insert above, insert
  below, duplicate, copy row URL).
- 11.1.x: Checkbox row selection mechanism (selecting rows via the checkbox column,
  mutual exclusivity with area selection).
- 11.2.x: Multi-row bulk actions on checkbox-selected rows.
- 12.x: Realtime multi-user row events.
- 13.x: Realtime metadata and presence.
- 14.x: Row expand modal — open via double-click or context menu "Enlarge row",
  navigate prev/next rows, edit fields from inside the modal, filter re-check on
  modal close.
- 15.x: Data-sync read-only mode — add row button and delete row option are hidden
  when the table has a data sync without two-way sync enabled.
- 16.x: Public shared grid view coverage.

## Robustness Rules

- Prefer locator assertions and Playwright polling over fixed sleeps.
- Seed state through API fixtures so tests do not depend on previous test order.
- Drive cells by visual row and field indices; use text only for assertions.
- Intercept or pause network requests when verifying failed or pending backend
  paths.
