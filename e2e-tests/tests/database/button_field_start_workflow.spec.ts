/**
 * Button field, start workflow action: a real click, the real worker, and a
 * builder reading "Started by" in the History panel.
 */

import { Page } from "@playwright/test";
import { test, expect } from "../baserowTest";
import { GridPage } from "../../pages/database/gridPage";
import { AutomationWorkflowPage } from "../../pages/automation/automationWorkflowPage";
import { PageConfig } from "../../pages/baserowPage";
import {
  addAction,
  openFieldEditor,
  saveField,
} from "../../pages/database/buttonFieldEditor";
import { setupGrid, GridSetupResult } from "../../fixtures/database/gridSetup";
import {
  createStartWorkflowAction,
  listWorkflowActions,
} from "../../fixtures/database/workflowAction";
import { createAutomation } from "../../fixtures/automation/automation";
import {
  AutomationWorkflow,
  createAutomationWorkflow,
  publishAutomationWorkflow,
} from "../../fixtures/automation/automationWorkflow";
import { createAutomationNode } from "../../fixtures/automation/automationNode";
import { User, createUser } from "../../fixtures/user";
import { addUserToWorkspace } from "../../fixtures/workspace";

// Index of Start in the right-hand section; the first field `beforeAll` creates.
const START_FIELD_INDEX = 0;

let g: GridSetupResult;
let workflow: AutomationWorkflow;
/** A workflow only an event can start, so the picker must leave it out. */
let eventWorkflow: AutomationWorkflow;
/** A member of the workspace who can click the button but not open the automation. */
let editor: User;

/** The builder, who owns the automation, on the workflow page. */
async function builderOnWorkflow(page: Page, goto: PageConfig["goto"]) {
  const workflowPage = new AutomationWorkflowPage(
    { page, goto },
    workflow.automation,
    workflow
  );
  await workflowPage.authenticate(g.user);
  await workflowPage.goto();
  return workflowPage;
}

async function openHistoryPanel(page: Page) {
  await page.locator('[data-item-type="history"]').click();
  await expect(page.locator(".history-side-panel__title")).toBeVisible();
}

/** The history entries in the panel, newest first, as the panel orders them. */
function historyEntries(page: Page) {
  return page.locator(".workflow-history__header");
}

test.describe("Button field, start workflow action", () => {
  test.beforeAll(async () => {
    g = await setupGrid({
      dbName: "Start workflow DB",
      tableName: "Jobs",
      fields: [
        { name: "Start", type: "button", settings: { label: "Start" } },
        { name: "Configure", type: "button", settings: { label: "Configure" } },
      ],
      rows: [{ Name: "row one" }],
    });

    const automation = await createAutomation(
      "Start workflow automation",
      g.database.workspace
    );
    workflow = await createAutomationWorkflow("Started by button", automation);
    await createAutomationNode(workflow, "manual");
    await publishAutomationWorkflow(workflow);
    eventWorkflow = await createAutomationWorkflow(
      "Waits for rows",
      automation
    );
    await createAutomationNode(eventWorkflow, "local_baserow_rows_created");
    await createStartWorkflowAction(
      g.user,
      g.fieldByName["Start"],
      workflow.id
    );

    editor = await createUser();
    await addUserToWorkspace(g.user, g.database.workspace, editor, "MEMBER");
  });

  test("a click by an editor shows up as started by them in the workflow history", async ({
    page,
    browser,
    goto,
  }) => {
    // The editor clicks, in their own browser.
    const editorContext = await browser.newContext();
    try {
      const editorPage = await editorContext.newPage();
      const grid = new GridPage(editorPage, editor);
      await grid.goTo(g.database, g.table);
      await grid.fieldCellAt(0, START_FIELD_INDEX).locator("button").click();
      // The cell settles once the dispatch has returned.
      await expect(
        grid.fieldCellAt(0, START_FIELD_INDEX).locator("button")
      ).toBeEnabled();
    } finally {
      await editorContext.close();
    }

    // The builder, who owns the automation, reads the run's history.
    await builderOnWorkflow(page, goto);
    await openHistoryPanel(page);

    const entry = historyEntries(page).first();
    await expect(
      entry.locator("..").locator(".workflow-history__started-by")
    ).toHaveText(`Started by ${editor.name}`);
    // Not a test run: no prefix on the title. The worker in the e2e stack
    // runs the workflow for real, so it also completes.
    await expect(entry.locator(".workflow-history__header-title")).toHaveText(
      "Ran successfully"
    );
  });

  test("a test run from the editor is started by whoever pressed the button", async ({
    page,
    goto,
  }) => {
    await builderOnWorkflow(page, goto);

    await page.locator('[data-highlight="automation-test-run"]').click();
    await openHistoryPanel(page);

    const entry = historyEntries(page).first();
    await expect(
      entry.locator(".workflow-history__header-title")
    ).toContainText("[Test]");
    await expect(
      entry.locator("..").locator(".workflow-history__started-by")
    ).toHaveText(`Started by ${g.user.name}`);
  });

  test("the editor offers only workflows a click can start, and saves the pick", async ({
    page,
  }) => {
    const grid = new GridPage(page, g.user);
    await grid.goTo(g.database, g.table);
    await openFieldEditor(page, "Configure");
    const added = await addAction(page, "Start workflow");

    await added
      .locator(".button-field-action-list__form .dropdown")
      .first()
      .click();
    const items = page.locator(".dropdown__items:visible");
    await expect(items).toContainText(workflow.name);
    // A rows-created trigger cannot start on demand, so it is not on offer.
    await expect(items).not.toContainText(eventWorkflow.name);
    await items.getByText(workflow.name).click();

    await saveField(page);
    await expect(page.locator(".button-field-action-list")).toBeHidden();

    const actions = await listWorkflowActions(
      g.user,
      g.fieldByName["Configure"]
    );
    const saved = actions.find((action) => action.type === "start_workflow");
    expect(saved, "the start workflow action was not saved").toBeDefined();
    expect(saved.service.workflow_id).toBe(workflow.id);
  });
});
