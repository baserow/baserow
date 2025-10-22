import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { expect, test } from "../../baserowTest";

test.describe("Builder page button element test suite", () => {
  let element1, element2;
  test.beforeEach(async ({ builderPagePage }) => {
    element1 = await createBuilderElement(
      builderPagePage.builderPage,
      "button",
      { value: "'First button'" }
    );
    await builderPagePage.goto();
  });

  test("Can create a simple instance of the element", async ({
    page,
    builderPagePage,
  }) => {
    const builderElementModal = await builderPagePage.openAddElementModal();
    await builderElementModal.addElementByName("Button");

    await expect(
      page.locator(".button-element").getByText("Empty button text...")
    ).toBeVisible();
  });

  test("Can update the element", async ({ page, builderPagePage }) => {
    const generalTab = await builderPagePage.getElementGeneralTab();

    await generalTab.getByRole("textbox").getByText("First button").click();

    // Change the name
    await generalTab
      .getByRole("textbox")
      .getByText("First button")
      .fill("New button name");

    // Is the title change reflected
    await expect(
      page.locator(".button-element").getByText("New button name")
    ).toBeVisible();
  });

  test("Can add an event", async ({ page, builderPagePage }) => {
    await builderPagePage.selectButtonByName("First button");

    const eventsTab = await builderPagePage.getElementEventsTab();

    // Let's add an action
    await eventsTab.getByText("add action").click();

    await page.locator(".context").getByText("Show Notification").click();

    await expect(
      eventsTab.getByText("Show Notification").locator("visible=true"),
      "Checks the action was created."
    ).toBeVisible();
  });
});
