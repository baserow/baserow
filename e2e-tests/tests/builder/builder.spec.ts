import { expect, test } from "../baserowTest";

test.describe("Builder application test suite", () => {
  test.beforeEach(async ({ workspacePage }) => {
    await workspacePage.goto();
  });

  test("Can create builder application", async ({ page }) => {
    // Create a builder application
    await page.locator(".sidebar__new").getByText("Add new").click();
    await page.locator(".context__menu").getByText("Application").click();
    await page.locator(".modal__box").getByText("Add application").click();

    await expect(
      page.locator(".page-editor").getByText("Page settings"),
      "Check we see the default page."
    ).toBeVisible();
  });

  test("Can create builder application with name", async ({ page }) => {
    // Create a builder application
    await page.locator(".sidebar__new").getByText("Add new").click();
    await page.locator(".context__menu").getByText("Application").click();
    // Change the application name
    await page.locator(".modal__box input").fill("My super application");
    await page.locator(".modal__box").getByText("Add application").click();

    await expect(
      page.locator(".tree__link").getByText("My super application"),
      "Checks the name of the application is displayed in the sidebar."
    ).toBeVisible();
  });
});
