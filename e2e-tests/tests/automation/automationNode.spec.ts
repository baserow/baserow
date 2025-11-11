import { expect, test } from "../baserowTest";

import { createAutomationNode } from "../../fixtures/automation/automationNode";

test.describe("Automation node test suite", () => {
  let trigger;
  test.beforeEach(async ({ automationWorkflowPage, page }) => {
    await automationWorkflowPage.goto();

    trigger = await createAutomationNode(
      automationWorkflowPage.automationWorkflow,
      "periodic"
    );

    const startsWhen = page.getByText("Configure");
    await expect(startsWhen).toBeVisible();
  });

  test("Can create an automation node", async ({ page }) => {
    const createNodeButton = page.getByRole("button", {
      name: "Create automation node",
    });
    await createNodeButton.click();

    const rowsCreatedOption = page.getByText("Create a row");
    await expect(rowsCreatedOption).toBeVisible();
    await rowsCreatedOption.click();

    const nodeDiv = page.getByRole("heading", {
      name: "Create a row",
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();
  });

  test("Can delete an automation node", async ({
    page,
    automationWorkflowPage,
  }) => {
    const createNode = await createAutomationNode(
      automationWorkflowPage.automationWorkflow,
      "local_baserow_create_row",
      trigger.id,
      "south",
      ""
    );

    const nodeDiv = page.getByRole("heading", {
      name: "Create a row",
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();

    // Let's select the node
    await nodeDiv.click();

    await page.locator(".vue-flow__controls-fitview").click();

    const nodeMenuButton = page
      .locator(".workflow-node-content--selected")
      .getByRole("button", { name: "Node options" });
    await nodeMenuButton.click();

    const deleteNodeButton = page.getByText("Delete");
    await deleteNodeButton.waitFor({ state: "visible" });
    deleteNodeButton.click();

    await expect(nodeDiv).not.toBeVisible();
  });
});
