/**
 * Grid view - row CRUD and mismatch warning tests.
 *
 * Catalogue sections: section 1 Row creation, section 2 Row update, section 3 Row deletion.
 *
 *
 */

import type { Page, Request } from "@playwright/test";
import { test, expect } from "../../baserowTest";
import { GridPage } from "../../../pages/database/gridPage";
import type {
  GridSetupResult,
  FieldSpec,
  GroupBySpec,
} from "../../../fixtures/database/gridSetup";
import { resetRows, setupGrid } from "../../../fixtures/database/gridSetup";
import { failRows, pauseRows } from "../../../fixtures/network";

type Setup = GridSetupResult;

// Keep docs/testing/grid-view-test-plan.md in sync with these cases.

type RegularFieldViewMode = {
  name: string;
  dbSuffix: string;
  extraFields: FieldSpec[];
  groupBys?: GroupBySpec[];
  rows: (rows: Record<string, unknown>[]) => Record<string, unknown>[];
  waitForRows: (grid: GridPage, count: number) => Promise<void>;
};

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

function numberedRows(count: number): Record<string, unknown>[] {
  return Array.from({ length: count }, (_, index) => ({
    Name: `Row ${String(index + 1).padStart(3, "0")}`,
    Score: index + 1,
  }));
}

async function collectGridViewGetRequests(
  page: Page,
  viewId: number,
  action: () => Promise<void>,
): Promise<string[]> {
  const urls: string[] = [];
  const listener = (request: Request): void => {
    const url = new URL(request.url());
    if (
      request.method() === "GET" &&
      url.pathname.startsWith(`/api/database/views/grid/${viewId}/`)
    ) {
      urls.push(request.url());
    }
  };

  page.on("request", listener);
  try {
    await action();
    await page.waitForTimeout(300);
  } finally {
    page.off("request", listener);
  }
  return urls;
}

const REGULAR_FIELD_VIEW_MODES: RegularFieldViewMode[] = [
  {
    name: "flat",
    dbSuffix: "Flat",
    extraFields: [],
    rows: (rows) => rows,
    waitForRows: waitForInitialRows,
  },
  {
    name: "group-by",
    dbSuffix: "GroupBy",
    extraFields: [{ name: "Team", type: "text" }],
    groupBys: [{ fieldName: "Team", order: "ASC" }],
    rows: (rows) => rows.map((row) => ({ Team: "A", ...row })),
    waitForRows: async (grid, count) => {
      // Grouped views load expanded, so the banner is already expanded and the
      // rows are present without an explicit expand-all.
      await grid.expectGroupByBanner("A", count);
      await waitForInitialRows(grid, count);
    },
  },
];

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");
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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");
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
// section 7  Group-by
// -----------------------------------------------------------------------------

test.describe("7 Group-by", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "GroupByFeatureDb",
      fields: [
        { name: "Team", type: "text" },
        { name: "Score", type: "number" },
      ],
      groupBys: [{ fieldName: "Team", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Team: "A", Score: 10 },
      { Name: "Bob", Team: "A", Score: 20 },
      { Name: "Carol", Team: "B", Score: 30 },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectRowCount(3);
  });

  test("7.1.1 grouped views load expanded and the context menu can collapse/expand all groups", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    // Grouped views load expanded with all rows present.
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectRowCount(3);

    // Collapse all hides every group's rows.
    await grid.collapseAllGroupsFromContext();
    await grid.expectGroupByBanner("A", 2, true);
    await grid.expectGroupByBanner("B", 1, true);
    await grid.expectRowCount(0);

    // Expand all restores the rows. They were fetched on the initial expanded
    // load and kept in the store while collapsed, so no refetch is needed.
    await grid.expandAllGroupsFromContext();
    await waitForInitialRows(grid, 3);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectRowCount(3);
  });

  test("7.1.2 collapsing and expanding a group hides and restores its rows", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.toggleGroupBy("A");
    await grid.expectGroupByBanner("A", 2, true);
    await grid.expectRowCount(1);
    await grid.expectPrimaryText(0, "Carol");

    await grid.toggleGroupBy("A");
    await grid.expectGroupByBanner("A", 2);
    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryText(2, "Carol");
  });
});

// -----------------------------------------------------------------------------
// section 1.5  Create with active group-by
// -----------------------------------------------------------------------------

