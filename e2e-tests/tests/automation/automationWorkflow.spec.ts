import { expect, test } from "../baserowTest";

test.describe("Automation workflow test suite", () => {
  test.beforeEach(async ({ automationWorkflowPage }) => {
    await automationWorkflowPage.goto();
  });

  test("Can create a workflow", async ({ page }) => {
    const workflowName = "Foo workflow";

    await page.getByText("New workflow").click();

    await page.getByText("Create workflow").waitFor();

    await page
      .locator(".modal__box")
      .getByPlaceholder("Enter a name...")
      .fill(workflowName);

    await page.getByRole("button").getByText("Add workflow").click();

    await expect(page.getByText("Create workflow")).toBeHidden();

    await expect(
      page.locator(".tree__link").getByText("Test Automation"),
      "Ensure the default automation name is displayed in the sidebar."
    ).toBeVisible();

    const chooseTriggerTitle = page.getByText("Choose an event...");
    await expect(
      chooseTriggerTitle,
      "Ensure the trigger chooser is visible."
    ).toBeVisible();
  });

  test("Can duplicate a workflow", async ({ page }) => {
    const defaultWorkflowName = "Default workflow";
    const workflow = page.getByRole("link", { name: defaultWorkflowName });
    await workflow.hover();
    await page.locator(".tree__sub > .tree__options").first().click();
    const duplicateLink = await page
      .locator(".context__menu")
      .getByText("Duplicate");
    await duplicateLink.click();
    await expect(duplicateLink).toBeHidden();

    // Ensure the duplicated workflow is visible
    const workflowLink = page.getByRole("link", {
      name: `${defaultWorkflowName} 2`,
    });
    await expect(
      workflowLink,
      "Ensure the duplicated workflow is displayed in the sidebar."
    ).toBeVisible();

    const chooseTriggerTitle = page.getByText("Choose an event...");
    await expect(
      chooseTriggerTitle,
      "Ensure the trigger chooser is visible."
    ).toBeVisible();
  });

  test("Can rename a workflow", async ({ page }) => {
    const defaultWorkflowName = "Default workflow";
    const workflow = page.getByRole("link", { name: defaultWorkflowName });
    await workflow.hover();
    await page.locator(".tree__sub > .tree__options").first().click();
    const renameLink = await page.locator(".context__menu").getByText("Rename");
    await renameLink.click();
    await expect(renameLink).toBeHidden();

    // Focus on the side bar item, click the input area, and clear the current name
    const editable = await page.locator('span[contenteditable="true"]');
    await editable.click();
    await editable.evaluate((el) => {
      el.textContent = "";
    });

    // Type new workflow name
    const newWorkflowName = "My new workflow name";
    await editable.fill(newWorkflowName);

    // Click outside to cause a blur event so that the name is saved
    await page.locator("body").click({ position: { x: 10, y: 10 } });

    const workflowLink = page.getByRole("link", { name: "Workflow" });
    await expect(
      workflowLink,
      "Ensure the renamed workflow is displayed in the sidebar."
    ).toBeVisible();

    const chooseTriggerTitle = page.getByText("Choose an event...");
    await expect(
      chooseTriggerTitle,
      "Ensure the trigger chooser is visible."
    ).toBeVisible();
  });

  // For some reasons this test is flaky. Marked as slow for now to prevent CI execution
  test("Can delete a workflow @slow", async ({ page }) => {
    const defaultWorkflowName = "Default workflow";

    const workflow = page.getByRole("link", { name: defaultWorkflowName });
    await workflow.hover();
    await page.locator(".tree__sub > .tree__options").first().click();

    const deleteLink = await page
      .locator(".context__menu")
      .getByText("Delete", { exact: true });
    await deleteLink.click();
    await expect(deleteLink).toBeHidden();

    const workflowLink = page.getByRole("link", { name: defaultWorkflowName });
    await expect(
      workflowLink,
      "Ensure the workflow is no longer visible in the sidebar."
    ).not.toBeVisible();

    const workspaceName = page
      .locator(".dashboard__header")
      .getByText("Default workspace");
    await expect(
      workspaceName,
      "Ensure that the dashboard page is shown after workflow is deleted."
    ).toBeVisible();
  });
});
