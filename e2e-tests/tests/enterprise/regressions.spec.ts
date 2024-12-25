import { expect, test } from "../baserowTest";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../fixtures/licence";

test.describe("Enterprise regression tests", () => {
  let license: License;

  test.beforeEach(async ({ page, workspacePage }) => {
    // Create a new Enterprise license.
    license = await createLicense(ENTERPRISE_LICENSE);
    await workspacePage.goto();
  });

  test("#1606: a non-staff user with an enterprise licence can login and view templates @enterprise", async ({
    workspacePage,
  }) => {
    // Click "Create new" > "From template".
    const templateModal =
      await workspacePage.sidebar.openCreateAppFromTemplateModal();

    const templatesLoadingSpinner = templateModal.getLoadingSpinner();

    await expect(
      templatesLoadingSpinner,
      "Checking that the templates modal spinner is hidden."
    ).toBeHidden();
  });

  test.afterEach(async () => {
    await deleteLicense(license);
  });
});
