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
      page.locator(".heading-element").getByText("Empty title...")
    ).toBeVisible();
  });

  test("Can update heading element", async ({ page, builderPagePage }) => {
    // Select second heading
    await builderPagePage.selectHeadingByName("SecondHeader");
    const generalTab = await builderPagePage.getElementGeneralTab();

    await generalTab.getByRole("textbox").getByText("SecondHeader").click();

    // Change the name
    await generalTab
      .getByRole("textbox")
      .getByText("SecondHeader")
      .fill("Test header");

    // Is the title change reflected
    await expect(
      page.locator(".ab-heading--h1").getByText("Test header")
    ).toBeVisible();

    // Change the title level
    await builderPagePage.changeDropdown(
      "Heading 1 <h1>",
      "Heading 3",
      generalTab
    );

    // Is the title level change reflected
    await expect(
      page.locator(".ab-heading--h3").getByText("Test header")
    ).toBeVisible();
  });
});
