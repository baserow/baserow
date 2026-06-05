/**
 * Grid view - multi-cell selection, keyboard navigation, copy/paste, row hover.
 *
 * Catalogue sections covered:
 *   section 4   Clipboard operations
 *   section 9   Multi-cell selection
 *   section 10  Keyboard navigation
 *   section 11  Row hover/context actions
 *   section 12  Checkbox row selection
 *   section 13  Row expand modal smoke coverage
 *
 */

import type { Page } from "@playwright/test";
import { test, expect } from "../../baserowTest";
import { GridPage } from "../../../pages/database/gridPage";
import {
  GridSetupResult,
  resetRows,
  setupGrid,
} from "../../../fixtures/database/gridSetup";
import { pauseNextRequestWithSignal } from "../../../fixtures/network";

type Setup = GridSetupResult;

async function pasteText(page: Page, text: string) {
  await page.evaluate((clipboardText) => {
    const data = new DataTransfer();
    data.setData("text/plain", clipboardText);
    const event = new ClipboardEvent("paste", {
      bubbles: true,
      cancelable: true,
      clipboardData: data,
    });
    document.dispatchEvent(event);
  }, text);
}

function multiSelectedFieldCells(page: Page) {
  return page.locator(".grid-view__right .grid-view__column--multi-select");
}

// -----------------------------------------------------------------------------
// section 9.1  Selection mechanics
// -----------------------------------------------------------------------------

test.describe("9.1 Selection mechanics", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;
  let groupBy: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "SelectionDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "note A" },
        { Name: "Bob", Score: 20, Notes: "note B" },
        { Name: "Carol", Score: 30, Notes: "note C" },
      ],
    });
    groupBy = await setupGrid({
      dbName: "SelectionGroupByDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "note A" },
        { Name: "Bob", Score: 20, Notes: "note B" },
        { Name: "Carol", Score: 30, Notes: "note C" },
      ],
      groupBys: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.1.1 clicking one field cell selects it and leaves no multi-select range visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.selectFieldCell(0, 0);

    await grid.expectFieldSelected(0, 0);
    await expect(page.locator(".grid-view__column--multi-select")).toHaveCount(
      0,
    );
  });

  test("9.1.2 shift-clicking another cell keeps the anchor selected and shows the rectangular range", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0); // head (Alice, Score)
    await grid.expectFieldSelected(0, 0);
    await grid.fieldCellAt(1, 1).click({ modifiers: ["Shift"] }); // tail (Bob, Notes)

    // Both cells should be in the multi-select range
    await expect(multiSelectedFieldCells(page)).toHaveCount(4, {
      timeout: 5_000,
    }); // 2 rows x 2 cols
  });

  test("9.1.3 dragging across cells shows a rectangular range that remains visible after mouseup", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    const fromCell = grid.fieldCellAt(0, 0); // Alice / Score
    const toCell = grid.fieldCellAt(1, 1); // Bob   / Notes

    const fromBox = await fromCell.boundingBox();
    const toBox = await toCell.boundingBox();

    if (!fromBox || !toBox)
      throw new Error("Could not measure cell bounding boxes");

    const cx = (box: { x: number; width: number }) => box.x + box.width / 2;
    const cy = (box: { y: number; height: number }) => box.y + box.height / 2;

    // Simulate a real drag: mousedown on the first cell, move to the last,
    // then release. The { steps } option fires intermediate mousemove events
    // so the grid's mouseover handler extends the selection incrementally.
    await page.mouse.move(cx(fromBox), cy(fromBox));
    await page.mouse.down();
    await page.mouse.move(cx(toBox), cy(toBox), { steps: 5 });
    await page.mouse.up();

    // The selection must still be present after mouseup.
    // This specifically tests the regression where mouseup clears
    // the selection instead of just releasing the hold.
    await expect(multiSelectedFieldCells(page)).toHaveCount(4, {
      timeout: 5_000,
    }); // 2 rows x 2 cols
  });

  test("9.1.4 Escape removes the visible multi-select range", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0);
    await grid.expectFieldSelected(0, 0);
    await grid.fieldCellAt(1, 1).click({ modifiers: ["Shift"] });
    await expect(
      page.locator(".grid-view__column--multi-select").first(),
    ).toBeVisible();

    await page.keyboard.press("Escape");

    await expect(page.locator(".grid-view__column--multi-select")).toHaveCount(
      0,
      { timeout: 5_000 },
    );
  });

  test("9.1.5 clicking outside the grid removes the visible multi-select range", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0);
    await grid.expectFieldSelected(0, 0);
    await grid.fieldCellAt(1, 0).click({ modifiers: ["Shift"] });

    await grid.clickAway();

    await expect(page.locator(".grid-view__column--multi-select")).toHaveCount(
      0,
      { timeout: 5_000 },
    );
  });

  test("9.1.6 group-by cell selection and shift range use visible row indexes", async ({
    page,
  }) => {
    const grid = new GridPage(page, groupBy.user);
    await grid.goTo(groupBy.database, groupBy.table);
    await grid.expectGroupByBanner("Alice", 1, true);
    await grid.expectGroupByBanner("Bob", 1, true);
    await grid.expandAllGroupsFromContext();
    await grid.expectGroupByBanner("Alice", 1);
    await grid.expectGroupByBanner("Bob", 1);

    await grid.selectFieldCell(0, 0);
    await grid.expectFieldSelected(0, 0);
    await grid.fieldCellAt(1, 1).click({ modifiers: ["Shift"] });

    await expect(multiSelectedFieldCells(page)).toHaveCount(4, {
      timeout: 5_000,
    });
  });
});

