import type { Browser, BrowserContext, Page, Response } from "@playwright/test";
import { expect, test } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import { KanbanPage } from "../../pages/database/kanbanPage";
import {
  GridSetupResult,
  resetRows,
  setupGrid,
} from "../../fixtures/database/gridSetup";
import {
  createRestrictedView,
  createViewFilter,
  setViewDefaultValues,
  updateViewFieldOptions,
  View,
} from "../../fixtures/database/view";
import {
  createLicense,
  deleteLicense,
  ENTERPRISE_LICENSE,
  License,
} from "../../fixtures/licence";
import {
  holdRowsResponse,
  realtimePageSubscribed,
} from "../../fixtures/network";
import { assignRoles } from "../../fixtures/roleAssignment";
import { createUser, deleteUser, User } from "../../fixtures/user";
import { addWorkspaceMember } from "../../fixtures/workspaceMember";

const STATUS_FIELD_INDEX = 0;
const SEED_ROWS = [
  { Name: "Alpha", Status: "Todo", Region: "North" },
  { Name: "Bravo", Status: "Doing", Region: "North" },
  { Name: "Charlie", Status: "Todo", Region: "North" },
  { Name: "Delta", Status: "Done", Region: "North" },
];

let license: License;
let g: GridSetupResult;
let editor: User;
let openWork: View;
let openBoard: View;
let northWithoutDefault: View;
let northWithDefault: View;

async function createNorthView(name: string): Promise<View> {
  const view = await createRestrictedView(g.user, g.table, { name });
  await createViewFilter(g.user, view, g.fieldByName.Region, "equal", "North");
  await updateViewFieldOptions(g.user, view, {
    [g.fieldByName.Region.id]: { hidden: true },
  });
  return view;
}

async function openEditorGrid(page: Page, view: View): Promise<GridPage> {
  const grid = new GridPage(page, editor);
  const subscribed = realtimePageSubscribed(page, "restricted_view");
  await grid.goTo(g.database, g.table, view);
  await subscribed;
  return grid;
}

async function openSecondEditorGrid(
  browser: Browser,
): Promise<{ context: BrowserContext; grid: GridPage }> {
  const context = await browser.newContext();
  try {
    const grid = await openEditorGrid(await context.newPage(), openWork);
    return { context, grid };
  } catch (error) {
    await context.close();
    throw error;
  }
}

async function openEditorKanban(page: Page): Promise<KanbanPage> {
  const kanban = new KanbanPage(page, editor);
  const subscribed = realtimePageSubscribed(page, "restricted_view");
  await kanban.goTo(g.database, g.table, openBoard);
  await subscribed;
  return kanban;
}

async function expectToast(
  page: Page,
  title: string,
  message: string,
): Promise<void> {
  const toast = page.locator(".toast", {
    has: page.locator(".toast__title", { hasText: title }),
  });
  await expect(toast).toBeVisible();
  await expect(toast.locator(".toast__message")).toContainText(message);
}

function rowsBatchResponse(
  page: Page,
  method: "POST" | "PATCH",
): Promise<Response> {
  return page.waitForResponse(
    (response) =>
      response.url().includes(`/database/rows/table/${g.table.id}/batch/`) &&
      response.request().method() === method,
  );
}

/** Pastes the options with the rich values a Baserow grid copy keeps next to the text. */
async function pasteSelectOptions(page: Page, labels: string[]): Promise<void> {
  const options = labels.map((label) => ({
    id: g.getOptionId("Status", label),
    value: label,
    color: "blue",
  }));
  await page.evaluate((values) => {
    const text = values.map((option) => option.value).join("\n");
    localStorage.setItem(
      "baserow.clipboardData",
      JSON.stringify({ text, json: values.map((option) => [option]) }),
    );
    const data = new DataTransfer();
    data.setData("text/plain", text);
    document.dispatchEvent(
      new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: data,
      }),
    );
  }, options);
}

