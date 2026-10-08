import { Page } from "@playwright/test";
import { baserowConfig } from "../../playwright.config";
import { Database } from "../../fixtures/database/database";
import { Table } from "../../fixtures/database/table";
import { User } from "../../fixtures/user";
import { View } from "../../fixtures/database/view";

/** Opens the table as the user and waits until Nuxt has hydrated the page. */
export async function openTableAs(
  page: Page,
  user: User,
  database: Database,
  table: Table,
  view?: View,
): Promise<void> {
  const baseUrl = baserowConfig.PUBLIC_WEB_FRONTEND_URL;
  const url = new URL(
    `/database/${database.id}/table/${table.id}${view ? `/${view.id}` : ""}`,
    baseUrl,
  );
  url.searchParams.set("token", user.refreshToken);

  await page.context().addCookies([
    {
      name: `${baserowConfig.BASEROW_FRONTEND_COOKIE_PREFIX}jwt_token`,
      value: user.refreshToken,
      url: baseUrl,
    },
  ]);
  await page.goto(url.toString(), { waitUntil: "domcontentloaded" });
  await page
    .waitForFunction(
      () =>
        typeof (window as any).useNuxtApp === "function" &&
        !(window as any).useNuxtApp().isHydrating,
      { timeout: 15_000 },
    )
    .catch(() => {
      // The dev server CSP can block this; callers then wait for their view to render.
    });
}
