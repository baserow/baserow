import { test as base } from "@playwright/test";
import { WorkspacePage } from "../pages/workspacePage";
import { createUser } from "../fixtures/user";
import { BuilderPagePage } from "../pages/builder/builderPagePage";
import { createWorkspace } from "../fixtures/workspace";
import { createBuilderPage } from "../fixtures/builder/builderPage";
import { createBuilder } from "../fixtures/builder/builder";

// Declare the types of your fixtures.
type BaserowFixtures = {
  workspacePage: WorkspacePage;
  builderPagePage: BuilderPagePage;
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
});
export { expect } from "@playwright/test";