test.describe("1.5 Create with active group-by", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudGroupByDb",
      fields: [
        { name: "Team", type: "text" },
        { name: "Score", type: "number" },
      ],
      groupBys: [{ fieldName: "Team", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Team: "A", Score: 10 },
      { Name: "Bob", Team: "A", Score: 20 },
      { Name: "Carol", Team: "B", Score: 30 },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectRowCount(3);
  });

  test("1.5.1 adding a row from a group add-row line appends it at the bottom of that group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    const gridGetRequests = await collectGridViewGetRequests(
      page,
      g.view.id,
      async () => {
        await grid.addRow();
        await pausedCreate.intercepted;

        await grid.expectRowCount(4);
        await grid.expectPrimaryText(0, "Alice");
        await grid.expectPrimaryText(1, "Bob");
        await grid.expectPrimaryEmpty(2);
        await grid.expectFieldText(2, 0, "A");
        await grid.expectPrimaryText(3, "Carol");
        await grid.expectGroupByBanner("A", 3);
        await grid.expectGroupByBanner("B", 1);
        await grid.expectRowLoading(2);

        pausedCreate.release();

        await grid.expectRowNotLoading(2);
        await grid.expectPrimaryEmpty(2);
        await grid.expectFieldText(2, 0, "A");
        await grid.expectPrimarySelected(2);
      },
    );
    expect(gridGetRequests).toEqual([]);
  });

  test("1.5.1b add-in-group deselected after confirmation keeps the row in its group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(4);
    await grid.expectFieldText(2, 0, "A");
    await grid.expectGroupByBanner("A", 3);
    await grid.expectRowLoading(2);

    pausedCreate.release();
    await grid.expectRowNotLoading(2);

    await grid.clickAway();
    await grid.expectRowCount(4);
    await grid.expectGroupByBanner("A", 3);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectFieldText(2, 0, "A");
    await grid.expectRowNoWarning(2);
  });

  test("1.5.1c add-in-group deselected before confirmation keeps the row in its group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(4);
    await grid.expectFieldText(2, 0, "A");
    await grid.expectGroupByBanner("A", 3);
    await grid.expectRowLoading(2);

    await grid.clickAway();
    // The created row already sits in its own group, so deselecting before the
    // backend confirms leaves it in place with no "Row has moved" warning.
    await grid.expectRowCount(4);
    await grid.expectGroupByBanner("A", 3);
    await grid.expectRowLoading(2);
    await grid.expectRowNoWarning(2);

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    await grid.expectRowCount(4);
    await grid.expectGroupByBanner("A", 3);
    await grid.expectFieldText(2, 0, "A");
    await grid.expectRowNoWarning(2);
  });

  test("1.5.1d failed add-in-group rolls back the optimistic row and restores group counts", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(4);
    await grid.expectGroupByBanner("A", 3);
    await grid.expectRowLoading(2);

    pausedCreate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(3);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryText(2, "Carol");
  });
});

test.describe("1.5.3 Create with formula-field group-by (deferred)", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFormulaCreateGroupByDb",
      fields: [
        {
          name: "NameSize",
          type: "formula",
          settings: {
            formula: "if(length(field('Name')) > 3, 'Long', 'Short')",
          },
        },
      ],
      groupBys: [{ fieldName: "NameSize", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice" }, // length 5 -> "Long"
      { Name: "Al" }, // length 2 -> "Short"
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(2);
    // Groups sort ASC: "Long" (Alice, index 0), "Short" (Al, index 1).
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 1);
  });

  test("1.5.3a paused formula-grouped create shows no move warning while pending then moves to its group after backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(3);
    await grid.expectPrimaryEmpty(1);
    await grid.expectRowLoading(1);
    // No move warning while pending — the empty row's formula group cannot be
    // evaluated locally.
    await grid.expectRowNoWarning(1);

    pausedCreate.release();
    await grid.expectRowNotLoading(1);
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row has moved");

    await grid.clickAway();
    // The empty row (length 0 -> "Short") joins the Short group after the backend
    // computes the formula.
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 2);
    await grid.expectRowCount(3);
  });

  test("1.5.3b deselecting before the create request completes keeps the row in place then moves it after the backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(3);
    await grid.expectRowNoWarning(1);

    await grid.clickAway();
    // Row stays in place because the frontend has not received the formula group.
    await grid.expectRowLoading(1);
    await grid.expectRowCount(3);

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 2);
    await grid.expectRowCount(3);
  });

  test("1.5.3c failed formula-grouped create rolls back the optimistic row and restores group counts", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    await grid.expectRowCount(3);
    await grid.expectRowLoading(1);
    await grid.expectRowNoWarning(1);

    pausedCreate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 1);
  });
});

