import { Locator, Page } from "@playwright/test";
import { TemplateModal } from "./templateModal";

export class Sidebar {
  page: Page;
  private createNewAppButton: Locator;
  private readonly createTemplateFromAppButton;

  constructor(page: Page) {
    this.page = page;
    this.createNewAppButton = page
      .locator(".sidebar__new")
      .getByText("Add new");
    this.createTemplateFromAppButton = this.page
      .locator(".context__menu")
      .getByText("From template");
  }

  async selectDatabaseAndTableByName(dbName: string, tableName: string) {
    await this.selectDatabaseByName(dbName);
    await this.selectTableByName(tableName);
  }

  async selectDatabaseByName(name: string) {
    await this.page.getByTitle(name).click();
  }

  clickCreateNewApplication() {
    return this.createNewAppButton.click();
  }

  clickCreateNewAppFromTemplateButton() {
    return this.createTemplateFromAppButton.click();
  }

  async openCreateAppFromTemplateModal(): Promise<TemplateModal> {
    await this.clickCreateNewApplication();
    await this.clickCreateNewAppFromTemplateButton();
    const templateModal = new TemplateModal(this.page);
    await templateModal.waitUntilLoaded();
    return templateModal;
  }

  async selectTableByName(name: string) {
    await this.page.getByText(name).click();
  }
}
