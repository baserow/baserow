import { createBuilderElement } from "../../fixtures/builder/builderElement";
import { expect, test } from "../baserowTest";
import { baserowConfig } from "../../playwright.config";

test.describe("Builder page test suite", () => {
  test.beforeEach(async ({ builderPagePage }) => {
    await builderPagePage.goto();
  });

  test("Can create a page", async ({ page }) => {
    await page.getByText("New page").click();
    await page.getByText("Create page").waitFor();
    await page
      .locator(".modal__box")
      .getByPlaceholder("Enter a name...")
      .fill("Super page");
    await page
      .locator(".modal__box")
      .getByPlaceholder("Enter a path...")
      .fill("/complex/path");
    await page.locator(".button").getByText("Add page").click();
    await expect(page.getByText("Create page")).toBeHidden();
    await expect(
      page
        .locator(".preview-navigation-bar__address-bar-path")
        .getByText("/complex/path")
    ).toBeVisible();
  });

  test("Can open page settings", async ({ page }) => {
    await page.getByText("Page settings").click();
    await expect(page.locator(".box__title").getByText("Page")).toBeVisible();
  });

  test("Can change page settings", async ({ page }) => {
    await page.getByText("Page settings").click();

    await page
      .locator(".modal__box")
      .getByPlaceholder("Enter a name...")
      .fill("New page name");
    await page
      .locator(".modal__box")
      .getByPlaceholder("Enter a path...")
      .fill("/new/path");

    await page.locator(".button").getByText("Save").click();
    await expect(
      page.getByText("The page settings have been updated.")
    ).toBeVisible();

    await page.getByTitle("Close").click();
    await expect(page.locator(".box__title").getByText("Page")).toBeHidden();

    await expect(
      page
        .locator(".preview-navigation-bar__address-bar-path")
        .getByText("/new/path")
    ).toBeVisible();
  });

  test("Can create an element from empty page", async ({ page }) => {
    await page.getByText("Click to create an element").click();
    await page.getByText("Heading", { exact: true }).click();

    await expect(
      page.locator(".modal__box").getByText("Add new element")
    ).toBeHidden();
    await expect(
      page.locator(".element-preview__name-tag").getByText("Heading")
    ).toBeVisible();
  });

  test("Can create an element from element menu", async ({ page }) => {
    await page.locator(".header").getByText("Elements").click();
    await page
      .locator(".elements-context")
      .getByText("Element", { exact: true })
      .click();
    await page.getByText("Heading", { exact: true }).click();

    await expect(
      page.locator(".modal__box").getByText("Add new element")
    ).toBeHidden();
    await expect(
      page.locator(".element-preview__name-tag").getByText("Heading")
    ).toBeVisible();
  });

  test("Can add query parameter to page setting", async ({
    page,
    builderPagePage,
  }) => {
    await page.getByText("Page settings").click();

    await page
      .locator(".modal__box")
      .getByPlaceholder("Enter a name...")
      .fill("New page name");

    // Add two params
    await page
      .getByRole("button", { name: "Add query string parameter" })
      .click();
    await page
      .getByRole("button", { name: "Add another query string parameter" })
      .click();

    // Update the name of the two params
    await page
      .locator(".page-settings-query-params .form-input__wrapper")
      .getByRole("textbox")
      .nth(1)
      .fill("my_param");
    await page
      .locator(".page-settings-query-params .form-input__wrapper")
      .getByRole("textbox")
      .nth(0)
      .fill("my_param2");

    // Change the type of a the first param to numeric
    await page.locator(".dropdown").getByText("Text").first().click();
    await page.getByTitle("Numeric").first().click();

    const responsePromise = page.waitForResponse((response) => {
      return response
        .url()
        .endsWith(`api/builder/pages/${builderPagePage.builderPage.id}/`);
    });

    // Save the page
    await page.getByRole("button", { name: "Save" }).click();
    await expect(
      page.getByText("The page settings have been updated.")
    ).toBeVisible();

    // Close the modal
    await page.getByTitle("Close").click();
    await expect(page.locator(".box__title").getByText("Page")).toBeHidden();

    // Wait for page update
    await responsePromise;

    // Create a link programmatically, we don't want to test link
    await createBuilderElement(builderPagePage.builderPage, "link", {
      value: "'linkim'",
      navigate_to_page_id: builderPagePage.builderPage.id,
      query_parameters: [
        {
          name: "my_param2",
          value: "get('page_parameter.my_param2')",
        },
        {
          name: "my_param",
          value: "get('page_parameter.my_param')",
        },
      ],
    });

    await page.getByText("linkim");

    // Set the value of page parameters
    await page.getByLabel("my_param=").fill("foo");
    await page.getByLabel("my_param2=").fill("15");

    await expect(page.getByRole("link", { name: "linkim" })).toHaveAttribute(
      "href",
      /\?my_param2=15&my_param=foo/
    );
  });
});