test.describe("2.2.6 Edit with active filter and group-by", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFilterGroupByDb",
      fields: [{ name: "Team", type: "text" }],
      filters: [{ fieldName: "Name", type: "contains", value: "Keep" }],
      groupBys: [{ fieldName: "Team", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Keep one", Team: "A" },
      { Name: "Keep two", Team: "A" },
      { Name: "Keep three", Team: "B" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(3);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
  });

  test("2.2.6a grouped filtered edit shows warning on the last group row and shrinks the group on deselect", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 1);
    await grid.type("Hidden");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(1, "Hidden");
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningVisible(1);
    await grid.expectRowWarningText(1, "Row does not match filters");

    pausedUpdate.release();
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningVisible(1);

    await grid.clickAway();
    await grid.expectRowCount(2);
    await grid.expectGroupByBanner("A", 1);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectPrimaryText(0, "Keep one");
    await grid.expectPrimaryText(1, "Keep three");
    await grid.expectPrimaryNotVisible("Hidden");
  });
});

test.describe("2.2.7 Edit single-select group-by", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudSingleSelectGroupByDb",
      fields: [
        {
          name: "Category",
          type: "single_select",
          options: ["Design", "Development"],
        },
      ],
      groupBys: [{ fieldName: "Category", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Rebranding website", Category: "Design" },
      { Name: "User portal", Category: "Development" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(2);
    await grid.expectGroupByBanner("Design", 1);
    await grid.expectGroupByBanner("Development", 1);
  });

  test("2.2.7a changing a selected row category warns, then moves it locally on deselect", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    const gridViewGets = await collectGridViewGetRequests(
      page,
      g.view.id,
      async () => {
        await grid.selectSingleSelectOption(0, 0, "Development");
        await pausedUpdate.intercepted;

        await grid.expectPrimaryText(0, "Rebranding website");
        await grid.expectSingleSelectFieldText(0, 0, "Development");
        await grid.expectRowHasWarning(0);
        await grid.expectRowWarningVisible(0);
        await grid.expectRowWarningText(0, "Row has moved");
        await grid.expectGroupByBanner("Design", 1);
        await grid.expectGroupByBanner("Development", 1);

        pausedUpdate.release();
        await grid.expectRowHasWarning(0);
        await grid.expectRowWarningText(0, "Row has moved");

        await grid.clickAway();
        await grid.expectNoGroupByBanner("Design");
        await grid.expectGroupByBanner("Development", 2);
        await grid.expectRowCount(2);
        await grid.expectPrimaryText(0, "Rebranding website");
        await grid.expectPrimaryText(1, "User portal");
        await grid.expectRowNoWarning(0);
      },
    );

    expect(gridViewGets).toEqual([]);
  });

  test("2.2.7b changing a grouped value deselected before confirmation moves the row immediately", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await grid.selectSingleSelectOption(0, 0, "Development");
    await pausedUpdate.intercepted;
    await grid.expectSingleSelectFieldText(0, 0, "Development");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await grid.expectGroupByBanner("Design", 1);
    await grid.expectGroupByBanner("Development", 1);

    await grid.clickAway();
    // The "Row has moved" warning was visible, so deselecting before the backend
    // confirms moves the row into its new group immediately.
    await grid.expectNoGroupByBanner("Design");
    await grid.expectGroupByBanner("Development", 2);
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Rebranding website");
    await grid.expectSingleSelectFieldText(0, 0, "Development");
    await grid.expectRowNoWarning(0);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectNoGroupByBanner("Design");
    await grid.expectGroupByBanner("Development", 2);
  });

  test("2.2.7c failed grouped-value PATCH rolls back to the original group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await grid.selectSingleSelectOption(0, 0, "Development");
    await pausedUpdate.intercepted;
    await grid.expectSingleSelectFieldText(0, 0, "Development");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");

    pausedUpdate.fail();
    await grid.expectErrorToast();
    // The optimistic group-by value is rolled back, the warning clears, and the
    // row stays in its original group.
    await grid.expectSingleSelectFieldText(0, 0, "Design");
    await grid.expectGroupByBanner("Design", 1);
    await grid.expectGroupByBanner("Development", 1);
    await grid.expectRowCount(2);
    await grid.expectRowNoWarning(0);
  });
});

