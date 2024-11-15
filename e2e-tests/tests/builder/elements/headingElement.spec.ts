import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { expect, test } from "../../baserowTest";

test.describe("Builder page heading element test suite", () => {
  let element1, element2;
  test.beforeEach(async ({ builderPagePage }) => {
    element1 = await createBuilderElement(
      builderPagePage.builderPage,
      "heading",
      { value: "'FirstHeader'" }
    );
    element2 = await createBuilderElement(
      builderPagePage.builderPage,
      "heading",
      { value: "'SecondHeader'" }
    );
    await builderPagePage.goto();
  });

  test("Can create a heading element", async ({ page, builderPagePage }) => {
    const builderElementModal = await builderPagePage.openAddElementModal();
    await builderElementModal.addElementByName("Heading");

    await expect(
      page.locator(".element").getByText("Missing title...")
    ).toBeVisible();
  });

  test("Can update heading element", async ({ page, builderPagePage }) => {
    // Select second heading
    await builderPagePage.selectHeadingByName("SecondHeader");

    await page
      .locator(".side-panels")
      .getByRole("textbox")
      .getByText("SecondHeader")
      .click();

    // Change the name
    await page
      .locator(".side-panels")
      .getByRole("textbox")
      .getByText("SecondHeader")
      .fill("Test header");

    // Is the title change reflected
    await expect(
      page.locator(".ab-heading--h1").getByText("Test header")
    ).toBeVisible();

    // Change the title level
    await page
      .locator(".dropdown__selected-text")
      .getByText("Heading 1 <h1>")
      .click();
    await page.locator(".select__item").getByText("Heading 3").click();

    // Is the title level change reflected
    await expect(
      page.locator(".ab-heading--h3").getByText("Test header")
    ).toBeVisible();
  });
});
