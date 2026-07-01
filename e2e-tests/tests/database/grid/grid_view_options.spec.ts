/**
 * Grid view - filters, sorts, and search.
 *
 * Catalogue sections covered:
 *   section 5   Filters loaded from saved view configuration
 *   section 6   Sorts loaded from saved view configuration
 *   section 7   Group-by
 *   section 8   Search (highlight mode, hide-not-matching mode)
 *   section 9   Presentation options (row coloring, fields, row height, freeze, identifiers)
 *   section 15  Public shared grid view
 *
 */

import type { Locator, Page, Request } from "@playwright/test";
import { test, expect } from "../../baserowTest";
import { GridPage } from "../../../pages/database/gridPage";
import type {
  GridSetupResult,
  FieldSpec,
  GroupBySpec,
} from "../../../fixtures/database/gridSetup";
import { setupGrid } from "../../../fixtures/database/gridSetup";
import {
  createViewDecoration,
  patchView,
} from "../../../fixtures/database/view";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../../fixtures/licence";
import { baserowConfig } from "../../../playwright.config";

type Setup = GridSetupResult;

// Keep docs/testing/grid-view-test-plan.md in sync with these cases.

type SavedViewMode = {
  name: string;
  dbSuffix: string;
  extraFields: FieldSpec[];
  groupBys?: GroupBySpec[];
  rows: (rows: Record<string, unknown>[]) => Record<string, unknown>[];
  waitForRows: (grid: GridPage, count: number) => Promise<void>;
};

const searchInputSelector = 'input[placeholder*="Search in"]';

async function waitForFlatRows(grid: GridPage, count: number): Promise<void> {
  await grid.expectRowCount(count);
}

const SAVED_VIEW_MODES: SavedViewMode[] = [
  {
    name: "flat",
    dbSuffix: "Flat",
    extraFields: [],
    rows: (rows) => rows,
    waitForRows: waitForFlatRows,
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
      await grid.expectRowCount(count);
    },
  },
];

async function waitForApiPatch(
  page: Page,
  path: string,
  action: () => Promise<void>,
): Promise<void> {
  const response = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname.endsWith(path) &&
      response.request().method() === "PATCH" &&
      response.ok()
    );
  });

  await action();
  await response;
}

async function waitForViewPatch(
  page: Page,
  viewId: number,
  action: () => Promise<void>,
): Promise<void> {
  await waitForApiPatch(page, `/api/database/views/${viewId}/`, action);
}

async function waitForFieldOptionsPatch(
  page: Page,
  viewId: number,
  action: () => Promise<void>,
): Promise<void> {
  await waitForApiPatch(
    page,
    `/api/database/views/${viewId}/field-options/`,
    action,
  );
}

function gridSearchContext(page: Page): Locator {
  return page
    .locator(".context")
    .filter({ has: page.locator(searchInputSelector) })
    .last();
}

async function openGridSearch(page: Page): Promise<Locator> {
  const input = page.locator(searchInputSelector).first();
  const searchLink = page
    .locator(".header__search .header__filter-link")
    .first();

  await expect(searchLink).toBeVisible({ timeout: 10_000 });
  if (!(await input.isVisible())) {
    await searchLink.click();
  }
  await expect(input).toBeVisible({ timeout: 10_000 });
  return input;
}

async function waitForSearchContextIdle(page: Page): Promise<void> {
  await expect(gridSearchContext(page)).not.toHaveClass(
    /context--loading-overlay/,
    { timeout: 10_000 },
  );
}

async function typeInGridSearch(page: Page, term: string): Promise<void> {
  const input = await openGridSearch(page);
  await waitForSearchContextIdle(page);
  await input.click();
  await input.press("ControlOrMeta+A");
  await input.pressSequentially(term);
}

async function clearGridSearch(page: Page): Promise<void> {
  const input = await openGridSearch(page);
  await waitForSearchContextIdle(page);
  await input.click();
  await input.press("ControlOrMeta+A");
  await input.press("Backspace");
}

