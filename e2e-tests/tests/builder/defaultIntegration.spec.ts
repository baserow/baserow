import type { Page } from "@playwright/test";
import { getClient } from "../../client";
import { createBuilderElement } from "../../fixtures/builder/builderElement";
import { createWorkspaceLocalBaserowIntegration } from "../../fixtures/integration";
import { createDatabase } from "../../fixtures/database/database";
import { getFieldsForTable } from "../../fixtures/database/field";
import { listRows } from "../../fixtures/database/rows";
import { createTable } from "../../fixtures/database/table";
import type { BuilderPagePage } from "../../pages/builder/builderPagePage";
import { expect, test } from "../baserowTest";

/** Choose a service through the creation modal, without touching the connection. */
async function openListRowsSource(page: Page) {
  await page.locator('a[data-item-type="data_sources"]').click();
  await page.getByRole("button", { name: "Add new data source" }).click();
  const modal = page.locator(".modal__box:visible").filter({
    has: page.locator(".data-source-form"),
  });
  await modal.getByRole("button", { name: "Choose action..." }).click();
  const menu = page.locator(".grouped-dropdown__context:visible");
  await menu
    .locator(".grouped-menu__navigation")
    .getByRole("menuitem", { name: /^Local Baserow/ })
    .click();
  await menu
    .locator(".grouped-menu__actions")
    .getByRole("menuitem", { name: /^List multiple rows/ })
    .click();
  return modal;
}

