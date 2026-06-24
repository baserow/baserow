/**
 * Grid view - row CRUD and mismatch warning tests.
 *
 * Catalogue sections: section 1 Row creation, section 2 Row update, section 3 Row deletion.
 *
 * ## Data isolation
 * Each describe block creates an isolated database in `beforeAll` (fields,
 * view config) and resets rows in `beforeEach` (row content). Tests within
 * each describe run serially so `resetRows` always fires before each test.
 *
 * ## Anti-flakiness
 * - All assertions use Playwright polling — no arbitrary timeouts.
 * - Network failures delivered via `failNextRequest` resolve only after the
 *   request has been intercepted, removing all timing races.
 * - Warning tests use Tab (not Enter) so the row stays selected long enough
 *   to assert the warning before deselect triggers removal.
 */

import { test } from "../../baserowTest";
import { GridPage } from "../../../pages/database/gridPage";
import {
  GridSetupResult,
  resetRows,
  setupGrid,
} from "../../../fixtures/database/gridSetup";
import {
  failNextRequest,
  pauseNextRequestWithSignal,
} from "../../../fixtures/network";

type Setup = GridSetupResult;

async function waitForInitialRows(
  grid: GridPage,
  count: number,
): Promise<void> {
  await grid.expectRowCount(count);
}

async function addRowAndWaitForCreatedRow(
  grid: GridPage,
  expectedCount: number,
): Promise<void> {
  await grid.addRow();
  await grid.expectRowCount(expectedCount);
  await grid.expectNoRowsLoading();
}

async function startEditingPrimary(
  grid: GridPage,
  rowIndex: number,
): Promise<void> {
  await grid.startEditingPrimary(rowIndex);
}

async function deleteRowThroughContextMenu(
  grid: GridPage,
  rowIndex: number,
): Promise<void> {
  await grid.rightClickRow(rowIndex);
  await grid.clickContextItem("Delete row");
}

// -----------------------------------------------------------------------------
// section 1.1  Basic add row
// -----------------------------------------------------------------------------

test.describe("1.1 Basic add row", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudBasicDb",
      fields: [{ name: "Score", type: "number" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice", Score: 10 }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await waitForInitialRows(grid, 1);
  });

  test("1.1.1 paused create shows the empty optimistic row with row loading spinner, then clears loading in place", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );
    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
    await grid.expectFieldEmpty(1, 0);
    await grid.expectRowLoading(1);
    pausedCreate.release();
    await grid.expectRowCount(2);
    await grid.expectRowNotLoading(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
  });

  test("1.1.3 failed create is rolled back and the optimistic row disappears", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );
    await grid.addRow();
    await pausedCreate.intercepted;
    // Optimistic row is visible with loading spinner while the POST is in-flight.
    await grid.expectRowCount(2);
    await grid.expectRowLoading(1);
    pausedCreate.fail();
    await grid.expectErrorToast();
    // Poll until the optimistic row is gone after rollback.
    // If a second POST fires and succeeds (double-dispatch), count stays at 2
    // and this assertion times out — making the bug immediately visible.
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
  });

  test("1.1.2 adding a row selects the new primary cell", async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await addRowAndWaitForCreatedRow(grid, 2);
    await grid.expectPrimarySelected(1);
  });
});

// -----------------------------------------------------------------------------
// section 1.3  Create with active sort - mismatch warning + move
// -----------------------------------------------------------------------------

test.describe("1.3 Create with active sort", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudSortDb",
      fields: [{ name: "Score", type: "number" }],
      sorts: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Score: 10 },
      { Name: "Bob", Score: 20 },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await waitForInitialRows(grid, 2);
  });

  test("1.3.1a paused simple-sorted add kept selected immediately shows Row has moved until deselect", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryEmpty(2);
    await grid.expectRowLoading(2);
    await grid.expectRowHasWarning(2);
    await grid.expectRowWarningText(2, "Row has moved");

    pausedCreate.release();
    await grid.expectRowNotLoading(2);
    await grid.expectRowHasWarning(2);
    await grid.expectRowWarningText(2, "Row has moved");

    await grid.clickAway();
    await grid.expectRowCount(3);
    await grid.expectPrimaryEmpty(0);
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectPrimaryText(2, "Bob");
    await grid.expectRowNoWarning(0);
  });

  test("1.3.1b paused simple-sorted add deselected before confirmation moves immediately and finalizes without warning", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryEmpty(2);
    await grid.expectRowLoading(2);
    await grid.expectRowHasWarning(2);
    await grid.expectRowWarningText(2, "Row has moved");

    await grid.clickAway();
    await grid.expectPrimaryEmpty(0);
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectPrimaryText(2, "Bob");
    await grid.expectRowLoading(0);
    await grid.expectRowNoWarning(0);

    pausedCreate.release();
    await grid.expectRowCount(3);
    await grid.expectNoRowsLoading();
    await grid.expectPrimaryEmpty(0);
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectPrimaryText(2, "Bob");
    await grid.expectRowNoWarning(0);
  });

  test("1.3.1c failed sort-affected create rolls back the optimistic row and restores row order", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );
    await grid.addRow();
    await pausedCreate.intercepted;
    // Optimistic row is appended at the bottom with loading spinner and immediate warning.
    await grid.expectRowCount(3);
    await grid.expectRowLoading(2);
    await grid.expectRowHasWarning(2);
    await grid.expectRowWarningText(2, "Row has moved");
    pausedCreate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });
});