async function turnOffHideNotMatchingRows(page: Page): Promise<void> {
  await openGridSearch(page);

  const searchContext = gridSearchContext(page);
  const hideSwitch = searchContext.locator(".switch", {
    hasText: /hide not matching rows/i,
  });

  await expect(hideSwitch).toHaveClass(/switch--active/, { timeout: 5_000 });
  await hideSwitch.click();
  await expect(hideSwitch).not.toHaveClass(/switch--active/, {
    timeout: 5_000,
  });
  await waitForSearchContextIdle(page);
}

// -----------------------------------------------------------------------------
// section 7  Group-by
// -----------------------------------------------------------------------------

test.describe("7.2 Group-by refresh", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "GroupByRefreshDb",
      fields: [
        { name: "Team", type: "text" },
        { name: "Role", type: "text" },
      ],
      rows: [
        { Name: "Alice", Team: "A", Role: "Developer" },
        { Name: "Ada", Team: "A", Role: "Designer" },
        { Name: "Bob", Team: "B", Role: "QA" },
        { Name: "Bea", Team: "B", Role: "Support" },
      ],
      groupBys: [{ fieldName: "Team", order: "ASC" }],
    });
  });

  test("7.2.1 adding a second group-by performs one metadata request and one row request", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.expandAllGroupsFromContext();
    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 2);
    await grid.expectRowCount(4);

    const groupByDataRequests: Request[] = [];
    const rowRequests: Request[] = [];
    page.on("request", (request) => {
      if (request.method() !== "GET") {
        return;
      }

      const url = new URL(request.url());
      if (
        url.pathname.endsWith(
          `/api/database/views/grid/${g.view.id}/group-by-data/`,
        )
      ) {
        groupByDataRequests.push(request);
      } else if (
        url.pathname.endsWith(`/api/database/views/grid/${g.view.id}/`) &&
        url.searchParams.has("limit")
      ) {
        rowRequests.push(request);
      }
    });

    const groupByCreated = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname.endsWith(`/api/database/views/${g.view.id}/group_bys/`) &&
        response.request().method() === "POST" &&
        response.ok()
      );
    });

    await grid.addGroupBy("Role");
    await groupByCreated;

    await grid.expectGroupByBanner("A", 2);
    await grid.expectGroupByBanner("B", 2);
    await grid.expectGroupByBanner("Developer", 1);
    await grid.expectGroupByBanner("Designer", 1);
    await grid.expectGroupByBanner("QA", 1);
    await grid.expectGroupByBanner("Support", 1);
    await grid.expectRowCount(4);

    expect(groupByDataRequests).toHaveLength(1);
    expect(rowRequests).toHaveLength(1);
    const groupByDataUrl = new URL(groupByDataRequests[0].url());
    expect(groupByDataUrl.searchParams.get("include_descendants")).toBe("true");
  });
});

// -----------------------------------------------------------------------------
// section 5  Filters
// -----------------------------------------------------------------------------

for (const viewMode of SAVED_VIEW_MODES) {
  test.describe(`5.1 Filter applied via API (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      // Apply a Name = "Alice" filter before the tests start
      g = await setupGrid({
        dbName: `FilterApi${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        rows: viewMode.rows([
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 20 },
          { Name: "Carol", Score: 30 },
        ]),
        filters: [{ fieldName: "Name", type: "equal", value: "Alice" }],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 1);
    });

    test("5.1.1 loading a filtered view shows only the matching row and hides non-matching rows", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);

      await grid.expectRowCount(1);
      await grid.expectPrimaryVisible("Alice");
      await grid.expectPrimaryNotVisible("Bob");
      await grid.expectPrimaryNotVisible("Carol");
    });
  });
}

for (const viewMode of SAVED_VIEW_MODES) {
  test.describe(`5.2 Filter types - text contains (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `FilterContains${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        rows: viewMode.rows([
          { Name: "Alice Smith", Score: 10 },
          { Name: "Alice Jones", Score: 20 },
          { Name: "Bob Brown", Score: 30 },
        ]),
        filters: [{ fieldName: "Name", type: "contains", value: "Alice" }],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 2);
    });

    test("5.2.1 loading a contains-filtered view shows all substring matches and hides non-matches", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);

      await grid.expectRowCount(2);
      await grid.expectPrimaryVisible("Alice Smith");
      await grid.expectPrimaryVisible("Alice Jones");
      await grid.expectPrimaryNotVisible("Bob Brown");
    });
  });
}

