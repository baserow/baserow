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
});
