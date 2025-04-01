import { TemplatePage } from "../../pages/templatePage";
import { expect, test } from "../baserowTest";

test.describe("Builder template application test suite", () => {
  test("Can show an AB template", async ({ page }) => {
    const templatePage = new TemplatePage(page, "ab_ivory_theme");

    await templatePage.goto();

    await expect(
      page.locator(".ab-heading--h3").getByText("Rebranding website")
    ).toBeVisible();
  });
});