for (const viewMode of SAVED_VIEW_MODES) {
  test.describe(`5.1.2 AND filter (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `FilterAnd${viewMode.dbSuffix}Db`,
        fields: [
          { name: "Score", type: "number" },
          {
            name: "Status",
            type: "single_select",
            options: ["Done", "In Progress"],
          },
          ...viewMode.extraFields,
        ],
        rows: viewMode.rows([
          { Name: "Alice", Score: 10, Status: "Done" },
          { Name: "Bob", Score: 20, Status: "Done" },
          { Name: "Carol", Score: 30, Status: "In Progress" },
        ]),
        filters: [
          { fieldName: "Name", type: "equal", value: "Alice" },
          { fieldName: "Status", type: "single_select_equal", value: "Done" },
        ],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 1);
    });

    test("5.1.2 loading an AND-filtered view shows only rows matching both conditions", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);

      // Only "Alice" matches Name=Alice AND Status=Done
      await grid.expectRowCount(1);
      await grid.expectPrimaryVisible("Alice");
      await grid.expectPrimaryNotVisible("Bob"); // Bob matches Status but not Name
      await grid.expectPrimaryNotVisible("Carol"); // Carol matches neither
    });
  });
}

// -----------------------------------------------------------------------------
// section 6  Sorts
// -----------------------------------------------------------------------------

for (const viewMode of SAVED_VIEW_MODES) {
  test.describe(`6.1 Sort ASC / DESC (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let gAsc: Setup;
    let gDesc: Setup;

    test.beforeAll(async () => {
      // Two setups: same data, one ASC one DESC
      [gAsc, gDesc] = await Promise.all([
        setupGrid({
          dbName: `SortAsc${viewMode.dbSuffix}Db`,
          fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
          rows: viewMode.rows([
            { Name: "Carol", Score: 30 },
            { Name: "Alice", Score: 10 },
            { Name: "Bob", Score: 20 },
          ]),
          sorts: [{ fieldName: "Name", order: "ASC" }],
          groupBys: viewMode.groupBys,
        }),
        setupGrid({
          dbName: `SortDesc${viewMode.dbSuffix}Db`,
          fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
          rows: viewMode.rows([
            { Name: "Carol", Score: 30 },
            { Name: "Alice", Score: 10 },
            { Name: "Bob", Score: 20 },
          ]),
          sorts: [{ fieldName: "Name", order: "DESC" }],
          groupBys: viewMode.groupBys,
        }),
      ]);
    });

    test("6.1.1 loading an ASC-sorted view shows rows in alphabetical order", async ({
      page,
    }) => {
      const grid = new GridPage(page, gAsc.user);
      await grid.goTo(gAsc.database, gAsc.table);
      await viewMode.waitForRows(grid, 3);

      // Names are in the LEFT section (primary field). Extract from primary cells.
      await grid.expectPrimaryText(0, "Alice");
      await grid.expectPrimaryText(1, "Bob");
      await grid.expectPrimaryText(2, "Carol");
    });

    test("6.1.2 loading a DESC-sorted view shows rows in reverse alphabetical order", async ({
      page,
    }) => {
      const grid = new GridPage(page, gDesc.user);
      await grid.goTo(gDesc.database, gDesc.table);
      await viewMode.waitForRows(grid, 3);

      await grid.expectPrimaryText(0, "Carol");
      await grid.expectPrimaryText(1, "Bob");
      await grid.expectPrimaryText(2, "Alice");
    });
  });
}

