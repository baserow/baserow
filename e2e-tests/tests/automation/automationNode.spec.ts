import { expect, test } from "../baserowTest";

test.describe("Automation node test suite", () => {
  test.beforeEach(async ({ automationWorkflowPage }) => {
    await automationWorkflowPage.goto();
  });

  test("Can create an automation node", async ({ page }) => {
    const createNodeButton = page.getByRole("button", { name: "Create automation node" });
    createNodeButton.click();

    const nodeDiv = page.getByRole('heading', {
      name: /^\d+ Row is created/,
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();
  });

  test("Can delete an automation node", async ({ page }) => {
    const createNodeButton = page.getByRole("button", { name: "Create automation node" });
    createNodeButton.click();

    const nodeDiv = page.getByRole('heading', {
      name: /^\d+ Row is created/,
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();

    const nodeMenuButton = page.getByRole("button", { name: "Node options" });
    await nodeMenuButton.click();

    const deleteNodeButton = page.getByRole("button", { name: "Delete action" });
    await deleteNodeButton.waitFor({ state: "visible" });
    deleteNodeButton.click();

    await expect(nodeDiv).not.toBeVisible();
  });
});
