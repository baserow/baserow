import { createServer } from "http";
import type { AddressInfo } from "net";
import { getClient } from "../../client";
import { createAgent } from "../../fixtures/agent/agent";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../fixtures/licence";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

const markup = '<img src="missing.png" onerror="window.injected = true">';

/** Serves another website on loopback, as Chrome blocks a public page's loopback scripts. */
async function serveWebsite(
  html: string
): Promise<{ url: string; close: () => Promise<void> }> {
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "text/html" });
    response.end(html);
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${port}/`,
    close: () =>
      new Promise((resolve) => {
        server.closeAllConnections();
        server.close(() => resolve());
      }),
  };
}

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
    const website = await serveWebsite(
      `<html><body><h1>Acme</h1><script src="${script}" async></script></body></html>`
    );
    try {
      await page.goto(website.url);
      const host = page.locator(`#baserow-agent-widget-${widget.slug}`);
      const button = host.getByRole("button", { name: markup, exact: true });
      await expect(button).toBeVisible();
      await expect(host.locator("img")).toHaveCount(0);

      await button.click();
      await expect(button).toHaveAttribute("aria-expanded", "true");
      const chat = page.frameLocator(
        `#baserow-agent-widget-${widget.slug} iframe`
      );
      await expect(
        chat.getByRole("heading", { name: markup, exact: true }).first()
      ).toBeVisible();
      expect(
        await page.evaluate(() => (window as any).injected)
      ).toBeUndefined();
    } finally {
      await website.close();
    }
  } finally {
    await deleteLicense(license);
  }
});
