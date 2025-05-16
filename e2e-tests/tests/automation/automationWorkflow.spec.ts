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
      .locator(".modal__wrapper")
      .getByPlaceholder("Enter a name...")
      .fill(workflowName);

    await page.locator(".button").getByText("Add workflow").click();

    await expect(page.getByText("Create workflow")).toBeHidden();

    await expect(
      page.locator(".tree__link").getByText("Test Automation"),
      "Ensure the default automation name is displayed in the sidebar."
    ).toBeVisible();

    await expect(
      page.locator(".automation-app__title").getByText(workflowName),
      "Ensure we see the newly created Automation's workflow."
    ).toBeVisible();
  });

  test("Can duplicate a workflow", async ({ page }) => {
    const defaultWorkflowName = "Default workflow";
    const workflow = await page
      .locator(".side-bar-automation__link-text")
      .getByText(defaultWorkflowName);
    await workflow.hover();
    await page.locator(".tree__sub > .tree__options").first().click();
    await page.getByText("Duplicate").click();
    await expect(page.getByText("Duplicate")).toBeHidden();

    // Ensure the duplicated workflow is visible
    await expect(
      page
        .locator(".side-bar-automation__link-text")
        .getByText(`${defaultWorkflowName} 2`),
      "Ensure the duplicated workflow is displayed in the sidebar."
    ).toBeVisible();
  });

  test("Can rename a workflow", async ({ page }) => {
    const defaultWorkflowName = "Default workflow";
    const workflow = await page
      .locator(".side-bar-automation__link-text")
      .getByText(defaultWorkflowName);
    await workflow.hover();
    await page.locator(".tree__sub > .tree__options").first().click();
    await page.getByText("Rename").click();
    await expect(page.getByText("Rename")).toBeHidden();

    // Focus on the side bar item, click the input area, and clear the current name
    const editable = await page.locator('span[contenteditable="true"]');
    await editable.click();
    await editable.evaluate((el) => {
      el.textContent = "";
    });

    // Type new workflow name
    const newWorkflowName = "My new workflow name";
    await editable.type(newWorkflowName);

    // Click outside to cause a blur event so that the name is saved
    await page.locator("body").click();

    await expect(
      page
        .locator(".side-bar-automation__link-text")
        .getByText(newWorkflowName),
      "Ensure the renamed workflow is displayed in the sidebar."
    ).toBeVisible();

    await expect(
      page.locator(".automation-app__title").getByText(newWorkflowName),
      "Ensure that we can see the updated workflow name in the editor."
    ).toBeVisible();
  });

  test("Can delete a workflow", async ({ page }) => {
    const defaultWorkflowName = "Default workflow";
    const workflow = await page
      .locator(".side-bar-automation__link-text")
      .getByText(defaultWorkflowName);
    await workflow.hover();
    await page.locator(".tree__sub > .tree__options").first().click();
    await page.getByText("Delete").click();
    await expect(page.getByText("Delete")).toBeHidden();

    await expect(
      page
        .locator(".side-bar-automation__link-text")
        .getByText(defaultWorkflowName),
      "Ensure the workflow is no longer visible in the sidebar."
    ).not.toBeVisible();
  });
});
