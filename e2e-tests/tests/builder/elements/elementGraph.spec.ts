import { createBuilderElement } from "../../../fixtures/builder/builderElement";
import { expect, test } from "../../baserowTest";

test.describe("Builder element graph test suite", () => {
  test.describe("with a 2-column element", () => {
    let column;

    test.beforeEach(async ({ builderPagePage }) => {
      column = await createBuilderElement(
        builderPagePage.builderPage,
        "column",
        { column_amount: 2 }
      );
      await builderPagePage.goto();
    });

    test("Can create a child element inside a container slot", async ({
      page,
    }) => {
      await page
        .locator(".column-element__column")
        .first()
        .locator(".add-element-zone")
        .click();
      await page
        .locator(".add-element-modal")
        .getByText("Heading", { exact: true })
        .click();
      await expect(
        page.locator(".add-element-modal").getByText("Add new element")
      ).toBeHidden();
      await expect(
        page
          .locator(".column-element__column")
          .first()
          .locator(".heading-element")
      ).toBeVisible();
    });

    test("Can move a child element between container slots", async ({
      page,
      builderPagePage,
    }) => {
      // Create a heading in slot 0 via API then reload
      await createBuilderElement(builderPagePage.builderPage, "heading", {
        value: "'SlotHeading'",
        reference_element_id: column.id,
        position: "child",
        place_in_container: "0",
      });
      await builderPagePage.goto();

      // Select the heading inside slot 0
      await page
        .locator(".column-element__column")
        .first()
        .locator(".column-element__element")
        .click();
      await expect(
        page.locator(".element-preview__name-tag").getByText("Heading")
      ).toBeVisible();

      // Click the move-right button in the element menu
      await page
        .locator(".element-preview--active .element-preview__menu")
        .locator("a:has(.iconoir-nav-arrow-right)")
        .click();

      // Heading is now in slot 1
      await expect(
        page.locator(".column-element__column").nth(1).locator(".ab-heading")
      ).toBeVisible();
      // Slot 0 is empty
      await expect(
        page
          .locator(".column-element__column")
          .first()
          .locator(".add-element-zone")
      ).toBeVisible();
    });
  });

  test.describe("with a root heading", () => {
    test.beforeEach(async ({ builderPagePage }) => {
      await createBuilderElement(builderPagePage.builderPage, "heading", {
        value: "'RootHeading'",
      });
      await builderPagePage.goto();
    });

    test("Can duplicate an element at root level", async ({
      page,
      builderPagePage,
    }) => {
      await builderPagePage.selectHeadingByName("RootHeading");
      await page
        .locator(".element-preview--active .element-preview__menu")
        .locator("a:has(.iconoir-copy)")
        .click();
      await expect(page.locator(".heading-element")).toHaveCount(2);
    });

    test("Can delete an element", async ({ page, builderPagePage }) => {
      await builderPagePage.selectHeadingByName("RootHeading");
      await page
        .locator(".element-preview--active .element-preview__menu")
        .locator("a:has(.iconoir-bin)")
        .click();
      await expect(page.locator(".heading-element")).toHaveCount(0);
    });
  });

  test.describe("with a column containing a child heading", () => {
    let column;

    test.beforeEach(async ({ builderPagePage }) => {
      column = await createBuilderElement(
        builderPagePage.builderPage,
        "column",
        { column_amount: 2 }
      );
      await createBuilderElement(builderPagePage.builderPage, "heading", {
        value: "'SlotHeading'",
        reference_element_id: column.id,
        position: "child",
        place_in_container: "0",
      });
      await builderPagePage.goto();
    });

    test("Can duplicate a child element inside a container slot", async ({
      page,
    }) => {
      // Select the heading inside slot 0
      await page
        .locator(".column-element__column")
        .first()
        .locator(".column-element__element")
        .click();
      await expect(
        page.locator(".element-preview__name-tag").getByText("Heading")
      ).toBeVisible();

      await page
        .locator(".element-preview--active .element-preview__menu")
        .locator("a:has(.iconoir-copy)")
        .click();

      // Both headings stay inside column slot 0 — not spuriously at root level
      await expect(
        page
          .locator(".column-element__column")
          .first()
          .locator(".heading-element")
      ).toHaveCount(2);
      // Only one column on the page (no duplicate column at root)
      await expect(page.locator(".column-element")).toHaveCount(1);
    });

    test("Can duplicate a container with its children", async ({ page }) => {
      // Select the child heading, then press 'p' to move selection to the column
      await page
        .locator(".column-element__column")
        .first()
        .locator(".column-element__element")
        .click();
      await page.locator(".page-preview__scaled").focus();
      await page.keyboard.press("p");
      await expect(
        page.locator(".element-preview__name-tag").getByText("Column")
      ).toBeVisible();

      // Duplicate the column
      await page
        .locator(".element-preview--active .element-preview__menu")
        .locator("a:has(.iconoir-copy)")
        .click();

      await expect(page.locator(".column-element")).toHaveCount(2);
      // Each column contains the heading that was duplicated with it
      await expect(
        page.locator(".column-element .heading-element")
      ).toHaveCount(2);
    });
  });
});
