import { Page } from "@playwright/test";
import { getClient } from "../../client";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
} from "../../fixtures/licence";
import { getBrowserRefreshToken, getStaffUser } from "../../fixtures/user";
import { createWorkspace } from "../../fixtures/workspace";
import { WorkspacePage } from "../../pages/workspacePage";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

const identityRow = (page: Page, name: string) =>
  page.locator("tr").filter({ has: page.getByText(name, { exact: true }) });

// Requires identities enabled on both servers (the standard E2E stack uses *).
// Covers the UI/realtime boundary; API permission and execution cases are also
// mapped in docs/testing/identities-test-plan.md.
test("identity lifecycle updates another session and keeps Members human-only @enterprise", async ({
  page,
  browser,
  goto,
}, testInfo) => {
  test.setTimeout(180_000);
  const cleanups: (() => Promise<unknown>)[] = [];
  let bodyFailed = false;

  try {
    const license = await createLicense(ENTERPRISE_LICENSE);
    cleanups.push(() => deleteLicense(license));
    const user = await getStaffUser();
    const client = getClient(user);
    const workspace = await createWorkspace(user, "Identity lifecycle");
    cleanups.push(() => client.delete(`workspaces/${workspace.id}/`));
    const workspacePage = new WorkspacePage({ page, goto }, user, workspace);
    const observerContext = await browser.newContext();
    cleanups.push(() => observerContext.close());
    const observer = await observerContext.newPage();
    const pageErrors: string[] = [];
    for (const currentPage of [page, observer]) {
      currentPage.on("pageerror", (error) => pageErrors.push(error.message));
    }

    const url = `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/workspace/${workspace.id}/settings/identities`;
    await workspacePage.authenticate();
    await goto(url, { waitUntil: "hydration" });
    await expect(
      page
        .locator(".data-table__header")
        .getByRole("button", { name: "Create identity", exact: true })
    ).toBeVisible();

    // Each browser needs its own refresh token because refreshing rotates it.
    const observerToken = await getBrowserRefreshToken(user);
    await observer.goto(
      `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}?token=${observerToken}`
    );
    let observerConnected = false;
    observer.on("websocket", (socket) => {
      socket.on("framereceived", ({ payload }) => {
        const message = JSON.parse(String(payload));
        if (message.type === "authentication" && message.success) {
          observerConnected = true;
        }
      });
    });
    await observer.goto(url);
    await expect(observer.getByPlaceholder("Search identities")).toBeVisible();
    await expect.poll(() => observerConnected).toBe(true);

    const originalName = "Browser identity";
    const renamedName = "Renamed browser identity";
    await page
      .locator(".data-table__header")
      .getByRole("button", { name: "Create identity", exact: true })
      .click();
    let modal = page.locator(".modal__wrapper:visible");
    const create = modal.getByRole("button", {
      name: "Create identity",
      exact: true,
    });
    await expect(create).toBeDisabled();
    await expect(modal).toContainText("No access");
    await modal.locator("input[type=text]").first().fill(originalName);
    await create.click();
    await expect(identityRow(page, originalName)).toBeVisible();
    await expect(identityRow(observer, originalName)).toBeVisible();

    await page
      .getByPlaceholder("Search identities")
      .fill("no matching identity");
    await expect(identityRow(page, originalName)).toHaveCount(0);
    await expect(
      page.getByText("No results found. Try adjusting your search or filters.")
    ).toBeVisible();
    await page.getByPlaceholder("Search identities").fill("");
    await identityRow(page, originalName).locator(".data-table__more").click();
    await page.getByText("Edit identity", { exact: true }).click();
    modal = page.locator(".modal__wrapper:visible");
    await modal.locator("input[type=text]").first().fill(renamedName);
    await modal
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(modal).toContainText("saved");
    await modal
      .locator("button")
      .filter({ hasText: /^Close$/ })
      .click();
    await expect(identityRow(observer, renamedName)).toBeVisible();
    await expect(identityRow(observer, originalName)).toHaveCount(0);

    await identityRow(page, renamedName)
      .getByRole("button", { name: "No access", exact: true })
      .click();
    await page
      .locator(".context__menu-item-title:visible")
      .filter({ hasText: /^\s*Builder\s*$/ })
      .click();
    await expect(
      identityRow(observer, renamedName).getByRole("button", {
        name: "Builder",
        exact: true,
      })
    ).toBeVisible();

    await page
      .locator(".tabs__link")
      .filter({ hasText: /^\s*Members\s*$/ })
      .click();
    await expect(page.locator("tbody tr")).toHaveCount(1);
    await expect(identityRow(page, user.email)).toBeVisible();
    await expect(identityRow(page, renamedName)).toHaveCount(0);
    const members = await client.get(
      `workspaces/users/workspace/${workspace.id}/`
    );
    expect(members.data.map((member) => member.email)).toEqual([user.email]);
    // The Members heading/sidebar intentionally count humans + identities;
    // the rows and API above are the human-only membership boundary.

    await page.locator(".tabs__link").filter({ hasText: "Identities" }).click();
    await identityRow(page, renamedName).locator(".data-table__more").click();
    await page.getByText("Delete identity", { exact: true }).click();
    await expect(identityRow(page, renamedName)).toHaveCount(0);
    await expect(identityRow(observer, renamedName)).toHaveCount(0);

    await page
      .locator(".sidebar__item-name")
      .filter({ hasText: /^\s*Trash\s*$/ })
      .click();
    const entry = page
      .locator(".modal__wrapper:visible .trash-entry")
      .filter({ hasText: renamedName });
    await entry.getByText("Restore", { exact: true }).click();
    await expect(entry).toHaveCount(0);
    await expect(identityRow(observer, renamedName)).toBeVisible();
    await page.keyboard.press("Escape");
    await page.reload();
    await expect(identityRow(page, renamedName)).toBeVisible();
    expect(pageErrors).toEqual([]);
  } catch (error) {
    bodyFailed = true;
    throw error;
  } finally {
    const cleanupErrors: unknown[] = [];
    for (const cleanup of cleanups.reverse()) {
      try {
        await cleanup();
      } catch (error) {
        cleanupErrors.push(error);
      }
    }
    if (cleanupErrors.length) {
      testInfo.annotations.push({
        type: "cleanup-error",
        description: cleanupErrors.map(String).join("\n"),
      });
      if (!bodyFailed) {
        throw new AggregateError(
          cleanupErrors,
          "Identity lifecycle cleanup failed"
        );
      }
    }
  }
});
