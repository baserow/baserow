import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { createField } from "../../fixtures/database/field";
import { getDefaultGridView, patchView } from "../../fixtures/database/view";
import { TablePage } from "../../pages/database/tablePage";

// Regression: opening a link-row field that is already limited to a view used
// to show an empty "No items available" dropdown because the linked table's
// views were never fetched on mount, so the saved selection looked gone.
test.describe("Link-row 'Limit selection to view'", () => {
  test.describe.configure({ timeout: 60_000 });

  test("editing a field limited to a view shows the saved view", async ({
    page,
    goto,
    workspacePage,
  }) => {
    const user = workspacePage.user;
    const workspace = workspacePage.workspace;

    const database = await createDatabase(user, "Limit View DB", workspace);

    // Linked table whose grid view limits the selection. The view gets a
    // distinctive name so it cannot be confused with the editing table's own
    // default "Grid" view.
    const projects = await createTable(user, "Projects", database, [
      ["Name"],
      ["Apollo"],
    ]);
    const limitView = await getDefaultGridView(user, projects);
    await patchView(user, limitView, { name: "Active Projects" });

    // Table holding the link-row field, already limited to the view above.
    const customers = await createTable(user, "Customers", database, [
      ["Name"],
      ["Ada"],
    ]);
    await createField(
      user,
      "Linked projects",
      "link_row",
      {
        link_row_table_id: projects.id,
        link_row_limit_selection_view_id: limitView.id,
      },
      customers,
    );

    const tablePage = new TablePage({ page, goto });
    await tablePage.goToTable(customers);

    // Open the link-row field's context menu, then "Edit field".
    const fieldHeader = page
      .locator(".grid-view__description", { hasText: "Linked projects" })
      .first();
    await fieldHeader.hover();
    await fieldHeader.locator(".grid-view__description-icon-trigger").click();
    await page
      .locator(".context__menu-item-link")
      .getByText("Edit field", { exact: true })
      .click();

    // The view the selection is limited to must be shown as the dropdown's
    // selected value, instead of falling back to the "Make a choice"
    // placeholder (the "my view selection is gone" bug).
    await expect(
      page.locator(".dropdown__selected-text", { hasText: "Active Projects" })
    ).toBeVisible();
    await expect(page.getByText("Make a choice")).toBeHidden();
  });
});