for (const viewMode of SAVED_VIEW_MODES) {
  test.describe(`6.1.3 Multiple sorts (${viewMode.name})`, () => {
    test.describe.configure({ mode: "serial" });
    let g: Setup;

    test.beforeAll(async () => {
      g = await setupGrid({
        dbName: `MultiSort${viewMode.dbSuffix}Db`,
        fields: [{ name: "Score", type: "number" }, ...viewMode.extraFields],
        rows: viewMode.rows([
          { Name: "Alice", Score: 50 },
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 30 },
        ]),
        sorts: [
          { fieldName: "Name", order: "ASC" },
          { fieldName: "Score", order: "DESC" },
        ],
        groupBys: viewMode.groupBys,
      });
    });

    test.beforeEach(async ({ page }) => {
      const grid = new GridPage(page, g.user);
      await grid.goTo(g.database, g.table);
      await viewMode.waitForRows(grid, 3);
    });

    test("6.1.3 loading multi-sort view applies Name ASC first and Score DESC for tied names", async ({
      page,
    }) => {
      const grid = new GridPage(page, g.user);

      // First two rows are the two Alices; Alice with Score 50 should be first (DESC on Score)
      const firstScore = await grid.fieldCellAt(0, 0).innerText();
      const secondScore = await grid.fieldCellAt(1, 0).innerText();
      expect(Number(firstScore)).toBeGreaterThan(Number(secondScore));
    });
  });
}

// -----------------------------------------------------------------------------
// section 8  Search
// -----------------------------------------------------------------------------

test.describe("8.1 Search highlight mode", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "SearchDb",
      fields: [{ name: "Notes", type: "text" }],
      rows: [
        { Name: "Alice", Notes: "Modernize the dashboard" },
        { Name: "Bob", Notes: "Refactor the backend" },
        { Name: "Carol", Notes: "Design the landing page" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    // The flat grid defaults hideRowsNotMatchingSearch=true (set in CLEAR_ROWS).
    // For highlight-mode tests, we must turn it OFF first.
    await turnOffHideNotMatchingRows(page);
    // Leave the search panel open - typeInSearch will use it.
  });

  test("8.1.1 highlight-mode search highlights matching cell while all rows remain visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await typeInGridSearch(page, "Alice");

    // Only Alice's Name cell is highlighted
    await grid.expectPrimaryHighlighted(0);
    // Non-matching rows are still visible
    await grid.expectPrimaryVisible("Bob");
    await grid.expectPrimaryVisible("Carol");
    // Their Name cells are NOT highlighted
    await grid.expectPrimaryNotHighlighted(1);
  });

  test("8.1.2 highlight-mode search with no matches shows no highlights and keeps all rows visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await typeInGridSearch(page, "XYZ_NO_MATCH");

    await grid.expectRowCount(3);
    await expect(
      page.locator(".grid-view__column--matches-search"),
    ).toHaveCount(0);
  });

  test("8.1.3 clearing search removes existing highlights and keeps all rows visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await typeInGridSearch(page, "Alice");
    await grid.expectPrimaryHighlighted(0);

    await clearGridSearch(page);
    await grid.expectPrimaryNotHighlighted(0);
    await grid.expectRowCount(3);
  });

  test("8.1.4 highlight-mode search marks the matching non-primary cell", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    // Search for "Modern" which matches Alice's Notes cell
    await typeInGridSearch(page, "Modern");

    await grid.expectCellHighlighted(0, 0); // Notes cell of Alice's row (row 0, first non-primary field)
  });
});

