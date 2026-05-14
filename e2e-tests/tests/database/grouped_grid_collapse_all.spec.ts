/**
 * Grouped grid: "Collapse all" / "Expand all" buttons in the group-by
 * popover toggle the visibility of every section in one shot.
 *
 * Seed: rows across two single-level groups (Category=Design and
 * Category=Marketing). With one group-by field, depth=0 banners are
 * the leaf sections.
 *
 * Tests:
 *   1) Collapse all leaves no row visible (only headers remain).
 *   2) Expand all puts every row back on screen.
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
let marketingOptionId: number;
const baseUrl = process.env.PUBLIC_WEB_FRONTEND_URL || "http://localhost:3000";

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  user = await createUser();
  const workspace = await createWorkspace(user);

  database = await createDatabase(user, "groupedCollapseAllDb", workspace);
  table = await createTable(user, "Projects", database);
  await deleteAllNonPrimaryFieldsFromTable(user, table);
  // The BE creates two empty rows by default on table create; delete
  // them so the visible row count matches our seed exactly.
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
    {
      select_options: [
        { value: "Design", color: "blue" },
        { value: "Marketing", color: "green" },
      ],
    },
    table,
  );
  const refreshed = await getFieldsForTable(user, table);
  const cat = refreshed.find((f) => f.id === categoryField.id)!;
  designOptionId = cat.fieldSettings.select_options.find(
    (o: { value: string }) => o.value === "Design",
  ).id;
  marketingOptionId = cat.fieldSettings.select_options.find(
    (o: { value: string }) => o.value === "Marketing",
  ).id;

  await createRows(user, table, [
    { Name: "D1", Category: designOptionId },
    { Name: "D2", Category: designOptionId },
    { Name: "M1", Category: marketingOptionId },
  ]);

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
  // Wait for at least the two banners we seeded to render. The BE may
  // include an additional banner for the implicit "empty" group, so we
  // assert "at least two" rather than an exact count.
  await expect
    .poll(
      async () =>
        page.locator('.grid-grouped-banner[data-depth="0"]').count(),
      { timeout: 15000 },
    )
    .toBeGreaterThanOrEqual(2);
});

// ── Tests ─────────────────────────────────────────────────────────

test(
  "Collapse all hides every section's rows",
  { tag: "@grouped" },
  async ({ page }) => {
    // Expand both groups so we have rows to start with.
    await expandAllVisibleGroups(page);
    await expect(page.locator(".grid-grouped-row")).toHaveCount(3, {
      timeout: 5000,
    });

    await clickGroupByMenuAction(page, "Collapse all");

    // No row should remain in the DOM and every visible banner is
    // collapsed (the actual banner count varies with the BE's
    // empty-group handling, so we check "no rows" as the strong
    // signal instead).
    await expect(page.locator(".grid-grouped-row")).toHaveCount(0, {
      timeout: 5000,
    });
    await expect(
      page.locator('.grid-grouped-banner:not(.grid-grouped-banner--collapsed)[data-depth="0"]'),
    ).toHaveCount(0);
  },
);

test(
  "Expand all reveals every section's rows",
  { tag: "@grouped" },
  async ({ page }) => {
    // Start from the default (all collapsed in a multi-group view —
    // here single-group so just confirm starting state).
    await clickGroupByMenuAction(page, "Collapse all");
    await expect(page.locator(".grid-grouped-row")).toHaveCount(0);

    await clickGroupByMenuAction(page, "Expand all");

    // Both sections expand and all rows render.
    await expect(
      page.locator('.grid-grouped-banner--collapsed[data-depth="0"]'),
    ).toHaveCount(0, { timeout: 5000 });
    await expect(page.locator(".grid-grouped-row")).toHaveCount(3);
  },
);

// ── Helpers ───────────────────────────────────────────────────────

async function expandAllVisibleGroups(page: Page) {
  // Loop until no collapsed banner remains. Re-query each iteration
  // because expanding one shifts the layout and stale handles can
  // become detached.
  for (let safety = 0; safety < 10; safety++) {
    const collapsed = page.locator(
      '.grid-grouped-banner--collapsed[data-depth="0"]',
    );
    if ((await collapsed.count()) === 0) return
    await collapsed.first().locator(".grid-grouped-banner__toggle").click()
    await page.waitForTimeout(150)
  }
}

// Open the group-by header popover and click the named action button
// in its footer.
async function clickGroupByMenuAction(page: Page, label: string) {
  const popover = page.locator(".group-bys");
  // The "Group by" link is a toggle. If the popover is hidden, open
  // it; if it's already open from a previous action, leave it alone.
  const popoverIsOpen = await popover
    .evaluate((el) => !el.classList.contains("visibility-hidden"))
    .catch(() => false);
  if (!popoverIsOpen) {
    await page
      .locator(".header__filter-link", { hasText: "Group by" })
      .first()
      .click();
    await expect(popover).toBeVisible({ timeout: 5000 });
  }
  const button = popover
    .locator(".group-bys__collapse-actions .button-text", { hasText: label })
    .first();
  await expect(button).toBeVisible({ timeout: 5000 });
  await button.click();
  // Let the dispatch + refetch finish before the caller asserts.
  await page.waitForTimeout(500);
}
