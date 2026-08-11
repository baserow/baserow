/**
 * View ownership type toggle - permission-gated visibility.
 *
 * Verifies that the "To personal" / "To collaborative" context menu item
 * is shown or hidden based on the user's role and the view's ownership type.
 *
 * Requires enterprise license (for RBAC roles: Editor, Builder, Viewer).
 */

import type { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import { setupGrid } from "../../fixtures/database/gridSetup";
import type { GridSetupResult } from "../../fixtures/database/gridSetup";
import { createUser, deleteUser, User } from "../../fixtures/user";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../fixtures/licence";
import { addWorkspaceMember } from "../../fixtures/workspaceMember";
import { getClient } from "../../client";
import { View } from "../../fixtures/database/view";

async function createPersonalView(
  user: User,
  table: { id: number },
  name: string,
): Promise<View> {
  const response: any = await getClient(user).post(
    `database/views/table/${table.id}/`,
    { name, type: "grid", ownership_type: "personal" },
  );
  const d = response.data;
  return new View(d.id, d.name, d.type, d.slug, table as any);
}

async function openViewContextMenu(page: Page, viewName: string) {
  await page
    .locator(".header__filter-item--grids .header__filter-link")
    .click();
  const viewsDropdown = page.locator(
    ".select__items.select__items--no-max-height",
  );
  await expect(viewsDropdown).toBeVisible({ timeout: 5000 });
  const viewItem = viewsDropdown.locator(".select__item", {
    hasText: viewName,
  });
  await viewItem.hover();
  await viewItem.locator("a.select__item-options").click();
}

async function expectContextMenuOpen(page: Page) {
  await expect(
    page.locator(".context__menu:visible"),
  ).toBeVisible({ timeout: 5000 });
}

function ownershipToggleLocator(
  page: Page,
  text: "To personal" | "To collaborative",
) {
  return page.locator(".context__menu-item-link", { hasText: text });
}

test.describe("View ownership type toggle permissions", () => {
  let license: License;
  let g: GridSetupResult;
  let editor: User;
  let builder: User;
  let viewer: User;

  test.beforeAll(async () => {
    license = await createLicense(ENTERPRISE_LICENSE);

    g = await setupGrid({
      dbName: "ViewOwnershipDb",
      fields: [{ name: "Score", type: "number" }],
      rows: [{ Name: "Alice", Score: 10 }],
    });

    editor = await createUser();
    builder = await createUser();
    viewer = await createUser();

    const workspace = g.database.workspace;
    await addWorkspaceMember(g.user, workspace, editor, "EDITOR");
    await addWorkspaceMember(g.user, workspace, builder, "BUILDER");
    await addWorkspaceMember(g.user, workspace, viewer, "VIEWER");
  });

  test.afterAll(async () => {
    await deleteLicense(license);
    await deleteUser(editor);
    await deleteUser(builder);
    await deleteUser(viewer);
  });

  test("editor cannot see 'To personal' on admin's collaborative view", async ({
    page,
  }) => {
    const grid = new GridPage(page, editor);
    await grid.goTo(g.database, g.table, g.view);
    await openViewContextMenu(page, g.view.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To personal")).toHaveCount(0);
  });

  test("builder can see 'To personal' on admin's collaborative view", async ({
    page,
  }) => {
    const grid = new GridPage(page, builder);
    await grid.goTo(g.database, g.table, g.view);
    await openViewContextMenu(page, g.view.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To personal")).toBeVisible();
  });

  test("editor cannot see 'To collaborative' on own personal view", async ({
    page,
  }) => {
    const personalView = await createPersonalView(
      editor,
      g.table,
      "Editor Personal",
    );
    const grid = new GridPage(page, editor);
    await grid.goTo(g.database, g.table, personalView);
    await openViewContextMenu(page, personalView.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To collaborative")).toHaveCount(0);
  });

  test("builder can see 'To collaborative' on own personal view", async ({
    page,
  }) => {
    const personalView = await createPersonalView(
      builder,
      g.table,
      "Builder Personal",
    );
    const grid = new GridPage(page, builder);
    await grid.goTo(g.database, g.table, personalView);
    await openViewContextMenu(page, personalView.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To collaborative")).toBeVisible();
  });

  test("admin can see 'To personal' on collaborative view", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table, g.view);
    await openViewContextMenu(page, g.view.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To personal")).toBeVisible();
  });

  test("viewer cannot see 'To collaborative' on own personal view", async ({
    page,
  }) => {
    const personalView = await createPersonalView(
      viewer,
      g.table,
      "Viewer Personal",
    );
    const grid = new GridPage(page, viewer);
    await grid.goTo(g.database, g.table, personalView);
    await openViewContextMenu(page, personalView.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To collaborative")).toHaveCount(0);
  });

  test("viewer cannot see 'To personal' on collaborative view", async ({
    page,
  }) => {
    const grid = new GridPage(page, viewer);
    await grid.goTo(g.database, g.table, g.view);
    await openViewContextMenu(page, g.view.name);
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To personal")).toHaveCount(0);
  });

  test("builder can convert collaborative view to personal", async ({
    page,
  }) => {
    const builderView = await createPersonalView(
      builder,
      g.table,
      "Builder Convert Test",
    );
    // First convert personal → collaborative so we have a collab view owned by builder
    await getClient(builder).patch(`database/views/${builderView.id}/`, {
      ownership_type: "collaborative",
    });

    const grid = new GridPage(page, builder);
    await grid.goTo(g.database, g.table, builderView);
    await openViewContextMenu(page, "Builder Convert Test");
    await expectContextMenuOpen(page);
    const toggle = ownershipToggleLocator(page, "To personal");
    await expect(toggle).toBeVisible();
    await toggle.click();

    // Wait for the ownership change to propagate
    await page.waitForTimeout(1000);

    // Verify conversion succeeded — menu now shows "To collaborative"
    await openViewContextMenu(page, "Builder Convert Test");
    await expectContextMenuOpen(page);
    await expect(ownershipToggleLocator(page, "To collaborative")).toBeVisible();
  });
});
