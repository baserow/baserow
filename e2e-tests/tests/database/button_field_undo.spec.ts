/**
 * Undoing a button field's action configuration, end to end.
 *
 * The backend tests group the actions by hand and the frontend tests mock the
 * service, so only this file proves the editor sends a save under one action
 * group, that one Ctrl+Z takes all of it back, and that the editor shows what
 * the undo left.
 */

import { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import {
  actionItem,
  addAction,
  exactly,
  fieldHeader,
  openFieldEditor,
  saveField,
} from "../../pages/database/buttonFieldEditor";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import {
  createOpenUrlAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import { getFieldsForTable } from "../../fixtures/database/field";

// Positions in the right-hand section, in the order `beforeAll` creates them.
const UNDONE_FIELD_INDEX = 0;
const REDONE_FIELD_INDEX = 1;

let g: GridSetupResult;

/** The field as the server has it now, looked up by name. */
async function fieldNamed(name: string) {
  const fields = await getFieldsForTable(g.user, g.table);
  const field = fields.find((candidate) => candidate.name === name);
  if (!field) throw new Error(`no field named ${name}`);
  return field;
}

async function actionUrls(name: string) {
  const actions = await listWorkflowActions(g.user, await fieldNamed(name));
  return actions.map((action) => action.url.formula);
}

/**
 * Presses the undo shortcut and waits for the toast to say it worked. The app
 * ignores the shortcut while an input has focus, and the closed editor's label
 * input can still hold it, so focus is dropped first. It also ignores a redo
 * while an undo is still running, hence the wait.
 */
async function pressUndo(page: Page, { redo = false } = {}) {
  await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
  await page.keyboard.press(redo ? "ControlOrMeta+Shift+z" : "ControlOrMeta+z");
  await expect(
    page.locator(".toast", {
      hasText: redo ? "Action is redone" : "Action is undone",
    })
  ).toBeVisible();
}

/** Removes an action from the editor's list by its position. */
async function removeAction(page: Page, index: number) {
  const items = page.locator(
    ".button-field-action-list .button-field-action-list__item"
  );
  const before = await items.count();
  await actionItem(page, index)
    .locator(".button-field-action-list__header .button-icon")
    .click();
  await expect(items).toHaveCount(before - 1);
}

/** Saves the open editor and waits for it to close once every call is done. */
async function saveAndClose(page: Page) {
  await saveField(page);
  // A save is a field update plus one call per changed action.
  await expect(page.locator(".field-context:visible")).toHaveCount(0, {
    timeout: 20_000,
  });
}

async function closeFieldEditor(page: Page) {
  await page
    .locator(".field-context:visible")
    .locator("a.form-action", { hasText: "Cancel" })
    .click();
  await expect(page.locator(".field-context:visible")).toHaveCount(0);
}

test.describe("Button field, undo", () => {
  test.use({ viewport: { width: 1800, height: 900 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Undo DB",
      tableName: "Tickets",
      fields: [
        { name: "Undone", type: "button", settings: { label: "Before" } },
        { name: "Redone", type: "button", settings: { label: "Before" } },
        { name: "Convert", type: "text" },
      ],
    });

    for (const name of ["Undone", "Redone"]) {
      await createOpenUrlAction(g.user, g.fieldByName[name], {
        url: "'/keep'",
      });
      await createOpenUrlAction(g.user, g.fieldByName[name], {
        url: "'/drop'",
      });
    }
  });

  test("one undo takes back the label and the removed action together", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    const button = grid.fieldCellAt(0, UNDONE_FIELD_INDEX).locator("button");

    await openFieldEditor(page, "Undone");
    await page
      .locator(".field-context:visible")
      .getByPlaceholder("Open")
      .fill("After");
    await removeAction(page, 1);
    await saveAndClose(page);

    await expect(button).toHaveText("After");
    await expect(async () => {
      expect(await actionUrls("Undone")).toEqual(["'/keep'"]);
    }).toPass({ timeout: 15_000 });

    await pressUndo(page);

    // The field update, the delete and the order were sent as one group, so
    // one undo reverts all three.
    await expect(button).toHaveText("Before");
    await expect(async () => {
      expect(await actionUrls("Undone")).toEqual(["'/keep'", "'/drop'"]);
    }).toPass({ timeout: 15_000 });

    // The editor keeps its buffer between opens, so without re-reading the
    // list it would still show one action, and saving would delete the other.
    await openFieldEditor(page, "Undone");
    await expect(
      page.locator(".button-field-action-list .button-field-action-list__item")
    ).toHaveCount(2);
  });

  test("redo puts the whole save back, and the editor follows", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    const button = grid.fieldCellAt(0, REDONE_FIELD_INDEX).locator("button");
    const items = page.locator(
      ".button-field-action-list .button-field-action-list__item"
    );

    await openFieldEditor(page, "Redone");
    await page
      .locator(".field-context:visible")
      .getByPlaceholder("Open")
      .fill("After");
    await removeAction(page, 0);
    await saveAndClose(page);
    await expect(button).toHaveText("After");

    await pressUndo(page);
    await expect(button).toHaveText("Before");
    await openFieldEditor(page, "Redone");
    await expect(items).toHaveCount(2);
    await closeFieldEditor(page);

    await pressUndo(page, { redo: true });

    await expect(button).toHaveText("After");
    await expect(async () => {
      expect(await actionUrls("Redone")).toEqual(["'/drop'"]);
    }).toPass({ timeout: 15_000 });

    await openFieldEditor(page, "Redone");
    await expect(items).toHaveCount(1);
  });

  test("undoing a field made into a button, then redoing it, keeps its action", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await fieldHeader(page, "Convert")
      .locator(".grid-view__description-icon-trigger")
      .click();
    await page
      .locator(".context__menu-item", { hasText: exactly("Edit field") })
      .click();
    const context = page.locator(".field-context:visible");
    await context.locator(".dropdown").first().click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: "Button" })
      .click();
    await context.getByPlaceholder("Open").fill("Go");
    await addAction(page, "Open URL");
    await saveAndClose(page);

    let actionId: number | undefined;
    await expect(async () => {
      const field = await fieldNamed("Convert");
      expect(field.type).toBe("button");
      const actions = await listWorkflowActions(g.user, field);
      expect(actions.map((action) => action.type)).toEqual(["open_url"]);
      actionId = actions[0].id;
    }).toPass({ timeout: 15_000 });

    await pressUndo(page);
    await expect(async () => {
      expect((await fieldNamed("Convert")).type).toBe("text");
    }).toPass({ timeout: 15_000 });

    await pressUndo(page, { redo: true });

    // Turning the field back into text deletes its actions, so redo only
    // brings the action back if the undo kept it, under the same id.
    await expect(async () => {
      const field = await fieldNamed("Convert");
      expect(field.type).toBe("button");
      const actions = await listWorkflowActions(g.user, field);
      expect(actions.map((action) => action.id)).toEqual([actionId]);
    }).toPass({ timeout: 15_000 });
  });
});