test.describe("2.4 Edit a text group-by value", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "EditTextGroupByDb",
      // A trailing "Notes" column gives Tab a target after the group-by field so
      // the row stays selected (and its "Row has moved" warning visible) after the
      // edit commits, mirroring the keep-selected pattern in 2.2.6a.
      fields: [
        { name: "Team", type: "text" },
        { name: "Notes", type: "text" },
      ],
      groupBys: [{ fieldName: "Team", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Alice", Team: "A" },
      { Name: "Bob", Team: "A" },
      { Name: "Carol", Team: "B" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(3);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
  });

  test("2.4.1 changing a text group-by value deselected before confirmation moves the row immediately", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await grid.startEditingField(0, 0);
    await grid.type("B");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectFieldText(0, 0, "B");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);

    await grid.clickAway();
    await grid.expectGroupByBanner("A", 1);
    await grid.expectGroupByBanner("B", 2);
    await grid.expectRowCount(3);
    await grid.expectRowNoWarning(0);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectGroupByBanner("A", 1);
    await grid.expectGroupByBanner("B", 2);
  });

  test("2.4.2 failed text group-by-value PATCH rolls back to the original group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await grid.startEditingField(0, 0);
    await grid.type("B");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectFieldText(0, 0, "B");
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");

    pausedUpdate.fail();
    await grid.expectErrorToast();
    await grid.expectFieldText(0, 0, "A");
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectRowCount(3);
    await grid.expectRowNoWarning(0);
  });

  test("2.4.3 Escape during a text group-by-value edit restores it and leaves the row in its group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.startEditingField(0, 0);
    await grid.type("B");
    await grid.cancelEdit();
    await grid.expectFieldText(0, 0, "A");
    await grid.expectRowNoWarning(0);
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 1);
    await grid.expectRowCount(3);
  });
});

test.describe("2.4.4 Edit with formula-field group-by (deferred)", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudFormulaGroupByDb",
      fields: [
        {
          name: "NameSize",
          type: "formula",
          settings: {
            formula: "if(length(field('Name')) > 3, 'Long', 'Short')",
          },
        },
      ],
      groupBys: [{ fieldName: "NameSize", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, [
      { Name: "Al" }, // length 2 -> "Short"
      { Name: "Alice" }, // length 5 -> "Long"
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectRowCount(2);
    // Groups sort ASC: "Long" (Alice, index 0), "Short" (Al, index 1).
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 1);
  });

  test("2.4.4a paused formula-grouped edit shows typed value immediately but no move warning until backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 1); // edit "Al" (Short group)
    await grid.type("Alexander"); // length 9 -> "Long"
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;

    // Typed value is visible immediately, but the formula-derived group needs the
    // backend response, so the row remains loading in its original group.
    await grid.expectPrimaryText(1, "Alexander");
    await grid.expectRowLoading(1);
    await grid.expectRowNoWarning(1);
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 1);

    pausedUpdate.release();
    // The "Row has moved" warning appears only after the backend computes the
    // formula group.
    await grid.expectRowHasWarning(1);
    await grid.expectRowWarningText(1, "Row has moved");
    await grid.expectRowNotLoading(1);

    await grid.clickAway();
    await grid.expectGroupByBanner("Long", 2);
    await grid.expectNoGroupByBanner("Short");
    await grid.expectRowCount(2);
  });

  test("2.4.4b deselecting before backend confirmation keeps the row in its group then moves it after the backend responds", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 1);
    await grid.type("Alexander");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectRowNoWarning(1);

    await grid.clickAway();
    // Row stays in "Short" because the frontend has not received the formula result.
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 1);
    await grid.expectPrimaryText(1, "Alexander");

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    // Row moves to "Long" after the backend responds.
    await grid.expectGroupByBanner("Long", 2);
    await grid.expectNoGroupByBanner("Short");
  });

  test("2.4.4c failed formula-group-affecting PATCH rolls back to the original group", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 1);
    await grid.type("Alexander");
    // Enter commits and clears the selection so the rollback can revert the
    // displayed value (a still-selected cell keeps showing the user's draft).
    await grid.confirmWithEnter();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryText(1, "Alexander");
    await grid.expectRowLoading(1);
    await grid.expectRowNoWarning(1);

    pausedUpdate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(1, "Al");
    await grid.expectGroupByBanner("Long", 1);
    await grid.expectGroupByBanner("Short", 1);
    await grid.expectRowNoWarning(1);
  });
});

// -----------------------------------------------------------------------------
// section 1.3  Create with active sort - mismatch warning + move
// -----------------------------------------------------------------------------

