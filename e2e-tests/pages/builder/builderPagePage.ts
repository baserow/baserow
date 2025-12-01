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
    const heading = await this.page
      .locator(".ab-heading")
      .getByText(name, { exact: true });

    await this.page
      .locator(".heading-element")
      .filter({ has: heading })
      .click();

    await expect(
      this.page.locator(".element-preview__name-tag").getByText("Heading")
    ).toBeVisible();
  }

  async selectButtonByName(name) {
    const button = await this.page
      .locator(".ab-button")
      .getByText(name, { exact: true });

    await this.page.locator(".button-element").filter({ has: button }).click();
    await expect(
      this.page.locator(".element-preview__name-tag").getByText("Button")
    ).toBeVisible();
  }

  async getElementGeneralTab() {
    // Check that the tab is selected first
    await this.page.locator(".side-panels").getByText("General").click();
    return this.page.locator(".side-panels__panel-general");
  }

  async getElementEventsTab() {
    // Check
    await this.page.locator(".side-panels").getByText("Events").click();
    return this.page.locator(".side-panels__panel-events");
  }

  async removeAll() {
    // TODO remove all
  }

  getFullUrl() {
    return `${this.baseUrl}/builder/${this.builder.id}/page/${this.builderPage.id}`;
  }
}
