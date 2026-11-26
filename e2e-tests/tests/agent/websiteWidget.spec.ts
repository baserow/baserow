import { getClient } from "../../client";
import { createAgent } from "../../fixtures/agent/agent";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../fixtures/licence";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

const website = "http://customer-website.test/";
const markup = '<img src="missing.png" onerror="window.injected = true">';

test("a website shows the widget's texts as text and opens the chat", async ({
  page,
  workspacePage,
}) => {
  const license = await createLicense(ENTERPRISE_LICENSE);
  try {
    const { workspace, user } = workspacePage;
    const agent = await createAgent("Customer support", workspace);
    const { data: widget } = await getClient(user).post(
      `agent/${agent.id}/channels/`,
      { type: "website_widget", title: markup, button_text: markup }
    );
    const script = `${baserowConfig.PUBLIC_BACKEND_URL}/api/agent/public-chat/${widget.slug}/widget.js`;
    await page.route(website, (route) =>
      route.fulfill({
        contentType: "text/html",
        body: `<html><body><h1>Acme</h1><script src="${script}" async></script></body></html>`,
      })
    );

    await page.goto(website);
    const host = page.locator(`#baserow-agent-widget-${widget.slug}`);
    const button = host.getByRole("button", { name: markup, exact: true });
    await expect(button).toBeVisible();
    await expect(host.locator("img")).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).injected)).toBeUndefined();

    await button.click();
    const chat = page.frameLocator(`#baserow-agent-widget-${widget.slug} iframe`);
    await expect(chat.getByText(markup, { exact: true }).first()).toBeVisible();
    await expect(button).toHaveAttribute("aria-expanded", "true");
  } finally {
    await deleteLicense(license);
  }
});
