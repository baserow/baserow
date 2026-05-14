/**
 * Grouped grid: "+ Add row" affordance on each group's trailer.
 *
 * Confirms that for every (Category × Completed) combination, clicking
 * the trailer creates a row that:
 *   1) lands in BE under the right group (Category + Completed match),
 *   2) carries a positive autonumber value (BE-populated),
 *   3) gets an incremental id (strictly greater than any previously
 *      seen id),
 *   4) renders in the DOM strictly between its banner and the next
 *      depth-1 banner — i.e. the right pixel range, no neighbour
 *      displacement.
 *
 * The setup (DB → table → fields → seed rows → group-bys) runs once
 * in `beforeAll`. Each test navigates fresh, expands all groups,
 * and exercises one (category, completed) combination, so failures
 * point at the specific group that broke.
 */
import { expect, test } from "../baserowTest";
import { Page } from "@playwright/test";
import { User } from "../../fixtures/user";
import { createDatabase, Database } from "../../fixtures/database/database";
import { createTable, Table } from "../../fixtures/database/table";
import {
  createField,
  deleteAllNonPrimaryFieldsFromTable,
  Field,
  getFieldsForTable,
} from "../../fixtures/database/field";
import { createRows, listRows } from "../../fixtures/database/rows";
import {
  createViewGroupBy,
  getDefaultGridView,
  View,
} from "../../fixtures/database/view";

// ── Test parameters ───────────────────────────────────────────────
const CATEGORIES = ["Marketing", "Engineering", "Sales"] as const;
const COMPLETED_VALUES = [true, false] as const;
type CategoryName = (typeof CATEGORIES)[number];
type Completed = (typeof COMPLETED_VALUES)[number];

// ── Shared state, populated once in beforeAll ─────────────────────
let user: User;
let database: Database;
let table: Table;
let view: View;
let categoryField: Field;
let completedField: Field;
let baseUrl: string;
// `Marketing` → select option id (BE-assigned).
const optionIdByCategory: Record<CategoryName, number> = {} as never;

test.describe.configure({ mode: "serial" });

// ── Setup ─────────────────────────────────────────────────────────
test.beforeAll(async ({ workspacePage }) => {
  user = workspacePage.user;
  baseUrl = workspacePage.baseUrl;

  database = await createDatabase(
    user,
    "groupedAddRowDb",
    workspacePage.workspace
  );
  table = await createTable(user, "Projects", database);
  await deleteAllNonPrimaryFieldsFromTable(user, table);

  categoryField = await createField(
    user,
    "Category",
    "single_select",
    {
      select_options: CATEGORIES.map((value, i) => ({
        value,
        color: ["blue", "green", "red"][i % CATEGORIES.length],
      })),
    },
    table
  );
  completedField = await createField(user, "Completed", "boolean", {}, table);
  await createField(user, "Auto", "autonumber", {}, table);

  // Re-read the category field for the BE-assigned select option ids.
  const refreshed = await getFieldsForTable(user, table);
  const cat = refreshed.find((f) => f.id === categoryField.id)!;
  for (const opt of cat.fieldSettings.select_options) {
    if (CATEGORIES.includes(opt.value)) {
      optionIdByCategory[opt.value as CategoryName] = opt.id;
    }
  }

  // Seed one row per (Category × Completed) so every leaf banner
  // exists in the tree from the start. Without seeds, depth-1
  // nodes wouldn't appear and the layout wouldn't have a banner
  // to anchor the addRow trailer to.
  const seedRows = CATEGORIES.flatMap((c) =>
    COMPLETED_VALUES.map((done) => ({
      Category: optionIdByCategory[c],
      Completed: done,
    }))
  );
  await createRows(user, table, seedRows);

  // View group-bys: Category first, Completed second.
  view = await getDefaultGridView(user, table);
  await createViewGroupBy(user, view, categoryField);
  await createViewGroupBy(user, view, completedField);
});

// ── Per-test page bootstrap ───────────────────────────────────────
test.beforeEach(async ({ page }) => {
  await page.goto(`${baseUrl}/database/${database.id}/table/${table.id}`);
  await expect(page.locator(".grid-grouped")).toBeVisible({ timeout: 20000 });
  await expandAllGroups(page);
});

