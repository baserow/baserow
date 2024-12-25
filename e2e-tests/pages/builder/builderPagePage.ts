import { Locator, Page } from "@playwright/test";
import { BaserowPage } from "../baserowPage";
import { Builder } from "../../fixtures/builder/builder";
import { BuilderPage } from "../../fixtures/builder/builderPage";
import { Workspace } from "../../fixtures/workspace";
import { BuilderElementModal } from "./builderElementModal";
import { expect } from "@playwright/test";

export class BuilderPagePage extends BaserowPage {
  readonly emailInput: Locator;
  builderPage: BuilderPage;
  builder: Builder;
  readonly workspace: Workspace;

  constructor(page: Page, builder: Builder, builderPage: BuilderPage) {
    super(page);
    this.builder = builder;
    this.builderPage = builderPage;
  }

  async openAddElementModal() {
    await this.page.locator(".header").getByText("Elements").click();
    await this.page
      .locator(".elements-context")
      .getByText("Element", { exact: true })
      .click();
    return new BuilderElementModal(this.page);
  }

  async selectHeadingByName(name) {
    await this.page
      .locator(".ab-heading")
      .getByText(name, { exact: true })
      .click();
    await expect(
      this.page.locator(".element-preview__name").getByText("Heading")
    ).toBeVisible();
  }

  async removeAll() {
    // TODO remove all
  }

  getFullUrl() {
    return `${this.baseUrl}/builder/${this.builder.id}/page/${this.builderPage.id}`;
  }
}
