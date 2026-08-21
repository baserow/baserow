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
  createDeleteRowAction,
  createOpenUrlAction,
  createWorkflowAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import { listRows } from "../../fixtures/database/rows";
import { Table, createTable, listTables } from "../../fixtures/database/table";
import { createField, getFieldsForTable } from "../../fixtures/database/field";
import { patchView } from "../../fixtures/database/view";
import { User, createUser } from "../../fixtures/user";
import { addUserToWorkspace } from "../../fixtures/workspace";
import { getClient } from "../../client";
import { baserowConfig } from "../../playwright.config";

// Positions in the right-hand section, in the order `beforeAll` creates them.
const STATUS_FIELD_INDEX = 0;
const NOTE_FIELD_INDEX = 1;
const RUN_FIELD_INDEX = 2;
const RUN_TWO_FIELD_INDEX = 3;
const DEFERRED_FIELD_INDEX = 4;
const LINK_FIELD_INDEX = 6;
const BROKEN_FIELD_INDEX = 10;
const BAD_LINK_FIELD_INDEX = 11;
const REMOVE_FIELD_INDEX = 13;
const SPAWN_FIELD_INDEX = 14;
const MODIFIED_BY_FIELD_INDEX = 15;
const RECONFIGURE_FIELD_INDEX = 18;
// Phase 3: an action reading what an earlier one returned.
const CHAINED_FIELD_INDEX = 19;
const CHAINED_LINK_FIELD_INDEX = 20;
const STALE_FIELD_INDEX = 22;
const CHAINED_CROSS_FIELD_INDEX = 23;
const INSERTABLE_FIELD_INDEX = 24;
const BROKEN_CHAIN_FIELD_INDEX = 25;
const DEEP_FIELD_INDEX = 26;
const CHAINABLE_FIELD_INDEX = 27;
// The field one test creates in the UI, which lands after all of the above.
const CREATED_FIELD_INDEX = 28;

/** Every button field this suite creates, none of which may reach the public. */
const BUTTON_FIELD_NAMES = [
  "Run",
  "RunTwo",
  "Deferred",
  "Retarget",
  "Link",
  "Editable",
  "Orderable",
  "Failing",
  "Broken",
  "BadLink",
  "Retype",
  "Remove",
  "Spawn",
  "Cross",
  "Prunable",
  "Reconfigure",
  "Chained",
  "ChainedLink",
  "Buildable",
  "Stale",
  "ChainedCross",
  "Insertable",
  "BrokenChain",
  "Deep",
  "Chainable",
];

let g: GridSetupResult;
let otherTable: Table;
/** A second member of the workspace, for the tests about who a click runs as. */
let otherUser: User;

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

/**
 * A table's row in the sidebar, matched on the whole name so "Tickets" and
 * "Tickets 2" stay apart.
 */
function sidebarTable(page: Page, name: string) {
  return page.locator("li.tree__sub").filter({
    has: page.locator("a.tree__sub-link", {
      hasText: new RegExp(`^\\s*${name}\\s*$`),
    }),
  });
}

/** Opens a field's "Edit field" form from its header dropdown. */
async function openFieldEditor(page: Page, name: string) {
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

/** The data explorer that opens under a formula input. */
function explorer(page: Page) {
  return page.locator("[data-formula-input-context]:visible");
}

/** Walks the explorer, opening each node in turn and picking the last. */
async function pickExplorerNode(page: Page, ...names: string[]) {
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
function actionItem(page: Page, index: number) {
  return page
    .locator(".button-field-action-list .button-field-action-list__item")
    .nth(index);
}

/** Adds an action of `type` at the end of the list. */
async function addAction(page: Page, type: string) {
  const list = page.locator(".button-field-action-list");
  const before = await list
    .locator(".button-field-action-list__item")
    .count();
  await list.getByText("Add action").click();
  const added = actionItem(page, before);
  await added.locator(".button-field-action-list__type").click();
  await page
    .locator(".dropdown__items:visible")
    .locator(".select__item-link", { hasText: type })
    .click();
  return added;
}

/**
 * Points an action at a table. The database has to be chosen first: until it
 * is, the table dropdown has nothing to offer.
 */
async function pickTableOn(
  page: Page,
  index: number,
  database: string,
  table: string,
) {
  const dropdowns = actionItem(page, index).locator(
    ".button-field-action-list__form .dropdown",
  );
  for (const [position, name] of [
    [0, database],
    [1, table],
  ] as [number, string][]) {
    await dropdowns.nth(position).click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: name })
      .click();
  }
}

/**
 * Drags one action onto another's position. The sortable directive tracks
 * mousemove, so a single jump does not register as a drag.
 */
/** The action type shown on each row of the list, in order. */
async function actionOrder(page: Page) {
  return await page
    .locator(".button-field-action-list .button-field-action-list__type")
    .allTextContents();
}

/**
 * Moves one action to another's position.
 *
 * The sortable directive tracks mousemove, so a single jump does not register
 * as a drag, and how far the pointer has to travel depends on how tall the
 * target action's form is. Rather than guess, this drops once and checks
 * whether the order actually changed, trying a different landing point if not.
 */
