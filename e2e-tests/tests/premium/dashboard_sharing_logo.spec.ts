/**
 * Hiding the Baserow logo on a shared dashboard is a premium option of the
 * share popover. The instance wide enterprise licence covers it.
 */

import type { Page } from "@playwright/test";
import {
  getDashboardSharing,
  updateDashboardSharing,
} from "../../fixtures/dashboard/dashboard";
import {
  createDashboardWithSummary,
  dashboardEditorUrl,
  publicDashboardUrl,
  SUMMARY_WIDGET_VALUE,
} from "../../fixtures/dashboard/sharing";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../fixtures/licence";
import { expect, test } from "../baserowTest";

const DASHBOARD_NAME = "Dashboard logo e2e";
const PASSWORD = "visitor-password";
const BASEROW_LOGO_LINK = 'a[href="https://baserow.io"]';

async function expectPublicDashboard(page: Page): Promise<void> {
  await expect(page.locator(".dashboard-app__title")).toHaveText(
    DASHBOARD_NAME
  );
  await expect(page.locator(".dashboard-summary-widget__summary")).toHaveText(
    SUMMARY_WIDGET_VALUE
  );
}

test.describe("Dashboard sharing premium options", () => {
  let license: License | undefined;

  test.beforeAll(async () => {
    license = await createLicense(ENTERPRISE_LICENSE);
  });

  test.afterAll(async () => {
    if (license) {
      await deleteLicense(license);
    }
  });

  test("hides the Baserow logo from visitors", async ({
    page,
    browser,
    workspacePage,
  }) => {
    test.setTimeout(90_000);
    const { dashboard } = await createDashboardWithSummary(
      workspacePage.workspace,
      DASHBOARD_NAME
    );
    const { slug } = await updateDashboardSharing(dashboard, { public: true });

    await page.goto(dashboardEditorUrl(dashboard));
    await page
      .locator(".header__filter-link", { hasText: "Share dashboard" })
      .click();
    const popover = page.locator(".dashboard-sharing");
    await expect(popover).toBeVisible();

    const logoOption = popover.locator(".dashboard-sharing__option", {
      hasText: "Hide Baserow logo on shared dashboard",
    });
    await expect(logoOption).not.toHaveClass(
      /dashboard-sharing__option--disabled/
    );
    const logoSwitch = logoOption.locator(".switch");
    await expect(logoSwitch).not.toHaveClass(/switch--active/);

    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        response.url().includes(`/dashboard/${dashboard.id}/premium/`)
    );
    await logoSwitch.click();
    expect((await saved).status()).toBe(200);
    await expect(logoSwitch).toHaveClass(/switch--active/);
    expect((await getDashboardSharing(dashboard)).show_logo).toBe(false);

    const visitorContext = await browser.newContext();
    try {
      const visitor = await visitorContext.newPage();
      await visitor.goto(publicDashboardUrl(slug));
      await expectPublicDashboard(visitor);
      // No logo in the footer and no Baserow suffix in the title, the
      // abuse report link stays.
      await expect(visitor.locator(BASEROW_LOGO_LINK)).toHaveCount(0);
      await expect(
        visitor.locator(".public-dashboard__report-abuse")
      ).toBeVisible();
      await expect(visitor).toHaveTitle(DASHBOARD_NAME);
    } finally {
      await visitorContext.close();
    }

    // The password page of the dashboard follows the same setting.
    await updateDashboardSharing(dashboard, { public_password: PASSWORD });
    const anotherContext = await browser.newContext();
    try {
      const visitor = await anotherContext.newPage();
      await visitor.goto(publicDashboardUrl(slug));
      await expect(
        visitor.getByRole("heading", { name: "Password required" })
      ).toBeVisible();
      await expect(visitor.locator(BASEROW_LOGO_LINK)).toHaveCount(0);
      await expect(visitor).toHaveTitle("Password required");
    } finally {
      await anotherContext.close();
    }
  });
});
