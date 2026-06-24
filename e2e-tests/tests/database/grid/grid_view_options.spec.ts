/**
 * Grid view - filters, sorts, and search.
 *
 * Catalogue sections covered:
 *   section 4  Filters (add/remove, types, AND combination)
 *   section 5  Sorts  (add, direction, multiple)
 *   section 6  Search (highlight mode, hide-not-matching mode)
 *   section 7  Presentation options (row coloring, fields, row height)
 *
 * Each describe block creates its own isolated database so a failing filter
 * test cannot corrupt the sort seed data. All setups run once via beforeAll;
 * each test re-navigates via beforeEach so it starts with a clean slate.
 *
 * Anti-flakiness:
 *   - Filters and sorts are applied via the API in beforeAll (not via UI
 *     configuration in beforeEach), so the view is already configured when
 *     the test navigates to it. This removes any race between "panel open"
 *     and "filter applied".
 *   - For UI-driven operations (section 4/section 5 panel interactions) we wait for the
 *     updated row count before asserting row content.
 */

import type { Locator, Page } from "@playwright/test";
import { test, expect } from "../../baserowTest";
import { GridPage } from "../../../pages/database/gridPage";
import {
  GridSetupResult,
  setupGrid,
} from "../../../fixtures/database/gridSetup";
import { createViewDecoration, patchView } from "../../../fixtures/database/view";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../../fixtures/licence";

type Setup = GridSetupResult;

const searchInputSelector = 'input[placeholder*="Search in"]';

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
// section 4  Filters
// -----------------------------------------------------------------------------

test.describe("4.1 Filter applied via API - rows hidden on load", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    // Apply a Name = "Alice" filter before the tests start
    g = await setupGrid({
      dbName: "FilterApiDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice", Score: 10 },
        { Name: "Bob", Score: 20 },
        { Name: "Carol", Score: 30 },
      ],
      filters: [{ fieldName: "Name", type: "equal", value: "Alice" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("4.1.1 loading a filtered view shows only the matching row and hides non-matching rows", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(1);
    await grid.expectPrimaryVisible("Alice");
    await grid.expectPrimaryNotVisible("Bob");
    await grid.expectPrimaryNotVisible("Carol");
  });
});

test.describe("4.2 Filter types - text contains", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "FilterContainsDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice Smith", Score: 10 },
        { Name: "Alice Jones", Score: 20 },
        { Name: "Bob Brown", Score: 30 },
      ],
      filters: [{ fieldName: "Name", type: "contains", value: "Alice" }],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("4.2.2 loading a contains-filtered view shows all substring matches and hides non-matches", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(2);
    await grid.expectPrimaryVisible("Alice Smith");
    await grid.expectPrimaryVisible("Alice Jones");
    await grid.expectPrimaryNotVisible("Bob Brown");
  });
});

test.describe("4.3 AND filter - two conditions must both match", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "FilterAndDb",
      fields: [
        { name: "Score", type: "number" },
        {
          name: "Status",
          type: "single_select",
          options: ["Done", "In Progress"],
        },
      ],
      rows: [
        { Name: "Alice", Score: 10, Status: "Done" },
        { Name: "Bob", Score: 20, Status: "Done" },
        { Name: "Carol", Score: 30, Status: "In Progress" },
      ],
      filters: [
        { fieldName: "Name", type: "equal", value: "Alice" },
        { fieldName: "Status", type: "single_select_equal", value: "Done" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("4.1.3 loading an AND-filtered view shows only rows matching both conditions", async ({
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

// -----------------------------------------------------------------------------
// section 5  Sorts
// -----------------------------------------------------------------------------

test.describe("5.1 Sort ASC / DESC", () => {
  test.describe.configure({ mode: "serial" });
  let gAsc: Setup;
  let gDesc: Setup;

  test.beforeAll(async () => {
    // Two setups: same data, one ASC one DESC
    [gAsc, gDesc] = await Promise.all([
      setupGrid({
        dbName: "SortAscDb",
        fields: [{ name: "Score", type: "number" }],
        rows: [
          { Name: "Carol", Score: 30 },
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 20 },
        ],
        sorts: [{ fieldName: "Name", order: "ASC" }],
      }),
      setupGrid({
        dbName: "SortDescDb",
        fields: [{ name: "Score", type: "number" }],
        rows: [
          { Name: "Carol", Score: 30 },
          { Name: "Alice", Score: 10 },
          { Name: "Bob", Score: 20 },
        ],
        sorts: [{ fieldName: "Name", order: "DESC" }],
      }),
    ]);
  });

  test("5.1.1 loading an ASC-sorted view shows rows in alphabetical order", async ({
    page,
  }) => {
    const grid = new GridPage(page, gAsc.user);
    await grid.goTo(gAsc.database, gAsc.table);

    // Names are in the LEFT section (primary field). Extract from primary cells.
    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryText(2, "Carol");
  });

  test("5.1.2 loading a DESC-sorted view shows rows in reverse alphabetical order", async ({
    page,
  }) => {
    const grid = new GridPage(page, gDesc.user);
    await grid.goTo(gDesc.database, gDesc.table);

    await grid.expectRowCount(3);
    await grid.expectPrimaryText(0, "Carol");
    await grid.expectPrimaryText(1, "Bob");
    await grid.expectPrimaryText(2, "Alice");
  });
});

test.describe("5.1.3 Multiple sorts - primary ASC, secondary DESC", () => {
  test.describe.configure({ mode: "serial" });
  let g: Setup;

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "MultiSortDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [
        { Name: "Alice", Score: 50 },
        { Name: "Alice", Score: 10 },
        { Name: "Bob", Score: 30 },
      ],
      sorts: [
        { fieldName: "Name", order: "ASC" },
        { fieldName: "Score", order: "DESC" },
      ],
    });
  });

  test.beforeEach(async ({ page }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
  });

  test("5.1.3 loading multi-sort view applies Name ASC first and Score DESC for tied names", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.expectRowCount(3);

    // First two rows are the two Alices; Alice with Score 50 should be first (DESC on Score)
    const firstScore = await grid.fieldCellAt(0, 0).innerText();
    const secondScore = await grid.fieldCellAt(1, 0).innerText();
    expect(Number(firstScore)).toBeGreaterThan(Number(secondScore));
  });
});