/** Create the action in the editor so default selection happens on the backend. */
async function addCreateRowAction(page: Page, builder: BuilderPagePage) {
  await builder.selectButtonByName("Create shared row");
  const events = await builder.getElementEventsTab();
  await events.getByText("add action").click();
  const menu = page.locator(".event__add-action-context:visible");
  await menu
    .locator(".grouped-menu__navigation")
    .getByRole("menuitem", { name: /^Local Baserow/ })
    .click();
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/page/${builder.builderPage.id}/workflow_actions/`)
  );
  await menu
    .locator(".grouped-menu__actions")
    .getByRole("menuitem", { name: /^Create a row/ })
    .click();
  const response = await created;
  expect(response.ok()).toBeTruthy();
  const action = await response.json();
  await events.getByText("Create a row", { exact: true }).click();
  return { action, events };
}

test.describe("Builder default workspace integration", () => {
  test.setTimeout(90000);
  test.use({ actionTimeout: 15000 });

  test("preselects a shared connection and displays its rows", async ({
    page,
    context,
    workspacePage,
    builderPagePage,
  }) => {
    const { user, workspace } = workspacePage;
    const database = await createDatabase(user, "Shared data", workspace);
    const table = await createTable(user, "Contacts", database, [
      ["Name"],
      ["Ada from the shared connection"],
    ]);
    const integration = await createWorkspaceLocalBaserowIntegration(workspace);
    await builderPagePage.goto();
    const modal = await openListRowsSource(page);
    await expect(
      modal.locator(".integration-dropdown .dropdown__selected-text")
    ).toHaveText(integration.name);
    const created = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith(
          `/page/${builderPagePage.builderPage.id}/data-sources/`
        )
    );
    await modal.getByRole("button", { name: "Create", exact: true }).click();
    const response = await created;
    expect(response.ok()).toBeTruthy();
    const source = await response.json();
    expect(source.integration_id).toBe(integration.id);
    // Creation opens the edit form, where the table can be configured.
    await modal
      .locator(".form-row .dropdown")
      .first()
      .locator(".dropdown__selected")
      .click();
    await page
      .locator(".select__item:visible")
      .getByText(table.name, { exact: true })
      .click();
    await modal.getByRole("button", { name: "Save", exact: true }).click();
    await expect(modal).toBeHidden();
    const fields = await getFieldsForTable(user, table);
    await createBuilderElement(builderPagePage.builderPage, "table", {
      data_source_id: source.id,
      fields: [
        {
          name: "Name",
          type: "text",
          value: `get('current_record.field_${fields[0].id}')`,
        },
      ],
    });
    const { data: grant } = await getClient(user).post(
      `builder/preview/${builderPagePage.builder.id}/grant/`,
      { path: builderPagePage.builderPage.path }
    );
    const preview = await context.newPage();
    await preview.goto(grant.url);
    await expect(preview.locator(".ab-table tbody")).toContainText(
      "Ada from the shared connection"
    );
  });

  test("leaves a new data source connection empty when shared choices are ambiguous", async ({
    page,
    workspacePage,
    builderPagePage,
  }) => {
    const first = await createWorkspaceLocalBaserowIntegration(
      workspacePage.workspace,
      "Shared first"
    );
    const second = await createWorkspaceLocalBaserowIntegration(
      workspacePage.workspace,
      "Shared second"
    );
    await builderPagePage.goto();
    const modal = await openListRowsSource(page);
    const dropdown = modal.locator(".integration-dropdown");
    await expect(
      dropdown.locator(".dropdown__selected-placeholder")
    ).toHaveText("Choose connection...");
    await modal.getByRole("button", { name: "Create", exact: true }).click();
    await expect(
      modal.getByText("This field is required.", { exact: true })
    ).toBeVisible();
    await dropdown.locator(".dropdown__selected").click();
    for (const integration of [first, second]) {
      await expect(
        page
          .locator(".select__item:visible")
          .getByText(integration.name, { exact: true })
      ).toBeVisible();
    }
  });

  for (const ambiguous of [false, true]) {
    test(`a new action ${ambiguous ? "leaves ambiguous shared connections empty" : "preselects and uses the shared connection"}`, async ({
      page,
      context,
      workspacePage,
      builderPagePage,
    }) => {
      const { user, workspace } = workspacePage;
      const integration = await createWorkspaceLocalBaserowIntegration(workspace);
      if (ambiguous) {
        await createWorkspaceLocalBaserowIntegration(
          workspace,
          "Another shared connection"
        );
      }
      const database = await createDatabase(user, "Action results", workspace);
      const table = await createTable(user, "Created rows", database, [["Name"]]);
      await createBuilderElement(builderPagePage.builderPage, "button", {
        value: "'Create shared row'",
      });
      await builderPagePage.goto();
      const { action, events } = await addCreateRowAction(page, builderPagePage);
      const dropdown = events.locator(".integration-dropdown");
      expect(action.service.integration_id).toBe(
        ambiguous ? null : integration.id
      );
      if (ambiguous) {
        await expect(
          dropdown.locator(".dropdown__selected-placeholder")
        ).toBeVisible();
        return;
      }
      await expect(dropdown.locator(".dropdown__selected-text")).toHaveText(
        integration.name
      );
      const fields = await getFieldsForTable(user, table);
      // Configure the payload using the connection returned by action creation.
      await getClient(user).patch(`builder/workflow_action/${action.id}/`, {
        service: {
          type: action.service.type,
          integration_id: action.service.integration_id,
          table_id: table.id,
          field_mappings: [
            {
              field_id: fields[0].id,
              value: "'Created through shared connection'",
              enabled: true,
            },
          ],
        },
      });
      const { data: grant } = await getClient(user).post(
        `builder/preview/${builderPagePage.builder.id}/grant/`,
        { path: builderPagePage.builderPage.path }
      );
      const preview = await context.newPage();
      await preview.goto(grant.url);
      const dispatched = preview.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          response.url().endsWith(`/${action.id}/dispatch/`)
      );
      await preview.getByRole("button", { name: "Create shared row" }).click();
      const response = await dispatched;
      expect(response.status(), await response.text()).toBe(200);
      await expect.poll(() => listRows(user, table)).toEqual([
        expect.objectContaining({ Name: "Created through shared connection" }),
      ]);
    });
  }
});
