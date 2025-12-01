import { expect, test } from "../baserowTest";

test.describe("Automation application test suite", () => {
  test.beforeEach(async ({ workspacePage }) => {
    await workspacePage.goto();
  });

  test("Can create automation application - default name", async ({ page }) => {
    // Create an automation application
    await page.locator(".sidebar__new").getByText("Add new").click();
    await page.locator(".context__menu").getByText("Automation").click();
    await page.locator(".modal__box").getByText("Add automation").click();

    await expect(
      page.locator(".tree__link").getByText("Untitled Automation"),
      "Ensure the default automation name is displayed in the sidebar."
    ).toBeVisible();

    const workflowLink = page.getByRole("link", { name: "Workflow" });
    await expect(
      workflowLink,
      "Ensure the default Workflow has been created and is visible."
    ).toBeVisible();

    const chooseTriggerTitle = page.getByText("Choose an event...");
    await expect(
      chooseTriggerTitle,
      "Ensure the trigger chooser is visible."
    ).toBeVisible();
  });

  test("Can create automation application - custom name", async ({ page }) => {
    // Create an automation application
    await page.locator(".sidebar__new").getByText("Add new").click();
    await page.locator(".context__menu").getByText("Automation").click();

    // Specify a custom name for the automation
    await page.locator(".modal__box input").fill("Foo Automation");
    await page.locator(".modal__box").getByText("Add automation").click();

    await expect(
      page.locator(".tree__link").getByText("Foo Automation"),
      "Ensure the custom automation name is displayed in the sidebar."
    ).toBeVisible();

    const workflowLink = page.getByRole("link", { name: "Workflow" });
    await expect(
      workflowLink,
      "Ensure the default Workflow has been created and is visible."
    ).toBeVisible();

    const chooseTriggerTitle = page.getByText("Choose an event...");
    await expect(
      chooseTriggerTitle,
      "Ensure the trigger chooser is visible."
    ).toBeVisible();
  });
});
