import { test as base } from "@playwright/test";
import { WorkspacePage } from "../pages/workspacePage";
import { createUser } from "../fixtures/user";
import { BuilderPagePage } from "../pages/builder/builderPagePage";
import { createWorkspace } from "../fixtures/workspace";
import { createBuilderPage } from "../fixtures/builder/builderPage";
import { createBuilder } from "../fixtures/builder/builder";
import { createAutomation } from "../fixtures/automation/automation";
import { createAutomationWorkflow } from "../fixtures/automation/automationWorkflow";
import { AutomationWorkflowPage } from "../pages/automation/automationWorkflowPage";
import { createDatabase } from "../fixtures/database/database";
import { createTable } from "../fixtures/database/table";
import { TablePage } from "../pages/database/tablePage";

// Declare the types of your fixtures.
type BaserowFixtures = {
  workspacePage: WorkspacePage;
  tablePage: TablePage;
  builderPagePage: BuilderPagePage;
  automationWorkflowPage: AutomationWorkflowPage;
};

/**
 * Fixture for all tests that need an authenticated user with an empty workspace.
 */
export const test = base.extend<BaserowFixtures>({
  workspacePage: async ({ page }, use) => {
    const user = await createUser();
    const workspace = await createWorkspace(user);
    const workspacePage = new WorkspacePage(page, user, workspace);
    await workspacePage.authenticate();

    // Use the fixture value in the test.
    await use(workspacePage);

    // Clean up the fixture.
    await workspacePage.removeAll();
  },
  builderPagePage: async ({ page, workspacePage }, use) => {
    const builder = await createBuilder(
      "Test builder",
      workspacePage.workspace
    );
    const builderPage = await createBuilderPage(
      "Default page",
      "/default/page",
      builder
    );
    const builderPagePage = new BuilderPagePage(page, builder, builderPage);

    await use(builderPagePage);

    await builderPagePage.removeAll();
  },
  automationWorkflowPage: async ({ page, workspacePage }, use) => {
    const automation = await createAutomation(
      "Test automation",
      workspacePage.workspace
    );
    const automationWorkflow = await createAutomationWorkflow(
      "Default workflow",
      automation
    );
    const automationWorkflowPage = new AutomationWorkflowPage(page, automation, automationWorkflow);

    await use(automationWorkflowPage);
  },
  tablePage: async ({ page, workspacePage }, use) => {
    const database = await createDatabase(
      workspacePage.workspace.user,
      "Database",
      workspacePage.workspace
    );
    const table = await createTable(
      workspacePage.workspace.user,
      "Table",
      database
    );
    const tablePage = new TablePage(page);
    tablePage.user = workspacePage.workspace.user
    tablePage.workspace = workspacePage.workspace
    await tablePage.goToTable(table)
    await use(tablePage);
    await tablePage.removeAll();
  },
});
export { expect } from "@playwright/test";
