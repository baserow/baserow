import { Locator, Page } from "@playwright/test";
import { BaserowPage, PageConfig } from "./baserowPage";

export class LoginPage extends BaserowPage {
  readonly pageUrl = `login`;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly loginButton: Locator;

  constructor(pageConfig: PageConfig) {
    super(pageConfig);
    this.emailInput = this.page.locator('input[type="email"]').first();
    this.passwordInput = this.page.locator('input[type="password"]').first();
    this.loginButton = this.page.locator('button span:text("Login")').first();
  }

  async loginWithPassword(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    await this.page.locator(".tree__item").getByText("Home").waitFor();
  }
}