// -----------------------------------------------------------------------------
// section 1.3.2  Create with active formula-field sort — deferred move
// -----------------------------------------------------------------------------

test.describe("1.3.2 Create with active formula-field sort (deferred)", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFormulaCreateSortDb",
      fields: [
        {
          name: "NameLength",
          type: "formula",
          settings: { formula: "length(field('Name'))" },
        },
      ],
      sorts: [{ fieldName: "NameLength", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice" }]); // length 5, sorts after an empty row
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("1.3.2a paused formula-sorted create shows no move warning while pending then shows warning after backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowLoading(1);
    // No move warning while pending — formula sort cannot be evaluated locally
    await grid.expectRowNoWarning(1);

    pausedCreate.release();
    await grid.expectRowNotLoading(1);
    // Warning appears only after the backend responds with the formula result
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row has moved");
    await grid.expectRowCount(2);

    await grid.clickAway();
    // Row moves to its sorted position (length 0 < length 5)
    await grid.expectPrimaryEmpty(0);
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("1.3.2b deselecting before the create request completes keeps the row in place then moves it after the backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectRowNoWarning(1);

    await grid.clickAway();
    // Row stays at the bottom because the frontend has not yet received the
    // backend-computed sort value
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowLoading(1);

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    // Row moves to its sorted position after the backend responds
    await grid.expectPrimaryEmpty(0);
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("1.3.2c failed formula-sort-affected create rolls back the optimistic row and restores row order", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );
    await grid.addRow();
    await pausedCreate.intercepted;
    // Optimistic row visible with spinner; no move warning because the frontend
    // cannot evaluate the formula sort locally.
    await grid.expectRowCount(2);
    await grid.expectRowLoading(1);
    await grid.expectRowNoWarning(1);
    pausedCreate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
  });
});

// -----------------------------------------------------------------------------
// section 1.2  Create with active filter - mismatch warning + removal
// -----------------------------------------------------------------------------

test.describe("1.2 Create with active filter", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFilterDb",
      fields: [{ name: "Score", type: "number" }],
      filters: [{ fieldName: "Name", type: "equal", value: "Alice" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice", Score: 10 }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("1.2.1a paused simple-filtered add kept selected immediately shows filter warning until deselect", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowLoading(1);
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row does not match filters");

    pausedCreate.release();
    await grid.expectRowCount(2);
    await grid.expectRowNotLoading(1);
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row does not match filters");

    await grid.clickAway();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
  });

  test("1.2.1b paused simple-filtered add deselected before confirmation is removed immediately", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowLoading(1);
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row does not match filters");

    await grid.clickAway();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
  });

  test("1.2.1d failed filter-affected create rolls back the optimistic row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );
    await grid.addRow();
    await pausedCreate.intercepted;
    // Optimistic row visible with loading spinner and immediate filter warning.
    await grid.expectRowCount(2);
    await grid.expectRowLoading(1);
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row does not match filters");
    pausedCreate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
  });
});

// -----------------------------------------------------------------------------
// section 1.2.1c  Newly created row corrected to match active filter
// -----------------------------------------------------------------------------

test.describe("1.2.1c Newly created row corrected to match active filter", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFilter1c3Db",
      fields: [{ name: "Score", type: "number" }],
      filters: [{ fieldName: "Name", type: "not_empty", value: "" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice", Score: 10 }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("1.2.1c typing a value that matches the active filter into the new row clears the warning and keeps the row visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.addRow();
    await grid.expectRowCount(2);
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row does not match filters");

    await startEditingPrimary(grid, 1);
    await grid.type("Bob");
    await grid.confirmWithTab();
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectRowNoWarning(1);
    await grid.expectRowCount(2);

    await grid.clickAway();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectRowNoWarning(1);
  });
});

