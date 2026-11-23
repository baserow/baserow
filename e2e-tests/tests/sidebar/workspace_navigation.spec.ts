import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { expect, test } from "../baserowTest";

test("the mobile workspace sidebar opens by default and remembers when dismissed", async ({
  page,
  workspacePage,
}) => {
  const phone = { width: 390, height: 844 };
  await page.setViewportSize(phone);
  await workspacePage.goto();

  const sidebar = page.locator(".sidebar");
  const addNew = sidebar.locator('[data-highlight="create-new"]');
  await expect(addNew).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    phone.width
  );

  await page.locator(".layout__sidebar-backdrop").click({
    position: { x: phone.width - 10, y: 100 },
  });
  await expect(addNew).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    phone.width
  );
  await page.setViewportSize({ width: 844, height: 390 });
  await expect(addNew).toBeVisible();
  await page.setViewportSize(phone);
  await expect(addNew).toBeHidden();
  await sidebar.locator(".sidebar__foot-link .baserow-icon-sidebar").click();
  await expect(addNew).toBeInViewport();
});

test("the workspace tour can be completed on a phone", async ({
  page,
  workspacePage,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await workspacePage.goto();
  await page.locator(".sidebar__account-trigger").click();
  await page.getByRole("button", { name: "Replay guided tour" }).click();

  const step = page.locator(".guided-tour-step");
  await step.getByRole("button", { name: "Start the tour" }).click();
  const next = step.getByRole("button", { name: "Next" });
  await expect(next).toBeInViewport({ ratio: 1 });
  await next.click();
  await expect(step.locator(".guided-tour-step__title")).toHaveText(
    "Create a new database or application"
  );
  await expect(page.locator('[data-highlight="create-new"]')).toBeInViewport();
  for (const name of ["Back", "Stop tour"]) {
    await expect(step.getByRole("link", { name })).toBeInViewport({ ratio: 1 });
  }
  const finish = step.getByRole("button", { name: "Got it" });
  await expect(finish).toBeInViewport({ ratio: 1 });
  await finish.click();
  await expect(step).toBeHidden();
});

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

test("the tables tour reveals and highlights the selected database", async ({
  page,
  workspacePage,
}) => {
  const { user, workspace } = workspacePage;
  const first = await createDatabase(user, "First database", workspace);
  const active = await createDatabase(user, "Active database", workspace);
  await createTable(user, "Current table", active, [["Name"], ["Record"]]);
  await workspacePage.goto();

  const sidebar = page.locator(".sidebar");
  const firstTitle = sidebar.getByTitle(first.name, { exact: true });
  const activeTitle = sidebar.getByTitle(active.name, { exact: true });
  await firstTitle.click();
  await activeTitle.click();
  await sidebar
    .locator(".tree__sub-link")
    .filter({ hasText: "Current table" })
    .click();
  await expect(page).toHaveURL(/\/database\/\d+\/table\/\d+/);
  await activeTitle.click();
  const databases = sidebar.getByRole("button", {
    name: "Databases",
    exact: true,
  });
  await databases.click();
  await expect(databases).toHaveAttribute("aria-expanded", "false");

  await sidebar.locator(".sidebar__account-trigger").click();
  await page.getByRole("button", { name: "Replay guided tour" }).click();
  const step = page.locator(".guided-tour-step");
  await expect(step).toBeVisible();
  const title = step.locator(".guided-tour-step__title");
  const advance = step.locator(".guided-tour-step__foot .button");
  while ((await title.innerText()) !== "Setup tables") {
    const previousTitle = await title.innerText();
    await expect(advance).not.toHaveText("Got it");
    await advance.click();
    await expect(title).not.toHaveText(previousTitle);
  }
  await expect(title).toHaveText("Setup tables");
  await expect(databases).toHaveAttribute("aria-expanded", "true");
  await expect(firstTitle).toHaveAttribute("aria-expanded", "true");
  await expect(activeTitle).toHaveAttribute("aria-expanded", "true");

  const target = sidebar.locator(
    `[data-highlight="create-table-${active.id}"]`
  );
  await expect(target).toBeInViewport();
  // The highlight includes two pixels of padding on each side of the button.
  await expect
    .poll(async () => {
      const box = await target.boundingBox();
      const highlight = await page.locator(".highlight").boundingBox();
      return box && highlight
        ? Math.max(
            Math.abs(box.x - highlight.x - 2),
            Math.abs(box.y - highlight.y - 2)
          )
        : Infinity;
    })
    .toBeLessThan(2);
});
