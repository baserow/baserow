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
  removes: "Saving removes the identities already assigned in this field.",
};
const IDENTITY_ICON = ".iconoir-hexagon";

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
  const picker = gridPage.page.locator(".select__items:visible");
  await expect(async () => {
    if (!(await picker.isVisible())) {
      await gridPage.selectFieldCell(0, 0);
      await gridPage
        .fieldCellAt(0, 0)
        .locator(".grid-field-many-to-many__item--link")
        .click();
    }
    await expect(picker).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  return picker;
}

test("identities are assignable only where a collaborator field allows it", async ({
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
  await createField(
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
  await test.info().attach("Collaborator picker with identity", {
    body: await picker.screenshot(),
    contentType: "image/png",
  });
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
  await test.info().attach("Collaborator field settings", {
    body: await form.screenshot(),
    contentType: "image/png",
  });
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

  // Long text fields never suggest identities.
  const mentionList = page.locator(".rich-text-editor__mention-list:visible");
  const editor = gridPage.activeRichTextEditor();
  await gridPage.startEditingRichTextField(0, 2);
  await editor.click();
  await editor.pressSequentially("@");
  await expect(mentionList.getByText(user.name, { exact: true })).toBeVisible();
  await expect(
    mentionList.getByText(identity.name, { exact: true })
  ).toHaveCount(0);
});