test.describe("Restricted view editors @enterprise", () => {
  // One worker in order: the tests share the table, the editor and the license.
  test.describe.configure({ mode: "default" });

  test.beforeAll(async () => {
    license = await createLicense(ENTERPRISE_LICENSE);
    g = await setupGrid({
      dbName: "RestrictedViewDb",
      fields: [
        {
          name: "Status",
          type: "single_select",
          options: ["Todo", "Doing", "Done"],
        },
        { name: "Region", type: "text" },
      ],
      filters: [
        { fieldName: "Status", type: "single_select_not_equal", value: "Done" },
      ],
    });
    const doneOptionId = String(g.getOptionId("Status", "Done"));

    openWork = await createRestrictedView(g.user, g.table, {
      name: "Open work",
    });
    openBoard = await createRestrictedView(g.user, g.table, {
      name: "Open board",
      type: "kanban",
      settings: { single_select_field: g.fieldByName.Status.id },
    });
    for (const view of [openWork, openBoard]) {
      await createViewFilter(
        g.user,
        view,
        g.fieldByName.Status,
        "single_select_not_equal",
        doneOptionId,
      );
    }
    northWithoutDefault = await createNorthView("North");
    northWithDefault = await createNorthView("North with default");
    await setViewDefaultValues(g.user, northWithDefault, [
      { field: g.fieldByName.Region, value: "North" },
    ]);

    editor = await createUser();
    const workspace = g.database.workspace;
    await addWorkspaceMember(g.user, workspace, editor, "EDITOR");
    await assignRoles(g.user, workspace, editor, [
      { scopeType: "workspace", scopeId: workspace.id, role: "NO_ACCESS" },
      ...[openWork, openBoard, northWithoutDefault, northWithDefault].map(
        (view) => ({
          scopeType: "database_view" as const,
          scopeId: view.id,
          role: "EDITOR",
        }),
      ),
    ]);
  });

  test.beforeEach(async () => {
    await resetRows(g, SEED_ROWS);
  });

  test.afterAll(async () => {
    if (editor) {
      await deleteUser(editor);
    }
    if (license) {
      await deleteLicense(license);
    }
  });

  test("a row added while its create response is held shows once, also on another page", async ({
    page,
    browser,
  }) => {
    const grid = await openEditorGrid(page, openWork);
    const other = await openSecondEditorGrid(browser);
    try {
      await grid.expectRowCount(3);
      await other.grid.expectRowCount(3);

      const held = await holdRowsResponse(page, g.table.id, "POST");
      await grid.addRow();
      await held.committed;
      // The other page receiving the row proves the event went out before the response.
      await other.grid.expectRowCount(4);
      await grid.expectRowCount(4);

      held.release();
      await grid.expectNoRowsLoading();
      await grid.expectRowCount(4);
      await grid.expectFooterRowCount(4);
      await other.grid.expectRowCount(4);
      await other.grid.expectFooterRowCount(4);
    } finally {
      await other.context.close();
    }
  });

  test("editing a cell so the row leaves the filters hides it, also on another page", async ({
    page,
    browser,
  }) => {
    const grid = await openEditorGrid(page, openWork);
    const other = await openSecondEditorGrid(browser);
    try {
      await grid.expectPrimaryText(0, "Alpha");

      await grid.selectSingleSelectOption(0, STATUS_FIELD_INDEX, "Done");

      await expectToast(
        page,
        "Row hidden",
        "The row no longer matches the filters of this view",
      );
      await grid.expectPrimaryNotVisible("Alpha");
      await grid.expectRowCount(2);
      await grid.expectFooterRowCount(2);
      await other.grid.expectPrimaryNotVisible("Alpha");
      await other.grid.expectRowCount(2);
      await other.grid.expectFooterRowCount(2);
    } finally {
      await other.context.close();
    }
  });

  test("pasting over several rows hides only the rows that leave the filters", async ({
    page,
    browser,
    browserName,
  }) => {
    test.skip(
      browserName !== "chromium",
      "Playwright cannot deliver clipboard data to Firefox.",
    );
    const grid = await openEditorGrid(page, openWork);
    const other = await openSecondEditorGrid(browser);
    try {
      await grid.expectRowCount(3);
      await other.grid.expectRowCount(3);

      const held = await holdRowsResponse(page, g.table.id, "PATCH");
      await grid.selectFieldCell(0, STATUS_FIELD_INDEX);
      await pasteSelectOptions(page, ["Done", "Todo", "Done"]);
      await held.committed;
      // The other page hiding the rows proves the events went out before the response.
      await other.grid.expectRowCount(1);
      await grid.expectRowCount(3);
      await grid.expectPrimaryText(0, "Alpha");
      await grid.expectPrimaryText(2, "Charlie");

      held.release();
      await expectToast(
        page,
        "Rows hidden",
        "2 rows no longer match the filters of this view",
      );
      await grid.expectRowCount(1);
      await grid.expectPrimaryText(0, "Bravo");
      await grid.expectSingleSelectFieldText(0, STATUS_FIELD_INDEX, "Todo");
      await grid.expectFooterRowCount(1);
    } finally {
      await other.context.close();
    }
  });

  test("dragging a kanban card into a stack the filters exclude hides it without moving it", async ({
    page,
  }) => {
    // A mouse drag needs every stack on screen.
    await page.setViewportSize({ width: 1800, height: 900 });
    const kanban = await openEditorKanban(page);
    await kanban.expectStackCount("Todo", 2);
    await kanban.expectStackCount("Done", 0);
    const moveRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/move/")) {
        moveRequests.push(request.url());
      }
    });

    const updated = rowsBatchResponse(page, "PATCH");
    await kanban.dragCardToStack("Todo", "Alpha", "Done");
    const [item] = (await updated).request().postDataJSON().items;
    expect(item[`field_${g.fieldByName.Status.id}`]).toBe(
      g.getOptionId("Status", "Done"),
    );

    await expectToast(
      page,
      "Row hidden",
      "The row no longer matches the filters of this view",
    );
    await kanban.expectStackCount("Done", 0);
    await kanban.expectStackCount("Todo", 1);
    await expect(kanban.card("Todo", "Charlie")).toBeVisible();
    expect(moveRequests).toEqual([]);
  });

  test("creating a kanban card in a stack the filters exclude doesn't show it", async ({
    page,
  }) => {
    const kanban = await openEditorKanban(page);
    await kanban.expectStackCount("Done", 0);

    const modal = await kanban.openCreateRowModal("Done");
    await modal
      .locator(".row-modal__field-item", { hasText: "Name" })
      .locator("input")
      .first()
      .fill("Echo");
    await modal.getByRole("button", { name: "Create" }).click();

    await expectToast(
      page,
      "Row hidden",
      "The new row doesn't match the filters of this view",
    );
    await expect(modal).toBeHidden();
    await kanban.expectStackCount("Done", 0);
    await expect(
      page.locator(".kanban-view__stack-card:visible", { hasText: "Echo" }),
    ).toHaveCount(0);
  });

  test("editing a row out of a restricted view from its modal closes the modal", async ({
    page,
  }) => {
    const grid = await openEditorGrid(page, openWork);
    await grid.openRowModalFromContext(0);
    await grid.expectRowModalVisibleFor("Alpha");
    await expect(page).toHaveURL(/\/row\/\d+/);

    await grid.selectRowModalSingleSelectOption("Status", "Done");

    await expectToast(
      page,
      "Row hidden",
      "The row no longer matches the filters of this view",
    );
    await expect(grid.rowEditModal()).toHaveCount(0);
    await expect(page).not.toHaveURL(/\/row\/\d+/);
    await grid.expectPrimaryNotVisible("Alpha");
    await grid.expectRowCount(2);
    await grid.expectFooterRowCount(2);
  });

  test("editing a row out of a collaborative view from its modal keeps the modal open", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table, g.view);
    await grid.openRowModalFromContext(0);
    await grid.expectRowModalVisibleFor("Alpha");

    const updated = rowsBatchResponse(page, "PATCH");
    await grid.selectRowModalSingleSelectOption("Status", "Done");
    await updated;

    await expect(
      grid
        .rowEditModal()
        .locator(".row-modal__field-item", { hasText: "Status" })
        .locator(".select-options__dropdown-selected"),
    ).toHaveText(/^\s*Done\s*$/);
    await expect(grid.rowEditModal()).toBeVisible();

    await grid.closeRowModal();
    await grid.expectPrimaryNotVisible("Alpha");
    await grid.expectRowCount(2);
    await expect(page.locator(".toast", { hasText: "Row hidden" })).toHaveCount(
      0,
    );
  });

  test("a row added in a view filtered on a hidden field is hidden without a matching default", async ({
    page,
  }) => {
    const grid = await openEditorGrid(page, northWithoutDefault);
    await grid.expectNonPrimaryFieldHeaderHidden("Region");
    await grid.expectRowCount(4);

    const created = rowsBatchResponse(page, "POST");
    await grid.addRow();
    const body = await (await created).json();
    expect(body.metadata.hidden_row_ids).toEqual([body.items[0].id]);

    await expectToast(
      page,
      "Row hidden",
      "The new row doesn't match the filters of this view",
    );
    await grid.expectRowCount(4);
    await grid.expectFooterRowCount(4);
  });

  test("a row added in a view filtered on a hidden field stays visible with a matching default", async ({
    page,
  }) => {
    const grid = await openEditorGrid(page, northWithDefault);
    await grid.expectNonPrimaryFieldHeaderHidden("Region");
    await grid.expectRowCount(4);

    const created = rowsBatchResponse(page, "POST");
    await grid.addRow();
    const body = await (await created).json();
    expect(body.metadata.hidden_row_ids).toEqual([]);

    await grid.expectNoRowsLoading();
    await grid.expectRowCount(5);
    await grid.expectFooterRowCount(5);
    await expect(page.locator(".toast", { hasText: "Row hidden" })).toHaveCount(
      0,
    );
  });
});