// -----------------------------------------------------------------------------
// section 1.2.2  Create with active formula-field filter — deferred warning
// -----------------------------------------------------------------------------

test.describe("1.2.2 Create with active formula-field filter (deferred)", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFormulaCreateFilterDb",
      fields: [
        {
          name: "NameLength",
          type: "formula",
          settings: { formula: "length(field('Name'))" },
        },
      ],
      filters: [{ fieldName: "NameLength", type: "higher_than", value: "3" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice" }]); // length 5, matches > 3
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("1.2.2a paused formula-filtered create shows no warning while pending then shows warning after backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowLoading(1);
    // No warning while pending — formula filter cannot be evaluated locally
    await grid.expectRowNoWarning(1);

    pausedCreate.release();
    await grid.expectRowNotLoading(1);
    // Warning appears only after the backend responds with the formula result
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row does not match filters");
    await grid.expectRowCount(2);

    await grid.clickAway();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
  });

  test("1.2.2b deselecting before the create request completes keeps the row visible until the backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(2);
    await grid.expectRowLoading(1);
    await grid.expectRowNoWarning(1);

    await grid.clickAway();
    // Row stays visible because the frontend has not yet received the formula result
    await grid.expectRowCount(2);
    await grid.expectPrimaryEmpty(1);

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    // Row is removed after the backend responds with the formula result
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
  });

  test("1.2.2c failed formula-filter-affected create rolls back the optimistic row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );
    await grid.addRow();
    await pausedCreate.intercepted;
    // Optimistic row visible with loading spinner; no warning because the
    // frontend cannot evaluate the formula filter locally.
    await grid.expectRowCount(2);
    await grid.expectRowLoading(1);
    await grid.expectRowNoWarning(1);
    pausedCreate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
  });
});

// -----------------------------------------------------------------------------
// section 1.4  Task queue — update during pending create
// -----------------------------------------------------------------------------

test.describe("1.4 Task queue — update during pending create", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "TaskQueueDb",
      fields: [{ name: "Score", type: "number" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice", Score: 10 }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("1.4.1 typing in a field of a pending row shows the value immediately and saves after create completes", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowLoading(1);

    await grid.startEditingField(1, 0);
    await grid.type("99");
    await grid.clickAway();
    await grid.expectFieldText(1, 0, "99");

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    await grid.expectFieldText(1, 0, "99");
  });

  test("1.4.2 PATCH is not sent to the network until after the create request completes", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "POST" },
    );

    await grid.addRow();
    await pausedCreate.intercepted;

    await grid.startEditingField(1, 0);
    await grid.type("42");
    await grid.clickAway();

    // Register the PATCH interceptor now, after the POST is already held.
    // If the queue did not exist the PATCH would have fired before this point
    // and the intercepted promise below would never resolve.
    const pausedPatch = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    pausedCreate.release();
    await pausedPatch.intercepted;

    pausedPatch.release();
    await grid.expectNoRowsLoading();
    await grid.expectFieldText(1, 0, "42");
  });
});

// -----------------------------------------------------------------------------
// section 2.1  Simple field edit
// -----------------------------------------------------------------------------

test.describe("2.1 Simple field edit", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "EditBasicDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Email", type: "email" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Score: 10, Email: "alice@example.com" },
      { Name: "Bob", Score: 20, Email: "bob@example.com" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await waitForInitialRows(grid, 2);
  });

  test("2.1.1 Enter save makes the typed primary value visible and removes the original value from the grid", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await startEditingPrimary(grid, 0);
    await grid.type("Alicia");
    await grid.confirmWithEnter();
    await grid.expectPrimaryText(0, "Alicia");
    await grid.expectPrimaryNotVisible("Alice");
    await grid.expectRowNotLoading(0);
  });

  test("2.1.4 Escape while editing discards the typed value and keeps the original value visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await startEditingPrimary(grid, 1);
    await grid.type("Changed");
    await grid.cancelEdit();
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryNotVisible("Changed");
    await grid.expectRowNotLoading(1);
  });

  test("2.1.2 blur save makes the typed value visible after clicking outside the cell", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await startEditingPrimary(grid, 0);
    await grid.type("Alicia");
    await grid.clickAway();
    await grid.expectPrimaryVisible("Alicia");
    await grid.expectNoRowsLoading();
  });

  test("2.1.3 failed PATCH rolls back the typed value and shows an error toast", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const failed = failNextRequest(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );
    await startEditingPrimary(grid, 0);
    await grid.type("WillFail");
    await grid.confirmWithEnter();
    await failed;
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryNotVisible("WillFail");
  });

  test("2.1.5 invalid email edit shows validation error and keeps editor open", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.startEditingField(0, 1);
    await grid.type("not-an-email");
    await grid.expectActiveCellError("Invalid email");
    await grid.confirmWithEnter();
    await grid.expectActiveCellError("Invalid email");
    await grid.expectActiveEditorValue("not-an-email");
  });
});

