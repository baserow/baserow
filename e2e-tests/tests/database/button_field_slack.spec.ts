/**
 * The button field's Slack action, end to end.
 *
 * The bot lives on the button's own database and is created from the action
 * form itself, so this file drives that editor flow for real and checks what
 * the API ends up holding. A click reaches whatever
 * BASEROW_INTEGRATIONS_SLACK_API_URL names: the e2e stack points it at the
 * WireMock stub in `e2e-tests/stubs/slack` and sets E2E_SLACK_STUB, and the
 * one test that clicks is skipped without that, since it would reach
 * slack.com with a made-up token otherwise.
 */

import { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import {
  actionItem,
  addAction,
  exactly,
  expandAction,
  explorer,
  openFieldEditor,
  saveField,
} from "../../pages/database/buttonFieldEditor";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import {
  createRowAction,
  createSlackAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import {
  createSlackBotIntegration,
  listIntegrations,
} from "../../fixtures/database/integration";
import { createDatabase } from "../../fixtures/database/database";
import { User } from "../../fixtures/user";

// Positions in the right-hand section, in the order `beforeAll` creates them.
const TS_FIELD_INDEX = 0;
const LIVE_FIELD_INDEX = 3;
const SLOW_FIELD_INDEX = 4;

const SLACK_STUB = process.env.E2E_SLACK_STUB === "yes";
// What `e2e-tests/stubs/slack` answers every post with.
const STUB_TS = "1700000000.000100";

let g: GridSetupResult;

/** Something short and unique, so parallel workers cannot read each other's bots. */
function token() {
  return Math.random().toString(36).slice(2, 10);
}

async function gridFor(page: Page, user: User) {
  const grid = new GridPage(page, user);
  await grid.goTo(g.database, g.table);
  return grid;
}

/** The dropdown inside an action's form that lists the database's bots. */
function integrationDropdown(page: Page, index: number) {
  return actionItem(page, index).locator(
    ".button-field-action-list__form .integration-dropdown",
  );
}

test.describe("Button field, Slack action", () => {
  test.use({ viewport: { width: 2200, height: 900 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Slack DB",
      tableName: "People",
      fields: [
        { name: "Slack ts", type: "text" },
        { name: "Post", type: "button", settings: { label: "Post" } },
        { name: "Chain", type: "button", settings: { label: "Chain" } },
        { name: "Live", type: "button", settings: { label: "Live" } },
        { name: "Slow", type: "button", settings: { label: "Slow" } },
      ],
    });
  });

  test("a bot is created from the action form and the action saves with it", async ({
    page,
  }) => {
    const botName = `Bot ${token()}`;
    await gridFor(page, g.user);
    await openFieldEditor(page, "Post");
    await addAction(page, "Send a Slack message");

    // Nothing to pick yet: the database was created a moment ago.
    const dropdown = integrationDropdown(page, 0);
    await dropdown.click();
    const items = page.locator(".dropdown__items:visible");
    await expect(items).toContainText("No integrations found");
    await items.getByText("Add new integration").click();

    const modal = page.locator(".modal__box:visible", {
      hasText: "New integration",
    });
    await expect(modal).toBeVisible();
    await modal.getByPlaceholder("Enter integration name...").fill(botName);
    await modal.getByPlaceholder("xoxb-1234-...").fill("xoxb-made-up");
    await modal.getByRole("button", { name: exactly("Create") }).click();
    await expect(modal).toBeHidden();

    // Offered now, and chosen for the action.
    await dropdown.click();
    await page
      .locator(".dropdown__items:visible")
      .locator(".select__item-link", { hasText: exactly(botName) })
      .click();
    await expect(dropdown).toContainText(botName);

    const form = actionItem(page, 0).locator(".button-field-action-list__form");
    await form.getByPlaceholder("Enter a channel name").fill("social");
    await form.locator(".formula-input-field__editor").click();
    await page.keyboard.type("Hello from e2e");
    await saveField(page);
    await expect(page.locator(".button-field-action-list")).toBeHidden();

    const bots = await listIntegrations(g.user, g.database);
    const bot = bots.find((candidate) => candidate.name === botName);
    expect(bot, "the bot was not created on the database").toBeDefined();
    expect(bot.type).toBe("slack_bot");

    const actions = await listWorkflowActions(g.user, g.fieldByName["Post"]);
    const slack = actions.find(
      (action) => action.type === "slack_write_message",
    );
    expect(slack, "the Slack action was not saved").toBeDefined();
    expect(slack.service.integration_id).toBe(bot.id);
    expect(slack.service.channel).toBe("social");
    expect(slack.service.text.formula).toContain("Hello from e2e");
  });

  test("a later action can point at the message timestamp", async ({
    page,
  }) => {
    const bot = await createSlackBotIntegration(g.user, g.database, {
      name: `Chain bot ${token()}`,
      token: "xoxb-made-up",
    });
    await createSlackAction(g.user, g.fieldByName["Chain"], {
      integrationId: bot.id,
      channel: "social",
      text: "'chained'",
    });
    await createRowAction(g.user, g.fieldByName["Chain"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [],
    });

    await gridFor(page, g.user);
    await openFieldEditor(page, "Chain");
    await expandAction(page, 1);
    // Any formula input of the second action opens the explorer.
    await actionItem(page, 1)
      .locator(".button-field-action-list__form .formula-input-field__editor")
      .first()
      .click();
    await explorer(page)
      .locator(".node-explorer-content__name", {
        hasText: exactly("Send a Slack message"),
      })
      .click();

    // What the backend answers with, offered before any click has happened.
    await expect(explorer(page)).toContainText("Message timestamp");
    await expect(explorer(page)).toContainText("Channel");
  });

  test("a bot of another database is refused", async () => {
    const elsewhere = await createDatabase(
      g.user,
      "Elsewhere",
      g.database.workspace,
    );
    const foreign = await createSlackBotIntegration(g.user, elsewhere, {
      token: "xoxb-made-up",
    });

    let status: number | undefined;
    let error: string | undefined;
    try {
      await createSlackAction(g.user, g.fieldByName["Post"], {
        integrationId: foreign.id,
        channel: "social",
        text: "'nope'",
      });
    } catch (exception: any) {
      status = exception.response?.status;
      error = exception.response?.data?.error;
    }
    expect(status).toBe(400);
    expect(error).toBe("ERROR_WORKFLOW_ACTION_INVALID_INTEGRATION");
  });

  test("a click posts through the bot and the row keeps the message timestamp", async ({
    page,
  }) => {
    test.skip(
      !SLACK_STUB,
      "E2E_SLACK_STUB is not set, a click would reach slack.com",
    );

    await resetRows(g, [{ Name: "Ada", "Slack ts": "" }]);
    const bot = await createSlackBotIntegration(g.user, g.database, {
      name: "Live bot",
      token: "xoxb-made-up",
    });
    const name = g.fieldByName["Name"];
    await createSlackAction(g.user, g.fieldByName["Live"], {
      integrationId: bot.id,
      channel: "social",
      text: `concat('Hello from e2e ', get('row.field_${name.id}'))`,
    });
    const slack = (await listWorkflowActions(g.user, g.fieldByName["Live"]))[0];
    await createRowAction(g.user, g.fieldByName["Live"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [
        {
          field: g.fieldByName["Slack ts"],
          value: `get('previous_action.${slack.id}.ts')`,
        },
      ],
    });

    const grid = await gridFor(page, g.user);
    await grid.fieldCellAt(0, LIVE_FIELD_INDEX).locator("button").click();

    // The stub's own timestamp, so it can only have come back through the
    // bot's post and the action after it.
    await expect(grid.fieldCellAt(0, TS_FIELD_INDEX)).toHaveText(STUB_TS, {
      timeout: 15_000,
    });
    await expect(page.locator(".toast")).toHaveCount(0);
  });
  test("a click while the same row is still posting is refused", async ({
    page,
    browser,
  }) => {
    test.skip(
      !SLACK_STUB,
      "E2E_SLACK_STUB is not set, a click would reach slack.com",
    );
    test.setTimeout(120_000);

    await resetRows(g, [{ Name: "Ada", "Slack ts": "" }]);
    const bot = await createSlackBotIntegration(g.user, g.database, {
      name: "Slow bot",
      token: "xoxb-made-up",
    });
    // The stub holds this channel open for eight seconds, which is what the
    // second click has to land inside.
    await createSlackAction(g.user, g.fieldByName["Slow"], {
      integrationId: bot.id,
      channel: "slow",
      text: "'taking a while'",
    });

    const grid = await gridFor(page, g.user);

    // The cell disables itself while its request is in flight, so a second
    // click in the same session never reaches the server. Another session is
    // what the lock is for.
    const other = await browser.newContext({
      viewport: { width: 2200, height: 900 },
    });
    const otherPage = await other.newPage();
    const otherGrid = new GridPage(otherPage, g.user);
    await otherGrid.goTo(g.database, g.table);

    const button = grid.fieldCellAt(0, SLOW_FIELD_INDEX).locator("button");
    const otherButton = otherGrid
      .fieldCellAt(0, SLOW_FIELD_INDEX)
      .locator("button");

    await button.click();
    await expect(button).toHaveClass(/button--loading/);
    await otherButton.click();

    await expect(otherPage.locator(".toast")).toBeVisible({ timeout: 20_000 });

    // The first post is still in flight. Waiting for it keeps it out of the
    // teardown and out of the test after this one.
    await expect(button).not.toHaveClass(/button--loading/, {
      timeout: 30_000,
    });
    await other.close();
  });
});
