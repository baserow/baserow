/**
 * Button field actions that reach outside Baserow, end to end.
 *
 * The backend tests call the service layer directly and the frontend tests
 * hand the types a schema by hand, so only this file proves a request really
 * leaves the process.
 *
 * The environment provides an HTTP stub, wired up in
 * `e2e-tests/justfile` and in the e2e CI job. Against a dev stack the
 * defaults in `run-e2e-tests-locally.sh` use the public httpbin instead.
 */

import { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import {
  actionItem,
  addAction,
  expandAction,
  explorer,
  openFieldEditor,
  pickExplorerNode,
} from "../../pages/database/buttonFieldEditor";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import {
  createHttpRequestAction,
  createRowAction,
  getWorkflowAction,
  listWorkflowActions,
  WorkflowAction,
} from "../../fixtures/database/workflowAction";
import { listRows } from "../../fixtures/database/rows";
import { duplicateField } from "../../fixtures/database/field";
import { User, createUser } from "../../fixtures/user";
import { addUserToWorkspace } from "../../fixtures/workspace";

/** The stub as the *backend* reaches it, which is not where the tests run. */
const STUB = process.env.E2E_HTTP_STUB_URL ?? "http://e2e-httpbin:80";

/**
 * How many external clicks one user gets per minute in this environment. It
 * has to match what the backend was started with, which only the environment
 * that started it knows, so the two tests that click until they are refused
 * are skipped when it is not declared. Everything else keeps under it by
 * clicking as a user of its own.
 */
const DECLARED_RATE_LIMIT = process.env.E2E_BUTTON_RATE_LIMIT;
const RATE_LIMIT = Number(DECLARED_RATE_LIMIT ?? "3");

/** The HTTP action's label, which is also what its explorer node is named. */
const HTTP_ACTION = "Send an HTTP request";

/** A host that answers nothing, so a request to it fails rather than 404s. */
const UNREACHABLE = "http://127.0.0.1:9/secret-path?token=shhh";

// Positions in the right-hand section, in the order `beforeAll` creates them.
const STATUS_FIELD_INDEX = 0;
const HTTP_FIELD_INDEX = 1;
const ECHO_FIELD_INDEX = 2;
const FAILING_FIELD_INDEX = 3;
const CHAINED_FIELD_INDEX = 4;
const SLOW_FIELD_INDEX = 5;
const SLOW_TWO_FIELD_INDEX = 6;
const LOCAL_FIELD_INDEX = 7;
const FRESH_FIELD_INDEX = 8;
const CAPTURED_FIELD_INDEX = 9;
const LIMITED_FIELD_INDEX = 10;
const DUPLICATE_FIELD_INDEX = 11;

let g: GridSetupResult;
let httpAction: WorkflowAction;
let capturedAction: WorkflowAction;
let duplicateAction: WorkflowAction;

/**
 * A member of the workspace who has clicked nothing yet. The rate limit counts
 * per user and is set low here, so tests take a budget of their own.
 */
async function freshClicker(): Promise<User> {
  const clicker = await createUser();
  await addUserToWorkspace(g.user, g.database.workspace, clicker);
  return clicker;
}

/** The request's node in the explorer, named after the action it describes. */
function httpNode(page: Page) {
  return explorer(page)
    .locator(".node-explorer-content__name", { hasText: HTTP_ACTION })
    .first();
}

/** A node in the explorer, matched on its whole name. */
function explorerNode(page: Page, name: string) {
  return explorer(page).locator(".node-explorer-content__name", {
    hasText: new RegExp(`^\\s*${name}\\s*$`),
  });
}

async function gridFor(page: Page, user: User) {
  const grid = new GridPage(page, user);
  await grid.goTo(g.database, g.table);
  return grid;
}

test.describe("Button field, external actions", () => {
  // Every button field has to be on screen at once, or the grid never renders
  // the column a test clicks.
  test.use({ viewport: { width: 3600, height: 900 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "External DB",
      tableName: "Tickets",
      fields: [
        { name: "Status", type: "text" },
        { name: "Http", type: "button", settings: { label: "Http" } },
        { name: "Echo", type: "button", settings: { label: "Echo" } },
        { name: "Failing", type: "button", settings: { label: "Failing" } },
        { name: "Chained", type: "button", settings: { label: "Chained" } },
        { name: "Slow", type: "button", settings: { label: "Slow" } },
        { name: "SlowTwo", type: "button", settings: { label: "SlowTwo" } },
        { name: "Local", type: "button", settings: { label: "Local" } },
        { name: "Fresh", type: "button", settings: { label: "Fresh" } },
        { name: "Captured", type: "button", settings: { label: "Captured" } },
        { name: "Limited", type: "button", settings: { label: "Limited" } },
        { name: "Duplicate", type: "button", settings: { label: "Duplicate" } },
      ],
    });

    const name = g.fieldByName["Name"];
    const status = g.fieldByName["Status"];

    // "Http" only calls the stub, so a click that goes wrong has nowhere else
    // to have gone wrong.
    httpAction = await createHttpRequestAction(g.user, g.fieldByName["Http"], {
      url: `'${STUB}/json'`,
    });

    // "Echo" builds its URL out of the clicked row and writes back what the
    // stub echoed, so the row has to reach the service's own formula fields.
    const echoRequest = await createHttpRequestAction(
      g.user,
      g.fieldByName["Echo"],
      { url: `concat('${STUB}/anything/', get('row.field_${name.id}'))` },
    );
    await createRowAction(g.user, g.fieldByName["Echo"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [
        {
          field: status,
          value: `get('previous_action.${echoRequest.id}.body.url')`,
        },
      ],
    });

    // "Failing" cannot reach its host, and would write the row afterwards, so
    // one click says both what the clicker is told and what is left behind.
    await createHttpRequestAction(g.user, g.fieldByName["Failing"], {
      url: `'${UNREACHABLE}'`,
    });
    await createRowAction(g.user, g.fieldByName["Failing"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: status, value: "'reached'" }],
    });

    // "Chained" is the scenario the issue asks for: call an endpoint, then put
    // part of its answer in the row.
    const chainedRequest = await createHttpRequestAction(
      g.user,
      g.fieldByName["Chained"],
      { url: `'${STUB}/json'` },
    );
    await createRowAction(g.user, g.fieldByName["Chained"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [
        {
          field: status,
          value: `get('previous_action.${chainedRequest.id}.body.slideshow.title')`,
        },
      ],
    });

    // Slow enough that a second click lands while the first is still running.
    for (const fieldName of ["Slow", "SlowTwo"]) {
      await createHttpRequestAction(g.user, g.fieldByName[fieldName], {
        url: `'${STUB}/delay/3'`,
      });
    }

    // "Local" reaches nothing outside, so no number of clicks may be refused.
    await createRowAction(g.user, g.fieldByName["Local"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: status, value: "'local'" }],
    });

    // "Fresh" is never clicked by anything, which is the whole point of it:
    // it is what an action looks like before it has answered once.
    await createHttpRequestAction(g.user, g.fieldByName["Fresh"], {
      url: `'${STUB}/json'`,
    });

    // "Captured" is the same, for the tests that click first and then look.
    capturedAction = await createHttpRequestAction(
      g.user,
      g.fieldByName["Captured"],
      { url: `'${STUB}/json'` },
    );

    // "Limited" is clicked until the rate limit refuses it.
    await createHttpRequestAction(g.user, g.fieldByName["Limited"], {
      url: `'${STUB}/json'`,
    });

    // "Duplicate" is copied, and the copy must carry no answer of its own.
    duplicateAction = await createHttpRequestAction(
      g.user,
      g.fieldByName["Duplicate"],
      { url: `'${STUB}/json'` },
    );
  });

  // A. The request really leaves the process

  test("a click calls the endpoint and keeps what it answered", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, HTTP_FIELD_INDEX).locator("button").click();

    // Nothing on the grid changes, so what the endpoint answered is the only
    // evidence the request was made at all.
    await expect(async () => {
      const saved = await getWorkflowAction(g.user, httpAction);
      expect(saved.service.sample_data?.data?.status_code).toBe(200);
    }).toPass({ timeout: 20_000 });

    await expect(page.locator(".toast")).toHaveCount(0);
  });

  test("the URL is built from the row that was clicked", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, ECHO_FIELD_INDEX).locator("button").click();

    // The stub echoes the URL it was called on, and the following action puts
    // that back in the row, so the row's own name has to come back around.
    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toContainText("Ada");
  });

  test("a request that fails says so without repeating the URL", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, FAILING_FIELD_INDEX).locator("button").click();

    const toast = page.locator(".toast");
    await expect(toast).toBeVisible();

    // Named like any other failure, so the clicker can count to it in the
    // editor rather than being told only that something went wrong.
    await expect(toast).toContainText("Action 1");

    // The service puts the URL it could not reach in its own message, and that
    // carries the path and the query string, which is where an API key would
    // be. It stays server side.
    const shown = (await toast.textContent()) ?? "";
    expect(shown).not.toContain("secret-path");
    expect(shown).not.toContain("shhh");
    expect(shown).not.toContain("127.0.0.1");
  });

  test("an action after a failed request does not run", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, FAILING_FIELD_INDEX).locator("button").click();
    await expect(page.locator(".toast")).toBeVisible();

    // ADR 006 section 3: what already ran stays, what comes after does not run.
    const rows = await listRows(g.user, g.table);
    expect(rows[0].Status).toBe("todo");
  });

  // B. What the editor can say about the answer

  test("an endpoint that has not answered yet describes no body", async ({
    page,
  }) => {
    await gridFor(page, g.user);
    await openFieldEditor(page, "Fresh");

    // The request's own form says what a click would capture, rather than
    // leaving the missing body unexplained.
    await expandAction(page, 0);
    await expect(
      actionItem(page, 0).locator(".sample-data-viewer"),
    ).toHaveCount(0);
    await expect(actionItem(page, 0).locator(".alert")).toContainText(
      "capture what the endpoint answers",
    );

    // What a request always has is offered from the start; what the endpoint
    // sends back is not, because nothing knows its shape yet.
    await addAction(page, "Open URL");
    await expandAction(page, 1);
    await actionItem(page, 1)
      .locator(".formula-input-field__editor")
      .first()
      .click();

    await expect(explorer(page)).toBeVisible();
    await httpNode(page).click();

    await expect(explorerNode(page, "Status code")).toHaveCount(1);
    await expect(explorerNode(page, "Raw body")).toHaveCount(1);
    // The body is the part that only a real answer can describe.
    await expect(explorerNode(page, "Body")).toHaveCount(0);

    // Left unsaved on purpose: this field is what an untouched action looks
    // like, and nothing else may click it.
    await page.keyboard.press("Escape");
  });

  test("once it has answered, the editor offers its body", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, CAPTURED_FIELD_INDEX).locator("button").click();
    await expect(async () => {
      const saved = await getWorkflowAction(g.user, capturedAction);
      expect(saved.service.sample_data).toBeTruthy();
    }).toPass({ timeout: 20_000 });

    // Reopened as whoever configures the field, which is who the editor is for.
    await gridFor(page, g.user);
    await openFieldEditor(page, "Captured");

    // The answer is shown back in the action that made the request, so the
    // note about capturing is gone.
    await expandAction(page, 0);
    await expect(
      actionItem(page, 0).locator(".sample-data-viewer"),
    ).toHaveCount(1);
    await expect(actionItem(page, 0).locator(".alert")).toHaveCount(0);

    await addAction(page, "Open URL");
    await expandAction(page, 1);
    await actionItem(page, 1)
      .locator(".formula-input-field__editor")
      .first()
      .click();

    await httpNode(page).click();
    await expect(explorerNode(page, "Body")).toHaveCount(1);

    // The stub's own keys, so this is the answer that came back rather than a
    // shape somebody wrote down.
    await pickExplorerNode(page, "Body", "slideshow");
    await expect(explorerNode(page, "title")).toHaveCount(1);
  });

  test("the answer it describes survives a reload", async ({ page }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, CAPTURED_FIELD_INDEX).locator("button").click();
    await expect(async () => {
      const saved = await getWorkflowAction(g.user, capturedAction);
      expect(saved.service.sample_data).toBeTruthy();
    }).toPass({ timeout: 20_000 });

    await gridFor(page, g.user);
    await page.reload();

    // Nothing of the click is left in this page's memory, so what the explorer
    // offers can only have come back from the backend.
    await openFieldEditor(page, "Captured");
    await addAction(page, "Open URL");
    await expandAction(page, 1);
    await actionItem(page, 1)
      .locator(".formula-input-field__editor")
      .first()
      .click();

    await expect(
      explorer(page).locator(".node-explorer-content__name", {
        hasText: HTTP_ACTION,
      }),
    ).toHaveCount(1);
  });

  // C. Chaining through an action that reaches outside

  test("a later action writes what the endpoint answered into the row", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, CHAINED_FIELD_INDEX).locator("button").click();

    // httpbin's own fixture, so the value can only have come from the request.
    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText(
      "Sample Slide Show",
    );

    const rows = await listRows(g.user, g.table);
    expect(rows[0].Status).toBe("Sample Slide Show");
  });

  test("removing the request an action reads is reported", async ({ page }) => {
    await gridFor(page, g.user);
    await openFieldEditor(page, "Chained");

    // Delete the request, leaving the action that reads it behind.
    await actionItem(page, 0).locator(".button-icon").first().click();

    await expect(page.locator("[data-action-error]")).toContainText(
      "no longer runs before it",
    );
  });

  // D. The limit, as the clicker meets it

  test("a user who keeps clicking is refused", async ({ page }) => {
    test.skip(
      !DECLARED_RATE_LIMIT,
      "set E2E_BUTTON_RATE_LIMIT to the limit the backend runs with",
    );
    test.setTimeout(120_000);
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    const button = grid.fieldCellAt(0, LIMITED_FIELD_INDEX).locator("button");

    // One external click at a time; waiting for the cell to come back is what
    // keeps them in order.
    for (let click = 0; click < RATE_LIMIT; click++) {
      await button.click();
      await expect(button).not.toHaveClass(/button--loading/, {
        timeout: 30_000,
      });
      await expect(page.locator(".toast")).toHaveCount(0);
    }

    await button.click();
    await expect(page.locator(".toast")).toBeVisible({ timeout: 20_000 });
  });

  test("a button that reaches nothing outside is never refused", async ({
    page,
  }) => {
    test.skip(
      !DECLARED_RATE_LIMIT,
      "set E2E_BUTTON_RATE_LIMIT to the limit the backend runs with",
    );
    test.setTimeout(120_000);
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    const button = grid.fieldCellAt(0, LOCAL_FIELD_INDEX).locator("button");

    // More clicks than the budget allows, none of which may spend any of it.
    for (let click = 0; click < RATE_LIMIT + 2; click++) {
      await button.click();
      await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText("local");
    }

    await expect(page.locator(".toast")).toHaveCount(0);
  });

  // F. Two clicks at once, with a request slow enough to overlap

  test("a click while the same row is still running is refused", async ({
    page,
    browser,
  }) => {
    test.setTimeout(120_000);
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    // The cell disables itself while its request is in flight, so a second
    // click in the same session never reaches the server. Another session is
    // what the lock is for, and a slow request widens the window enough to hit.
    await grid.fieldCellAt(0, SLOW_FIELD_INDEX).locator("button").click();

    const other = await browser.newContext({
      viewport: { width: 3600, height: 900 },
    });
    const otherPage = await other.newPage();
    const otherGrid = new GridPage(otherPage, clicker);
    await otherGrid.goTo(g.database, g.table);
    await otherGrid.fieldCellAt(0, SLOW_FIELD_INDEX).locator("button").click();

    await expect(otherPage.locator(".toast")).toBeVisible({ timeout: 20_000 });
    await other.close();
  });

  test("two buttons on one row do not block each other", async ({ page }) => {
    test.setTimeout(120_000);
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    // The lock is keyed on the field and the row together, so a slow request
    // on one button must leave the other alone.
    await grid.fieldCellAt(0, SLOW_FIELD_INDEX).locator("button").click();
    await grid.fieldCellAt(0, SLOW_TWO_FIELD_INDEX).locator("button").click();

    await expect(page.locator(".toast")).toHaveCount(0);
  });

  // G. Copies

  test("a copied field keeps the request but not the answer", async ({
    page,
  }) => {
    // Two clicks and a duplication job, each waiting on a real request.
    test.setTimeout(90_000);
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    // Answer once, so the original has something a copy could inherit.
    await grid.fieldCellAt(0, DUPLICATE_FIELD_INDEX).locator("button").click();
    await expect(async () => {
      const saved = await getWorkflowAction(g.user, duplicateAction);
      expect(saved.service.sample_data).toBeTruthy();
    }).toPass({ timeout: 20_000 });

    const copy = await duplicateField(
      g.user,
      g.fieldByName["Duplicate"],
      g.table,
    );

    const copied = await listWorkflowActions(g.user, copy);
    expect(copied).toHaveLength(1);
    expect(copied[0].type).toBe("http_request");
    // What a click remembered describes this installation's data, and a copy,
    // which an export can carry anywhere, is where it must not follow.
    expect(copied[0].service.sample_data).toBeNull();

    // The copy is a working button, not a broken one: it answers for itself
    // the first time somebody clicks it.
    await gridFor(page, clicker);
    const copyIndex = DUPLICATE_FIELD_INDEX + 1;
    await grid.fieldCellAt(0, copyIndex).locator("button").click();
    await expect(async () => {
      const after = await listWorkflowActions(g.user, copy);
      expect(after[0].service.sample_data).toBeTruthy();
    }).toPass({ timeout: 20_000 });
  });
});