// -----------------------------------------------------------------------------
// section 2.2  Edit with active filter - mismatch warning + removal
// -----------------------------------------------------------------------------

test.describe("2.2 Edit with active filter on the edited field", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "EditFilterDb",
      fields: [{ name: "Score", type: "number" }],
      filters: [{ fieldName: "Name", type: "equal", value: "Alice" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice", Score: 10 }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("2.2.1a paused non-matching filtered edit shows warning while selected until confirmation", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Charlie");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Charlie");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");
    await grid.expectRowNotLoading(0);

    pausedUpdate.release();
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");
    await grid.expectRowCount(1);
  });

  test("2.2.1b paused non-matching filtered edit deselected before confirmation is removed immediately", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Charlie");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Charlie");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");

    await grid.clickAway();
    await grid.expectRowCount(0);
    await grid.expectPrimaryNotVisible("Charlie");

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectRowCount(0);
    await grid.expectPrimaryNotVisible("Charlie");
  });

  test("2.2.4 Escape during filter-mismatched edit restores matching value, clears warning, and keeps row visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await startEditingPrimary(grid, 0);
    await grid.type("Charlie");
    await grid.cancelEdit();
    await grid.expectPrimaryVisible("Alice");
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(1);
  });

  test("2.2.3 saving the same matching value keeps row visible and produces no warning", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await startEditingPrimary(grid, 0);
    await grid.type("Alice");
    await grid.confirmWithEnter();
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(1);
    await grid.expectNoRowsLoading();
  });

  test("2.2.2 failed filter-affecting PATCH rolls back the typed value and shows an error toast", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const failed = failNextRequest(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );
    await startEditingPrimary(grid, 0);
    await grid.type("Charlie");
    await grid.confirmWithEnter();
    await failed;
    await grid.expectErrorToast();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryNotVisible("Charlie");
    await grid.expectRowNoWarning(0);
  });
});

// -----------------------------------------------------------------------------
// section 2.2  Edit with formula-field filter (deferred) — deferred warning
// -----------------------------------------------------------------------------

test.describe("2.2.5 Edit with formula-field filter (deferred)", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFormulaEditFilterDb",
      fields: [
        {
          name: "NameLength",
          type: "formula",
          settings: { formula: "length(field('Name'))" },
        },
      ],
      filters: [{ fieldName: "NameLength", type: "higher_than", value: "3" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [{ Name: "Alice" }]); // length 5, matches > 3
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(1);
  });

  test("2.2.5a paused formula-filtered edit shows typed value immediately but no warning until backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Al"); // length 2, does not match > 3
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;

    // Typed value visible immediately (field edit is optimistic); no loading
    // spinner because the row update is optimistic.
    await grid.expectPrimaryText(0, "Al");
    await grid.expectRowNotLoading(0);
    // No warning while pending — formula filter cannot be evaluated locally
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(1);

    pausedUpdate.release();
    // Warning appears only after the backend responds with the formula result
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");
    await grid.expectRowCount(1);
  });

  test("2.2.5b deselecting after backend confirmation removes the formula-filtered row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Al");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectRowNoWarning(0);

    pausedUpdate.release();
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");

    await grid.clickAway();
    await grid.expectRowCount(0);
  });

  test("2.2.5c deselecting before backend confirmation keeps the row visible until the backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Al");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Al");
    await grid.expectRowNoWarning(0);

    await grid.clickAway();
    // Row stays visible because the frontend has not yet received the formula result
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Al");

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    // Row is removed after the backend responds with the formula result
    await grid.expectRowCount(0);
  });

  test("2.2.5d failed formula-filter-affecting PATCH restores the original row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );
    await startEditingPrimary(grid, 0);
    await grid.type("Al");
    await grid.confirmWithEnter();
    await pausedUpdate.intercepted;
    // Typed value visible immediately; no warning because the frontend cannot
    // evaluate the formula filter locally.
    await grid.expectPrimaryText(0, "Al");
    await grid.expectRowNoWarning(0);
    pausedUpdate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
  });
});

// -----------------------------------------------------------------------------
// section 2.3  Edit with active sort - mismatch warning + move
// -----------------------------------------------------------------------------

