import { expect, test } from "../baserowTest";

import { createAutomationNode } from "../../fixtures/automation/automationNode";

test.describe("Automation node test suite", () => {
  test.beforeEach(async ({ automationWorkflowPage }) => {
    await automationWorkflowPage.goto();
  });

  test("Can create an automation node", async ({ page }) => {
    const createNodeButton = page.getByRole("button", { name: "Create automation node" });
    await createNodeButton.click();

    const rowsCreatedOption = page.getByText("Create a row")
    await expect(rowsCreatedOption).toBeVisible();
    await rowsCreatedOption.click();

    const nodeDiv = page.getByRole("heading", {
      name: "Create a row",
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();
  });

  test("Can delete an automation node", async ({ page, automationWorkflowPage }) => {
    await createAutomationNode(automationWorkflowPage.automationWorkflow, "create_row")

    // TODO: Remove this manual reload once real-time events have been
    // implemented for automations.
    await page.reload();

    const nodeDiv = page.getByRole("heading", {
      name: "Create a row",
      level: 1,
    });
    await expect(nodeDiv).toBeVisible();

    const nodeMenuButton = page.getByRole("button", { name: "Node options" });
    await nodeMenuButton.click();

    const deleteNodeButton = page.getByRole("button", { name: "Delete" });
    await deleteNodeButton.waitFor({ state: "visible" });
    deleteNodeButton.click();

    await expect(nodeDiv).not.toBeVisible();
  });
});
