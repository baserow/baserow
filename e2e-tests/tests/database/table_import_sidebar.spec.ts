import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { getClient } from "../../client";

test.describe("Import into existing table from the sidebar context menu", () => {
  test("imports CSV rows into the table via the table three-dots menu", async ({
    page,
    workspacePage,
  }) => {
    test.setTimeout(60000);
    // Tall viewport so the sidebar Context menu fits and doesn't self-close.
    await page.setViewportSize({ width: 1440, height: 1200 });

    const user = workspacePage.user;
    const db = await createDatabase(
      user,
      "SidebarImportDb",
      workspacePage.workspace
    );
    // One "Name" field with a single existing row ("First").
    const table = await createTable(user, "Target", db, [["Name"], ["First"]]);

    await workspacePage.goto();
    await page.getByTitle("SidebarImportDb").click();
    await page.getByText("Target").click();

    // Open the table's sidebar three-dots menu. The Context self-hides if it
    // doesn't fit the viewport and the first click can land before hydration
    // settles, so retry until the "Import file" item is actually visible.
    await page.getByText("Target").first().hover();
    const optsBtn = page.locator(".tree__sub > .tree__options").first();
    const importItem = page.locator(
      '.context__menu-item-link:visible:has-text("Import file")'
    );
    await expect(async () => {
      await optsBtn.click();
      await expect(importItem).toBeVisible({ timeout: 1000 });
    }).toPass({ timeout: 15000 });
    await importItem.click();

    // The import modal for THIS existing table.
    const modal = page
      .locator(".modal__box")
      .filter({ hasText: "Import into Target" });
    await expect(modal).toBeVisible();

    // Choose the CSV importer and upload a small CSV whose header matches the
    // primary field so the columns auto-map.
    await modal
      .locator(".choice-items__link")
      .filter({ hasText: "CSV file" })
      .click();
    const csv = "Name\nAlice\nBob\nCarol";
    await modal.locator('input[type="file"]').setInputFiles({
      name: "people.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv, "utf-8"),
    });
    // The preview renders once parsing succeeds (regression guard: previously
    // the modal threw on unpopulated fields and hung on "Parsing data").
    await expect(modal.getByText("people.csv")).toBeVisible({ timeout: 15000 });

    await modal.getByRole("button", { name: "Import" }).click();

    // The import must actually add the rows: 1 existing + 3 imported = 4.
    await expect
      .poll(
        async () => {
          const resp: any = await getClient(user).get(
            `database/rows/table/${table.id}/?size=200&user_field_names=true`
          );
          return resp.data.count;
        },
        { timeout: 30000 }
      )
      .toBe(4);

    const resp: any = await getClient(user).get(
      `database/rows/table/${table.id}/?size=200&user_field_names=true`
    );
    const names = resp.data.results.map((r: any) => r.Name);
    expect(names).toEqual(
      expect.arrayContaining(["First", "Alice", "Bob", "Carol"])
    );
  });
});