// ── The actual tests: one per (Category × Completed) combination ──
for (const cat of CATEGORIES) {
  for (const done of COMPLETED_VALUES) {
    test(
      `adds a row in ${cat} / completed=${done}`,
      { tag: "@grouped" },
      async ({ page }) => {
        const beforeRowIds = (await listRows(user, table)).map((r) => r.id);
        const beforeMaxId = Math.max(...beforeRowIds, 0);

        await clickAddRowInGroup(page, cat, done);

        const newRow = await waitForNewRowInBackend(beforeRowIds);
        const categoryCell = newRow.Category as
          | { id: number; value: string }
          | null;

        expect(categoryCell?.value, "Category should match the clicked group")
          .toBe(cat);
        expect(newRow.Completed, "Completed should match the clicked group")
          .toBe(done);
        expect(newRow.Auto, "Autonumber should be populated by the BE")
          .toBeGreaterThan(0);
        expect(newRow.id, "Row id should be incremental")
          .toBeGreaterThan(beforeMaxId);

        await expectRowRendersUnderItsBanner(page, newRow.id, cat, done);
      }
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────

// JSON-encoded `data-path` substrings, anchored so option id `:1`
// can't prefix-match `:11`. Depth-1 (leaf) selectors include both
// fields; depth-0 selectors include just the category.
function leafSelector(cat: CategoryName, done: Completed): string {
  const cId = optionIdByCategory[cat];
  return (
    `[data-path*='"field_${categoryField.id}":${cId},']` +
    `[data-path*='"field_${completedField.id}":${done}}']`
  );
}

function categorySelector(cat: CategoryName): string {
  return `[data-path*='"field_${categoryField.id}":${optionIdByCategory[cat]}}']`;
}

async function expandAllGroups(page: Page) {
  // Expand every depth-0 banner, wait for depth-1 banners to render,
  // then expand each depth-1 banner. Grouped views default to
  // collapse-mode, so a fresh page load shows only depth-0 banners.
  const expectedDepth1Count = CATEGORIES.length * COMPLETED_VALUES.length;
  await expect(page.locator('.grid-grouped-banner[data-depth="0"]')).toHaveCount(
    CATEGORIES.length,
    { timeout: 15000 }
  );
  for (const cat of CATEGORIES) {
    await page
      .locator(
        `.grid-grouped-banner[data-depth="0"]${categorySelector(cat)} .grid-grouped-banner__toggle`
      )
      .click();
  }
  await expect(
    page.locator('.grid-grouped-banner[data-depth="1"]')
  ).toHaveCount(expectedDepth1Count, { timeout: 15000 });
  // Expand every depth-1 banner so its rows + addRow trailer render.
  const depth1Toggles = await page
    .locator('.grid-grouped-banner[data-depth="1"] .grid-grouped-banner__toggle')
    .all();
  for (const toggle of depth1Toggles) {
    await toggle.click();
  }
  await expect(page.locator(".grid-grouped-add-row")).toHaveCount(
    expectedDepth1Count,
    { timeout: 10000 }
  );
}

async function clickAddRowInGroup(
  page: Page,
  cat: CategoryName,
  done: Completed
) {
  const addRow = page.locator(`.grid-grouped-add-row${leafSelector(cat, done)}`);
  await expect(
    addRow,
    `expected exactly one + Add row trailer for ${cat} / ${done}`
  ).toHaveCount(1);
  await addRow.click();
}

async function waitForNewRowInBackend(beforeRowIds: number[]) {
  const seen = new Set(beforeRowIds);
  let newRow: { id: number; [k: string]: any } | undefined;
  await expect
    .poll(
      async () => {
        const rows = await listRows(user, table);
        newRow = rows.find((r) => !seen.has(r.id));
        return newRow !== undefined;
      },
      {
        message: "expected the BE to create a new row",
        timeout: 10000,
      }
    )
    .toBe(true);
  return newRow!;
}

async function expectRowRendersUnderItsBanner(
  page: Page,
  rowId: number,
  cat: CategoryName,
  done: Completed
) {
  const rowLocator = page.locator(`.grid-grouped-row[data-row-id="${rowId}"]`);
  await expect(
    rowLocator,
    `row ${rowId} should render in the DOM`
  ).toBeVisible({ timeout: 10000 });

  const banner = page.locator(
    `.grid-grouped-banner[data-depth="1"]${leafSelector(cat, done)}`
  );
  const rowTop = await elementTop(rowLocator);
  const bannerTop = await elementTop(banner);
  expect(
    rowTop,
    `row ${rowId} must render below its group's banner`
  ).toBeGreaterThan(bannerTop);

  // The row must also be above the NEXT depth-1 banner (or the next
  // top-level banner, whichever comes first), so it can't have
  // leaked into a neighbouring group's pixel range.
  const nextBoundary = await page.evaluate(
    ({ rowTopPx }) => {
      const banners = Array.from(
        document.querySelectorAll(
          '.grid-grouped-banner[data-depth="0"], .grid-grouped-banner[data-depth="1"]'
        )
      ) as HTMLElement[];
      const tops = banners
        .map((b) => parseInt(b.style.top, 10) || 0)
        .filter((t) => t > rowTopPx)
        .sort((a, b) => a - b);
      return tops.length > 0 ? tops[0] : null;
    },
    { rowTopPx: rowTop }
  );
  if (nextBoundary !== null) {
    expect(
      rowTop,
      `row ${rowId} must not cross into the next group`
    ).toBeLessThan(nextBoundary);
  }
}

async function elementTop(
  locator: ReturnType<Page["locator"]>
): Promise<number> {
  return locator.evaluate(
    (el) => parseInt((el as HTMLElement).style.top, 10) || 0
  );
}