test.describe("2.3 Edit with active sort on the edited field", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "EditSortDb",
      fields: [{ name: "Score", type: "number" }],
      sorts: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Score: 10 },
      { Name: "Bob", Score: 20 },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await waitForInitialRows(grid, 2);
  });

  test("2.3.1a paused sorted edit kept selected shows Row has moved until confirmation", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Zara");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Zara");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await grid.expectRowNotLoading(0);

    pausedUpdate.release();
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
  });

  test("2.3.1b paused sorted edit deselected before confirmation moves immediately", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Zara");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(0, "Zara");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");

    await grid.clickAway();
    await grid.expectPrimaryText(0, "Bob");
    await grid.expectPrimaryText(1, "Zara");
    await grid.expectRowNoWarning(1);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectPrimaryText(0, "Bob");
    await grid.expectPrimaryText(1, "Zara");
    await grid.expectRowNoWarning(1);
  });

  test("2.3.2 failed sort-affecting PATCH restores the original row order", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const failed = failNextRequest(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );
    await startEditingPrimary(grid, 0);
    await grid.type("Zara");
    await grid.confirmWithEnter();
    // Optimistic state: typed value and sort warning visible before the PATCH resolves.
    await grid.expectPrimaryText(0, "Zara");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await failed;
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("2.3.3 Escape during sort-mismatched edit restores original value, clears warning, and leaves row in place", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await startEditingPrimary(grid, 0);
    await grid.type("Zara");
    await grid.cancelEdit();
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(2);
  });
});

// -----------------------------------------------------------------------------
// section 2.3  Edit with formula-field sort (deferred) — deferred move
// -----------------------------------------------------------------------------

test.describe("2.3.4 Edit with formula-field sort (deferred)", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFormulaSortDb",
      fields: [
        {
          name: "NameLength",
          type: "formula",
          settings: { formula: "length(field('Name'))" },
        },
      ],
      sorts: [{ fieldName: "NameLength", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Al" }, // length 2, sorts first
      { Name: "Alice" }, // length 5, sorts second
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(2);
  });

  test("2.3.4a paused formula-sorted edit shows typed value immediately but no move warning until backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0); // edit "Al"
    await grid.type("Alexander"); // length 9, should sort after "Alice" (5)
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;

    // Typed value visible immediately (field edit is optimistic); no loading
    // spinner because the row update is optimistic.
    await grid.expectPrimaryText(0, "Alexander");
    await grid.expectRowNotLoading(0);
    // No move warning while pending — formula sort cannot be evaluated locally
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(2);

    pausedUpdate.release();
    // Warning appears only after the backend responds with the formula result
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await grid.expectPrimaryText(0, "Alexander");
    await grid.expectRowCount(2);

    await grid.clickAway();
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Alexander");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("2.3.4b deselecting before backend confirmation keeps the row in place then moves it after the backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseNextRequestWithSignal(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );

    await startEditingPrimary(grid, 0);
    await grid.type("Alexander");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectRowNoWarning(0);

    await grid.clickAway();
    // Row stays in current position because the frontend has not yet received the
    // backend-computed sort value
    await grid.expectPrimaryText(0, "Alexander");
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectRowCount(2);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    // Row moves to its sorted position after backend responds
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Alexander");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });

  test("2.3.4c failed formula-sort-affecting PATCH restores the original row order", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const failed = failNextRequest(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "PATCH" },
    );
    await startEditingPrimary(grid, 0);
    await grid.type("Alexander");
    await grid.confirmWithEnter();
    // Optimistic state: typed value visible immediately; no warning because the
    // frontend cannot evaluate the formula sort locally.
    await grid.expectPrimaryText(0, "Alexander");
    await grid.expectRowNoWarning(0);
    await failed;
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Al");
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });
});

// -----------------------------------------------------------------------------
// section 3.1  Row deletion
// -----------------------------------------------------------------------------

test.describe("3.1 Row deletion", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "DeleteDb",
      fields: [{ name: "Score", type: "number" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Score: 10 },
      { Name: "Bob", Score: 20 },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await waitForInitialRows(grid, 2);
  });

  test("3.1.1 context-menu delete removes the row immediately and leaves the next row visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await deleteRowThroughContextMenu(grid, 0);
    await grid.expectRowCount(1);
    await grid.expectPrimaryNotVisible("Alice");
    await grid.expectPrimaryVisible("Bob");
  });

  test("3.1.2 failed delete request is intercepted and both rows remain visible after rollback/stability check", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const failed = failNextRequest(
      page,
      `**/api/database/rows/table/${g.table.id}/**`,
      { method: "DELETE" },
    );
    await deleteRowThroughContextMenu(grid, 1);
    await failed;
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryVisible("Alice");
    await grid.expectPrimaryVisible("Bob");
  });
});
