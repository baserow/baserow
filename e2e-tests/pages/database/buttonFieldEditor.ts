import { Page, expect } from "@playwright/test";

/**
 * Driving a button field's action editor from the grid: opening it, adding and
 * expanding actions, and picking values out of the data explorer.
 *
 * Shared by the button field suites so the two specs cannot drift apart on how
 * the editor is reached.
 */

/** The header column of a non-primary field, by name. */
export function fieldHeader(page: Page, name: string) {
  return page
    .locator(".grid-view__right .grid-view__head .grid-view__column")
    .filter({
      has: page.locator(".grid-view__description-name", {
        hasText: new RegExp(`^\\s*${name}\\s*$`),
      }),
    });
}

/** Matches a whole label, so one name cannot select another that contains it. */
export function exactly(name: string) {
  return new RegExp(`^\\s*${name}\\s*$`);
}

/** Opens a field's "Edit field" form from its header dropdown. */
export async function openFieldEditor(page: Page, name: string) {
  // The Context self-hides when it does not fit, and the first click can land
  // before the header has settled, so open it until the menu is really there.
  const editItem = page.locator(".context__menu-item", {
    hasText: "Edit field",
  });
  await expect(async () => {
    await fieldHeader(page, name)
      .locator(".grid-view__description-icon-trigger")
      .click();
    await expect(editItem).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await editItem.click();
  await expect(page.locator(".button-field-action-list")).toBeVisible();
}

export async function saveField(page: Page) {
  await page.locator(".field-context button", { hasText: "Save" }).click();
}

/** The data explorer that opens under a formula input. */
export function explorer(page: Page) {
  return page.locator("[data-formula-input-context]:visible");
}

/** Walks the explorer, opening each node in turn and picking the last. */
export async function pickExplorerNode(page: Page, ...names: string[]) {
  for (const name of names) {
    await explorer(page)
      .locator(".node-explorer-content__name", {
        hasText: new RegExp(`^\\s*${name}\\s*$`),
      })
      .first()
      .click();
  }
}

/** One action's row in the editor's list. */
export function actionItem(page: Page, index: number) {
  return page
    .locator(".button-field-action-list .button-field-action-list__item")
    .nth(index);
}

/**
 * Opens an action's card. Saved actions load collapsed, so anything that
 * reaches into a form has to open it first, the way a user would.
 */
export async function expandAction(page: Page, index: number) {
  const item = actionItem(page, index);
  const form = item.locator(".button-field-action-list__form");
  if (!(await form.isVisible())) {
    await item.locator("[data-action-toggle]").click();
    await expect(form).toBeVisible();
  }
}

/** Adds an action of `type` at the end of the list. */
export async function addAction(page: Page, type: string) {
  const list = page.locator(".button-field-action-list");
  const before = await list.locator(".button-field-action-list__item").count();
  // The explorer hides when the formula input loses focus, and it stays open
  // over the list until then. The section heading is above the cards, so
  // clicking it blurs the editor without the popup in the way.
  await list.locator(".button-field-action-list__title").click();
  await list.getByText("Add action").click();
  const added = actionItem(page, before);
  await added.locator(".button-field-action-list__type").click();
  await page
    .locator(".dropdown__items:visible")
    .locator(".select__item-link", { hasText: exactly(type) })
    .click();
  return added;
}

/** The action type shown on each row of the list, in order. */
export async function actionOrder(page: Page) {
  return await page
    .locator(".button-field-action-list .button-field-action-list__type")
    .allTextContents();
}

/** Points a row action at a table by picking its database and table. */
export async function pickTableOn(
  page: Page,
  index: number,
  database: string,
  table: string,
) {
  await expandAction(page, index);
  const dropdowns = actionItem(page, index).locator(
    ".button-field-action-list__form .dropdown",
  );
  for (const [position, name] of [
    [0, database],
    [1, table],
  ] as [number, string][]) {
    await dropdowns.nth(position).click();
    // Matched whole, or "Tickets" also picks up the "Tickets 2" the
    // duplication test leaves behind.
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: exactly(name) })
      .click();
  }
}