test.describe("8.2 Search hide-not-matching mode", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "SearchHideDb",
      fields: [{ name: "Notes", type: "text" }],
      rows: [
        // Only Alice and Carol have "found" in Notes; Bob does not.
        { Name: "Alice", Notes: "Found it here" },
        { Name: "Bob", Notes: "Unrelated note" },
        { Name: "Carol", Notes: "Also found" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    // The grid defaults to hide mode ON. Open search and type - it will hide rows.
    await openGridSearch(page);
  });

  test("8.2.1 hide-mode search hides non-matching rows and keeps matching rows visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    // Default is hide mode ON - typing immediately hides non-matching rows
    await typeInGridSearch(page, "found");

    // "Bob" ("Unrelated note") doesn't match -> disappears
    await grid.expectPrimaryNotVisible("Bob");
    await grid.expectPrimaryVisible("Alice");
    await grid.expectPrimaryVisible("Carol");
    await grid.expectRowCount(2);
  });

  test("8.2.2 turning hide mode off restores hidden rows while keeping matching cells highlighted", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await typeInGridSearch(page, "found");
    await grid.expectRowCount(2);

    // Toggle hide mode OFF - all rows reappear
    await turnOffHideNotMatchingRows(page);

    await grid.expectRowCount(3);
    await grid.expectPrimaryVisible("Bob");
    // Alice's Notes cell should still be highlighted (highlight mode now active)
    await grid.expectCellHighlighted(0, 0); // Alice's Notes (row 0, first non-primary field)
  });
});

// -----------------------------------------------------------------------------
// section 9  Presentation options
// -----------------------------------------------------------------------------

test.describe("9.1 Row coloring", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;
  let license: License;

  test.beforeAll(async () => {
    license = await createLicense(ENTERPRISE_LICENSE);
    g = await setupGrid({
      dbName: "RowColoringDb",
      fields: [
        {
          name: "Status",
          type: "single_select",
          options: [
            { value: "Blocked", color: "red" },
            { value: "Ready", color: "green" },
          ],
        },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Status: "Blocked", Notes: "Investigate" },
        { Name: "Bob", Status: "Ready", Notes: "Ship" },
      ],
    });
    await createViewDecoration(g.user, g.view, {
      type: "background_color",
      value_provider_type: "single_select_color",
      value_provider_conf: { field_id: g.fieldByName.Status.id },
    });
  });

  test.afterAll(async () => {
    if (license) {
      await deleteLicense(license);
    }
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.1.1 background row coloring uses the selected single-select option color on both grid sections", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(2);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "Blocked");
    await grid.expectRowBackgroundColor(0, "red");

    await grid.expectPrimaryText(1, "Bob");
    await grid.expectFieldText(1, 0, "Ready");
    await grid.expectRowBackgroundColor(1, "green");
    await grid.expectNoRowsLoading();
  });
});

test.describe("9.2 Field visibility", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "FieldVisibilityDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "Alpha" },
        { Name: "Bob", Score: 20, Notes: "Beta" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.2.1 fields panel hides and shows a non-primary field and persists both states", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(2);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(2);
    await grid.expectFieldText(0, 1, "Alpha");

    await grid.openFieldVisibilityContext();
    await waitForFieldOptionsPatch(page, g.view.id, () =>
      grid.setFieldVisibility("Notes", false),
    );

    await grid.expectRowCount(2);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderHidden("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(1);
    await grid.expectFieldText(0, 0, "10");

    await grid.goTo(g.database, g.table);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderHidden("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(1);

    await grid.openFieldVisibilityContext();
    await waitForFieldOptionsPatch(page, g.view.id, () =>
      grid.setFieldVisibility("Notes", true),
    );

    await grid.expectRowCount(2);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(2);
    await grid.expectFieldText(0, 1, "Alpha");

    await grid.goTo(g.database, g.table);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(2);
  });
});

test.describe("9.3 Row height", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "RowHeightDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice", Score: 10 },
        { Name: "Bob", Score: 20 },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.3.1 height menu switches visible rows from small to medium and large", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(2);
    await grid.expectRowHeight("small", 33);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");

    await waitForViewPatch(page, g.view.id, () =>
      grid.selectRowHeight("Medium"),
    );
    await grid.expectRowHeight("medium", 55);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");

    await waitForViewPatch(page, g.view.id, () =>
      grid.selectRowHeight("Large"),
    );
    await grid.expectRowHeight("large", 99);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");

    await grid.goTo(g.database, g.table);
    await grid.expectRowHeight("large", 99);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");
    await grid.expectNoRowsLoading();
  });
});

