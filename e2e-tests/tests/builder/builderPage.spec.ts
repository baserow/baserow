import {expect, test} from "../baserowTest";

test.describe("Builder page test suite", () => {
  test.beforeEach(async ({builderPagePage}) => {
    await builderPagePage.goto();
  });

  test("Can create a page", async ({page}) => {
    await page.getByText("New page").click();
    await page.getByText("Create page").waitFor();
    await page
      .locator(".modal__wrapper")
      .getByPlaceholder("Enter a name...")
      .fill("Super page");
    await page
      .locator(".modal__wrapper")
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

  test("Can open page settings", async ({page}) => {
    await page.getByText("Page settings").click();
    await expect(page.locator(".box__title").getByText("Page")).toBeVisible();
  });

  test("Can change page settings", async ({page}) => {
    await page.getByText("Page settings").click();

    await page
      .locator(".modal__wrapper")
      .getByPlaceholder("Enter a name...")
      .fill("New page name");
    await page
      .locator(".modal__wrapper")
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

  test("Can create an element from empty page", async ({page}) => {
    await page.getByText("Click to create an element").click();
    await page.getByText("Heading", {exact: true}).click();

    await expect(
      page.locator(".modal__box").getByText("Add new element")
    ).toBeHidden();
    await expect(
      page.locator(".element-preview__name").getByText("Heading")
    ).toBeVisible();
  });

  test("Can create an element from element menu", async ({page}) => {
    await page.locator(".header").getByText("Elements").click();
    await page
      .locator(".elements-context")
      .getByText("Element", {exact: true})
      .click();
    await page.getByText("Heading", {exact: true}).click();

    await expect(
      page.locator(".modal__box").getByText("Add new element")
    ).toBeHidden();
    await expect(
      page.locator(".element-preview__name").getByText("Heading")
    ).toBeVisible();
  });


  test("Can add query parameter to page setting", async ({page}) => {
    await page.getByText("Page settings").click();

    await page
      .locator(".modal__wrapper")
      .getByPlaceholder("Enter a name...")
      .fill("New page name");

    await page.getByRole('button', {name: 'Add query string parameter'}).click();

    await page
      .locator(".page-settings-query-params .form-input__wrapper")
      .getByRole('textbox')
      .fill("my_param");

    await page.locator(".button").getByText("Save").click();
    await expect(
      page.getByText("The page settings have been updated.")
    ).toBeVisible();

    await page.getByTitle("Close").click();
    await expect(page.locator(".box__title").getByText("Page")).toBeHidden();
    await page.getByText('Click to create an element').click();
    await page.locator('.add-element-card__element-type-icon-link').click();
    await page.getByLabel('my_param=').fill("foo")
    await page.getByRole('complementary').getByRole('textbox').click();
    await page.getByRole('complementary').getByRole('textbox').locator('div').first().fill('linkim');
    await page.locator('a').filter({hasText: 'Make a choice'}).click();
    await page.locator('a').filter({hasText: '?my_param=*'}).click();
    // click empty place to close tooltip from prev. step
    await page.click('body')
    await page.getByRole('textbox').nth(2).click();
    await page.getByText('my_param', { exact: true }).first().click();
    await page.click('body')
    await expect(page.getByRole('link', {name: 'linkim'})).toHaveAttribute(
      'href', /\?my_param=foo/);

  });
});