// -----------------------------------------------------------------------------
// section 9.2  Keyboard multi-cell selection
// -----------------------------------------------------------------------------

test.describe("9.2 Keyboard multi-cell selection", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "KeyboardSelectionDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "note A" },
        { Name: "Bob", Score: 20, Notes: "note B" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.2.1 Shift+Arrow expands the selected range from one cell to a 2x2 area", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0);
    await page.keyboard.press("Shift+ArrowRight");
    await grid.expectMultiSelectedCellCount(2);
    await page.keyboard.press("Shift+ArrowDown");
    await grid.expectMultiSelectedCellCount(4);
  });
});

// -----------------------------------------------------------------------------
// section 4  Clipboard operations
// -----------------------------------------------------------------------------

test.describe("4 Clipboard operations", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;
  let pasteFilter: Setup;
  let pasteSort: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "PasteDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Row1", Score: 10, Notes: "note1" },
        { Name: "Row2", Score: 20, Notes: "note2" },
        { Name: "Row3", Score: 30, Notes: "note3" },
      ],
    });
    pasteFilter = await setupGrid({
      dbName: "PasteFilterDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Keep", Score: 10 },
        { Name: "Keep", Score: 20 },
      ],
      filters: [{ fieldName: "Name", type: "equal", value: "Keep" }],
    });
    pasteSort = await setupGrid({
      dbName: "PasteSortDb",
      fields: [{ name: "Score", type: "number" }],
      sorts: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page, browserName }) => {
    await resetRows(g, [
      { Name: "Row1", Score: 10, Notes: "note1" },
      { Name: "Row2", Score: 20, Notes: "note2" },
      { Name: "Row3", Score: 30, Notes: "note3" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    if (browserName === "chromium") {
      await page
        .context()
        .grantPermissions(["clipboard-read", "clipboard-write"], {
          origin:
            process.env.PUBLIC_WEB_FRONTEND_URL ?? "http://localhost:3000",
        });
    }
  });

  test("4.1.1 copy stores selected value in clipboard and paste immediately shows it in target cell", async ({
    browserName,
    page,
  }) => {
    test.skip(
      browserName !== "chromium",
      "Playwright cannot grant clipboard-read permission in Firefox.",
    );

    const grid = new GridPage(page, g.user);

    // Select Score cell of Row1 and copy
    await grid.selectFieldCell(0, 0); // Row1 / Score
    await grid.expectFieldSelected(0, 0);
    await grid.copyShortcut();
    await expect
      .poll(async () =>
        (await page.evaluate(() => navigator.clipboard.readText())).trim(),
      )
      .toBe("10");
    const copiedText = await page.evaluate(() =>
      navigator.clipboard.readText(),
    );

    // Select Score cell of Row3 and paste
    await grid.selectFieldCell(2, 0); // Row3 / Score
    await pasteText(page, copiedText);

    // Row3's Score should now be 10 (same as Row1); no loading spinner since
    // the cell update is optimistic.
    await grid.expectFieldText(2, 0, "10");
    await grid.expectNoRowsLoading();
  });

  test("4.1.2 pasting two lines on last row updates last row and immediately creates visible overflow row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    // Select the last row's primary field (Row3 / Name) and paste two rows
    // across Name and Score.
    await grid.selectPrimaryCell(2);
    await pasteText(page, "OverflowA\t99\nOverflowB\t88");

    // New rows should have been created for the overflow lines
    await grid.expectRowCount(4); // 3 original + 1 new (Row3 updated + 1 new)
    await grid.expectPrimaryText(2, "OverflowA");
    await grid.expectFieldText(2, 0, "99");
    await grid.expectPrimaryText(3, "OverflowB");
    await grid.expectFieldText(3, 0, "88");
  });

  test("4.2.1a filter-breaking paste shows warning, keeps selection, then removes row on deselect", async ({
    page,
  }) => {
    await resetRows(pasteFilter, [{ Name: "Keep", Score: 10 }]);
    const grid = new GridPage(page, pasteFilter.user);
    await grid.goTo(pasteFilter.database, pasteFilter.table);
    await grid.expectRowCount(1);

    // Paste a value that breaks the filter - "Keep" -> "Gone"
    await grid.selectPrimaryCell(0); // first Keep row / Name
    await pasteText(page, "Gone");

    // The pasted row should show a filter-mismatch warning while still selected
    await grid.expectPrimaryText(0, "Gone");
    await grid.expectPrimarySelected(0);
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");

    await grid.clickAway();

    await grid.expectPrimaryNotVisible("Gone");
    await grid.expectRowCount(0);
  });

  test("4.2.1b filter-breaking paste deselected before backend confirmation removes the row immediately", async ({
    page,
  }) => {
    await resetRows(pasteFilter, [{ Name: "Keep", Score: 10 }]);
    const grid = new GridPage(page, pasteFilter.user);
    await grid.goTo(pasteFilter.database, pasteFilter.table);
    await grid.expectRowCount(1);

    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${pasteFilter.table.id}/**`,
      { method: "PATCH" },
    );

    await grid.selectPrimaryCell(0);
    await pasteText(page, "Gone");
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Gone");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");

    await grid.clickAway();
    await grid.expectRowCount(0);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectRowCount(0);
  });

  test("4.3.1a sort-affecting paste shows Row has moved warning while selected then moves row on deselect", async ({
    page,
  }) => {
    await resetRows(pasteSort, [
      { Name: "Alice", Score: 10 },
      { Name: "Bob", Score: 20 },
    ]);
    const grid = new GridPage(page, pasteSort.user);
    await grid.goTo(pasteSort.database, pasteSort.table);
    await grid.expectRowCount(2);

    await grid.selectPrimaryCell(0); // Alice, sorts to position 1 after "Zara" replaces it
    await pasteText(page, "Zara"); // Zara > Bob alphabetically

    await grid.expectPrimaryText(0, "Zara");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await grid.expectPrimaryText(1, "Bob");

    await grid.clickAway();
    await grid.expectPrimaryText(0, "Bob");
    await grid.expectPrimaryText(1, "Zara");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("4.3.1b sort-affecting paste deselected before backend confirmation moves row immediately on deselect", async ({
    page,
  }) => {
    await resetRows(pasteSort, [
      { Name: "Alice", Score: 10 },
      { Name: "Bob", Score: 20 },
    ]);
    const grid = new GridPage(page, pasteSort.user);
    await grid.goTo(pasteSort.database, pasteSort.table);
    await grid.expectRowCount(2);

    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${pasteSort.table.id}/**`,
      { method: "PATCH" },
    );

    await grid.selectPrimaryCell(0); // Alice
    await pasteText(page, "Zara");
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Zara");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");

    await grid.clickAway();
    // Warning was visible so row moves to sorted position immediately
    await grid.expectPrimaryText(0, "Bob");
    await grid.expectPrimaryText(1, "Zara");
    await grid.expectRowNoWarning(0);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectPrimaryText(0, "Bob");
    await grid.expectPrimaryText(1, "Zara");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("4.4.1 Delete clears every value in the selected cell range", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0);
    await grid.fieldCellAt(1, 1).click({ modifiers: ["Shift"] });
    await grid.expectMultiSelectedCellCount(4);

    await page.keyboard.press("Delete");

    await grid.expectFieldEmpty(0, 0);
    await grid.expectFieldEmpty(0, 1);
    await grid.expectFieldEmpty(1, 0);
    await grid.expectFieldEmpty(1, 1);
    await grid.expectPrimaryText(0, "Row1");
    await grid.expectFieldText(2, 0, "30");
  });
});

// -----------------------------------------------------------------------------
// section 10.1  Keyboard navigation
// -----------------------------------------------------------------------------

test.describe("10.1 Keyboard navigation", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "KeyboardDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Row1", Score: 10, Notes: "n1" },
        { Name: "Row2", Score: 20, Notes: "n2" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Row1", Score: 10, Notes: "n1" },
      { Name: "Row2", Score: 20, Notes: "n2" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("10.1.1 Tab moves selection to next cell, typing opens editor there, and Enter saves visible value", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0); // Row1 / Score cell
    await grid.expectFieldSelected(0, 0);
    await page.keyboard.press("Tab");

    await grid.expectFieldSelected(0, 1);
    await page.keyboard.type("tabbed");
    await expect(grid.activeEditor()).toHaveValue("tabbed", { timeout: 5_000 });
    await grid.confirmWithEnter();
    await grid.expectFieldText(0, 1, "tabbed");
  });

  test("10.1.2 pressing Enter on a selected cell shows the editor in that cell", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.startEditingField(0, 0); // Row1 / Score
  });

  test("10.1.3 Enter while editing saves visible value, moves focus down, and allows editing next row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.startEditingField(0, 1); // Row1 / Notes
    await grid.type("Row1Updated");
    await grid.confirmWithEnter();

    await grid.expectFieldText(0, 1, "Row1Updated");

    await page.keyboard.type("Row2Updated");
    await expect(grid.activeEditor()).toHaveValue("Row2Updated", {
      timeout: 5_000,
    });
    await grid.confirmWithEnter();
    await grid.expectFieldText(1, 1, "Row2Updated");
  });

  test("10.1.4 Escape while editing discards typed draft and keeps original row visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.startEditingField(0, 1); // Row1 / Notes
    await grid.type("ShouldNotSave");
    await grid.cancelEdit();

    await expect(grid.activeEditor()).toHaveCount(0);
    await grid.expectFieldText(0, 1, "n1");
  });

  test("10.1.5 arrow key moves selection to adjacent row without showing an editor", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0); // Row1 / Score
    await grid.expectFieldSelected(0, 0);
    await page.keyboard.press("ArrowDown");

    // Row2's first cell should now be active and ready to edit - no editor opened
    // until the user starts typing.
    await expect(grid.activeEditor()).toHaveCount(0);
    await grid.expectFieldSelected(1, 0);
  });

  test("10.1.6 typing while a cell is selected shows editor containing the typed characters", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 1); // Row1 / Notes cell (fieldIndex 1)
    await grid.expectFieldSelected(0, 1);
    await page.keyboard.type("42");

    const editor = grid.activeEditor();
    await expect(editor).toBeVisible({ timeout: 5_000 });
    await expect(editor).toHaveValue("42");
  });
});

// -----------------------------------------------------------------------------
// section 11.1  Row hover actions
// -----------------------------------------------------------------------------

test.describe("11.1 Row hover actions", () => {
  test.describe.configure({ mode: "serial" });
  let gUnsorted: Setup;
  let gSorted: Setup;

  test.beforeAll(async () => {
    [gUnsorted, gSorted] = await Promise.all([
      setupGrid({
        dbName: "HoverDb",
        fields: [{ name: "Score", type: "number" }],
        rows: [
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 20 },
        ],
      }),
      setupGrid({
        dbName: "HoverSortedDb",
        fields: [{ name: "Score", type: "number" }],
        rows: [{ Name: "Alice", Score: 10 }],
        sorts: [{ fieldName: "Name", order: "ASC" }],
      }),
    ]);
  });

  test("11.1.1 hovering and unhovering a row toggles the checkbox and row count", async ({
    page,
  }) => {
    const grid = new GridPage(page, gUnsorted.user);
    await grid.goTo(gUnsorted.database, gUnsorted.table);

    await grid.expectRowCountVisible(0);
    await grid.expectRowCheckboxHidden(0);

    await grid.hoverRow(0);

    await grid.expectRowCheckboxVisible(0);
    await grid.expectRowCountHidden(0);

    await grid.unhoverRow();

    await grid.expectRowCountVisible(0);
    await grid.expectRowCheckboxHidden(0);
  });

  test("11.1.2 drag handle is present in an unsorted view and absent when a sort is active", async ({
    page,
  }) => {
    const grid = new GridPage(page, gUnsorted.user);
    await grid.goTo(gUnsorted.database, gUnsorted.table);
    await grid.expectRowDragHandlePresent(0);

    const sortedGrid = new GridPage(page, gSorted.user);
    await sortedGrid.goTo(gSorted.database, gSorted.table);
    await sortedGrid.expectRowDragHandleAbsent(0);
  });
});

// -----------------------------------------------------------------------------
// section 11.2 / 13.1  Row context menu and row modal
// -----------------------------------------------------------------------------

test.describe("11.2 Row context menu actions", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "ContextMenuDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice", Score: 10 },
        { Name: "Bob", Score: 20 },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Score: 10 },
      { Name: "Bob", Score: 20 },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("11.2.1 context-menu insert below creates an empty row below the selected row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.rightClickRow(0);
    await grid.clickContextItem("Insert row below");

    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
    await grid.expectPrimaryText(2, "Bob");
  });

  test("11.2.2 context-menu duplicate creates a copied row directly below the selected row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.rightClickRow(0);
    await grid.clickContextItem("Duplicate row");

    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectFieldText(1, 0, "10");
    await grid.expectPrimaryText(2, "Bob");
  });

  test("13.1.1 context-menu enlarge opens and closes the row edit modal", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.openRowModalFromContext(0);
    await grid.expectRowModalVisibleFor("Alice");
    await grid.closeRowModal();
  });
});

// -----------------------------------------------------------------------------
// section 12.1  Checkbox row selection
// -----------------------------------------------------------------------------

test.describe("12.1 Checkbox row selection", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;
  let groupBy: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CheckboxSelectionDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "note A" },
        { Name: "Bob", Score: 20, Notes: "note B" },
      ],
    });
    groupBy = await setupGrid({
      dbName: "CheckboxSelectionGroupByDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "note A" },
        { Name: "Bob", Score: 20, Notes: "note B" },
      ],
      groupBys: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("12.1.1 selecting a row checkbox clears an active multi-cell selection", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.selectFieldCell(0, 0);
    await grid.fieldCellAt(1, 1).click({ modifiers: ["Shift"] });
    await grid.expectMultiSelectedCellCount(4);

    await grid.hoverRow(0);
    await grid.checkboxAt(0).click();

    await grid.expectRowCheckboxChecked(0);
    await grid.expectMultiSelectedCellCount(0);
  });

  test("12.1.2 grouped row checkbox selection clears an active multi-cell selection", async ({
    page,
  }) => {
    const grid = new GridPage(page, groupBy.user);
    await grid.goTo(groupBy.database, groupBy.table);
    await grid.expectGroupByBanner("Alice", 1, true);
    await grid.expandAllGroupsFromContext();
    await grid.expectGroupByBanner("Alice", 1);

    await grid.selectFieldCell(0, 0);
    await grid.fieldCellAt(1, 1).click({ modifiers: ["Shift"] });
    await grid.expectMultiSelectedCellCount(4);

    await grid.hoverRow(0);
    await grid.checkboxAt(0).click();

    await grid.expectRowCheckboxChecked(0);
    await grid.expectMultiSelectedCellCount(0);
  });
});