test.describe("9.4 Frozen columns", () => {
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "FrozenColumnsDb",
      fields: [
        { name: "Score", type: "number" },
        { name: "Notes", type: "text" },
      ],
      rows: [
        { Name: "Alice", Score: 10, Notes: "Alpha" },
        { Name: "Bob", Score: 20, Notes: "Beta" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    await patchView(g.user, g.view, { frozen_column_count: 2 });
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.4.1 loading a view with two frozen columns keeps the first non-primary field frozen after reload", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectFrozenFieldHeaderVisible("Score");
    await grid.expectScrollableFieldHeaderHidden("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");

    await grid.goTo(g.database, g.table);
    await grid.expectFrozenFieldHeaderVisible("Score");
    await grid.expectScrollableFieldHeaderHidden("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");
  });
});

test.describe("9.5 Row identifier type", () => {
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "RowIdentifierDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice", Score: 10 },
        { Name: "Bob", Score: 20 },
        { Name: "Carol", Score: 30 },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    await patchView(g.user, g.view, { row_identifier_type: "count" });
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("9.5.1 count mode shows sequential row position starting from 1", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.expectRowCount(3);
    await grid.expectRowIdentifierText(0, "1");
    await grid.expectRowIdentifierText(1, "2");
    await grid.expectRowIdentifierText(2, "3");
  });

  test("9.5.2 row identifier menu switches to backend row IDs and back to count", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await waitForViewPatch(page, g.view.id, () =>
      grid.selectRowIdentifierType("id"),
    );
    // Backend row IDs are shown; sequential position values are no longer visible.
    await grid.expectRowIdentifierText(0, String(g.rowIds[0]));
    await grid.expectRowIdentifierText(1, String(g.rowIds[1]));
    await grid.expectRowIdentifierText(2, String(g.rowIds[2]));
    await expect(grid.rowIdentifierContentAt(0)).not.toHaveText("1", {
      timeout: 5_000,
    });
    await expect(grid.rowIdentifierContentAt(1)).not.toHaveText("2", {
      timeout: 5_000,
    });

    await grid.goTo(g.database, g.table);
    await grid.expectRowIdentifierText(0, String(g.rowIds[0]));
    await grid.expectRowIdentifierText(1, String(g.rowIds[1]));
    await grid.expectRowIdentifierText(2, String(g.rowIds[2]));

    await waitForViewPatch(page, g.view.id, () =>
      grid.selectRowIdentifierType("count"),
    );
    await grid.expectRowIdentifierText(0, "1");
    await grid.expectRowIdentifierText(1, "2");
    await grid.expectRowIdentifierText(2, "3");

    await grid.goTo(g.database, g.table);
    await grid.expectRowIdentifierText(0, "1");
    await grid.expectRowIdentifierText(1, "2");
    await grid.expectRowIdentifierText(2, "3");
  });
});

// -----------------------------------------------------------------------------
// section 15  Public shared grid view
// -----------------------------------------------------------------------------

test.describe("15.1 Public shared grid", () => {
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "PublicGridDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice", Score: 10 },
        { Name: "Bob", Score: 20 },
      ],
    });
    await patchView(g.user, g.view, { public: true });
  });

  test("15.1.1 public shared grid renders rows without edit controls", async ({
    page,
  }) => {
    const slug = g.view.slug;
    if (!slug) {
      throw new Error("Expected setup grid view to include a public slug.");
    }

    await page.goto(
      `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/public/grid/${slug}`,
      {
        waitUntil: "domcontentloaded",
      },
    );

    await expect(page.locator(".grid-view__right")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.locator(".grid-view__left .grid-view__row", {
        hasText: "Alice",
      }),
    ).toBeVisible();
    await expect(
      page.locator(".grid-view__left .grid-view__row", {
        hasText: "Bob",
      }),
    ).toBeVisible();
    await expect(page.locator(".grid-view__add-row")).toHaveCount(0);
    await page
      .locator(".grid-view__left .grid-view__row")
      .first()
      .click({ button: "right" });
    await expect(
      page.locator(".context__menu:visible .context__menu-item-link", {
        hasText: /Delete row|Insert row|Duplicate row/,
      }),
    ).toHaveCount(0);
  });
});
