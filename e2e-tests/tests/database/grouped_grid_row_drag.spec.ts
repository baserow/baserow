/**
 * Grouped grid: row drag-handle reorders a row inside its section.
 *
 * Test flow per case:
 *   1. Seed a single Design section with 3 rows in known order.
 *   2. Drag the source row's handle and drop it on a different row
 *      in the same section.
 *   3. Verify both the BE row order (via the rows API) and the DOM
 *      order match the expected outcome.
 *
 * A "drop on self" sub-test confirms that a mousedown + immediate
 * mouseup on the handle (no movement) is a no-op — neither BE nor
 * DOM order changes.
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
import { createRows, deleteRows, listRows } from "../../fixtures/database/rows";
import {
  createViewGroupBy,
  getDefaultGridView,
  View,
} from "../../fixtures/database/view";

// ── Shared state, populated once in beforeAll ─────────────────────
//
// Setup goes through plain HTTP fixtures (no Page) so it's safe in
// `beforeAll` — Playwright forbids `page`/`context` fixtures there.
// Each test authenticates fresh via a token redirect in beforeEach.
let user: User;
let database: Database;
let table: Table;
let view: View;
let categoryField: Field;
let designOptionId: number;
const baseUrl = process.env.PUBLIC_WEB_FRONTEND_URL || "http://localhost:3000";
// Row ids of the three Design rows we seed, in BE-order at fetch time.
let seededRowIds: number[] = [];

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  user = await createUser();
  const workspace = await createWorkspace(user);

  database = await createDatabase(user, "groupedRowDragDb", workspace);
  table = await createTable(user, "Projects", database);
  await deleteAllNonPrimaryFieldsFromTable(user, table);
  // The BE auto-creates two empty rows on table create; delete them
  // so our seeded rows are the only ones rendered.
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

  // Re-read to learn the BE-assigned option id.
  const refreshed = await getFieldsForTable(user, table);
  const cat = refreshed.find((f) => f.id === categoryField.id)!;
  designOptionId = cat.fieldSettings.select_options[0].id;

  // Seed three rows in the Design section.
  const created = await createRows(user, table, [
    { Name: "Alpha", Category: designOptionId },
    { Name: "Beta", Category: designOptionId },
    { Name: "Gamma", Category: designOptionId },
  ]);
  seededRowIds = created.map((r: { id: number }) => r.id);

  view = await getDefaultGridView(user, table);
  await createViewGroupBy(user, view, categoryField);
});

// ── Per-test page bootstrap ───────────────────────────────────────
test.beforeEach(async ({ page }) => {
  await page.context().addCookies([
    {
      name: "baserow_dashboard_alert_closed_v2",
      value: "true",
      domain: "localhost",
      path: "/",
    },
  ]);
  // Token-based auth → land on the table page in one hop.
  await page.goto(`${baseUrl}?token=${user.refreshToken}`);
  await page.goto(`${baseUrl}/database/${database.id}/table/${table.id}`);
  await expect(page.locator(".grid-grouped")).toBeVisible({ timeout: 20000 });
  await expandDesignGroup(page);
});

// ── Tests ─────────────────────────────────────────────────────────

test(
  "drag-handle drop on the row below swaps the two rows",
  { tag: "@grouped" },
  async ({ page }) => {
    const [alphaId, betaId, gammaId] = seededRowIds;

    // Sanity: rows render in the seeded order [Alpha, Beta, Gamma].
    await expectDomOrder(page, [alphaId, betaId, gammaId]);

    // Act: drag Alpha onto Beta. Drop lands inside Beta's upper half,
    // which the snap algorithm reads as "drop above Beta" — but
    // since Alpha is the source and Beta sits below, the row moves
    // down, swapping their positions.
    await dragRowOntoRow(page, alphaId, betaId);

    // BE order: Beta before Alpha before Gamma.
    await expectBackendOrder([betaId, alphaId, gammaId]);
    // DOM order matches.
    await expectDomOrder(page, [betaId, alphaId, gammaId]);
  },
);

test(
  "drag-handle click without movement leaves the row in place",
  { tag: "@grouped" },
  async ({ page }) => {
    // The previous test in this file (drag swap) reorders the rows
    // and the order persists in the shared database. Snapshot
    // whatever order is *currently* in BE + DOM and assert that the
    // mousedown-mouseup (without movement) leaves it untouched.
    const beforeOrder = await fetchBackendOrder();
    const sourceId = beforeOrder[0];

    await clickRowDragHandleWithoutMoving(page, sourceId);

    expect(await fetchBackendOrder()).toEqual(beforeOrder);
    await expectDomOrder(page, beforeOrder);
  },
);

// ── Helpers ───────────────────────────────────────────────────────

async function expandDesignGroup(page: Page) {
  // Grouped views default to "collapse-mode" — every banner starts
  // collapsed. Wait for the banner to render, then click its toggle
  // and wait for the rows to load.
  const banner = page.locator(
    `.grid-grouped-banner--collapsed[data-depth="0"]`,
  );
  await expect(banner).toHaveCount(1, { timeout: 15000 });
  await banner.locator(".grid-grouped-banner__toggle").click();
  await expect(page.locator(".grid-grouped-row")).toHaveCount(3, {
    timeout: 10000,
  });
}

async function expectDomOrder(page: Page, expectedIds: number[]) {
  await expect
    .poll(
      async () =>
        page
          .locator(".grid-grouped-row")
          .evaluateAll((rows) =>
            rows.map((r) => parseInt(r.getAttribute("data-row-id") ?? "0", 10)),
          ),
      { message: "DOM row order should match expected", timeout: 8000 },
    )
    .toEqual(expectedIds);
}

async function fetchBackendOrder(): Promise<number[]> {
  const rows = await listRows(user, table);
  // listRows returns BE order (asc by `order` field).
  return rows.map((r: { id: number }) => r.id);
}

async function expectBackendOrder(expectedIds: number[]) {
  await expect
    .poll(fetchBackendOrder, {
      message: "BE row order should match expected",
      timeout: 8000,
    })
    .toEqual(expectedIds);
}

// Drag the source row's `.grid-view__row-drag` handle to land
// inside the target row's upper half. The snap algorithm picks
// "drop above target" → which moves the source past the target.
async function dragRowOntoRow(page: Page, sourceId: number, targetId: number) {
  const sourceRow = page
    .locator(`.grid-grouped-row[data-row-id="${sourceId}"]`)
    .first();
  const target = page
    .locator(`.grid-grouped-row[data-row-id="${targetId}"]`)
    .first();
  // The drag handle is hover-revealed; hover the row first so the
  // handle has a non-zero bounding box.
  await sourceRow.hover();
  const handle = sourceRow.locator(".grid-view__row-drag");
  const handleBox = await handle.boundingBox();
  const targetBox = await target.boundingBox();
  if (!handleBox || !targetBox) {
    throw new Error("handle or target row not in viewport");
  }

  const startX = handleBox.x + handleBox.width / 2;
  const startY = handleBox.y + handleBox.height / 2;
  const dropX = targetBox.x + targetBox.width / 2;
  const dropY = targetBox.y + targetBox.height * 0.25;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  // A short intermediate move so the dragging component sees a
  // mousemove event before mouseup.
  await page.mouse.move(dropX, (startY + dropY) / 2, { steps: 5 });
  await page.mouse.move(dropX, dropY, { steps: 5 });
  await page.mouse.up();
}

async function clickRowDragHandleWithoutMoving(page: Page, rowId: number) {
  const sourceRow = page
    .locator(`.grid-grouped-row[data-row-id="${rowId}"]`)
    .first();
  await sourceRow.hover();
  const handle = sourceRow.locator(".grid-view__row-drag");
  const box = await handle.boundingBox();
  if (!box) throw new Error("handle not in viewport");
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.up();
  // Give the dragging component a tick to settle.
  await page.waitForTimeout(200);
}
