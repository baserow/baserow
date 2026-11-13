import { Page } from "@playwright/test";
import { getClient } from "../../client";
import { createDatabase } from "../../fixtures/database/database";
import { createField, Field } from "../../fixtures/database/field";
import { listRows, updateRows } from "../../fixtures/database/rows";
import { createTable } from "../../fixtures/database/table";
import { exactly, fieldHeader } from "../../pages/database/buttonFieldEditor";
import { GridPage } from "../../pages/database/gridPage";
import { expect, test } from "../baserowTest";

// The form copy, from web-frontend/modules/database/locales/en.json.
const COPY = {
  assign: "Allow assigning identities",
  mention: "Allow mentioning identities",
  removes: "Saving removes the identities already assigned in this field.",
};
const IDENTITY_ICON = ".iconoir-lock";

async function editField(page: Page, name: string, option: string) {
  const editItem = page.locator(".context__menu-item:visible", {
    hasText: exactly("Edit field"),
  });
  await expect(async () => {
    await fieldHeader(page, name)
      .locator(".grid-view__description-icon-trigger")
      .click();
    await expect(editItem).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await editItem.click();
  const form = page.locator(".field-context:visible");
  await form.locator(".checkbox", { hasText: option }).click();
  return form;
}

async function saveField(page: Page, field: Field) {
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/database/fields/${field.id}/`)
  );
  await page
    .locator(".field-context:visible button", { hasText: "Save" })
    .click();
  expect((await saved).status()).toBe(200);
  await expect(page.locator(".field-context:visible")).toHaveCount(0);
}

async function openPicker(gridPage: GridPage) {
  await gridPage.selectFieldCell(0, 0);
  await gridPage
    .fieldCellAt(0, 0)
    .locator(".grid-field-many-to-many__item--link")
    .click();
  return gridPage.page.locator(".select__items:visible");
}

test("identities are assignable and mentionable only where a field allows it", async ({
  page,
  workspacePage,
}) => {
  test.setTimeout(180_000);
  const { user, workspace } = workspacePage;
  const client = getClient(user);
  const userId = (
    await client.get(`workspaces/users/workspace/${workspace.id}/`)
  ).data[0].user_id;
  const identity = (
    await client.post(`identities/workspace/${workspace.id}/`, { name: "Ops" })
  ).data;
  const database = await createDatabase(user, "Identities", workspace);
  const table = await createTable(user, "Tasks", database, [
    ["Name"],
    ["Task"],
  ]);
  const owners = await createField(
    user,
    "Owners",
    "multiple_collaborators",
    {},
    table
  );
  await createField(
    user,
    "Count",
    "formula",
    { formula: "count(field('Owners'))" },
    table
  );
  const notes = await createField(
    user,
    "Notes",
    "long_text",
    { long_text_enable_rich_text: true },
    table
  );
  const ownersOf = async () =>
    ((await listRows(user, table))[0].Owners as { id: number }[])
      .map((owner) => owner.id)
      .sort();
  const countOf = async () => Number((await listRows(user, table))[0].Count);

  const gridPage = new GridPage(page, user);
  await gridPage.goTo(database, table);

  // Off by default: only people can be picked.
  let picker = await openPicker(gridPage);
  await expect(picker.getByText(user.name, { exact: true })).toBeVisible();
  await expect(picker.getByText(identity.name, { exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");

  // On: the identity is listed in its own group and can be assigned.
  await editField(page, "Owners", COPY.assign);
  await saveField(page, owners);
  picker = await openPicker(gridPage);
  const option = picker.locator(".select-collaborators__dropdown-item", {
    hasText: identity.name,
  });
  await expect(option.locator(IDENTITY_ICON)).toBeVisible();
  await option.click();
  await expect(gridPage.fieldCellAt(0, 0)).toContainText(identity.name);
  // Adding the person through the API keeps the picker steps about identities.
  const [row] = await listRows(user, table);
  await updateRows(user, table, [
    { id: row.id, Owners: [{ id: identity.id }, { id: userId }] },
  ]);
  await expect.poll(ownersOf).toEqual([userId, identity.id].sort());
  await expect.poll(countOf).toBe(2);

  // Off again: the form warns, then the identity is removed and stops counting.
  const form = await editField(page, "Owners", COPY.assign);
  await expect(form.getByText(COPY.removes)).toBeVisible();
  await saveField(page, owners);
  await expect(gridPage.fieldCellAt(0, 0)).not.toContainText(identity.name);
  await expect.poll(ownersOf).toEqual([userId]);
  await expect.poll(countOf).toBe(1);

  // Undo brings the removed identity back.
  await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
  await page.keyboard.press("ControlOrMeta+z");
  await expect(
    page.locator(".toast", { hasText: "Action is undone" })
  ).toBeVisible();
  await expect.poll(ownersOf).toEqual([userId, identity.id].sort());
  await expect.poll(countOf).toBe(2);

  // Mentions follow the long text field's own option.
  const mentionList = page.locator(".rich-text-editor__mention-list:visible");
  const suggest = async () => {
    await gridPage.selectFieldCell(0, 2);
    await page.keyboard.press("Enter");
    await expect(gridPage.activeRichTextEditor()).toBeVisible();
    // Start from an empty cell: a mention only starts after a space or nothing.
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.press("Backspace");
    await page.keyboard.type("@O");
  };
  await suggest();
  await expect(
    page.locator(".rich-text-editor__mention-list-item:visible", {
      hasText: identity.name,
    })
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");

  await editField(page, "Notes", COPY.mention);
  await saveField(page, notes);
  await suggest();
  const suggestion = mentionList.locator(
    ".rich-text-editor__mention-list-item",
    {
      hasText: identity.name,
    }
  );
  await expect(suggestion.locator(IDENTITY_ICON)).toBeVisible();
});
