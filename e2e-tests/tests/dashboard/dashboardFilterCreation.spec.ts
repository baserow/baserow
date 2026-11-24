import type { Locator, Page } from "@playwright/test";
import { getClient } from "../../client";
import { createDatabase } from "../../fixtures/database/database";
import { getFieldsForTable } from "../../fixtures/database/field";
import { createTable } from "../../fixtures/database/table";
import type {
  Dashboard,
  DashboardWidget,
} from "../../fixtures/dashboard/dashboard";
import {
  createDashboard,
  createSummaryWidget,
  pauseWidgetRequest,
  updateDashboardDataSource,
  updateDashboardWidgetLayout,
} from "../../fixtures/dashboard/dashboard";
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

async function stackWidgets(dashboard: Dashboard, first: DashboardWidget) {
  const widgets = await Promise.all(
    [1, 2, 3].map((i) => createSummaryWidget(dashboard, `Existing widget ${i}`))
  );
  await updateDashboardWidgetLayout(dashboard, [
    {
      ...first,
      grid_x: 0,
      grid_y: 0,
      grid_width: 6,
    },
    ...widgets.map((widget, i) => ({
      id: widget.id,
      grid_x: 0,
      grid_y: first.grid_height + i * 6,
      grid_width: 6,
      grid_height: 6,
    })),
  ]);
}

test("reveals a filter added from a widget's context menu", async ({
  page,
  workspacePage,
}) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1800, height: 760 });
  const { workspace, user } = workspacePage;
  const database = await createDatabase(user, "Filter data", workspace);
  const table = await createTable(user, "Products", database, [
    ["Name"],
    ["Alpha"],
  ]);
  const [field] = await getFieldsForTable(user, table);
  const dashboard = await createDashboard(
    "Add a filter to a widget",
    workspace
  );
  const summary = await createSummaryWidget(dashboard, "Product count");
  if (!summary.data_source_id)
    throw new Error("Summary data source is missing");
  await updateDashboardDataSource(dashboard, summary.data_source_id, {
    table_id: table.id,
    field_id: field.id,
    aggregation_type: "count",
  });
  await stackWidgets(dashboard, summary);
  await page.goto(
    `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`
  );
  await page.getByText("Edit mode", { exact: true }).click();

  const creation = await pauseWidgetRequest(
    page,
    "POST",
    `/api/dashboard/${dashboard.id}/widgets/`
  );
  try {
    await page.getByTestId(`dashboard-widget-${summary.id}`).hover();
    const context = page.getByTestId(`dashboard-widget-context-${summary.id}`);
    await expect(context).toBeVisible();
    await context.click();
    const addFilter = page.getByRole("button", {
      name: "Add a filter for this widget",
    });
    await expect(addFilter).toBeVisible();
    await addFilter.click();
    const preview = page.getByRole("status", { name: "Adding Filter…" });
    await expect(preview).toBeInViewport({ ratio: 0.95 });
    const response = await creation.complete();
    expect(response.ok()).toBe(true);
    const filter = await response.json();
    expect(filter).toMatchObject({
      type: "text_filter",
      target_filters: [{ target_widget_id: summary.id, enabled: true }],
    });
    await expect(preview).toHaveCount(0);
    const card = page.getByTestId(`dashboard-widget-${filter.id}`);
    await expect(card).toBeInViewport({ ratio: 0.95 });
    await expect(card).toHaveClass(/dashboard-widget--selected/);
  } finally {
    creation.release();
    await page.unrouteAll({ behavior: "wait" });
  }
});

test("creates a widget from a filter and filters its displayed result", async ({
  page,
  workspacePage,
}) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1800, height: 760 });
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
  await stackWidgets(dashboard, filter);

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
  const creation = await pauseWidgetRequest(
    page,
    "POST",
    `/api/dashboard/${dashboard.id}/widgets/`
  );
  let widget: DashboardWidget;
  try {
    await page.getByRole("button", { name: "Summary", exact: true }).click();
    const preview = page.getByRole("status", { name: "Adding Summary…" });
    await expect(preview).toBeInViewport({ ratio: 0.95 });
    const response = await creation.complete();
    expect(response.ok()).toBe(true);
    widget = await response.json();
    await expect(preview).toHaveCount(0);
    await expect(
      page.getByTestId(`dashboard-widget-${widget.id}`)
    ).toBeInViewport({ ratio: 0.95 });
    await expect(filterCard).toHaveClass(/dashboard-widget--selected/);
  } finally {
    creation.release();
    await page.unrouteAll({ behavior: "wait" });
  }
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
