import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { expect, test } from "../../baserowTest";

test.describe("Builder page heading element test suite", () => {
  let element1, element2;
  test.beforeEach(async ({ builderPagePage }) => {
    element1 = await createBuilderElement(
      builderPagePage.builderPage,
      "rating",
      { value: "'A Rate'" }
    );
    element2 = await createBuilderElement(
      builderPagePage.builderPage,
      "rating_input",
      { value: "'B Rate'" }
    );
    await builderPagePage.goto();
  });

  test("Can create a rating element", async ({ page, builderPagePage }) => {
    const builderElementModal = await builderPagePage.openAddElementModal();
    await builderElementModal.addElementByName("Rating");
    await expect(
      page.locator("a").filter({ hasText: "Star" }).first()
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
      page.locator('[data-test-id="rating-form-value"]')
    ).toBeVisible();

    await page.evaluate(() => {
      const node = document.querySelector(".toasts__container-top");
      if (node) node.remove();
    });

    await page.getByRole("button", { name: "Preview" }).click();

    const newPage = await context.waitForEvent("page");

    await newPage.waitForLoadState();

    const title = await newPage.title();
    await expect(title).toBe("Default page");

    await expect(newPage.locator(".rating")).toHaveCount(3);
  });
});
