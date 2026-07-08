import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { expect, test } from "../../baserowTest";

test.describe("Builder page heading element test suite", () => {
  let element1, element2;
  test.beforeEach(async ({ builderPagePage }) => {
    element1 = await createBuilderElement(
      builderPagePage.builderPage,
      "rating",
      { value: "'A Rate'" },
    );
    element2 = await createBuilderElement(
      builderPagePage.builderPage,
      "rating_input",
      { value: "'B Rate'" },
    );
    await builderPagePage.goto();
  });

  test("Can create a rating element", async ({ page, builderPagePage }) => {
    const builderElementModal = await builderPagePage.openAddElementModal();
    await builderElementModal.addElementByName("Rating");
    await expect(
      page.locator("a").filter({ hasText: "Star" }).first(),
    ).toBeVisible();
  });

  test("Can create a rating input element", async ({
    page,
    context,
    builderPagePage,
  }) => {
    const builderElementModal = await builderPagePage.openAddElementModal();
    await builderElementModal.addElementByName("Rating input");

    await expect(
      page.locator('[data-test-id="rating-form-value"]'),
    ).toBeVisible();

    await page.evaluate(() => {
      const node = document.querySelector(".toasts__container-top");
      if (node) node.remove();
    });

    // Subscribe before clicking: the Preview handler calls window.open()
    // synchronously, so the "page" event can fire before click() resolves.
    const newPagePromise = context.waitForEvent("page");
    await page.getByRole("button", { name: "Preview" }).click();
    const newPage = await newPagePromise;

    await newPage.waitForLoadState();

    await expect(newPage).toHaveTitle("Default page");

    await expect(newPage.locator(".rating")).toHaveCount(3);
  });
});
