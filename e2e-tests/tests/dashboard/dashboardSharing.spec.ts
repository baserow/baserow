import type { Browser, BrowserContext, Locator, Page } from "@playwright/test";
import {
  Dashboard,
  getDashboardSharing,
  updateDashboardSharing,
} from "../../fixtures/dashboard/dashboard";
import {
  createDashboardWithSummary,
  dashboardEditorUrl,
  publicDashboardUrl,
  SUMMARY_WIDGET_VALUE,
} from "../../fixtures/dashboard/sharing";
import { expect, test } from "../baserowTest";

const DASHBOARD_NAME = "Dashboard sharing e2e";
const PASSWORD = "visitor-password";

async function openDashboard(page: Page, dashboard: Dashboard): Promise<void> {
  await page.goto(dashboardEditorUrl(dashboard));
  await expect(page.getByText("Edit mode", { exact: true })).toBeVisible();
}

function shareDashboardLink(page: Page): Locator {
  return page.locator(".header__filter-link", { hasText: "Share dashboard" });
}

/** Opens the share popover from the header and returns its content. */
async function openSharePopover(page: Page): Promise<Locator> {
  await shareDashboardLink(page).click();
  const popover = page.locator(".dashboard-sharing");
  await expect(popover).toBeVisible();
  return popover;
}

/** A browser context of its own: someone who has the link but is not logged in. */
async function openVisitor(
  browser: Browser
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  return { context, page };
}

async function expectPublicDashboard(page: Page): Promise<void> {
  await expect(page.locator(".dashboard-app__title")).toHaveText(
    DASHBOARD_NAME
  );
  await expect(page.locator(".dashboard-summary-widget__summary")).toHaveText(
    SUMMARY_WIDGET_VALUE
  );
}

async function expectNotFound(page: Page): Promise<void> {
  await expect(page.locator(".placeholder__title")).toHaveText(
    "Dashboard not found."
  );
}

async function expectPasswordPage(page: Page, slug: string): Promise<void> {
  await expect(page).toHaveURL(new RegExp(`/public/dashboard/${slug}/auth`));
  await expect(
    page.getByRole("heading", { name: "Password required" })
  ).toBeVisible();
}

