/**
 * Button field workflow actions, end to end.
 *
 * The unit tests mock the dispatch request at the cell and the backend tests
 * call the service layer directly, so nothing below this file exercises the
 * whole loop: a real click, the real endpoint, the real row write, and the
 * realtime broadcast that puts the result back on the clicker's screen.
 */

import { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import {
  createRowAction,
  createOpenUrlAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import { listRows } from "../../fixtures/database/rows";

const STATUS_FIELD_INDEX = 0;
const RUN_FIELD_INDEX = 1;
const LINK_FIELD_INDEX = 2;

let g: GridSetupResult;

/** The header column of a non-primary field, by name. */
function fieldHeader(page: Page, name: string) {
  return page
    .locator(".grid-view__right .grid-view__head .grid-view__column")
    .filter({
      has: page.locator(".grid-view__description-name", {
        hasText: new RegExp(`^\\s*${name}\\s*$`),
      }),
    });
}

/** Opens a field's "Edit field" form from its header dropdown. */
async function openFieldEditor(page: Page, name: string) {
  await fieldHeader(page, name)
    .locator(".grid-view__description-icon-trigger")
    .click();
  await page.locator(".context__menu-item", { hasText: "Edit field" }).click();
  await expect(page.locator(".button-field-action-list")).toBeVisible();
}

test.describe("Button field", () => {
  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Button DB",
      tableName: "Tickets",
      fields: [
        { name: "Status", type: "text" },
        { name: "Run", type: "button", settings: { label: "Run" } },
        { name: "Link", type: "button", settings: { label: "Link" } },
        { name: "Editable", type: "button", settings: { label: "Editable" } },
      ],
    });

    // "Run" approves the row that was clicked.
    await createRowAction(g.user, g.fieldByName["Run"], {
      type: "update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'done'" }],
    });

    // "Link" only opens a URL, so the dispatch runs nothing server side.
    await createOpenUrlAction(g.user, g.fieldByName["Link"], {
      url: "'/dashboard'",
      target: "self",
    });

    // "Editable" starts with one action, which the editor test adds to.
    await createRowAction(g.user, g.fieldByName["Editable"], {
      type: "update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'seeded'" }],
    });
  });

  test("clicking a button runs its row action and the grid shows the result", async ({
    page,
  }) => {
    await resetRows(g, [
      { Name: "Ada", Status: "todo" },
      { Name: "Grace", Status: "todo" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText("todo");

    await grid.fieldCellAt(0, RUN_FIELD_INDEX).locator("button").click();

    // No reload: the clicker opts out of the WebSocketId header precisely so
    // the broadcast its own dispatch triggers comes back to it.
    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText("done");

    // The action targets `get('row.id')`, so only the clicked row moves.
    await expect(grid.fieldCellAt(1, STATUS_FIELD_INDEX)).toHaveText("todo");

    const rows = await listRows(g.user, g.table);
    expect(rows.map((row) => row.Status)).toEqual(["done", "todo"]);
  });

  test("a frontend only action runs in the browser after the dispatch", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.fieldCellAt(0, LINK_FIELD_INDEX).locator("button").click();

    // `open_url` is never dispatched server side. It comes back in
    // `client_actions` and the browser runs it, here in the same tab.
    // `/dashboard` resolves to the user's default workspace, so accept either.
    await expect(page).toHaveURL(/\/(dashboard|workspace\/\d+)/);
  });

  test("actions added in the field editor are saved alongside the existing ones", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Editable");

    const actionList = page.locator(".button-field-action-list");
    await expect(
      actionList.locator(".button-field-action-list__item"),
    ).toHaveCount(1);

    await actionList.getByText("Add action").click();
    const newAction = actionList
      .locator(".button-field-action-list__item")
      .nth(1);
    await newAction.locator(".button-field-action-list__type").click();
    // The dropdown renders its items outside the action, and every action's
    // list stays in the DOM, so only the open one is addressable.
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: "Open URL" })
      .click();

    await page.locator(".field-context button", { hasText: "Save" }).click();

    // Saving is a sequence of create, update and order calls, so assert the
    // list the server actually ended up with rather than the form's own state.
    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Editable"],
      );
      expect(actions.map((action) => action.type)).toEqual([
        "update_row",
        "open_url",
      ]);
      // The action that was already there keeps its configuration.
      expect(actions[0].service.field_mappings[0].value.formula).toBe(
        "'seeded'",
      );
    }).toPass({ timeout: 15_000 });
  });
});
