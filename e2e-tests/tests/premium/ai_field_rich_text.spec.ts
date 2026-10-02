import type { Locator, Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import { exactly, fieldHeader } from "../../pages/database/buttonFieldEditor";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import { createField, getFieldsForTable } from "../../fixtures/database/field";
import { listRows } from "../../fixtures/database/rows";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../fixtures/licence";
import { getClient } from "../../client";

const RICH_NOTES = "Rich notes";
const RICH_AI = "Rich summary";
const PLAIN_AI = "Plain summary";

const RICH_NOTES_INDEX = 0;
const RICH_AI_INDEX = 1;
const PLAIN_AI_INDEX = 2;

const AI_PROVIDER_TYPE = "openai";
const AI_PROVIDER_NAME = "OpenAI";
const AI_MODEL = "e2e-rich-text-model";

const MENTION = '[data-type="mention"]';
const MENTION_LIST = ".rich-text-editor__mention-list";
const RICH_TEXT_LABEL = "Enable rich text formatting";
const EXTERNAL_IMAGE = "![x](https://example.com/a.png)";
const IMAGE_ELEMENTS = "img, .rich-text-image-placeholder";

type WorkspaceMember = { email: string; user_id: number };

let license: License | undefined;
let g: GridSetupResult;
let memberId: number;

function aiFieldSettings(richText: boolean): Record<string, unknown> {
  return {
    ai_generative_ai_type: AI_PROVIDER_TYPE,
    ai_generative_ai_model: AI_MODEL,
    ai_prompt: "'Summarize the row'",
    ai_output_type: "text",
    long_text_enable_rich_text: richText,
  };
}

function rowModalField(grid: GridPage, fieldName: string): Locator {
  return grid
    .rowEditModal()
    .locator(".row-modal__field-item", { hasText: fieldName })
    .first();
}

function fieldForm(page: Page): Locator {
  return page.locator(".field-context:visible");
}

function richTextCheckbox(page: Page): Locator {
  return fieldForm(page).locator(".checkbox", { hasText: RICH_TEXT_LABEL });
}

async function pickDropdownItem(page: Page, name: string): Promise<void> {
  await page
    .locator(".dropdown__items:visible")
    .locator(".select__item-link", { hasText: name })
    .first()
    .click();
}

function formControl(page: Page, label: string): Locator {
  return fieldForm(page)
    .locator("label.control__label", { hasText: label })
    .locator("xpath=..");
}

async function chooseFormDropdownItem(
  page: Page,
  label: string,
  name: string
): Promise<void> {
  await formControl(page, label).locator(".dropdown").first().click();
  await pickDropdownItem(page, name);
}

async function chooseFieldType(page: Page, name: string): Promise<void> {
  await fieldForm(page).locator(".dropdown").first().click();
  await pickDropdownItem(page, name);
}

function primaryFieldHeader(page: Page): Locator {
  return page
    .locator(".grid-view__left .grid-view__head .grid-view__column")
    .filter({
      has: page.locator(".grid-view__description-name", {
        hasText: exactly("Name"),
      }),
    });
}

async function openFieldEditForm(page: Page, header: Locator): Promise<void> {
  // "Edit field permissions" also matches a loose "Edit field".
  const editItem = page.locator(".context__menu-item:visible", {
    hasText: exactly("Edit field"),
  });
  // The header context can self-hide on the first click before the grid settles.
  await expect(async () => {
    await header.locator(".grid-view__description-icon-trigger").click();
    await expect(editItem).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await editItem.click();
  await expect(fieldForm(page)).toBeVisible();
}

async function closeFieldForm(grid: GridPage): Promise<void> {
  await grid.clickAway();
  await expect(fieldForm(grid.page)).toHaveCount(0);
}

test.describe("AI field rich text", () => {
  test.describe.configure({ mode: "serial" });
  test.skip(
    ({ browserName }) => browserName !== "chromium",
    "The behaviour is browser independent, so one browser is enough."
  );

  test.beforeAll(async () => {
    license = await createLicense(ENTERPRISE_LICENSE);
    g = await setupGrid({
      dbName: "AI rich text DB",
      tableName: "AI rich text",
      fields: [
        {
          name: RICH_NOTES,
          type: "long_text",
          settings: { long_text_enable_rich_text: true },
        },
      ],
    });

    const workspaceId = g.database.workspace.id;
    const client = getClient(g.user);
    await client.post(`ai-providers/?workspace_id=${workspaceId}`, {
      provider_type: AI_PROVIDER_TYPE,
      api_key: "e2e-secret",
      models: [{ model_identifier: AI_MODEL }],
    });

    g.fieldByName[RICH_AI] = await createField(
      g.user,
      RICH_AI,
      "ai",
      aiFieldSettings(true),
      g.table
    );
    g.fieldByName[PLAIN_AI] = await createField(
      g.user,
      PLAIN_AI,
      "ai",
      aiFieldSettings(false),
      g.table
    );

    const { data: members } = await client.get<WorkspaceMember[]>(
      `workspaces/users/workspace/${workspaceId}/`
    );
    memberId = members.find((member) => member.email === g.user.email)!.user_id;
  });

  test.afterAll(async () => {
    // Skipped groups still run afterAll, without beforeAll having created it.
    if (license) {
      await deleteLicense(license);
    }
  });

  test("a rich AI cell renders markdown but keeps mentions literal", async ({
    page,
  }) => {
    const mention = `@${memberId}`;
    const value = `**bold** and ${mention}`;
    await resetRows(g, [
      { Name: "formatted", [RICH_AI]: value, [RICH_NOTES]: value },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // The same value in rich long text proves the id belongs to a real member.
    await expect(
      grid.fieldCellAt(0, RICH_NOTES_INDEX).locator(MENTION)
    ).toBeVisible();

    const aiCell = grid.fieldCellAt(0, RICH_AI_INDEX);
    await expect(aiCell.locator("strong")).toHaveText("bold");
    await expect(aiCell).toContainText(`bold and ${mention}`);
    await expect(aiCell.locator(MENTION)).toHaveCount(0);

    await grid.openRowModalFromContext(0);
    const modalEditor = rowModalField(grid, RICH_AI).locator(".ProseMirror");
    await expect(modalEditor.locator("strong")).toHaveText("bold");
    await expect(modalEditor).toContainText(`bold and ${mention}`);
    await expect(modalEditor.locator(MENTION)).toHaveCount(0);
    await expect(
      rowModalField(grid, RICH_NOTES).locator(`.ProseMirror ${MENTION}`)
    ).toBeVisible();
  });

  test("a rich AI value keeps image markdown as literal text", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "image", [RICH_AI]: EXTERNAL_IMAGE }]);
    expect((await listRows(g.user, g.table))[0][RICH_AI]).toBe(EXTERNAL_IMAGE);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    const rowPatches: string[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "PATCH" &&
        request.url().includes(`/database/rows/table/${g.table.id}/`)
      ) {
        rowPatches.push(request.url());
      }
    });

    const cell = grid.fieldCellAt(0, RICH_AI_INDEX);
    await expect(cell).toContainText(EXTERNAL_IMAGE);
    await expect(cell.locator(IMAGE_ELEMENTS)).toHaveCount(0);

    await grid.startEditingRichTextField(0, RICH_AI_INDEX);
    const editor = grid.activeRichTextEditor();
    await expect(editor).toHaveText(EXTERNAL_IMAGE);
    await expect(editor.locator(IMAGE_ELEMENTS)).toHaveCount(0);
    await grid.clickAway();
    await expect(editor).toHaveCount(0);
    await expect(cell).toContainText(EXTERNAL_IMAGE);

    await grid.openRowModalFromContext(0);
    const modalEditor = rowModalField(grid, RICH_AI).locator(".ProseMirror");
    await expect(modalEditor).toHaveText(EXTERNAL_IMAGE);
    await expect(modalEditor.locator(IMAGE_ELEMENTS)).toHaveCount(0);

    expect(rowPatches).toEqual([]);
    expect((await listRows(g.user, g.table))[0][RICH_AI]).toBe(EXTERNAL_IMAGE);
  });

  test("a plain AI cell keeps markdown as literal text", async ({ page }) => {
    await resetRows(g, [{ Name: "plain", [PLAIN_AI]: "**bold**" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.expectFieldText(0, PLAIN_AI_INDEX, "**bold**");
    await expect(
      grid.fieldCellAt(0, PLAIN_AI_INDEX).locator("strong")
    ).toHaveCount(0);

    await grid.openRowModalFromContext(0);
    await expect(rowModalField(grid, PLAIN_AI).locator("textarea")).toHaveValue(
      "**bold**"
    );
  });

  test("editing rich AI text preserves a reference image destination and title", async ({
    page,
  }) => {
    const imageUrl = "https://external.invalid/reference.png";
    const imageTitle = "Photo title";
    const value = `Before\n\n![photo][ref]\n\n[ref]: ${imageUrl} "${imageTitle}"`;
    await resetRows(g, [{ Name: "reference image", [RICH_AI]: value }]);
    const imageRequests: string[] = [];
    await page.route("**/external.invalid/**", (route) => route.abort());
    page.on("request", (request) => {
      if (request.url().includes("external.invalid")) {
        imageRequests.push(request.url());
      }
    });

    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await grid.openRowModalFromContext(0);
    const editor = rowModalField(grid, RICH_AI).locator(".ProseMirror");
    await expect(editor).toContainText("Before");
    await expect(editor).toContainText("photo");
    await expect(editor.locator(IMAGE_ELEMENTS)).toHaveCount(0);

    // Edit only the first paragraph. A collapsed DOM selection avoids an
    // OS-specific select-all/cursor shortcut accidentally replacing the image.
    await editor.locator("p").first().click();
    await editor.evaluate((element) => {
      const range = document.createRange();
      range.selectNodeContents(element.querySelector("p")!);
      range.collapse(false);
      const selection = window.getSelection()!;
      selection.removeAllRanges();
      selection.addRange(range);
      document.dispatchEvent(new Event("selectionchange"));
    });
    await expect
      .poll(() => editor.evaluate(() => window.getSelection()?.isCollapsed))
      .toBe(true);
    await page.keyboard.type(" edited");
    await expect(editor).toContainText("Before edited");
    await expect(editor).toContainText("photo");
    await grid.rowEditModal().locator(".row-modal__title").click();

    await expect(async () => {
      const saved = (await listRows(g.user, g.table))[0][RICH_AI];
      expect(saved).toContain("Before edited");
      expect(saved).toContain("photo");
      expect(saved).toContain(imageUrl);
      expect(saved).toContain(imageTitle);
    }).toPass({ timeout: 10_000 });

    await grid.goTo(g.database, g.table);
    await expect(
      grid.fieldCellAt(0, RICH_AI_INDEX).locator(IMAGE_ELEMENTS)
    ).toHaveCount(0);
    await grid.openRowModalFromContext(0);
    const reopened = rowModalField(grid, RICH_AI).locator(".ProseMirror");
    await expect(reopened).toContainText("Before edited");
    await expect(reopened).toContainText(imageUrl);
    await expect(reopened).toContainText(imageTitle);
    await expect(reopened.locator(IMAGE_ELEMENTS)).toHaveCount(0);
    expect(imageRequests).toEqual([]);
  });

  test("the rich AI cell editor formats text but suggests no mentions", async ({
    page,
  }) => {
    await resetRows(g, [
      { Name: "ai", [RICH_AI]: "Draft" },
      { Name: "control", [RICH_NOTES]: "Draft" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    const editor = grid.activeRichTextEditor();

    // Control: rich long text suggests mentions for the same keystrokes.
    await grid.startEditingRichTextField(1, RICH_NOTES_INDEX);
    await page.keyboard.type(" @");
    await expect(editor.locator("span.suggestion")).toBeVisible();
    await expect(page.locator(MENTION_LIST)).toBeVisible();
    await grid.clickAway();
    await expect(page.locator(MENTION_LIST)).toHaveCount(0);

    await grid.startEditingRichTextField(0, RICH_AI_INDEX);
    await expect(
      grid.fieldCellAt(0, RICH_AI_INDEX).getByText("Regenerate")
    ).toBeVisible();
    await page.keyboard.type(" @");
    await expect(editor).toHaveText("Draft @");
    // The suggestion decoration lands in the same render as the typed "@".
    await expect(editor.locator("span.suggestion")).toHaveCount(0);
    await expect(page.locator(MENTION_LIST)).toHaveCount(0);

    await page.keyboard.press("ControlOrMeta+a");
    const boldButton = page.locator(
      '.rich-text-editor__bubble-menu-button[title="Bold"] button'
    );
    await expect(boldButton).toBeVisible();
    await boldButton.click();
    await expect(editor.locator("strong")).toHaveText("Draft @");
    await expect(editor).toBeVisible();

    const aiRowId = (await listRows(g.user, g.table))[0].id;
    const rowUpdate = page.waitForRequest(
      (request) =>
        request.method() === "PATCH" &&
        request.url().includes(`/database/rows/table/${g.table.id}/batch/`)
    );
    await grid.clickAway();
    const patchedItems = (await rowUpdate).postDataJSON().items;
    expect(patchedItems).toEqual([
      { id: aiRowId, [`field_${g.fieldByName[RICH_AI].id}`]: "**Draft @**" },
    ]);

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      expect(rows[0][RICH_AI]).toBe("**Draft @**");
    }).toPass({ timeout: 10_000 });
    await expect(
      grid.fieldCellAt(0, RICH_AI_INDEX).locator("strong")
    ).toHaveText("Draft @");
  });

  test("the link input and the expand modal keep the rich AI cell editor open", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "ai", [RICH_AI]: "Draft" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    const editor = grid.activeRichTextEditor();
    const cell = grid.fieldCellAt(0, RICH_AI_INDEX);

    await grid.startEditingRichTextField(0, RICH_AI_INDEX);
    await page.keyboard.press("ControlOrMeta+a");
    await page
      .locator('.rich-text-editor__bubble-menu-button[title="Link"] button')
      .click();
    const linkInput = page.locator(
      ".rich-text-editor__bubble-menu-link-edit-input"
    );
    await linkInput.click();
    await expect(editor).toBeVisible();
    await linkInput.fill("https://baserow.io");
    await linkInput.press("Enter");
    await expect(editor.locator('a[href="https://baserow.io"]')).toHaveText(
      "Draft"
    );
    await expect(cell.getByText("Regenerate")).toBeVisible();

    await cell.locator(".grid-field-rich-text__textarea-expand-icon").click();
    const expandModal = page.locator(".modal__box:visible", {
      has: page.locator(".rich-text-modal__editor"),
    });
    const modalEditor = expandModal.locator(".ProseMirror");
    await modalEditor.click();
    await expect(expandModal).toBeVisible();
    await expect(grid.selectedFieldCellAt(0, RICH_AI_INDEX)).toBeVisible();
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.type("Rewritten in the modal");

    await expandModal.locator(".modal__close").click();
    await expect(expandModal).toHaveCount(0);
    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      expect(rows[0][RICH_AI]).toBe("Rewritten in the modal");
    }).toPass({ timeout: 10_000 });
  });

  test("editing a rich AI value in the row modal saves it", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "modal", [RICH_AI]: "Draft" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.openRowModalFromContext(0);
    const modalEditor = rowModalField(grid, RICH_AI).locator(".ProseMirror");
    await modalEditor.click();
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.type("Edited in the row modal");
    await grid.rowEditModal().locator(".row-modal__title").click();

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      expect(rows[0][RICH_AI]).toBe("Edited in the row modal");
    }).toPass({ timeout: 10_000 });
  });

  test("the field form defaults new AI text fields to rich text", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "form" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditForm(page, fieldHeader(page, PLAIN_AI));
    await expect(richTextCheckbox(page).locator("input")).not.toBeChecked();
    await closeFieldForm(grid);

    await openFieldEditForm(page, fieldHeader(page, RICH_AI));
    await expect(richTextCheckbox(page).locator("input")).toBeChecked();
    await closeFieldForm(grid);

    await openFieldEditForm(page, primaryFieldHeader(page));
    await chooseFieldType(page, "AI prompt");
    await expect(formControl(page, "Output type")).toContainText("Text");
    await expect(richTextCheckbox(page)).toHaveCount(0);
    await closeFieldForm(grid);

    await page.locator(".grid-view__add-column").click();
    await fieldForm(page).getByPlaceholder("Name").fill("Created AI");
    await chooseFieldType(page, "AI prompt");
    await expect(richTextCheckbox(page).locator("input")).toBeChecked();
    await chooseFormDropdownItem(page, "Output type", "Choice");
    await expect(richTextCheckbox(page)).toHaveCount(0);
    await chooseFormDropdownItem(page, "Output type", "Text");
    await expect(richTextCheckbox(page).locator("input")).toBeChecked();

    await chooseFormDropdownItem(page, "AI Type", AI_PROVIDER_NAME);
    await expect(formControl(page, "AI Model")).toContainText(AI_MODEL);
    await fieldForm(page).locator(".formula-input-field__editor").click();
    await page.keyboard.type("Summarize the row");
    await fieldForm(page).locator("button", { hasText: "Create" }).click();
    await expect(fieldHeader(page, "Created AI")).toBeVisible();

    const created = (await getFieldsForTable(g.user, g.table)).find(
      (field) => field.name === "Created AI"
    );
    expect(created?.fieldSettings.ai_output_type).toBe("text");
    expect(created?.fieldSettings.long_text_enable_rich_text).toBe(true);
    await getClient(g.user).delete(`database/fields/${created!.id}/`);
  });
});
