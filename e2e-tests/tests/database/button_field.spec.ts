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
  createWorkflowAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import { listRows } from "../../fixtures/database/rows";
import { patchView } from "../../fixtures/database/view";
import { getClient } from "../../client";
import { baserowConfig } from "../../playwright.config";

const STATUS_FIELD_INDEX = 0;
const RUN_FIELD_INDEX = 1;
const LINK_FIELD_INDEX = 2;
const BROKEN_FIELD_INDEX = 6;
const BAD_LINK_FIELD_INDEX = 7;

/** Every button field this suite creates, none of which may reach the public. */
const BUTTON_FIELD_NAMES = [
  "Run",
  "Link",
  "Editable",
  "Orderable",
  "Failing",
  "Broken",
  "BadLink",
];

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
  // The grid only renders the columns that fit, and this suite needs one
  // button field per behaviour, so every column has to be on screen at once.
  test.use({ viewport: { width: 2200, height: 900 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Button DB",
      tableName: "Tickets",
      fields: [
        { name: "Status", type: "text" },
        { name: "Run", type: "button", settings: { label: "Run" } },
        { name: "Link", type: "button", settings: { label: "Link" } },
        { name: "Editable", type: "button", settings: { label: "Editable" } },
        { name: "Orderable", type: "button", settings: { label: "Orderable" } },
        { name: "Failing", type: "button", settings: { label: "Failing" } },
        { name: "Broken", type: "button", settings: { label: "Broken" } },
        { name: "BadLink", type: "button", settings: { label: "BadLink" } },
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

    // "Orderable" starts with two actions the drag test swaps. Their URLs are
    // what tells them apart afterwards.
    await createOpenUrlAction(g.user, g.fieldByName["Orderable"], {
      url: "'/first'",
    });
    await createOpenUrlAction(g.user, g.fieldByName["Orderable"], {
      url: "'/second'",
    });

    // "Failing" starts with one action that a half-failed save must not touch.
    await createRowAction(g.user, g.fieldByName["Failing"], {
      type: "update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'kept'" }],
    });

    // "Broken" has an action with no table, so dispatching it fails.
    await createWorkflowAction(g.user, g.fieldByName["Broken"], "create_row");

    // "BadLink" points at a field that does not exist, so the URL never
    // resolves in the browser.
    await createOpenUrlAction(g.user, g.fieldByName["BadLink"], {
      url: "get('fields.field_999999')",
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

  test("another viewer of the grid sees the click's result too", async ({
    page,
    browser,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // A second connection, so the broadcast is the only way it can learn.
    const observerContext = await browser.newContext();
    try {
      const observerPage = await observerContext.newPage();
      const observer = new GridPage(observerPage, g.user);
      await observer.goTo(g.database, g.table);
      await expect(observer.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText(
        "todo",
      );

      await grid.fieldCellAt(0, RUN_FIELD_INDEX).locator("button").click();

      await expect(observer.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText(
        "done",
      );
    } finally {
      await observerContext.close();
    }
  });

  // The first click on an unselected cell also promotes it from the functional
  // component to the stateful one, which remounts it. The in-flight flag is
  // keyed by field and row for exactly that reason, so it survives the swap.
  test("the cell shows a loading state and refuses a second click", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Held open so the in-flight state is observable at all.
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    let dispatches = 0;
    await page.route(
      (url) => url.pathname.endsWith("/workflow_actions/dispatch/"),
      async (route) => {
        dispatches += 1;
        await held;
        await route.continue();
      },
    );

    const button = grid.fieldCellAt(0, RUN_FIELD_INDEX).locator("button");
    await button.click();

    // Disabled while dispatching, which is what stops a second click from
    // starting a second sequence.
    await expect(button).toHaveClass(/button--loading/);
    await expect(button).toBeDisabled();

    release();
    await expect(button).not.toHaveClass(/button--loading/);
    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText("done");

    // The guard is what kept the held request the only one.
    expect(dispatches).toBe(1);
  });

  test("dragging an action to a new position saves the new order", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Orderable");
    const actionList = page.locator(".button-field-action-list");
    const handles = actionList.locator("[data-sortable-handle]");
    await expect(handles).toHaveCount(2);

    const first = await handles.nth(0).boundingBox();
    const second = await handles.nth(1).boundingBox();
    if (!first || !second) throw new Error("action handles are not rendered");

    // The sortable directive tracks mousemove, so a single jump does not
    // register as a drag.
    await page.mouse.move(
      second.x + second.width / 2,
      second.y + second.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      first.x + first.width / 2,
      first.y + first.height / 2 - 8,
      { steps: 12 },
    );
    await page.mouse.up();

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Orderable"],
      );
      expect(actions.map((action) => action.url.formula)).toEqual([
        "'/second'",
        "'/first'",
      ]);
    }).toPass({ timeout: 15_000 });
  });

  test("a save that fails part way keeps what already persisted", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Saving creates each action with its own request, so failing the second
    // one leaves the first created and the seeded one untouched.
    let creates = 0;
    await page.route(/\/database\/field\/\d+\/workflow_actions\/$/, (route) => {
      if (route.request().method() !== "POST") {
        return route.continue();
      }
      creates += 1;
      if (creates === 2) {
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ error: "ERROR_TEST", detail: "boom" }),
        });
      }
      return route.continue();
    });

    await openFieldEditor(page, "Failing");
    const actionList = page.locator(".button-field-action-list");
    const items = actionList.locator(".button-field-action-list__item");
    await expect(items).toHaveCount(1);

    for (let i = 0; i < 2; i++) {
      await actionList.getByText("Add action").click();
      await items.last().locator(".button-field-action-list__type").click();
      await page
        .locator(".dropdown__items:visible")
        .locator(".select__item-link", { hasText: "Open URL" })
        .click();
    }

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(page.locator(".toast")).toBeVisible();

    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Failing"],
      );
      expect(actions.map((action) => action.type)).toEqual([
        "update_row",
        "open_url",
      ]);
      // Nothing is rolled back, so the action that was already there stays.
      expect(actions[0].service.field_mappings[0].value.formula).toBe("'kept'");
    }).toPass({ timeout: 15_000 });
  });

  test("a failing click tells the clicker which action failed", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // "Broken" has an action with no table selected, so the dispatch refuses
    // it and the error names the position the clicker can count in the editor.
    await grid.fieldCellAt(0, BROKEN_FIELD_INDEX).locator("button").click();
    await expect(page.locator(".toast__message")).toContainText("Action 1");

    await grid.goTo(g.database, g.table);

    // A URL that cannot resolve must say so rather than navigate nowhere.
    // Compared by path: the app strips its own `?token=` after authenticating.
    const pathBefore = new URL(page.url()).pathname;
    await grid.fieldCellAt(0, BAD_LINK_FIELD_INDEX).locator("button").click();
    await expect(page.locator(".toast")).toBeVisible();
    expect(new URL(page.url()).pathname).toBe(pathBefore);
  });

  test("a publicly shared view exposes no button field at all", async ({
    browser,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    await patchView(g.user, g.view, { public: true });

    // A button's label and actions are only meaningful to whoever configures
    // the field, and a public view has no one to configure it, so the field
    // type sets `can_be_in_public_view = False`.
    const anonContext = await browser.newContext();
    try {
      const anonPage = await anonContext.newPage();
      await anonPage.goto(
        `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/public/grid/${g.view.slug}`,
      );

      // The grid really did load, so the absences below mean something.
      await expect(anonPage.locator(".grid-view__left")).toContainText("Ada");
      await expect(anonPage.locator(".grid-field-button")).toHaveCount(0);
      for (const name of BUTTON_FIELD_NAMES) {
        await expect(
          anonPage.locator(".grid-view__description-name", { hasText: name }),
        ).toHaveCount(0);
      }
    } finally {
      await anonContext.close();
    }

    // The rendering is only half of it: an unauthenticated caller must not be
    // able to read the fields out of the public API either.
    const info: any = await getClient().get(
      `database/views/${g.view.slug}/public/info/`,
    );
    const publicFieldIds = info.data.fields.map((field: any) => field.id);
    const rows: any = await getClient().get(
      `database/views/grid/${g.view.slug}/public/rows/`,
    );

    for (const name of BUTTON_FIELD_NAMES) {
      const fieldId = g.fieldByName[name].id;
      expect(publicFieldIds).not.toContain(fieldId);
      expect(rows.data.results[0]).not.toHaveProperty(`field_${fieldId}`);
    }
  });
});
