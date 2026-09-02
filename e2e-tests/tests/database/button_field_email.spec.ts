/**
 * The button field's email action, end to end.
 *
 * The backend tests call the service layer directly and the frontend tests
 * hand the type its form by hand, so only this file proves a click really
 * sends and the mail really arrives.
 *
 * The environment provides a mail catcher, wired up in `e2e-tests/justfile`
 * and in the e2e CI job. Against a dev stack `run-e2e-tests-locally.sh` uses
 * the MailHog that `docker-compose.dev.yml` already runs.
 */

import { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import {
  addAction,
  openFieldEditor,
} from "../../pages/database/buttonFieldEditor";
import {
  setupGrid,
  resetRows,
  GridSetupResult,
} from "../../fixtures/database/gridSetup";
import {
  createEmailAction,
  createRowAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import { deleteEmail, waitForEmail } from "../../fixtures/mail";
import { User, createUser } from "../../fixtures/user";
import { addUserToWorkspace } from "../../fixtures/workspace";

// Positions in the right-hand section, in the order `beforeAll` creates them.
const STATUS_FIELD_INDEX = 0;
const MAIL_FIELD_INDEX = 1;
const MAIL_CHAIN_FIELD_INDEX = 2;

let g: GridSetupResult;
// The catcher keeps what every worker sent, and against a dev stack whatever
// the developer captured before, so a fixed subject would find someone else's
// message. Set once for the button `beforeAll` configures.
let chainSubject: string;

/** Something short and unique, so parallel workers cannot read each other's mail. */
function token() {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * A member of the workspace who has clicked nothing yet. The rate limit counts
 * per user and is set low here, so tests take a budget of their own.
 */
async function freshClicker(): Promise<User> {
  const clicker = await createUser();
  await addUserToWorkspace(g.user, g.database.workspace, clicker);
  return clicker;
}

async function gridFor(page: Page, user: User) {
  const grid = new GridPage(page, user);
  await grid.goTo(g.database, g.table);
  return grid;
}

test.describe("Button field, email action", () => {
  test.use({ viewport: { width: 2200, height: 900 } });

  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Email DB",
      tableName: "Tickets",
      fields: [
        { name: "Status", type: "text" },
        { name: "Mail", type: "button", settings: { label: "Mail" } },
        { name: "MailChain", type: "button", settings: { label: "MailChain" } },
      ],
    });

    const status = g.fieldByName["Status"];

    // "MailChain" sends, then writes, so an action that returns no row must
    // not break the ones after it.
    chainSubject = `Chained ${token()}`;
    await createEmailAction(g.user, g.fieldByName["MailChain"], {
      to: "'chain@example.com'",
      subject: `'${chainSubject}'`,
      body: "'Sent before the row was written'",
    });
    await createRowAction(g.user, g.fieldByName["MailChain"], {
      type: "local_baserow_update_row",
      table: g.table,
      rowId: "get('row.id')",
      fieldMappings: [{ field: status, value: "'after the email'" }],
    });
  });

  test("the email form offers no integration, because a button has none", async ({
    page,
  }) => {
    await gridFor(page, g.user);
    await openFieldEditor(page, "Mail");
    await addAction(page, "Send Email");

    const form = page.locator(".button-field-action-list__form").first();
    await expect(form).toContainText("To Emails");
    // Both belong to the integration branch of the shared form: a button's
    // actions send through the instance and nothing else.
    await expect(form).not.toContainText("Use the instance SMTP server");
    await expect(form).not.toContainText("From Email");
  });

  test("a click sends the email, carrying values from the row", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const subject = `Shipment ${token()}`;
    const recipient = `qa-${token()}@example.com`;
    const name = g.fieldByName["Name"];
    await createEmailAction(g.user, g.fieldByName["Mail"], {
      to: `'${recipient}'`,
      subject: `'${subject}'`,
      body: `concat('Ticket ', get('row.field_${name.id}'))`,
    });

    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);
    await grid.fieldCellAt(0, MAIL_FIELD_INDEX).locator("button").click();

    const email = await waitForEmail(subject);
    try {
      expect(email.to).toContain(recipient);
      // The body is a formula over the clicked row, not a fixed string.
      expect(email.body).toContain("Ticket Ada");
    } finally {
      // In a `finally`, or a failed assertion leaves the message behind for
      // every later run to read.
      await deleteEmail(email.id);
    }
  });

  test("a saved email action sends through the instance, with no integration", async () => {
    const actions = await listWorkflowActions(
      g.user,
      g.fieldByName["MailChain"],
    );
    const email = actions.find((action) => action.type === "smtp_email");

    expect(email, "the email action was not saved").toBeDefined();
    expect(email.service.use_instance_smtp_settings).toBe(true);
    expect(email.service.integration_id).toBeNull();
  });

  test("an action that returns no row does not stop the ones after it", async ({
    page,
  }) => {
    await resetRows(g, [{ Name: "Ada", Status: "todo" }]);
    const clicker = await freshClicker();
    const grid = await gridFor(page, clicker);

    await grid.fieldCellAt(0, MAIL_CHAIN_FIELD_INDEX).locator("button").click();

    await expect(grid.fieldCellAt(0, STATUS_FIELD_INDEX)).toHaveText(
      "after the email",
    );
    // The row being written only says the sequence carried on. Whether the
    // send before it reached anything is a question for the catcher.
    const email = await waitForEmail(chainSubject);
    try {
      expect(email.to).toContain("chain@example.com");
      expect(email.body).toContain("Sent before the row was written");
    } finally {
      await deleteEmail(email.id);
    }
  });
});
