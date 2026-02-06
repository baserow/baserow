import { Locator, Page, expect } from "@playwright/test";
import { baserowConfig } from "../playwright.config";
import { User } from "../fixtures/user";

import { GotoOptions } from "@nuxt/test-utils/e2e";

type GotoFn = (url: string, options?: GotoOptions) => Promise<Response | null>;

export type PageConfig = { page: Page; goto: GotoFn };

export class BaserowPage {
  readonly page: Page;
  readonly _goto: any;
  readonly baseUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL;
  pageUrl: string;

  constructor({ page, goto }: PageConfig) {
    this.page = page;
    this._goto = goto;
  }

  async authenticate(user: User) {
    await this.page.goto(`${this.baseUrl}?token=${user.refreshToken}`);
  }

  async goto(params = {}, maxRetries = 3) {
    const url = this.getFullUrl();
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        // Small delay before navigation to help with Firefox timing issues
        if (attempt > 0) {
          await this.page.waitForTimeout(500);
        }
        await this._goto(url, {
          waitUntil: "hydration",
          ...params,
        });
        return; // Success, exit the retry loop
      } catch (error: any) {
        lastError = error;
        // Check if this is a NS_BINDING_ABORTED error (Firefox-specific)
        if (
          error.message?.includes("NS_BINDING_ABORTED") ||
          error.message?.includes("frame was detached")
        ) {
          console.log(
            `Navigation interrupted (attempt ${attempt + 1}/${maxRetries}), retrying...`,
          );
          continue;
        }
        // For other errors, throw immediately
        throw error;
      }
    }

    // If we've exhausted all retries, throw the last error
    if (lastError) {
      throw lastError;
    }
  }

  async checkOnPage() {
    await expect(this.page.url()).toBe(this.getFullUrl());
  }

  async changeDropdown(
    currentValue: string,
    newValue: string,
    location?: Locator,
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