async function dragAction(page: Page, from: number, to: number) {
  const before = await actionOrder(page);
  let attempt = 0;

  await expect(async () => {
    const handles = page.locator(
      ".button-field-action-list [data-sortable-handle]",
    );
    await handles.nth(from).scrollIntoViewIfNeeded();
    const source = await handles.nth(from).boundingBox();
    // Alternates between the target's handle and the far edge of its whole
    // row, which is what a tall form needs.
    const useItem = attempt % 2 === 1;
    const target = useItem
      ? await actionItem(page, to).boundingBox()
      : await handles.nth(to).boundingBox();
    attempt += 1;
    if (!source || !target) throw new Error("action handles are not rendered");

    const y = useItem
      ? to > from
        ? target.y + target.height - 8
        : target.y + 8
      : target.y + target.height / 2 + (to > from ? 8 : -8);

    await page.mouse.move(
      source.x + source.width / 2,
      source.y + source.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(target.x + target.width / 2, y, { steps: 12 });
    await page.mouse.up();

    expect(await actionOrder(page)).not.toEqual(before);
  }).toPass({ timeout: 20_000 });
}

async function saveField(page: Page) {
  await page.locator(".field-context button", { hasText: "Save" }).click();
}

test.describe("Button field", () => {
  // The grid only renders the columns that fit, and this suite needs one
  // button field per behaviour, so every column has to be on screen at once.
  // Widen this whenever a field is added, or the new column never renders.
  test.use({ viewport: { width: 6400, height: 900 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Button DB",
      tableName: "Tickets",
      fields: [
        { name: "Status", type: "text" },
        { name: "Note", type: "text" },
        { name: "Run", type: "button", settings: { label: "Run" } },
        { name: "RunTwo", type: "button", settings: { label: "RunTwo" } },
        { name: "Deferred", type: "button", settings: { label: "Deferred" } },
        { name: "Retarget", type: "button", settings: { label: "Retarget" } },
        { name: "Link", type: "button", settings: { label: "Link" } },
        { name: "Editable", type: "button", settings: { label: "Editable" } },
        { name: "Orderable", type: "button", settings: { label: "Orderable" } },
        { name: "Failing", type: "button", settings: { label: "Failing" } },
        { name: "Broken", type: "button", settings: { label: "Broken" } },
        { name: "BadLink", type: "button", settings: { label: "BadLink" } },
        { name: "Retype", type: "button", settings: { label: "Retype" } },
        { name: "Remove", type: "button", settings: { label: "Remove" } },
        { name: "Spawn", type: "button", settings: { label: "Spawn" } },
        { name: "ModifiedBy", type: "last_modified_by" },
        { name: "Cross", type: "button", settings: { label: "Cross" } },
        { name: "Prunable", type: "button", settings: { label: "Prunable" } },
        {
          name: "Reconfigure",
          type: "button",
          settings: { label: "Reconfigure" },
        },
        { name: "Chained", type: "button", settings: { label: "Chained" } },
        {
          name: "ChainedLink",
          type: "button",
          settings: { label: "ChainedLink" },
        },
        { name: "Buildable", type: "button", settings: { label: "Buildable" } },
        { name: "Stale", type: "button", settings: { label: "Stale" } },
        {
          name: "ChainedCross",
          type: "button",
          settings: { label: "ChainedCross" },
        },
        {
          name: "Insertable",
          type: "button",
          settings: { label: "Insertable" },
        },
        {
          name: "BrokenChain",
          type: "button",
          settings: { label: "BrokenChain" },
        },
        { name: "Deep", type: "button", settings: { label: "Deep" } },
        { name: "Chainable", type: "button", settings: { label: "Chainable" } },
      ],
    });

    // "Run" approves the row that was clicked.
    await createRowAction(g.user, g.fieldByName["Run"], {
      type: "local_baserow_update_row",
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
      type: "local_baserow_update_row",
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
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'kept'" }],
    });

    // "Broken" has an action with no table, so dispatching it fails.
    await createWorkflowAction(g.user, g.fieldByName["Broken"], "local_baserow_create_row");

    // "BadLink" points at a field that does not exist, so the URL never
    // resolves in the browser.
    await createOpenUrlAction(g.user, g.fieldByName["BadLink"], {
      url: "get('fields.field_999999')",
    });

    // "RunTwo" writes a different column to "Run", so two buttons on one row
    // can be checked without the two writes racing each other.
    await createRowAction(g.user, g.fieldByName["RunTwo"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Note"], value: "'two'" }],
    });

    // "Deferred" runs server side and then hands a client action back, so the
    // browser still has work to do after the cell may be gone.
    await createRowAction(g.user, g.fieldByName["Deferred"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'scrolled'" }],
    });
    await createOpenUrlAction(g.user, g.fieldByName["Deferred"], {
      url: "'/dashboard'",
      target: "self",
    });

    // A second table for the re-pick test, with a field name this table has
    // none of, so which table's mappings are showing is unambiguous.
    otherTable = await createTable(g.user, "Others", g.database);
    const otherOnly = await createField(
      g.user,
      "OtherOnly",
      "text",
      {},
      otherTable,
    );

    // "Cross" points outside the table it lives on, so duplicating that table
    // leaves its target with no entry in the id mapping.
    await createOpenUrlAction(g.user, g.fieldByName["Prunable"], {
      url: "'/keep-me'",
    });
    await createOpenUrlAction(g.user, g.fieldByName["Prunable"], {
      url: "'/prune-me'",
    });

    await createRowAction(g.user, g.fieldByName["Cross"], {
      type: "local_baserow_create_row",
      table: otherTable,
      fieldMappings: [{ field: otherOnly, value: "'crossed'" }],
    });

    await createRowAction(g.user, g.fieldByName["Retarget"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'x'" }],
    });

    // "Reconfigure" starts as a link, so a test can retype it into a row
    // action and configure the new type in the same save.
    await createOpenUrlAction(g.user, g.fieldByName["Reconfigure"], {
      url: "'/dashboard'",
      target: "self",
    });

    // "Retype" has two actions so that changing the first one's type has to
    // keep the second one behind it.
    await createRowAction(g.user, g.fieldByName["Retype"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'first'" }],
    });
    await createRowAction(g.user, g.fieldByName["Retype"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'second'" }],
    });

    // "Remove" deletes the very row it is clicked on.
    await createDeleteRowAction(g.user, g.fieldByName["Remove"], {
      table: g.table,
      rowId: "get('row.id')",
    });

    // "Spawn" writes a row that did not exist when it was clicked, so the
    // effect lands somewhere other than the clicked row.
    await createRowAction(g.user, g.fieldByName["Spawn"], {
      type: "local_baserow_create_row",
      table: g.table,
      fieldMappings: [{ field: g.fieldByName["Name"], value: "'Spawned'" }],
    });

    // Phase 3. Every seed below writes a reference the same shape the editor
    // produces after it rewrites a client id: `previous_action.<id>.<path>`.

    // "Chained" creates a row, then stamps the created row's id onto the
    // clicked one, so the second action can only be right by reading the first.
    const chainedCreate = await createRowAction(g.user, g.fieldByName["Chained"], {
      type: "local_baserow_create_row",
      table: g.table,
      fieldMappings: [{ field: g.fieldByName["Name"], value: "'Chained child'" }],
    });
    await createRowAction(g.user, g.fieldByName["Chained"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [
        {
          field: g.fieldByName["Status"],
          value: `concat('child ',get('previous_action.${chainedCreate.id}.id'))`,
        },
      ],
    });

    // "ChainedLink" is the one case that spans the dispatch response, the
    // field names it carries, and the browser's own formula resolution.
    const linkCreate = await createRowAction(
      g.user,
      g.fieldByName["ChainedLink"],
      {
        type: "local_baserow_create_row",
        table: g.table,
        fieldMappings: [{ field: g.fieldByName["Name"], value: "'Linked child'" }],
      },
    );
    await createOpenUrlAction(g.user, g.fieldByName["ChainedLink"], {
      url: `concat('/chained-',get('previous_action.${linkCreate.id}.id'))`,
      target: "self",
    });

    // "Buildable" has one action; the explorer test adds a second by hand and
    // never saves it. "Chainable" is the same shape but for the test that does
    // save, so the two cannot tread on each other.
    for (const name of ["Buildable", "Chainable"]) {
      await createRowAction(g.user, g.fieldByName[name], {
        type: "local_baserow_create_row",
        table: g.table,
        fieldMappings: [
          { field: g.fieldByName["Name"], value: `'${name} child'` },
        ],
      });
    }

    // "Stale" starts already stale: its URL action sits first and reads an
    // action that runs after it, which is the state a reorder leaves behind.
    // Created in this order so no drag is needed to get there.
    const staleLink = await createOpenUrlAction(g.user, g.fieldByName["Stale"], {
      url: "'/stale-unset'",
      target: "self",
    });
    const staleCreate = await createRowAction(g.user, g.fieldByName["Stale"], {
      type: "local_baserow_create_row",
      table: g.table,
      fieldMappings: [{ field: g.fieldByName["Name"], value: "'Stale child'" }],
    });
    await getClient(g.user).patch(
      `database/workflow_action/${staleLink.id}/`,
      {
        url: `concat('/stale-',get('previous_action.${staleCreate.id}.id'))`,
      },
    );

    // "ChainedCross" reads a row in a table the clicked row's grid has no
    // fields for, which is why each result carries its own field names.
    const crossCreate = await createRowAction(
      g.user,
      g.fieldByName["ChainedCross"],
      {
        type: "local_baserow_create_row",
        table: otherTable,
        fieldMappings: [{ field: otherOnly, value: "'crossed child'" }],
      },
    );
    await createRowAction(g.user, g.fieldByName["ChainedCross"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [
        {
          field: g.fieldByName["Note"],
          value: `get('previous_action.${crossCreate.id}.field_${otherOnly.id}')`,
        },
      ],
    });

    // "Insertable" has one saved action, for the test that inserts another
    // above it and points the saved one at the new one.
    await createRowAction(g.user, g.fieldByName["Insertable"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: g.fieldByName["Status"], value: "'untouched'" }],
    });

    // "BrokenChain" fails first and would navigate second, which is the
    // combination the builder gets wrong.
    const brokenCreate = await createWorkflowAction(
      g.user,
      g.fieldByName["BrokenChain"],
      "local_baserow_create_row",
    );
    await createOpenUrlAction(g.user, g.fieldByName["BrokenChain"], {
      url: `concat('/never-',get('previous_action.${brokenCreate.id}.id'))`,
      target: "self",
    });

    // "Deep" is three actions, and the last reads the first, skipping the one
    // between. An off-by-one in the scoping still satisfies a two-action chain.
    const deepFirst = await createRowAction(g.user, g.fieldByName["Deep"], {
      type: "local_baserow_create_row",
      table: g.table,
      fieldMappings: [{ field: g.fieldByName["Name"], value: "'Deep one'" }],
    });
    const deepSecond = await createRowAction(g.user, g.fieldByName["Deep"], {
      type: "local_baserow_create_row",
      table: g.table,
      fieldMappings: [
        {
          field: g.fieldByName["Name"],
          value: `concat('Deep two via ',get('previous_action.${deepFirst.id}.id'))`,
        },
      ],
    });
    await createRowAction(g.user, g.fieldByName["Deep"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [
        {
          field: g.fieldByName["Status"],
          value:
            `concat(get('previous_action.${deepFirst.id}.id'),'-',` +
            `get('previous_action.${deepSecond.id}.id'))`,
        },
      ],
    });

    // A second member of the workspace, who clicks the same buttons as the
    // user that configured them.
    otherUser = await createUser();
    await addUserToWorkspace(g.user, g.database.workspace, otherUser);
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
        "local_baserow_update_row",
        "open_url",
      ]);
      // The action that was already there keeps its configuration.
      expect(actions[0].service.field_mappings[0].value.formula).toBe(
        "'seeded'",
      );
    }).toPass({ timeout: 15_000 });

    // Removing is the other half of the same reconciliation, and it deletes
    // server side rather than creating, so the list has to be re-sent without
    // the action that went.
    await openFieldEditor(page, "Editable");
    await expect(
      actionList.locator(".button-field-action-list__item"),
    ).toHaveCount(2);
    await actionList
      .locator(".button-field-action-list__item")
      .first()
      .locator(".button-field-action-list__header .button-icon")
      .click();
    await expect(
      actionList.locator(".button-field-action-list__item"),
    ).toHaveCount(1);

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Editable"],
      );
      // Only the survivor is left, still configured as it was.
      expect(actions.map((action) => action.type)).toEqual(["open_url"]);
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

  test("removing an action in the editor deletes it on save", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Prunable");
    const rows = page.locator(
      ".button-field-action-list .button-field-action-list__item",
    );
    await expect(rows).toHaveCount(2);

    // Remove the second, so the survivor is the one that was already first.
    await rows.nth(1).locator("button").first().click();
    await expect(rows).toHaveCount(1);

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Prunable"],
      );
      expect(actions.map((action) => action.url.formula)).toEqual(["'/keep-me'"]);
    }).toPass({ timeout: 15_000 });
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
        "local_baserow_update_row",
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

  test("a client action still runs when its cell scrolls away mid-dispatch", async ({
    page,
  }) => {
    // The grid only keeps the rows near the viewport mounted, so a slow
    // dispatch can outlive the cell that started it. Whatever is left to do
    // afterwards must neither be skipped nor throw at a dead component.
    await resetRows(
      g,
      Array.from({ length: 60 }, (_, i) => ({
        Name: `Row ${i + 1}`,
        Status: "todo",
      })),
    );
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(
      (url) => url.pathname.endsWith("/workflow_actions/dispatch/"),
      async (route) => {
        await held;
        await route.continue();
      },
    );

    await grid.fieldCellAt(0, DEFERRED_FIELD_INDEX).locator("button").click();

    // Scroll the clicked row out of the rendered buffer while the request is
    // still open, so the cell unmounts underneath it.
    await grid.scrollPrimaryIntoView("Row 60");
    await expect(
      page.locator(".grid-view__left").getByText("Row 1", { exact: true }),
    ).toHaveCount(0);

    release();

    // The `open_url` handed back by the dispatch still runs, in a browser
    // whose originating cell no longer exists.
    await expect(page).toHaveURL(/\/(dashboard|workspace\/\d+)/);
    expect(pageErrors).toEqual([]);

    const rows = await listRows(g.user, g.table);
    expect(rows.find((row) => row.Name === "Row 1")?.Status).toBe("scrolled");
  });

  test("two buttons on the same row do not block each other", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo", Note: "" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Both the in-flight guard and the backend lock are keyed by field and
    // row, so a click on one button must not shut out the other.
    let dispatches = 0;
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(
      (url) => url.pathname.endsWith("/workflow_actions/dispatch/"),
      async (route) => {
        dispatches += 1;
        await held;
        await route.continue();
      },
    );

    await grid.fieldCellAt(0, RUN_FIELD_INDEX).locator("button").click();
    await grid.fieldCellAt(0, RUN_TWO_FIELD_INDEX).locator("button").click();

    await expect.poll(() => dispatches).toBe(2);

    release();

    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText("done");
    await expect(grid.fieldCellAt(0, NOTE_FIELD_INDEX)).toHaveText("two");
  });

  test("re-picking a target table shows the newly picked table's fields", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Held back so the fields for "Others" arrive after the ones for the table
    // picked next. Without the fetch token that stale response would win and
    // the form would list a table the user is no longer pointing at.
    let releaseOthers: () => void = () => {};
    let othersFetched = 0;
    const othersHeld = new Promise<void>((resolve) => {
      releaseOthers = resolve;
    });
    const othersPath = `/database/fields/table/${otherTable.id}/`;
    await page.route(
      (url) => url.pathname.endsWith(othersPath),
      async (route) => {
        othersFetched += 1;
        await othersHeld;
        await route.continue();
      },
    );

    await openFieldEditor(page, "Retarget");
    const actionForm = page.locator(".button-field-action-list__form");
    // Database first, then table: the second dropdown of the pair.
    const tableDropdown = actionForm.locator(".dropdown").nth(1);

    const pickTable = async (name: string) => {
      await tableDropdown.click();
      await page
        .locator(".dropdown__items:visible")
        .locator(".select__item-link", { hasText: name })
        .click();
    };

    // Switched back straight away, so the first table's fields are still in
    // flight when the second request goes out.
    await pickTable("Others");
    await pickTable("Tickets");

    // The race only happened if the first table's fields were really in
    // flight across the second pick.
    expect(othersFetched).toBe(1);
    await expect(actionForm.getByText("Status")).toBeVisible();

    // Only now does the overtaken response land, and it has to be waited for:
    // asserting its absence before it arrives would pass either way.
    const stale = page.waitForResponse((response) =>
      response.url().endsWith(othersPath),
    );
    releaseOthers();
    await stale;
    await page.waitForTimeout(500);

    // The later request still owns the form, and nothing is left spinning.
    await expect(actionForm.getByText("OtherOnly")).toHaveCount(0);
    await expect(actionForm.getByText("Status")).toBeVisible();
    await expect(actionForm.locator(".loading-spinner")).toHaveCount(0);
  });

  test("changing an action's type keeps its id and the one after it in place", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Retype");
    const actionList = page.locator(".button-field-action-list");
    const items = actionList.locator(".button-field-action-list__item");
    await expect(items).toHaveCount(2);

    const before = await listWorkflowActions(g.user, g.fieldByName["Retype"]);

    // The server swaps the action's type in place, so the action the editor is
    // holding is the one that comes back.
    await items.first().locator(".button-field-action-list__type").click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: "Open URL" })
      .click();

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(async () => {
      const after = await listWorkflowActions(g.user, g.fieldByName["Retype"]);
      expect(after.map((action) => action.type)).toEqual([
        "open_url",
        "local_baserow_update_row",
      ]);
      // The retyped action is the same row as before, and the untouched one
      // kept both its position and its configuration.
      expect(after[0].id).toBe(before[0].id);
      expect(after[1].id).toBe(before[1].id);
      expect(after[1].service.field_mappings[0].value.formula).toBe("'second'");
    }).toPass({ timeout: 15_000 });

    // Retyping alone leaves the order untouched, so it cannot show that the
    // order call still lands. Moving the retyped action in the same save is
    // what makes the order call matter.
    const beforeMove = await listWorkflowActions(
      g.user,
      g.fieldByName["Retype"],
    );
    await openFieldEditor(page, "Retype");

    await items.nth(1).locator(".button-field-action-list__type").click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: "Open URL" })
      .click();

    const handles = actionList.locator("[data-sortable-handle]");
    const top = await handles.nth(0).boundingBox();
    const bottom = await handles.nth(1).boundingBox();
    if (!top || !bottom) throw new Error("action handles are not rendered");
    await page.mouse.move(
      bottom.x + bottom.width / 2,
      bottom.y + bottom.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(top.x + top.width / 2, top.y + top.height / 2 - 8, {
      steps: 12,
    });
    await page.mouse.up();

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(async () => {
      const moved = await listWorkflowActions(g.user, g.fieldByName["Retype"]);
      expect(moved).toHaveLength(2);
      // The retyped action moved to the front under the id it already had, and
      // the other one dropped behind it.
      expect(moved[0].id).toBe(beforeMove[1].id);
      expect(moved[1].id).toBe(beforeMove[0].id);
      expect(moved[0].type).toBe("open_url");
    }).toPass({ timeout: 15_000 });
  });

  test("retyping an action and configuring it in one save lands on the same action", async ({
    page,
  }) => {
    // Retyping and configuring take two calls, the second one against whatever
    // the first answered with. This is the path that breaks if a type change
    // hands back a different action than the editor asked about.
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    const before = await listWorkflowActions(
      g.user,
      g.fieldByName["Reconfigure"],
    );
    expect(before.map((action) => action.type)).toEqual(["open_url"]);

    await openFieldEditor(page, "Reconfigure");
    const actionList = page.locator(".button-field-action-list");
    await actionList.locator(".button-field-action-list__type").click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: "Create a row" })
      .click();

    // Database first, then table: the second dropdown of the pair.
    const actionForm = page.locator(".button-field-action-list__form");
    const pick = async (index: number, name: string) => {
      await actionForm.locator(".dropdown").nth(index).click();
      await page
        .locator(".dropdown__items:visible")
        .locator(".select__item-link", { hasText: name })
        .click();
    };
    await pick(0, "Button DB");
    await pick(1, "Tickets");

    await page.locator(".field-context button", { hasText: "Save" }).click();

    await expect(async () => {
      const after = await listWorkflowActions(
        g.user,
        g.fieldByName["Reconfigure"],
      );
      expect(after.map((action) => action.type)).toEqual([
        "local_baserow_create_row",
      ]);
      // Same action as before, now of a new type and carrying the config the
      // second call sent.
      expect(after[0].id).toBe(before[0].id);
      expect(after[0].service.table_id).toBe(g.table.id);
    }).toPass({ timeout: 15_000 });

    // The proof it is really wired up: the reconfigured action runs, and the
    // row it makes lands in the table the second call pointed it at.
    await grid.fieldCellAt(0, RECONFIGURE_FIELD_INDEX).locator("button").click();

    await expect(async () => {
      expect(await listRows(g.user, g.table)).toHaveLength(2);
    }).toPass({ timeout: 15_000 });
    await expect(grid.leftRows()).toHaveCount(2, { timeout: 15_000 });
  });

  test("a delete action removes the clicked row from the grid", async ({
    page,
  }) => {
    await resetRows(g, [
      { Name: "Ada", Status: "todo" },
      { Name: "Grace", Status: "todo" },
      { Name: "Hedy", Status: "todo" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await expect(grid.leftRows()).toHaveCount(3);

    // The row id resolves before the action runs, so the action can delete the
    // very row that was clicked.
    await grid.fieldCellAt(0, REMOVE_FIELD_INDEX).locator("button").click();

    await expect(grid.leftRows()).toHaveCount(2);
    await expect(grid.primaryCellAt(0)).toHaveText("Grace");

    const rows = await listRows(g.user, g.table);
    expect(rows.map((row) => row.Name)).toEqual(["Grace", "Hedy"]);
  });

  test("a create row action puts the new row on the grid", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await expect(grid.leftRows()).toHaveCount(1);

    await grid.fieldCellAt(0, SPAWN_FIELD_INDEX).locator("button").click();

    // The row the click made is not the row it was clicked on, so the grid can
    // only learn about it from the broadcast that follows the dispatch.
    await expect(grid.leftRows()).toHaveCount(2);
    await expect(grid.primaryCellAt(1)).toHaveText("Spawned");

    const rows = await listRows(g.user, g.table);
    expect(rows.map((row) => row.Name)).toEqual(["Ada", "Spawned"]);
  });

  test("a click runs as whoever clicked, not as whoever configured it", async ({
    page,
    browser,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.fieldCellAt(0, RUN_FIELD_INDEX).locator("button").click();
    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText("done");
    await expect(grid.fieldCellAt(0, MODIFIED_BY_FIELD_INDEX)).toContainText(
      g.user.name,
    );

    // A different member of the workspace, in their own browser, clicking the
    // same button on the same row.
    const otherContext = await browser.newContext();
    try {
      const otherPage = await otherContext.newPage();
      const otherGrid = new GridPage(otherPage, otherUser);
      await otherGrid.goTo(g.database, g.table);

      await otherGrid.fieldCellAt(0, RUN_FIELD_INDEX).locator("button").click();

      // The write is attributed to them, not to the user who built the field.
      // Nothing in the action says who it runs as, which is the point of
      // dispatching as the actor instead of an integration's authorized user.
      await expect(
        otherGrid.fieldCellAt(0, MODIFIED_BY_FIELD_INDEX),
      ).toContainText(otherUser.name);

      // The first user sees it land too, from a click they never made.
      await expect(grid.fieldCellAt(0, MODIFIED_BY_FIELD_INDEX)).toContainText(
        otherUser.name,
      );
    } finally {
      await otherContext.close();
    }
  });

  test("a duplicated table's actions target the copy, not the original", async ({
    page,
  }) => {
    // Duplicating a table this wide is slow, and the job has to finish before
    // anything can be asserted.
    test.setTimeout(180_000);
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Duplicate from the sidebar, the way a user would. The Context self-hides
    // when it does not fit, so the menu is opened until the item is there.
    const original = sidebarTable(page, "Tickets");
    await original.hover();
    const duplicateItem = page.locator(
      '.context__menu-item-link:visible:has-text("Duplicate")',
    );
    await expect(async () => {
      await original.locator(".tree__options").click();
      await expect(duplicateItem).toBeVisible({ timeout: 1000 });
    }).toPass({ timeout: 15_000 });
    await duplicateItem.click();

    const copyRow = sidebarTable(page, "Tickets 2");
    await expect(copyRow).toBeVisible({ timeout: 150_000 });
    await copyRow.locator("a.tree__sub-link").click();
    await expect(page.locator(".grid-view__right")).toBeVisible();

    const form = page.locator(".button-field-action-list__form");
    // Database first, then table.
    const targetTable = form.locator(".dropdown__selected-text").nth(1);

    // "Run" targets the table it lives on, so the copy's version follows the
    // copy.
    await openFieldEditor(page, "Run");
    await expect(targetTable).toHaveText("Tickets 2");
    await expect(form.getByText("Status")).toBeVisible();

    // A closed field context stays mounted, so the next editor has to open on
    // a fresh page or both forms would be addressable at once.
    await page.reload();
    await expect(page.locator(".grid-view__right")).toBeVisible();

    // "Cross" targets a table that was not duplicated, which has no entry in
    // the id mapping. Nulling it there is what emptied these dropdowns.
    await openFieldEditor(page, "Cross");
    await expect(targetTable).toHaveText("Others");
    await expect(form.getByText("OtherOnly")).toBeVisible();

    const copy = (await listTables(g.user, g.database)).find(
      (table) => table.name === "Tickets 2",
    );
    if (!copy) throw new Error("the duplicated table is missing");
    const copyFields = await getFieldsForTable(g.user, copy);
    const fieldNamed = (name: string) => {
      const field = copyFields.find((candidate) => candidate.name === name);
      if (!field) throw new Error(`the duplicated ${name} field is missing`);
      return field;
    };

    // The same two, read back from the server rather than the form.
    const runActions = await listWorkflowActions(g.user, fieldNamed("Run"));
    expect(runActions[0].service.table_id).toBe(copy.id);
    expect(runActions[0].service.table_id).not.toBe(g.table.id);

    const crossActions = await listWorkflowActions(g.user, fieldNamed("Cross"));
    expect(crossActions[0].service.table_id).toBe(otherTable.id);

    // A chained reference names an action by id, so the copy's URL action has
    // to point at the copy's create row action rather than the original's.
    const copyLink = await listWorkflowActions(
      g.user,
      fieldNamed("ChainedLink"),
    );
    const originalLink = await listWorkflowActions(
      g.user,
      g.fieldByName["ChainedLink"],
    );
    expect(copyLink[0].service.table_id).toBe(copy.id);
    expect(copyLink[1].url.formula).toContain(
      `previous_action.${copyLink[0].id}.`,
    );
    // A missed remap leaves the original's id behind, which still resolves at
    // click time and writes into the wrong table.
    expect(copyLink[1].url.formula).not.toContain(
      `previous_action.${originalLink[0].id}.`,
    );

    // Remapped is not the same as working, so click it on the copy.
    await grid.goTo(g.database, copy);
    const rowsBefore = await listRows(g.user, g.table);
    await grid
      .fieldCellAt(0, CHAINED_LINK_FIELD_INDEX)
      .locator("button")
      .click();
    await expect(page).toHaveURL(/\/chained-\d+$/);

    // The row landed in the copy, and the original was left alone.
    const copyRows = await listRows(g.user, copy);
    expect(
      copyRows.filter((row) => row.Name === "Linked child").length,
    ).toBeGreaterThan(0);
    expect(await listRows(g.user, g.table)).toHaveLength(rowsBefore.length);
  });

  test("a button field made in the UI renders disabled until it has an action", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await page.locator(".grid-view__add-column").click();
    const context = page.locator(".field-context:visible");
    await context.getByPlaceholder("Name").fill("Made");

    // The type only appears here while the feature flag is on, so picking it
    // is the flag's only end to end coverage.
    await context.locator(".dropdown").first().click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: "Button" })
      .click();

    await context.getByPlaceholder("Open").fill("Go");
    await context.locator("button", { hasText: "Create" }).click();

    await expect(fieldHeader(page, "Made")).toBeVisible();
    const button = grid
      .fieldCellAt(0, CREATED_FIELD_INDEX)
      .locator(".grid-field-button button");
    await expect(button).toHaveText("Go");
    // A button with nothing to run has nothing to do.
    await expect(button).toBeDisabled();

    // Put the table back, since the rest of the suite counts on its columns.
    await fieldHeader(page, "Made")
      .locator(".grid-view__description-icon-trigger")
      .click();
    await page
      .locator(".context__menu-item-link", { hasText: "Delete field" })
      .click();
    await expect(fieldHeader(page, "Made")).toHaveCount(0);
  });

  // Phase 3: an action reading what an earlier one returned.

  test("a later action uses the row an earlier one created", async ({
    page,
  }) => {
    await resetRows(g, [
      { Name: "Ada", Status: "todo" },
      { Name: "Grace", Status: "todo" },
    ]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.fieldCellAt(0, CHAINED_FIELD_INDEX).locator("button").click();

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      const child = rows.find((row) => row.Name === "Chained child");
      expect(child).toBeDefined();
      // Only the first action knows this id, so the second can be right only
      // by having read its result.
      expect(rows.find((row) => row.Name === "Ada").Status).toBe(
        `child ${child.id}`,
      );
      // The untouched row proves the write was targeted, not blanket.
      expect(rows.find((row) => row.Name === "Grace").Status).toBe("todo");
    }).toPass({ timeout: 15_000 });
  });

  test("a URL opens carrying the id of the row just created", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid
      .fieldCellAt(0, CHAINED_LINK_FIELD_INDEX)
      .locator("button")
      .click();

    // The only test spanning the dispatch response, the field names it
    // carries, and the browser resolving a formula against them.
    await expect(page).toHaveURL(/\/chained-\d+$/);

    const rows = await listRows(g.user, g.table);
    const child = rows.find((row) => row.Name === "Linked child");
    expect(new URL(page.url()).pathname).toBe(`/chained-${child.id}`);
  });

  test("a chained reference reads a row in another table", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid
      .fieldCellAt(0, CHAINED_CROSS_FIELD_INDEX)
      .locator("button")
      .click();

    // The grid holds no fields for "Others", so the value can only arrive
    // through the names the result carries with it.
    await expect(grid.fieldCellAt(0, NOTE_FIELD_INDEX)).toHaveText(
      "crossed child",
    );
  });

  test("a failing action stops the chain before it navigates", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    const pathBefore = new URL(page.url()).pathname;

    await grid
      .fieldCellAt(0, BROKEN_CHAIN_FIELD_INDEX)
      .locator("button")
      .click();

    await expect(page.locator(".toast__message")).toContainText("Action 1");
    // The builder navigates here with the failed action's id missing from the
    // URL. The dispatch raises before `client_actions` is built, so it cannot.
    expect(new URL(page.url()).pathname).toBe(pathBefore);
  });

  test("the explorer offers earlier actions, and only earlier ones", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // The first action in a list has nothing before it.
    await openFieldEditor(page, "Insertable");
    await actionItem(page, 0)
      .locator(".formula-input-field__editor")
      .first()
      .click();
    await expect(explorer(page)).toBeVisible();
    await expect(
      explorer(page).locator(".node-explorer-content__name", {
        hasText: "Create a row",
      }),
    ).toHaveCount(0);
    // Reloaded rather than cancelled, so the next editor opens clean.
    await grid.goTo(g.database, g.table);

    // The second action is offered the first, through the whole provide chain
    // from the sub-form down to the formula input.
    await openFieldEditor(page, "Buildable");
    const added = await addAction(page, "Open URL");
    await added.locator(".formula-input-field__editor").first().click();
    await expect(
      explorer(page).locator(".node-explorer-content__name", {
        hasText: "Create a row",
      }),
    ).toHaveCount(1);
  });

  test("two brand new actions can be chained in one save", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    // Nothing that reaches the API may carry the editor's own client id.
    const clientIdSent: string[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().includes("/workflow_actions/") &&
        (request.postData() ?? "").includes("_clientId")
      ) {
        clientIdSent.push(request.url());
      }
    });

    await openFieldEditor(page, "Chainable");
    await addAction(page, "Create a row");
    await pickTableOn(page, 1, "Button DB", "Tickets");
    const linkAction = await addAction(page, "Open URL");

    await linkAction.locator(".formula-input-field__editor").first().click();
    await page.keyboard.type("/fresh-");
    // The second of the two "Create a row" nodes is the one added above, which
    // has no id yet and is referenced by its client id until the save.
    await explorer(page)
      .locator(".node-explorer-content__name", { hasText: "Create a row" })
      .nth(1)
      .click();
    await pickExplorerNode(page, "Id");

    await saveField(page);

    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Chainable"],
      );
      expect(actions.map((action) => action.type)).toEqual([
        "local_baserow_create_row",
        "local_baserow_create_row",
        "open_url",
      ]);
      // Rewritten to the id the server handed the action created before it.
      expect(actions[2].url.formula).toContain(
        `previous_action.${actions[1].id}.`,
      );
    }).toPass({ timeout: 15_000 });

    expect(clientIdSent).toEqual([]);

    await grid.goTo(g.database, g.table);
    await grid
      .fieldCellAt(0, CHAINABLE_FIELD_INDEX)
      .locator("button")
      .click();
    await expect(page).toHaveURL(/\/fresh-\d+$/);
  });

  test("a saved action can be pointed at one inserted above it", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Insertable");
    // The new action is added at the end, then the saved one is moved after
    // it, so the saved action reconciles as an update that references
    // something created in the same save.
    await addAction(page, "Create a row");
    await pickTableOn(page, 1, "Button DB", "Tickets");
    await dragAction(page, 0, 1);

    await actionItem(page, 1)
      .locator(".formula-input-field__editor")
      .first()
      .click();
    await pickExplorerNode(page, "Create a row", "Id");
    await saveField(page);

    await expect(async () => {
      const actions = await listWorkflowActions(
        g.user,
        g.fieldByName["Insertable"],
      );
      expect(actions.map((action) => action.type)).toEqual([
        "local_baserow_create_row",
        "local_baserow_update_row",
      ]);
      // The update path of the rewrite: the referring action already existed.
      expect(actions[1].service.row_id.formula).toContain(
        `previous_action.${actions[0].id}.`,
      );
    }).toPass({ timeout: 15_000 });
  });

  test("a forward reference is marked, and moving it back heals it", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Stale");
    const list = page.locator(".button-field-action-list");

    // The URL action reads one that runs after it, so it can never resolve.
    await expect(list.locator("[data-action-error]")).toHaveCount(1);
    await expect(list).toContainText("At least one action is misconfigured");

    // Moved after the action it reads, with nothing retyped. The reference was
    // marked rather than cleared, which is what makes this reversible at all
    // (ADR 006 section 8).
    await dragAction(page, 0, 1);

    await expect(list.locator("[data-action-error]")).toHaveCount(0);
    await saveField(page);

    await grid.goTo(g.database, g.table);
    await grid.fieldCellAt(0, STALE_FIELD_INDEX).locator("button").click();
    await expect(page).toHaveURL(/\/stale-\d+$/);
  });

  test("a reordered chain still resolves after saving", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await openFieldEditor(page, "Chained");
    // An unrelated action is added, then the chain's second half is moved
    // after it. `order` and the formulas are rewritten in the same save and
    // have to agree, and the reference still points backwards.
    const added = await addAction(page, "Open URL");
    await added.locator(".formula-input-field__editor").first().click();
    await page.keyboard.type("/reordered");
    await dragAction(page, 1, 2);
    await saveField(page);

    await grid.goTo(g.database, g.table);
    await grid.fieldCellAt(0, CHAINED_FIELD_INDEX).locator("button").click();

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      const child = rows.find((row) => row.Name === "Chained child");
      expect(rows.find((row) => row.Name === "Ada").Status).toBe(
        `child ${child.id}`,
      );
    }).toPass({ timeout: 15_000 });
  });

  test("the third action can read the first, skipping the second", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);

    await grid.fieldCellAt(0, DEEP_FIELD_INDEX).locator("button").click();

    await expect(async () => {
      const rows = await listRows(g.user, g.table);
      const one = rows.find((row) => row.Name === "Deep one");
      const two = rows.find((row) => row.Name === `Deep two via ${one.id}`);
      expect(two).toBeDefined();
      // Both ids at once, so the last action reached past the one before it.
      expect(rows.find((row) => row.Name === "Ada").Status).toBe(
        `${one.id}-${two.id}`,
      );
    }).toPass({ timeout: 15_000 });
  });
});
