import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";

/**
 * Generate a large CSV string so the import job takes long enough
 * to survive a page reload (the backend needs to validate + create rows).
 */
function generateLargeCsv(rowCount: number): string {
  const header = "Name,Email,Age,City,Country,Notes";
  const rows = [header];
  for (let i = 0; i < rowCount; i++) {
    rows.push(
      `User ${i},user${i}@example.com,${20 + (i % 60)},City ${i % 100},Country ${i % 30},Some notes for row ${i} with extra padding to make the payload larger`
    );
  }
  return rows.join("\n");
}

test.describe("Table import job restore after reload", () => {
  test("CSV import into new table restores importer type and file name after reload", async ({
    page,
    workspacePage,
  }) => {
    // Increase timeout — large CSV upload + import takes time
    test.setTimeout(60000);

    await workspacePage.goto();
    const database = await createDatabase(
      workspacePage.user,
      "ImportTestDb",
      workspacePage.workspace
    );

    // Navigate to the workspace so the database appears in the sidebar
    await workspacePage.goto();
    await page.getByTitle("ImportTestDb").click();

    // Click "+ New table" in the sidebar
    await page.getByText("New table").click();

    // The "Create new table" modal
    const modal = page
      .locator(".modal__box:not(.modal__box--full-screen)")
      .filter({ hasText: "Create new table" });
    await expect(modal).toBeVisible();

    // Select "Import a CSV file"
    await modal.getByText("Import a CSV file").click();

    // Generate a large CSV (5000 rows) so the backend job takes a few seconds
    const csvContent = generateLargeCsv(5000);
    const buffer = Buffer.from(csvContent, "utf-8");

    // Upload the CSV file
    const fileInput = modal.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "test-contacts.csv",
      mimeType: "text/csv",
      buffer,
    });

    // Wait for the CSV to be parsed and the file name to appear
    await expect(modal.getByText("test-contacts.csv")).toBeVisible({
      timeout: 15000,
    });

    // Fill in the table name
    const nameInput = modal.locator('input[name="name"]');
    if (await nameInput.isVisible()) {
      await nameInput.fill("Contacts Import");
    }

    // Click the submit button to start the import
    await modal.getByRole("button", { name: "Add table" }).click();

    // Wait for the progress bar to appear (import is in progress)
    await expect(modal.locator(".progress-bar")).toBeVisible({
      timeout: 30000,
    });

    // Reload the page while the import is still running
    await page.reload();

    // Navigate back to the database
    await page.getByTitle("ImportTestDb").click();

    // Click "+ New table" again to reopen the modal
    await page.getByText("New table").click();
    const modalAfterReload = page
      .locator(".modal__box:not(.modal__box--full-screen)")
      .filter({ hasText: "Create new table" });
    await expect(modalAfterReload).toBeVisible();

    // Select "Import a CSV file" (needed to mount CreateTable with the right type)
    await modalAfterReload
      .locator(".choice-items__link")
      .filter({ hasText: "Import a CSV file" })
      .click();

    // The restored UI should show the original file name
    await expect(
      modalAfterReload.getByText("test-contacts.csv")
    ).toBeVisible({ timeout: 10000 });

    // A progress bar or cancel button should be visible (job still running)
    const cancelButton = modalAfterReload.getByRole("button", {
      name: "Cancel",
    });
    await expect(cancelButton).toBeVisible({ timeout: 5000 });

    // Click cancel and verify the job is cancelled
    await cancelButton.click();

    // The cancel button should disappear (job is no longer running)
    await expect(cancelButton).toBeHidden({ timeout: 10000 });

    // The modal should now show the normal create-table form again
    // (meaning the job was cleared and the restored state was reset)
    await expect(
      modalAfterReload.getByRole("button", { name: "Add table" })
    ).toBeVisible({ timeout: 5000 });
  });
});
