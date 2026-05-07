import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createField } from "../../fixtures/database/field";
import { createTable, Table } from "../../fixtures/database/table";
import {
  createViewGroupBy,
  getDefaultGridView,
} from "../../fixtures/database/view";
import { createRows } from "../../fixtures/database/rows";

test.describe("Grid view group-by collapse", () => {
  test("shows group value and count in the primary field area and toggles rows", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByCollapse",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design" },
      { Name: "Modernize logo", Category: "Design" },
      { Name: "User portal", Category: "Development" },
      { Name: "Barcode app", Category: "Development" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    const firstHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Design" });
    await expect(firstHeader).toHaveCount(1);
    await expect(
      firstHeader.locator(".grid-view__group-header-count"),
    ).toHaveText("2");

    const countBox = await firstHeader
      .locator(".grid-view__group-header-count")
      .boundingBox();
    const categoryHeaderBox = await page
      .locator(".grid-view__right .grid-view__head")
      .getByText("Category")
      .boundingBox();
    expect(countBox).not.toBeNull();
    expect(categoryHeaderBox).not.toBeNull();
    expect(countBox!.x).toBeLessThan(categoryHeaderBox!.x);

    await expect(page.getByText("Rebranding website")).toBeVisible();
    await expect(page.getByText("Modernize logo")).toBeVisible();

    await firstHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toHaveCount(0);
    await expect(page.getByText("User portal")).toBeVisible();

    await firstHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toBeVisible();
    await expect(page.getByText("Modernize logo")).toBeVisible();
  });

  test("keeps collapsed sibling headers visible when only the first group has rows", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByAllButFirstCollapsed",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design" },
      { Name: "Modernize logo", Category: "Design" },
      { Name: "User portal", Category: "Development" },
      { Name: "Barcode app", Category: "Development" },
      { Name: "Customer journey", Category: "Research" },
      { Name: "Paid ads", Category: "Marketing" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    await page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Development" })
      .locator(".grid-view__group-header-toggle")
      .click();
    await page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Research" })
      .locator(".grid-view__group-header-toggle")
      .click();
    await page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Marketing" })
      .locator(".grid-view__group-header-toggle")
      .click();

    await page.reload();

    await expect(page.getByText("Rebranding website")).toBeVisible();
    await expect(page.getByText("Modernize logo")).toBeVisible();

    const headers = page.locator(".grid-view__right .grid-view__group-header");
    await expect(headers.filter({ hasText: "Design" })).toBeVisible();
    await expect(headers.filter({ hasText: "Development" })).toBeVisible();
    await expect(headers.filter({ hasText: "Research" })).toBeVisible();
    await expect(headers.filter({ hasText: "Marketing" })).toBeVisible();
  });

  test("renders nested group-by with two sticky levels and isolates collapse to the right child", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByNested",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );
    const priorityField = await createField(
      workspacePage.user,
      "Priority",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design", Priority: "High" },
      { Name: "Modernize logo", Category: "Design", Priority: "Low" },
      { Name: "User portal", Category: "Development", Priority: "High" },
      { Name: "Barcode app", Category: "Development", Priority: "High" },
      { Name: "Auth refactor", Category: "Development", Priority: "Low" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);
    await createViewGroupBy(workspacePage.user, view, priorityField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    const stickyHeaders = page.locator(
      ".grid-view__right .grid-view__sticky-group-header",
    );
    // The sticky stack should contain one header per group-by depth.
    await expect(stickyHeaders).toHaveCount(2);
    await expect(stickyHeaders.nth(0)).toContainText("Category");
    await expect(stickyHeaders.nth(0)).toContainText("Design");
    await expect(stickyHeaders.nth(1)).toContainText("Priority");

    // Collapsing the depth-1 "High" header inside Design should hide Design's
    // High row but leave Design's Low row visible — and must not affect
    // Development's High group.
    const designHighHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "High" })
      .first();
    await designHighHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toBeVisible();
    await expect(page.getByText("User portal")).toBeVisible();
    await expect(page.getByText("Barcode app")).toBeVisible();

    // Re-expanding restores the row.
    await designHighHeader.locator(".grid-view__group-header-toggle").click();
    await expect(page.getByText("Rebranding website")).toBeVisible();
  });

  test("collapsing the parent hides every child of that parent", async ({
    page,
    workspacePage,
  }) => {
    const database = await createDatabase(
      workspacePage.user,
      "GroupByParentCollapse",
      workspacePage.workspace,
    );
    const table: Table = await createTable(
      workspacePage.user,
      "Projects",
      database,
    );
    const categoryField = await createField(
      workspacePage.user,
      "Category",
      "text",
      {},
      table,
    );
    const priorityField = await createField(
      workspacePage.user,
      "Priority",
      "text",
      {},
      table,
    );

    await createRows(workspacePage.user, table, [
      { Name: "Rebranding website", Category: "Design", Priority: "High" },
      { Name: "Modernize logo", Category: "Design", Priority: "Low" },
      { Name: "User portal", Category: "Development", Priority: "High" },
      { Name: "Barcode app", Category: "Development", Priority: "Low" },
    ]);

    const view = await getDefaultGridView(workspacePage.user, table);
    await createViewGroupBy(workspacePage.user, view, categoryField);
    await createViewGroupBy(workspacePage.user, view, priorityField);

    await page.goto(`/database/${database.id}/table/${table.id}`);

    // Wait for initial render.
    await expect(page.getByText("Rebranding website")).toBeVisible();

    const designHeader = page
      .locator(".grid-view__right .grid-view__group-header")
      .filter({ hasText: "Design" })
      .first();
    await designHeader.locator(".grid-view__group-header-toggle").click();

    // All depth-1 children of Design and their rows should be gone, and
    // Development's children should remain.
    await expect(page.getByText("Rebranding website")).toHaveCount(0);
    await expect(page.getByText("Modernize logo")).toHaveCount(0);
    await expect(page.getByText("User portal")).toBeVisible();
    await expect(page.getByText("Barcode app")).toBeVisible();
  });
});
