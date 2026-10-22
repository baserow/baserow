import { BrowserContext, expect, Locator, Page } from "@playwright/test";

/** Kuma's panel in the right sidebar of a workspace page. */
export class KumaPanel {
  readonly page: Page;
  readonly panel: Locator;

  constructor(page: Page) {
    this.page = page;
    this.panel = page.locator(".assistant");
  }

  /** A new tab on `url`, whose panel opens by itself because another tab left it open. */
  static async inNewTab(
    context: BrowserContext,
    url: string
  ): Promise<KumaPanel> {
    const kuma = new KumaPanel(await context.newPage());
    await kuma.page.goto(url);
    await expect(kuma.panel).toBeVisible();
    return kuma;
  }

  /** Opens the panel of a page that starts with it closed, as the configured storage state leaves it. */
  async open(): Promise<void> {
    await expect(this.panel).toBeHidden();
    await this.page.locator(".tree__link", { hasText: "Kuma AI" }).click();
    await expect(this.panel).toBeVisible();
  }

  async send(message: string): Promise<void> {
    const input = this.panel.locator(".assistant__input-textarea");
    await input.fill(message);
    await input.press("Enter");
  }

  /** The chat's AI messages, the answer still being written included. */
  answers(): Locator {
    return this.panel.locator(
      ".assistant__message--ai .assistant__message-text"
    );
  }

  lastAnswer(): Locator {
    return this.answers().last();
  }

  async expectIdle(): Promise<void> {
    await expect(
      this.panel.locator(".assistant__input-status")
    ).not.toHaveClass(/is-running/, { timeout: 60_000 });
  }

  async openLatestChat(): Promise<void> {
    await this.panel.getByTitle("Chat History").click();
    await this.page.locator(".select__item-link:visible").first().click();
  }
}
