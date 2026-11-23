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
  const database = await createDatabase(
    user,
    "Filter creation data",
    workspace
  );
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
  await page
    .getByRole("button", { name: "Create widget", exact: true })
    .click();
  const creationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/dashboard/${dashboard.id}/widgets/`)
  );
  await page.getByRole("button", { name: "Summary", exact: true }).click();
  const widget = await (await creationResponse).json();
  const modal = page.locator(".modal__box").filter({
    has: page.getByRole("heading", {
      name: /^Add a widget to .Product search.$/,
    }),
  });
  await expect(modal).toBeVisible();
  await modal.getByPlaceholder("Title", { exact: true }).fill("Product count");
  // Choosing a table links the widget to the filter, starting with one
  // condition on the table's first field.
  const seededCondition = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(`/dashboard/widgets/${filter.id}/`) &&
      response
        .request()
        .postDataJSON()
        .target_filters?.some(
          (link: any) =>
            link.target_widget_id === widget.id &&
            link.group.filters.length === 1
        )
  );
  await chooseTable(page, modal, table.name);
  expect((await seededCondition).ok()).toBe(true);
  await expect(
    modal.locator(".dropdown__selected-text", { hasText: /^Count$/ })
  ).toBeVisible();
  // The filter's conditions replace the widget's own refinements here.
  await expect(modal.locator(".service-form__filter-buttons")).toHaveCount(0);
  await expect(modal.locator(".service-form__condition-form-tab")).toHaveCount(
    0
  );

  const conditions = modal.getByRole("button", {
    name: /How .Product search. filters it/,
  });
  await expect(conditions).toContainText("1 condition");
  await conditions.click();
  await expect(conditions).toHaveAttribute("aria-expanded", "true");
  await expect(
    modal.locator(".dashboard-widget-filters__case").first()
  ).toContainText("Name");
  await modal.getByRole("button", { name: "Add widget", exact: true }).click();
  await expect(modal).toBeHidden();
  await expect(
    page.locator(".dashboard-sidebar .dashboard-widget-filter-target")
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Done editing", exact: true }).click();

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