test.describe("Dashboard sharing", () => {
  test("shares the dashboard through a private link and takes it back", async ({
    page,
    browser,
    workspacePage,
  }) => {
    test.setTimeout(90_000);
    const { dashboard } = await createDashboardWithSummary(
      workspacePage.workspace,
      DASHBOARD_NAME
    );
    await openDashboard(page, dashboard);

    const popover = await openSharePopover(page);
    await expect(
      popover.getByText("You have not yet shared this dashboard")
    ).toBeVisible();
    await expect(shareDashboardLink(page)).not.toHaveClass(/active/);

    await popover
      .getByRole("button", { name: "Create a private link" })
      .click();
    await expect(
      popover.getByText("This dashboard is currently shared via a private link")
    ).toBeVisible();
    await expect(shareDashboardLink(page)).toHaveClass(/active/);

    const { slug } = await getDashboardSharing(dashboard);
    await expect(
      popover.locator(".dashboard-sharing__shared-link-box")
    ).toContainText(`/public/dashboard/${slug}`);

    const visitor = await openVisitor(browser);
    try {
      await visitor.page.goto(publicDashboardUrl(slug));
      await expectPublicDashboard(visitor.page);
      await expect(visitor.page).toHaveTitle(new RegExp(`^${DASHBOARD_NAME}`));

      // Visitors only look: no header with the edit and share items.
      await expect(
        visitor.page.getByText("Edit mode", { exact: true })
      ).toHaveCount(0);
      await expect(visitor.page.locator(".header__filter-link")).toHaveCount(0);
      const footer = visitor.page.locator(".public-dashboard__footer");
      await expect(
        footer.locator('a[href="https://baserow.io"]')
      ).toBeVisible();
      await expect(
        footer.locator(".public-dashboard__report-abuse")
      ).toBeVisible();

      await popover
        .getByRole("button", { name: "Disable shared link" })
        .click();
      await expect(
        popover.getByText("You have not yet shared this dashboard")
      ).toBeVisible();
      await expect(shareDashboardLink(page)).not.toHaveClass(/active/);

      await visitor.page.goto(publicDashboardUrl(slug));
      await expectNotFound(visitor.page);
    } finally {
      await visitor.context.close();
    }

    // A member of the workspace can always open the link, shared or not.
    await page.goto(publicDashboardUrl(slug));
    await expectPublicDashboard(page);

    // Sharing again hands out the same link.
    const resharedDashboard = await updateDashboardSharing(dashboard, {
      public: true,
    });
    expect(resharedDashboard.slug).toBe(slug);
  });

  test("asks visitors for the password once one is set", async ({
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
    await openDashboard(page, dashboard);
    const popover = await openSharePopover(page);

    await popover
      .locator(".switch", { hasText: "Restrict access with a password" })
      .click();
    const enableModal = page.locator(".modal__box", {
      hasText: "Enter a password",
    });
    await expect(enableModal).toBeVisible();
    const passwordInput = enableModal.locator('input[type="password"]');
    const setPassword = enableModal.getByRole("button", {
      name: "Set password",
    });
    // A password needs 8 characters at least.
    await passwordInput.fill("short12");
    await expect(setPassword).toBeDisabled();
    await passwordInput.fill(PASSWORD);
    await expect(setPassword).toBeEnabled();
    await setPassword.click();
    await expect(enableModal).toBeHidden();

    const protectedSwitch = popover.locator(".switch", {
      hasText: "Access is password-protected",
    });
    await expect(protectedSwitch).toHaveClass(/switch--active/);
    expect((await getDashboardSharing(dashboard)).public_has_password).toBe(
      true
    );

    const visitor = await openVisitor(browser);
    try {
      await visitor.page.goto(publicDashboardUrl(slug));
      await expectPasswordPage(visitor.page, slug);

      const visitorPassword = visitor.page.getByPlaceholder("Password...");
      const submit = visitor.page.getByRole("button", { name: "Continue" });
      await visitorPassword.fill("wrong-password");
      await submit.click();
      await expect(visitor.page.locator(".alert")).toContainText(
        "Incorrect password"
      );
      await expectPasswordPage(visitor.page, slug);

      await visitorPassword.fill(PASSWORD);
      await submit.click();
      await expect(visitor.page).toHaveURL(publicDashboardUrl(slug));
      await expectPublicDashboard(visitor.page);

      // The password is remembered, a reload doesn't ask for it again.
      await visitor.page.reload();
      await expectPublicDashboard(visitor.page);
    } finally {
      await visitor.context.close();
    }

    await protectedSwitch.click();
    const disableModal = page.locator(".modal__box", {
      hasText: "Disable password protection for this public link?",
    });
    await expect(disableModal).toBeVisible();
    await disableModal
      .getByRole("button", { name: "Disable", exact: true })
      .click();
    await expect(disableModal).toBeHidden();
    await expect(
      popover.locator(".switch", { hasText: "Restrict access with a password" })
    ).not.toHaveClass(/switch--active/);
    expect((await getDashboardSharing(dashboard)).public_has_password).toBe(
      false
    );

    const anotherVisitor = await openVisitor(browser);
    try {
      await anotherVisitor.page.goto(publicDashboardUrl(slug));
      await expectPublicDashboard(anotherVisitor.page);
    } finally {
      await anotherVisitor.context.close();
    }
  });

  test("generating a new URL stops the old one from working", async ({
    page,
    browser,
    workspacePage,
  }) => {
    test.setTimeout(90_000);
    const { dashboard } = await createDashboardWithSummary(
      workspacePage.workspace,
      DASHBOARD_NAME
    );
    const { slug: oldSlug } = await updateDashboardSharing(dashboard, {
      public: true,
    });
    await openDashboard(page, dashboard);
    const popover = await openSharePopover(page);
    const linkBox = popover.locator(".dashboard-sharing__shared-link-box");
    await expect(linkBox).toContainText(`/public/dashboard/${oldSlug}`);

    await popover
      .locator(".dashboard-sharing__shared-link-action", {
        has: page.locator(".iconoir-refresh-double"),
      })
      .click();
    const rotateModal = page.locator(".modal__box", {
      hasText: `Refresh the URL of ${DASHBOARD_NAME}?`,
    });
    await expect(rotateModal).toBeVisible();
    await rotateModal.getByRole("button", { name: "Generate new URL" }).click();
    await expect(
      page.locator(".toast__title", {
        hasText: "Successfully generated new URL",
      })
    ).toBeVisible();
    await expect(rotateModal).toBeHidden();

    const { slug: newSlug } = await getDashboardSharing(dashboard);
    expect(newSlug).not.toBe(oldSlug);
    await expect(linkBox).toContainText(`/public/dashboard/${newSlug}`);

    const visitor = await openVisitor(browser);
    try {
      await visitor.page.goto(publicDashboardUrl(oldSlug));
      await expectNotFound(visitor.page);

      await visitor.page.goto(publicDashboardUrl(newSlug));
      await expectPublicDashboard(visitor.page);
    } finally {
      await visitor.context.close();
    }
  });
});
