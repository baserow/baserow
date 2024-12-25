import { test } from "@playwright/test";
import { LoginPage } from "../../pages/loginPage";
import { WorkspacePage } from "../../pages/workspacePage";
import { createUser, deleteUser, User } from "../../fixtures/user";
import { createWorkspace, Workspace } from "../../fixtures/workspace";

let user: User;
let workspace: Workspace;

test.beforeEach(async ({ page }) => {
  user = await createUser();
  workspace = await createWorkspace(user);
});

test.afterEach(async () => {
  // We only want to bother cleaning up in a devs local env or when pointed at a real
  // server. If in CI then the first user will be the first admin and this will fail.
  // Secondly in CI we are going to delete the database anyway so no need to clean-up.
  if (!process.env.CI) {
    await deleteUser(user);
  }
});

test("User can log in with email/password @fast", async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.loginWithPassword(user.email, user.password || "");

  const workspace = await createWorkspace(user);
  const workspacePage = new WorkspacePage(page, user, workspace);
  await workspacePage.goto();
  await workspacePage.checkOnPage();
});