// -----------------------------------------------------------------------------
// section 6  Search
// -----------------------------------------------------------------------------

test.describe("6.1 Search highlight mode", () => {
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

  test("6.1.1 highlight-mode search highlights matching cell while all rows remain visible", async ({
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

  test("6.1.2 highlight-mode search with no matches shows no highlights and keeps all rows visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await typeInGridSearch(page, "XYZ_NO_MATCH");

    await grid.expectRowCount(3);
    await expect(
      page.locator(".grid-view__column--matches-search"),
    ).toHaveCount(0);
  });

  test("6.1.3 clearing search removes existing highlights and keeps all rows visible", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await typeInGridSearch(page, "Alice");
    await grid.expectPrimaryHighlighted(0);

    await clearGridSearch(page);
    await grid.expectPrimaryNotHighlighted(0);
    await grid.expectRowCount(3);
  });

  test("6.1.4 highlight-mode search marks the matching non-primary cell", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    // Search for "Modern" which matches Alice's Notes cell
    await typeInGridSearch(page, "Modern");

    await grid.expectCellHighlighted(0, 0); // Notes cell of Alice's row (row 0, first non-primary field)
  });
});

test.describe("6.2 Search hide-not-matching mode", () => {
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

  test("6.2.1 hide-mode search hides non-matching rows and keeps matching rows visible", async ({
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

  test("6.2.2 turning hide mode off restores hidden rows while keeping matching cells highlighted", async ({
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
// section 7  Presentation options
// -----------------------------------------------------------------------------

test.describe("7.1 Row coloring", () => {
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

  test("7.1.1 background row coloring uses the selected single-select option color on both grid sections", async ({
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
  });
});

test.describe("7.2 Field visibility", () => {
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

  test("7.2.1 fields panel hides and shows a non-primary field without changing visible rows", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(2);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(2);
    await grid.expectFieldText(0, 1, "Alpha");

    await grid.openFieldVisibilityContext();
    await grid.setFieldVisibility("Notes", false);

    await grid.expectRowCount(2);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderHidden("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(1);
    await grid.expectFieldText(0, 0, "10");

    await grid.setFieldVisibility("Notes", true);

    await grid.expectRowCount(2);
    await grid.expectNonPrimaryFieldHeaderVisible("Score");
    await grid.expectNonPrimaryFieldHeaderVisible("Notes");
    await grid.expectVisibleNonPrimaryFieldCount(2);
    await grid.expectFieldText(0, 1, "Alpha");
  });
});

test.describe("7.7 Row identifier type", () => {
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

  test("7.7.1 count mode shows sequential row position starting from 1", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.expectRowCount(3);
    await grid.expectRowIdentifierText(0, "1");
    await grid.expectRowIdentifierText(1, "2");
    await grid.expectRowIdentifierText(2, "3");
  });

  test("7.7.2 switching to Row identifier shows the actual backend row ID for each row", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.selectRowIdentifierType("id");
    await grid.expectRowIdentifierText(0, String(g.rowIds[0]));
    await grid.expectRowIdentifierText(1, String(g.rowIds[1]));
    await grid.expectRowIdentifierText(2, String(g.rowIds[2]));
  });

  test("7.7.3 switching back to Count restores sequential row positions", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.selectRowIdentifierType("id");
    await grid.expectRowIdentifierText(0, String(g.rowIds[0]));
    await grid.selectRowIdentifierType("count");
    await grid.expectRowIdentifierText(0, "1");
    await grid.expectRowIdentifierText(1, "2");
    await grid.expectRowIdentifierText(2, "3");
  });
});

test.describe("7.3 Row height", () => {
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

  test("7.3.1 height menu switches visible rows from small to medium and large", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);

    await grid.expectRowCount(2);
    await grid.expectRowHeight("small", 33);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");

    await grid.selectRowHeight("Medium");
    await grid.expectRowHeight("medium", 55);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");

    await grid.selectRowHeight("Large");
    await grid.expectRowHeight("large", 99);
    await grid.expectPrimaryText(0, "Alice");
    await grid.expectFieldText(0, 0, "10");
  });
});
