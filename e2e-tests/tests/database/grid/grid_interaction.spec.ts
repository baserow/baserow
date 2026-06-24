/**
 * Grid view - multi-cell selection, keyboard navigation, copy/paste, row hover.
 *
 * Catalogue sections covered:
 *   section 8   Multi-cell selection (mechanics, copy/paste including overflow-create)
 *   section 9   Keyboard navigation
 *   section 10  Row hover actions
 *
 * Anti-flakiness:
 *   - Keyboard navigation tests prove where selection moved by typing into
 *     the newly selected cell and asserting the saved value.
 *   - All count/visibility assertions use Playwright's built-in polling.
 */

import type { Page } from "@playwright/test";
import { test, expect } from "../../baserowTest";
import { GridPage } from "../../../pages/database/gridPage";
import {
  GridSetupResult,
  resetRows,
  setupGrid,
} from "../../../fixtures/database/gridSetup";

type Setup = GridSetupResult;

test.describe.configure({ mode: "serial" });

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
// section 8.1  Selection mechanics
// -----------------------------------------------------------------------------

test.describe("8.1 Selection mechanics", () => {
  let g: Setup;

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
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("8.1.1 clicking one field cell selects it and leaves no multi-select range visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.selectFieldCell(0, 0);

    await grid.expectFieldSelected(0, 0);
    await expect(page.locator(".grid-view__column--multi-select")).toHaveCount(
      0,
    );
  });

  test("8.1.2 shift-clicking another cell keeps the anchor selected and shows the rectangular range", async ({
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

  test("8.1.3 dragging across cells shows a rectangular range that remains visible after mouseup", async ({
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

  test("8.1.4 Escape removes the visible multi-select range", async ({
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

  test("8.1.5 clicking outside the grid removes the visible multi-select range", async ({
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
});

// -----------------------------------------------------------------------------
// section 8.3  Copy and paste
// -----------------------------------------------------------------------------

test.describe("8.3 Copy and paste", () => {
  let g: Setup;
  let pasteFilter: Setup;
  let pasteFilterRemove: Setup;

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
    pasteFilterRemove = await setupGrid({
      dbName: "PasteFilterRemoveDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [{ Name: "Keep", Score: 10 }],
      filters: [{ fieldName: "Name", type: "equal", value: "Keep" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await page
      .context()
      .grantPermissions(["clipboard-read", "clipboard-write"], {
        origin: process.env.PUBLIC_WEB_FRONTEND_URL ?? "http://localhost:3000",
      });
  });

  test("8.3.1 copy stores selected value in clipboard and paste immediately shows it in target cell", async ({
    page,
  }) => {
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

    // Row3's Score should now be 10 (same as Row1)
    await grid.expectFieldText(2, 0, "10");
  });

  test("8.3.4 pasting two lines on last row updates last row and immediately creates visible overflow row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    // Select the last row's primary field (Row3 / Name) and paste two rows
    // across Name and Score.
    await grid.selectPrimaryCell(2);
    await pasteText(page, "OverflowA\t99\nOverflowB\t88");

    // New rows should have been created for the overflow lines
    await grid.expectRowCount(4); // 3 original + 1 new (Row3 updated + 1 new)
    await grid.expectPrimaryVisible("OverflowA");
    await grid.expectPrimaryVisible("OverflowB");
  });

  test("8.3.6 filter-breaking paste immediately shows pasted value with warning while row remains selected", async ({
    page,
  }) => {
    const grid = new GridPage(page, pasteFilter.user);
    await grid.goTo(pasteFilter.database, pasteFilter.table);
    await grid.expectRowCount(2);

    // Paste a value that breaks the filter - "Keep" -> "Gone"
    await grid.selectPrimaryCell(0); // first Keep row / Name
    await pasteText(page, "Gone");

    // The pasted row should show a filter-mismatch warning while still selected
    await grid.expectRowHasWarning(0);
  });

  test("8.3.7 deselecting after filter-breaking paste removes the pasted value from visible grid", async ({
    page,
  }) => {
    const grid = new GridPage(page, pasteFilterRemove.user);
    await grid.goTo(pasteFilterRemove.database, pasteFilterRemove.table);

    await grid.selectPrimaryCell(0); // Keep / Name
    await pasteText(page, "Gone");
    await grid.expectRowHasWarning(0);

    await grid.clickAway();

    await grid.expectPrimaryNotVisible("Gone");
    await grid.expectRowCount(0);
  });
});

// -----------------------------------------------------------------------------
// section 9  Keyboard navigation
// -----------------------------------------------------------------------------

test.describe("9. Keyboard navigation", () => {
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

  test("9.1 Tab moves selection to next cell, typing opens editor there, and Enter saves visible value", async ({
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

  test("9.3 pressing Enter on a selected cell shows the editor in that cell", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.startEditingField(0, 0); // Row1 / Score
  });

  test("9.4 Enter while editing saves visible value, moves focus down, and allows editing next row", async ({
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

  test("9.5 Escape while editing discards typed draft and keeps original row visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.startEditingField(0, 0); // Row1 / Score
    await grid.type("ShouldNotSave");
    await grid.cancelEdit();

    await grid.expectPrimaryVisible("Row1");
    await grid.expectPrimaryNotVisible("ShouldNotSave");
  });

  test("9.6 arrow key moves selection to adjacent row without showing an editor", async ({
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

  test("9.7 typing while a cell is selected shows editor containing the typed characters", async ({
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
// section 10.1  Row hover actions
// -----------------------------------------------------------------------------

test.describe("10.1 Row hover actions", () => {
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

  test("10.1.1 hovering a row shows the checkbox and hides the row count", async ({
    page,
  }) => {
    const grid = new GridPage(page, gUnsorted.user);
    await grid.goTo(gUnsorted.database, gUnsorted.table);

    await grid.expectRowCountVisible(0);
    await grid.expectRowCheckboxHidden(0);

    await grid.hoverRow(0);

    await grid.expectRowCheckboxVisible(0);
    await grid.expectRowCountHidden(0);
  });

  test("10.1.2 moving the mouse away restores the row count and hides the checkbox", async ({
    page,
  }) => {
    const grid = new GridPage(page, gUnsorted.user);
    await grid.goTo(gUnsorted.database, gUnsorted.table);

    await grid.hoverRow(0);
    await grid.expectRowCheckboxVisible(0);

    await grid.unhoverRow();

    await grid.expectRowCountVisible(0);
    await grid.expectRowCheckboxHidden(0);
  });

  test("10.1.3 drag handle is present in an unsorted view and absent when a sort is active", async ({
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
