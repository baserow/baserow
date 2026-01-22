import { Page } from "@playwright/test";
import { BaserowPage, PageConfig } from "./baserowPage";
import { Sidebar } from "./components/sidebar";
import { Workspace } from "../fixtures/workspace";
import { deleteUser, User } from "../fixtures/user";

export class WorkspacePage extends BaserowPage {
  readonly sidebar: Sidebar;
  readonly workspace: Workspace;
  readonly user: User;

  constructor(pageConfig: PageConfig, user: User, workspace: Workspace) {
    super(pageConfig);
    this.sidebar = new Sidebar(pageConfig.page);
    this.user = user;
    this.workspace = workspace;
  }

  async authenticate() {
    await this.page.goto(`${this.baseUrl}?token=${this.user.refreshToken}`);
  }

  getFullUrl() {
    return `${this.baseUrl}/workspace/${this.workspace.id}`;
  }

  async removeAll() {
    // We only want to bother cleaning up in a devs local env or when pointed at a real
    // server. If in CI then the first user will be the first admin and this will fail.
    // Secondly in CI we are going to delete the database anyway so no need to clean-up.
    if (!process.env.CI) {
      await deleteUser(this.user);
      // TODO remove workspace
    }
  }
}
