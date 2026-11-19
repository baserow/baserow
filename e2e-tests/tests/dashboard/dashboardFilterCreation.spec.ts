import type { Locator, Page } from "@playwright/test";
import { getClient } from "../../client";
import { createDatabase } from "../../fixtures/database/database";
import { createTable } from "../../fixtures/database/table";
import { createDashboard } from "../../fixtures/dashboard/dashboard";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

/** Select a table through the real widget data settings, not its source API. */
async function chooseTable(page: Page, modal: Locator, name: string) {
  const table = modal.locator(".control").filter({
    has: page.locator(".control__label", { hasText: /^Table$/ }),
  });
  await table.locator(".dropdown").click();
  await page.locator(".select__item:visible").filter({ hasText: name }).click();
}

test("creates a widget from a filter and filters its displayed result", async ({
  page,
  workspacePage,
}) => {
  test.setTimeout(90_000);
  const { workspace, user } = workspacePage;
  const database = await createDatabase(user, "Filter creation data", workspace);
  const table = await createTable(user, "Products", database, [
    ["Name"],
    ["Alpha"],
    ["Beta"],
    ["Alpha"],
  ]);
  const dashboard = await createDashboard("Guided filter creation", workspace);
  const client = getClient(user);
  const { data: filter } = await client.post(
    `dashboard/${dashboard.id}/widgets/`,
    { type: "text_filter", title: "Product search" }
  );

  await page.goto(
    `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`
  );
  await expect(page.getByTestId("dashboard-widget-grid")).toHaveClass(
    /dashboard-widget-grid--layout-ready/
  );
  await page.getByText("Edit mode", { exact: true }).click();
  const filterCard = page.getByTestId(`dashboard-widget-${filter.id}`);
  await filterCard.click();
  await page.getByRole("button", { name: "Add a widget", exact: true }).click();
  await page.getByRole("button", { name: "Create widget", exact: true }).click();
  const creationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/dashboard/${dashboard.id}/widgets/`)
  );
  await page.getByRole("button", { name: "Summary", exact: true }).click();
  const widget = await (await creationResponse).json();
  const configuration = page.locator(".modal__box").filter({
    has: page.getByRole("heading", { name: "Configure new widget", exact: true }),
  });
  await expect(configuration).toBeVisible();
  await configuration
    .getByPlaceholder("Title", { exact: true })
    .fill("Product count");
  await chooseTable(page, configuration, table.name);
  await expect(
    configuration.locator(".dropdown__selected-text", { hasText: /^Count$/ })
  ).toBeVisible();
  // The modal uses inline refinements rather than an offscreen floating context.
  await expect(
    configuration.locator(".service-form__condition-form-tab")
  ).toBeVisible();
  await expect(
    configuration.locator(".service-form__filter-buttons")
  ).toHaveCount(0);
  await configuration
    .getByRole("button", { name: "Add to filter", exact: true })
    .click();

  const conditions = page.locator(".modal__box").filter({
    has: page.getByRole("heading", { name: /Conditions for.*Product count/ }),
  });
  await expect(conditions).toBeVisible();
  await expect(conditions).toContainText("Product search");
  await expect(configuration).toBeHidden();
  await expect(
    page.locator(".dashboard-sidebar .dashboard-widget-filter-target")
  ).toHaveCount(1);
  const savedConditions = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(`/dashboard/widgets/${filter.id}/`) &&
      response.request().postDataJSON().target_filters?.some(
        (link: any) =>
          link.target_widget_id === widget.id && link.group.filters.length === 1
      )
  );
  await conditions
    .locator(".dashboard-widget-filters__case")
    .first()
    .getByRole("button", { name: "Add filter", exact: true })
    .click();
  expect((await savedConditions).ok()).toBe(true);
  await conditions
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Done editing", exact: true })
    .click();

  const result = page
    .getByTestId(`dashboard-widget-${widget.id}`)
    .locator(".dashboard-summary-widget__summary");
  await expect(result).toHaveText("3");
  const input = filterCard.locator("input");
  await input.fill("Alpha");
  await expect(result).toHaveText("2");
  await input.fill("Beta");
  await expect(result).toHaveText("1");
  await input.fill("");
  await expect(result).toHaveText("3");
});
