import { expect, test } from "../baserowTest";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { createField } from "../../fixtures/database/field";

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

    // Create the database first, then navigate — avoids double goto which
    // can cause NS_BINDING_ABORTED errors on Firefox.
    await createDatabase(
      workspacePage.user,
      "ImportTestDb",
      workspacePage.workspace
    );
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

    // Generate a large CSV (20000 rows) so the backend job takes long enough
    // to survive a page reload cycle
    const csvContent = generateLargeCsv(20000);
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

    // Wait for the backend job to be created (not just the frontend upload
    // phase) — otherwise a reload during upload would leave nothing to restore.
    await page.waitForFunction(
      () => {
        const nuxt =
          (window as any).useNuxtApp?.() || (window as any).__nuxt_app__;
        const store =
          nuxt?.$store ||
          nuxt?.vueApp?.config?.globalProperties?.$store;
        if (!store) return false;
        return store.state.job.items.some(
          (j: any) => j.type === "file_import" && j.state !== "finished"
        );
      },
      { timeout: 30000 }
    );

    // Reload the page while the import is still running. We deliberately
    // don't wait for "networkidle" — the job poller fires every 2s, so
    // networkidle won't settle and would eat the test budget. The next
    // click auto-waits for the title to appear.
    await page.reload();

    // Navigate back to the database
    await page.getByTitle("ImportTestDb").click();

    // Wait for the job store to be populated with the running job
    // (the poller runs on app mount and fetches unfinished jobs)
    await page.waitForFunction(
      () => {
        const nuxt =
          (window as any).useNuxtApp?.() || (window as any).__nuxt_app__;
        const store =
          nuxt?.$store ||
          nuxt?.vueApp?.config?.globalProperties?.$store;
        if (!store || !store.state.job.loaded) return false;
        return store.state.job.items.some(
          (j: any) => j.type === "file_import" && j.state !== "finished"
        );
      },
      { timeout: 15000 }
    );

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
    const cancelButton = modalAfterReload.locator(
      ".modal-progress__cancel-button"
    );
    await expect(cancelButton).toBeVisible({ timeout: 5000 });

    // Click cancel and verify the job is cancelled. Use force:true because
    // the surrounding ProgressBar updates its value rapidly and Vue can
    // re-render the actions block, briefly detaching the button.
    await cancelButton.click({ force: true });

    // The cancel button should disappear (job is no longer running)
    await expect(cancelButton).toBeHidden({ timeout: 15000 });
  });

  test("Create empty table with a given name", async ({
    page,
    workspacePage,
  }) => {
    await createDatabase(
      workspacePage.user,
      "EmptyTableDb",
      workspacePage.workspace
    );
    await workspacePage.goto();
    await page.getByTitle("EmptyTableDb").click();

    await page.getByText("New table").click();

    const modal = page
      .locator(".modal__box:not(.modal__box--full-screen)")
      .filter({ hasText: "Create new table" });
    await expect(modal).toBeVisible();

    // "Start with a new table" is the default selection — no importer needed,
    // so the only text input on screen is the Name field.
    const tableName = "Empty Table";
    await modal.getByRole("textbox").first().fill(tableName);

    await modal.getByRole("button", { name: "Add table" }).click();

    // The user is redirected to the newly-created table — its name appears
    // in the sidebar and the URL points at /database/.../table/...
    await expect(page.getByTitle(tableName)).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/\/database\/\d+\/table\/\d+/);
  });

  test("CSV import into existing table restores running job after reload", async ({
    page,
    workspacePage,
  }) => {
    test.setTimeout(60000);

    // Create everything via API first, then navigate once — avoids double
    // goto which can cause NS_BINDING_ABORTED errors on Firefox.
    const existingDb = await createDatabase(
      workspacePage.user,
      "ExistingImportDb",
      workspacePage.workspace
    );
    const table = await createTable(workspacePage.user, "Target", existingDb);
    // Add an extra text field so we have something to map CSV columns to
    // (the primary "Name" field is auto-created)
    await createField(workspacePage.user, "Email", "text", {}, table);

    await workspacePage.goto();
    await page.getByTitle("ExistingImportDb").click();
    await page.getByText("Target").click();

    // Open the view context menu (the vertical dots icon in the view header)
    // and click "Import file"
    await page.locator(".header__filter-link .baserow-icon-more-vertical").click();
    await page.getByText("Import file").click();

    // The import-file modal should appear
    const modal = page
      .locator(".modal__box")
      .filter({ hasText: "Import into Target" });
    await expect(modal).toBeVisible();

    // Select "CSV file" importer
    await modal
      .locator(".choice-items__link")
      .filter({ hasText: "CSV file" })
      .click();

    // Upload a large CSV (20000 rows so the job survives a reload cycle)
    const csvContent2 = generateLargeCsv(20000);
    const csvBuffer = Buffer.from(csvContent2, "utf-8");
    const fileInput = modal.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "existing-import.csv",
      mimeType: "text/csv",
      buffer: csvBuffer,
    });

    // Wait for the file to be parsed and the field mapping to show
    await expect(modal.getByText("existing-import.csv")).toBeVisible({
      timeout: 15000,
    });

    // Click Import
    await modal.getByRole("button", { name: "Import" }).click();

    // Wait for the backend job to be created (not just the frontend upload phase)
    await page.waitForFunction(
      () => {
        const nuxt =
          (window as any).useNuxtApp?.() || (window as any).__nuxt_app__;
        const store =
          nuxt?.$store ||
          nuxt?.vueApp?.config?.globalProperties?.$store;
        if (!store) return false;
        return store.state.job.items.some(
          (j: any) => j.type === "file_import" && j.state !== "finished"
        );
      },
      { timeout: 30000 }
    );

    // Reload while the import is running. Don't wait for "networkidle"
    // here — the job poller fires every 2s so networkidle won't settle and
    // would consume the test budget before the post-reload checks run.
    await page.reload();

    // After reload, navigate back to the table and reopen the import modal
    await page.getByTitle("ExistingImportDb").click();
    await page.getByText("Target").click();

    // Wait for the job store to be populated with the running job
    await page.waitForFunction(
      () => {
        const nuxt =
          (window as any).useNuxtApp?.() || (window as any).__nuxt_app__;
        const store =
          nuxt?.$store ||
          nuxt?.vueApp?.config?.globalProperties?.$store;
        if (!store || !store.state.job.loaded) return false;
        return store.state.job.items.some(
          (j: any) => j.type === "file_import" && j.state !== "finished"
        );
      },
      { timeout: 15000 }
    );

    await page
      .locator(".header__filter-link .baserow-icon-more-vertical")
      .click();
    await page.getByText("Import file").click();

    const modalAfterReload = page
      .locator(".modal__box")
      .filter({ hasText: "Import into Target" });
    await expect(modalAfterReload).toBeVisible();

    // The cancel button should be visible (meaning the running job was restored)
    const cancelButton = modalAfterReload.locator(
      ".modal-progress__cancel-button"
    );
    await expect(cancelButton).toBeVisible({ timeout: 10000 });

    // Cancel and verify the job stops. Use force:true because the
    // ProgressBar inside the same modal re-renders rapidly and can
    // briefly detach the button between visibility check and click.
    await cancelButton.click({ force: true });
    await expect(cancelButton).toBeHidden({ timeout: 10000 });
  });
});
