import { expect, test } from "../baserowTest";

test.describe("Automation node test suite", () => {
  test.beforeEach(async ({ automationWorkflowPage }) => {
    await automationWorkflowPage.goto();
  });

  test("Can create an automation node", async ({ page }) => {
    const createNodeButton = await page.locator(
      "button.button-floating--primary:has(i.iconoir-plus)"
    );
    createNodeButton.click();

    const nodeDiv = page.locator("div.workflow-editor__node", {
      hasText: /^ID:\s*\d+/,
    });
    await expect(nodeDiv).toBeVisible();
  });

  test("Can delete an automation node", async ({ page }) => {
    const createNodeButton = await page.locator(
      "button.button-floating--primary:has(i.iconoir-plus)"
    );
    createNodeButton.click();

    const node = page.locator("div.workflow-editor__node", {
      hasText: /^ID:\s*\d+/,
    });
    await expect(node).toBeVisible();

    const nodeMenuButton = node.locator(".workflow-editor__node-more-icon");
    await nodeMenuButton.click();

    const deleteNodeLink = page.locator(".context__menu-item-link--delete", {
      hasText: "Delete node",
    });
    await deleteNodeLink.waitFor({ state: "visible" });
    deleteNodeLink.click();

    await expect(node).not.toBeVisible();
  });
});
