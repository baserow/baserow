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
    await this.recoverFromNuxtError();
  }

  async goto(params = {}) {
    await this.page.waitForTimeout(100); // Small delay before navigation to help with Firefox timing issues
    try {
      await this._goto(this.getFullUrl(), {
        waitUntil: "hydration",
        ...params,
      });
      await this.recoverFromNuxtError();
    }
    } catch (e) {
      // Firefox aborts the in-flight navigation when the app client-side
      // redirects after load. Retry once; the redirect target is the page we want.
      if (!String(e).includes("NS_BINDING_ABORTED")) throw e;
      await this._goto(this.getFullUrl(), options);
    }
  }

  /**
   * Retries navigation when Nuxt briefly renders its error placeholder during
   * e2e startup. This only handles known placeholder titles before assertions.
   */
  async recoverFromNuxtError() {
    const errorTitle = this.page.locator(".placeholder__title");

    for (let attempt = 0; attempt < 2; attempt++) {
      const title = await errorTitle
        .textContent({ timeout: 500 })
        .catch(() => "");

      if (
        !title.includes("[nuxt] instance unavailable") &&
        !title.includes("Server Error")
      ) {
        return;
      }

      await this.page.goto(this.getFullUrl(), { waitUntil: "load" });
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
