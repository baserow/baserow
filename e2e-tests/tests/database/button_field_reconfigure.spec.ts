/**
 * A button whose action writes to a trashed field says so on the cell, before
 * anyone clicks it, and heals when the field comes back (ADR 006 section 8).
 * The trash and restore happen through the API, as another user would do them,
 * so the grid only learns of them through the realtime broadcast.
 */

import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import { setupGrid, GridSetupResult } from "../../fixtures/database/gridSetup";
import { createRowAction } from "../../fixtures/database/workflowAction";
import { deleteField, restoreField } from "../../fixtures/database/field";

let g: GridSetupResult;

test.describe("Button field reconfigure state", () => {
  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Reconfigure DB",
      tableName: "Tickets",
      fields: [
        { name: "Status", type: "text" },
        { name: "Go", type: "button", settings: { label: "Go" } },
      ],
      rows: [{ Name: "Ada", Status: "todo" }],
    });

    await createRowAction(g.user, g.fieldByName["Go"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'done'" }],
    });
  });

  test("trashing the mapped field disables the button until it is restored", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Deleting "Status" removes a column, which shifts the "Go" button's
    // field index, so it is located by its label instead.
    const button = page.getByRole("button", { name: "Go" });
    await expect(button).toBeEnabled();

    await deleteField(g.user, g.fieldByName["Status"]);

    await expect(button).toBeDisabled();
    await expect(button.locator(".iconoir-warning-triangle")).toBeVisible();

    await restoreField(g.user, g.fieldByName["Status"]);

    await expect(button).toBeEnabled();
    await expect(button.locator(".iconoir-warning-triangle")).toHaveCount(0);
  });
});
