/**
 * Grouped grid: global search highlights matching cells, and the
 * "Hide rows not matching search" toggle filters non-matches out of
 * the visible row set.
 *
 * Seed: two rows in the Design section — one with name "Modernize",
 * one with name "Other". The search term "Modern" should match only
 * the first row's Name cell.
 *
 * Each test starts fresh, expands the section, and exercises one
 * behaviour:
 *   1) typing a query highlights matching cells
 *   2) flipping "hide not matching" on hides the non-matching row
 *   3) clearing the query restores both rows
 */
import { expect, test, Page } from "../baserowTest";
import { createUser, User } from "../../fixtures/user";
import { createWorkspace } from "../../fixtures/workspace";
import { createDatabase, Database } from "../../fixtures/database/database";
import { createTable, Table } from "../../fixtures/database/table";
import {
  createField,
  deleteAllNonPrimaryFieldsFromTable,
  Field,
  getFieldsForTable,
} from "../../fixtures/database/field";
import {
  createRows,
  deleteRows,
  listRows,
} from "../../fixtures/database/rows";
import {
  createViewGroupBy,
  getDefaultGridView,
  View,
} from "../../fixtures/database/view";

let user: User;
let database: Database;
let table: Table;
let view: View;
let categoryField: Field;
let designOptionId: number;
const baseUrl = process.env.PUBLIC_WEB_FRONTEND_URL || "http://localhost:3000";
let matchingRowId: number;
let otherRowId: number;

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  user = await createUser();
  const workspace = await createWorkspace(user);

  database = await createDatabase(user, "groupedSearchDb", workspace);
  table = await createTable(user, "Projects", database);
  await deleteAllNonPrimaryFieldsFromTable(user, table);
  // The BE auto-creates two empty rows on table create; delete them
  // so the seed is the entire dataset.
  const defaultRows = await listRows(user, table);
  if (defaultRows.length > 0) {
    await deleteRows(
      user,
      table,
      defaultRows.map((r: { id: number }) => r.id),
    );
  }

  categoryField = await createField(
    user,
    "Category",
    "single_select",
    { select_options: [{ value: "Design", color: "blue" }] },
    table,
  );
  const refreshed = await getFieldsForTable(user, table);
  const cat = refreshed.find((f) => f.id === categoryField.id)!;
  designOptionId = cat.fieldSettings.select_options[0].id;

  const created = await createRows(user, table, [
    { Name: "Modernize", Category: designOptionId },
    { Name: "Other", Category: designOptionId },
  ]);
  matchingRowId = created[0].id;
  otherRowId = created[1].id;

  view = await getDefaultGridView(user, table);
  await createViewGroupBy(user, view, categoryField);
});

test.beforeEach(async ({ page }) => {
  await page.context().addCookies([
    {
      name: "baserow_dashboard_alert_closed_v2",
      value: "true",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.goto(`${baseUrl}?token=${user.refreshToken}`);
  await page.goto(`${baseUrl}/database/${database.id}/table/${table.id}`);
  await expect(page.locator(".grid-grouped")).toBeVisible({ timeout: 20000 });
  await expandDesignGroup(page);
});

// ── Tests ─────────────────────────────────────────────────────────

test(
  "typing a search term highlights matching cells",
  { tag: "@grouped" },
  async ({ page }) => {
    await openSearchAndType(page, "Modern");

    // The matching row's Name cell renders with the highlight class.
    await expect(
      page
        .locator(`.grid-grouped-row[data-row-id="${matchingRowId}"]`)
        .locator(".grid-view__column--matches-search"),
      "matching row should have a highlighted cell",
    ).toHaveCount(1, { timeout: 5000 });

    // The non-matching row has no highlights.
    await expect(
      page
        .locator(`.grid-grouped-row[data-row-id="${otherRowId}"]`)
        .locator(".grid-view__column--matches-search"),
      "non-matching row should have no highlights",
    ).toHaveCount(0);
  },
);

test(
  "search with default 'hide not matching' filters non-matching rows out",
  { tag: "@grouped" },
  async ({ page }) => {
    // The flat store's default `hideRowsNotMatchingSearch` is true,
    // so typing the search term should immediately drop non-matching
    // rows from the visible set — no toggle needed.
    await openSearchAndType(page, "Modern");

    await expect(
      page.locator(".grid-grouped-row"),
      "hide-mode should hide non-matching rows",
    ).toHaveCount(1, { timeout: 5000 });
    await expect(
      page.locator(`.grid-grouped-row[data-row-id="${matchingRowId}"]`),
      "matching row should still be present",
    ).toBeVisible();
  },
);

test(
  "clearing the search restores all rows",
  { tag: "@grouped" },
  async ({ page }) => {
    await openSearchAndType(page, "Modern");
    await expect(page.locator(".grid-grouped-row")).toHaveCount(1);

    await clearSearch(page);

    await expect(
      page.locator(".grid-grouped-row"),
      "clearing the search should restore both rows",
    ).toHaveCount(2, { timeout: 5000 });
  },
);

// ── Helpers ───────────────────────────────────────────────────────

async function expandDesignGroup(page: Page) {
  // Grouped views start every banner collapsed; wait for the banner
  // to render, click its toggle, then wait for the rows.
  const banner = page.locator(
    `.grid-grouped-banner--collapsed[data-depth="0"]`,
  );
  await expect(banner).toHaveCount(1, { timeout: 15000 });
  await banner.locator(".grid-grouped-banner__toggle").click();
  await expect(page.locator(".grid-grouped-row")).toHaveCount(2, {
    timeout: 10000,
  });
}

// Open the global search popover and type the query. The Context
// component uses MoveToBody so the popover renders at body root,
// not inside `.header__search` — we target the search input via its
// unique placeholder text instead.
async function openSearchAndType(page: Page, query: string) {
  await page.locator(".header__search .header__filter-link").click();
  const input = page.locator(
    'input[placeholder*="Search in"]',
  );
  await expect(input).toBeVisible({ timeout: 5000 });
  await input.fill(query);
  // FormInput uses @keyup to drive its debounced search.
  await input.press("End");
  // Wait for the debounce + store update.
  await page.waitForTimeout(700);
}

async function toggleHideNotMatching(page: Page) {
  // The "Hide rows not matching search" switch lives inside the
  // body-level popover, alongside the placeholder-tagged input.
  const popover = page
    .locator(".context")
    .filter({ has: page.locator('input[placeholder*="Search in"]') });
  await popover.locator(".switch").click();
  await page.waitForTimeout(700);
}

async function clearSearch(page: Page) {
  const input = page.locator('input[placeholder*="Search in"]');
  await input.fill("");
  await input.press("End");
  await page.waitForTimeout(700);
}