for (const viewMode of REGULAR_FIELD_VIEW_MODES) {
  test.describe(`1.3 Create with active sort (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `CrudSort${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        sorts: [{ fieldName: "Name", order: "ASC" }],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      await resetRows(
        g,
        viewMode.rows([
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 20 },
        ]),
      );
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 2);
    });

    test("1.3.1a paused simple-sorted add kept selected immediately shows Row has moved until deselect", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);
      const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
      const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
      const pausedCreate = await pauseRows(page, g.table.id, "POST");
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
}

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");
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
// section 1.3.3  Create with active sort where destination is outside buffer
// -----------------------------------------------------------------------------

test.describe("1.3.3 Create with active sort outside the current buffer", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudSortCreateOutsideBufferDb",
      fields: [{ name: "Score", type: "number" }],
      sorts: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    // Use a dataset large enough that the buffer can never hold the whole table
    // (bufferRequestSize * 3 = 120 rows max). Scrolling to the bottom then leaves
    // the top of the table genuinely unloaded, so a row that sorts to the top has
    // its destination outside the loaded window — the real virtualization case.
    await resetRows(g, numberedRows(200));
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectPrimaryText(0, "Row 001");
  });

  test("1.3.3 sorted add at bottom moves to a destination above the current buffer after deselect", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.scrollPrimaryIntoView("Row 200");
    await grid.expectLastRowPrimaryText("Row 200");

    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;
    // The new row is appended at the bottom and kept in place, so it stays the last
    // rendered row throughout. Assert on the last row (re-resolved each poll) rather
    // than a snapshotted renderedRowCount() index, which races with the confirmation
    // re-render — that stale index was the CI flake.
    await grid.expectLastRowPrimaryEmpty();
    await grid.expectLastRowLoading();
    // The row sorts above the loaded window (an empty Name sorts first), so it is
    // immediately flagged as moved while it stays selected — even before the create
    // request resolves, mirroring the in-buffer case (1.3.1a).
    await grid.expectLastRowWarning("Row has moved");

    pausedCreate.release();
    await grid.expectNoRowsLoading();
    // The kept-in-place new row stays the last rendered row after the create confirms.
    await grid.expectLastRowWarning("Row has moved");

    await grid.clickAway();
    await grid.expectLastRowPrimaryText("Row 200");
    await grid.expectLastRowNoWarning();

    await grid.goTo(g.database, g.table);
    await grid.expectPrimaryEmpty(0);
    await grid.expectPrimaryText(1, "Row 001");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });
});

// -----------------------------------------------------------------------------
// section 1.2  Create with active filter - mismatch warning + removal
// -----------------------------------------------------------------------------

for (const viewMode of REGULAR_FIELD_VIEW_MODES) {
  test.describe(`1.2 Create with active filter (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `CrudFilter${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        filters: [{ fieldName: "Name", type: "equal", value: "Alice" }],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      await resetRows(g, viewMode.rows([{ Name: "Alice", Score: 10 }]));
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 1);
    });

    test("1.2.1a paused simple-filtered add kept selected immediately shows filter warning until deselect", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);
      const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
      const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
      const pausedCreate = await pauseRows(page, g.table.id, "POST");
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
}

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");
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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

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
    const pausedCreate = await pauseRows(page, g.table.id, "POST");

    await grid.addRow();
    await pausedCreate.intercepted;

    await grid.startEditingField(1, 0);
    await grid.type("42");
    await grid.clickAway();

    // Register the PATCH interceptor now, after the POST is already held.
    // If the queue did not exist the PATCH would have fired before this point
    // and the intercepted promise below would never resolve.
    const pausedPatch = await pauseRows(page, g.table.id, "PATCH");

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
    const { failed } = await failRows(page, g.table.id, "PATCH");
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

for (const viewMode of REGULAR_FIELD_VIEW_MODES) {
  test.describe(`2.2 Edit with active filter on the edited field (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `EditFilter${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        filters: [{ fieldName: "Name", type: "equal", value: "Alice" }],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      await resetRows(g, viewMode.rows([{ Name: "Alice", Score: 10 }]));
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 1);
    });

    test("2.2.1a paused non-matching filtered edit shows warning while selected until confirmation", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);
      const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
      const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
      const { failed } = await failRows(page, g.table.id, "PATCH");
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
}

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
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 0);
    await grid.type("Al"); // length 2, does not match > 3
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;

    // Typed value is visible immediately, but formula-derived filter results
    // need the backend response, so the row remains loading while pending.
    await grid.expectPrimaryText(0, "Al");
    await grid.expectRowLoading(0);
    // No warning while pending — formula filter cannot be evaluated locally
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(1);

    pausedUpdate.release();
    // Warning appears only after the backend responds with the formula result
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row does not match filters");
    await grid.expectRowNotLoading(0);
    await grid.expectRowCount(1);
  });

  test("2.2.5b deselecting after backend confirmation removes the formula-filtered row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");
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

