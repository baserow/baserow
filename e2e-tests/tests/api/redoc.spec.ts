import { expect, test } from "@playwright/test";
import { baserowConfig } from "../../playwright.config";

test("renders the API reference with only the backend reachable", async ({
  page,
}) => {
  const docs = new URL("/api/redoc/", baserowConfig.PUBLIC_BACKEND_URL);
  await page.route(
    (url) => /^https?:$/.test(url.protocol) && url.origin !== docs.origin,
    (route) => route.abort()
  );
  await page.route(new URL("/api/schema.json", docs).href, (route) =>
    route.fulfill({
      json: {
        openapi: "3.0.3",
        info: { title: "Offline API reference", version: "1.0" },
        paths: {},
      },
    })
  );

  await page.goto(docs.href);
  await expect(
    page.getByRole("heading", { level: 1, name: /Offline API reference/ })
  ).toBeVisible();
});
