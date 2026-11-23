import { expect, test } from "../baserowTest";

test("Tab skips application groups and the workspace picker stays keyboard accessible", async ({
  page,
  workspacePage,
}) => {
  await workspacePage.goto();
  const sidebar = page.locator(".sidebar");
  const group = sidebar.locator(".tree__heading-name").first();
  await expect(group).toBeVisible();
  const picker = sidebar.locator(".sidebar__workspace-trigger");
  await picker.focus();
  await page.keyboard.press("Tab");
  await expect(sidebar.locator(":focus")).toHaveCount(0);
  await page.keyboard.press("Shift+Tab");
  await expect(picker).toBeFocused();

  await page.keyboard.press("Enter");
  const options = page.locator("[data-workspace-option]:visible");
  await page.keyboard.press("ArrowDown");
  await expect(options.first()).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(picker).toBeFocused();

  await group.click();
  await expect(group).toHaveAttribute("aria-expanded", "false");
});
