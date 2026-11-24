import type { Locator } from "@playwright/test";
import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createTable, listTables } from "../../fixtures/database/table";
import { getClient } from "../../client";

async function clickTableMenuItem(row: Locator, name: string) {
  const item = row.page().locator(".context__menu-item-link:visible", {
    hasText: name,
  });
  await row.hover();
  // The first click can land before the sidebar finishes rendering.
  await expect(async () => {
    await row.locator(".tree__options").click();
    await expect(item).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15000 });
  await item.click();
}

test.describe("Import into existing table from the sidebar context menu", () => {
  test("undo and redo target CSV rows imported into another database from the sidebar", async ({
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
    const activeDb = await createDatabase(
      user,
      "Active DB",
      workspacePage.workspace
    );
    const activeTable = await createTable(user, "Before rename", activeDb);

    await workspacePage.goto();
    const sidebar = page.locator(".sidebar");
    await sidebar.getByTitle(activeDb.name, { exact: true }).click();
    await sidebar.getByTitle(activeTable.name, { exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/table/${activeTable.id}(?:/|$)`));
    const activeRow = sidebar.locator(".tree__sub.active");
    await clickTableMenuItem(activeRow, "Rename");
    const editor = activeRow.locator('[contenteditable="true"]');
    await editor.fill("After rename");
    await editor.press("Enter");
    await expect
      .poll(async () => (await listTables(user, activeDb))[0].name)
      .toBe("After rename");
    await sidebar.getByTitle(db.name, { exact: true }).click();

    const targetRow = sidebar.locator("li.tree__sub", { hasText: table.name });
    await clickTableMenuItem(targetRow, "Import file");

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

    const rowNames = async () => {
      const { data } = await getClient(user).get(
        `database/rows/table/${table.id}/?user_field_names=true`
      );
      return data.results.map((row: { Name: string }) => row.Name);
    };
    const imported = ["First", "Alice", "Bob", "Carol"];
    await expect.poll(rowNames, { timeout: 30000 }).toEqual(imported);
    await expect(modal).toBeHidden();
    await expect(page).toHaveURL(new RegExp(`/table/${activeTable.id}(?:/|$)`));

    await page.keyboard.press("ControlOrMeta+z");
    await expect.poll(rowNames).toEqual(["First"]);
    expect((await listTables(user, activeDb))[0].name).toBe("After rename");
    await page.keyboard.press("ControlOrMeta+Shift+z");
    await expect.poll(rowNames).toEqual(imported);
    expect((await listTables(user, activeDb))[0].name).toBe("After rename");
  });
});