for (const viewMode of REGULAR_FIELD_VIEW_MODES) {
  test.describe(`2.3 Edit with active sort on the edited field (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `EditSort${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        sorts: [{ fieldName: "Name", order: "ASC" }],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      await resetRows(
        g,
        viewMode.rows([
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 20 },
        ]),
      );
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 2);
    });

    test("2.3.1a paused sorted edit kept selected shows Row has moved until confirmation", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);
      const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
      const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
      const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");
      await startEditingPrimary(grid, 0);
      await grid.type("Zara");
      await grid.confirmWithEnter();
      await pausedUpdate.intercepted;
      // Enter commits and clears the selection, so the locally-sortable row moves
      // immediately while the PATCH is still pending.
      await grid.expectPrimaryText(0, "Bob");
      await grid.expectPrimaryText(1, "Zara");
      await grid.expectRowNoWarning(1);
      pausedUpdate.fail();
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
}

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
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 0); // edit "Al"
    await grid.type("Alexander"); // length 9, should sort after "Alice" (5)
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;

    // Typed value is visible immediately, but formula-derived sort results
    // need the backend response, so the row remains loading while pending.
    await grid.expectPrimaryText(0, "Alexander");
    await grid.expectRowLoading(0);
    // No move warning while pending — formula sort cannot be evaluated locally
    await grid.expectRowNoWarning(0);
    await grid.expectRowCount(2);

    pausedUpdate.release();
    // Warning appears only after the backend responds with the formula result
    await grid.expectRowHasWarning(0);
    await grid.expectRowWarningText(0, "Row has moved");
    await grid.expectRowNotLoading(0);
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
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

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
    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");
    await startEditingPrimary(grid, 0);
    await grid.type("Alexander");
    await grid.confirmWithEnter();
    await pausedUpdate.intercepted;
    // Optimistic state: typed value visible immediately; no warning because the
    // frontend cannot evaluate the formula sort locally.
    await grid.expectPrimaryText(0, "Alexander");
    await grid.expectRowLoading(0);
    await grid.expectRowNoWarning(0);
    pausedUpdate.fail();
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Al");
    await grid.expectPrimaryText(1, "Alice");
    await grid.expectRowNoWarning(0);
    await grid.expectRowNoWarning(1);
  });
});

// -----------------------------------------------------------------------------
// section 2.3.5  Edit with active sort where destination is outside buffer
// -----------------------------------------------------------------------------

test.describe("2.3.5 Edit with active sort outside the current buffer", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "CrudSortUpdateOutsideBufferDb",
      fields: [{ name: "Score", type: "number" }],
      sorts: [{ fieldName: "Name", order: "ASC" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    await resetRows(g, numberedRows(50));
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expectPrimaryText(0, "Row 001");
  });

  test("2.3.5 sort-affecting edit moves the row outside the current buffer after deselect", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.reduceCurrentBufferToSlice(20, 30, "end");
    await grid.expectPrimaryVisible("Row 050");

    const pausedUpdate = await pauseRows(page, g.table.id, "PATCH");

    await startEditingPrimary(grid, 0);
    await grid.type("Row 000");
    await grid.expectActiveEditorValue("Row 000");
    await grid.confirmWithTab();
    await pausedUpdate.intercepted;
    await grid.expectPrimaryVisible("Row 000");
    await grid.expectPrimaryRowHasWarning("Row 000", "Row has moved");

    await grid.clickAway();
    await grid.expectPrimaryNotVisible("Row 000");
    await grid.expectRowNoWarning(0);

    pausedUpdate.release();
    await grid.expectNoRowsLoading();
    await grid.expectPrimaryNotVisible("Row 000");

    await grid.goTo(g.database, g.table);
    await grid.expectPrimaryText(0, "Row 000");
    await grid.expectPrimaryText(1, "Row 001");
    await grid.expectRowNoWarning(0);
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
    const { failed } = await failRows(page, g.table.id, "DELETE");
    await deleteRowThroughContextMenu(grid, 1);
    await failed;
    await grid.expectErrorToast();
    await grid.expectRowCount(2);
    await grid.expectPrimaryVisible("Alice");
    await grid.expectPrimaryVisible("Bob");
  });
});
