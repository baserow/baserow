import { Locator, Page, expect } from "@playwright/test";
import { baserowConfig } from "../playwright.config";
import { User } from "../fixtures/user";

export class BaserowPage {
  readonly page: Page;
  readonly baseUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL;
  pageUrl: string;

  constructor(page: Page) {
    this.page = page;
  }

  async authenticate(user: User) {
    await this.page.goto(`${this.baseUrl}?token=${user.refreshToken}`);
  }

  async goto() {
    await this.page.goto(this.getFullUrl());
  }

  async checkOnPage() {
    await expect(this.page.url()).toBe(this.getFullUrl());
  }

  async changeDropdown(
    currentValue: string,
    newValue: string,
    location?: Locator
  ) {
    await (location ? location : this.page)
      .locator(".dropdown__selected-text")
      .getByText(currentValue)
      .click();
    await (location ? location : this.page)
      .locator(".select__item")
      .getByText(newValue)
      .click();
  }

  getFullUrl() {
    return `${this.baseUrl}/${this.pageUrl}`;
  }
}
