import type { Page } from "@playwright/test";

import { getClient } from "../../client";
import {
  createDashboard,
  createSummaryWidget,
  updateDashboardDataSource,
  updateDashboardWidgetLayout,
} from "../../fixtures/dashboard/dashboard";
import type {
  Dashboard,
  DashboardWidget,
} from "../../fixtures/dashboard/dashboard";
import { createDatabase } from "../../fixtures/database/database";
import { getFieldsForTable } from "../../fixtures/database/field";
import { createTable } from "../../fixtures/database/table";
import type { Table } from "../../fixtures/database/table";
import { baserowConfig } from "../../playwright.config";
import { expect, test } from "../baserowTest";

/** Seed a row-count widget without spending browser steps on unrelated setup. */
async function createCountWidget(
  dashboard: Dashboard,
  title: string,
  table: Table,
  fieldId: number,
): Promise<DashboardWidget> {
  const widget = await createSummaryWidget(dashboard, title);
  if (!widget.data_source_id) throw new Error("Summary has no data source");
  await updateDashboardDataSource(dashboard, widget.data_source_id, {
    table_id: table.id,
    field_id: fieldId,
    aggregation_type: "count",
  });
  return widget;
}

function summary(page: Page, widget: DashboardWidget) {
  return page
    .getByTestId(`dashboard-widget-${widget.id}`)
    .locator(".dashboard-summary-widget__summary");
}

test("copies the first template while filtering multiple tables", async ({
  page,
  workspacePage,
}) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { workspace, user } = workspacePage;
  const database = await createDatabase(
    user,
    "Multi-table filter data",
    workspace,
  );
  const orders = await createTable(user, "Orders", database, [
    ["Customer", "Unrelated customer"],
    ["Acme", "Other"],
    ["Acme", "Other"],
    ["Beta", "Acme"],
  ]);
  const invoices = await createTable(user, "Invoices", database, [
    ["Contact"],
    ["Acme"],
    ["Beta"],
    ["Beta"],
  ]);
  const orderFields = await getFieldsForTable(user, orders);
  const invoiceFields = await getFieldsForTable(user, invoices);
  const customer = orderFields.find((field) => field.name === "Customer")!;
  const unrelated = orderFields.find(
    (field) => field.name === "Unrelated customer",
  )!;
  const contact = invoiceFields.find((field) => field.name === "Contact")!;
  const dashboard = await createDashboard("Multi-table filtering", workspace);
  const firstOrders = await createCountWidget(
    dashboard,
    "Orders by customer",
    orders,
    customer.id,
  );
  const laterOrders = await createCountWidget(
    dashboard,
    "Orders by another field",
    orders,
    customer.id,
  );
  const invoiceWidget = await createCountWidget(
    dashboard,
    "Invoices by contact",
    invoices,
    contact.id,
  );
  const additionalOrders = await createCountWidget(
    dashboard,
    "Additional orders",
    orders,
    customer.id,
  );
  const client = getClient(user);
  const { data: filter } = await client.post(`dashboard/${dashboard.id}/widgets/`, {
    type: "text_filter",
    title: "Customer search",
    placeholder: "Find a customer",
  });

  const link = (widget: DashboardWidget, fieldId: number) => ({
    target_widget_id: widget.id,
    enabled: true,
    empty_behavior: "apply_nothing",
    group: {
      filter_type: "AND",
      filter_groups: [],
      filters: [
        {
          id: `customer-${widget.id}`,
          field: fieldId,
          type: "contains",
          group: null,
          value: { formula: `get('widget_data.${filter.id}')`, mode: "simple" },
        },
      ],
    },
  });
  // Link order and newest id deliberately disagree with the displayed first model.
  await client.patch(`dashboard/widgets/${filter.id}/`, {
    target_filters: [
      link(laterOrders, unrelated.id),
      link(invoiceWidget, contact.id),
      link(firstOrders, customer.id),
    ],
  });
  await updateDashboardWidgetLayout(dashboard, [
    { id: filter.id, grid_x: 0, grid_y: 0, grid_width: 6, grid_height: 2 },
    ...[firstOrders, laterOrders, invoiceWidget, additionalOrders].map(
      (widget, index) => ({
        id: widget.id,
        grid_x: (index % 2) * 3,
        grid_y: 2 + Math.floor(index / 2) * 4,
        grid_width: 3,
        grid_height: 4,
      }),
    ),
  ]);

  await page.goto(
    `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`,
  );
  await expect(page.getByTestId("dashboard-widget-grid")).toBeVisible({
    timeout: 30_000,
  });
  await expect(summary(page, additionalOrders)).toHaveText("3");
  await page.getByText("Edit mode", { exact: true }).click();
  await page
    .getByTestId(`dashboard-widget-${filter.id}`)
    .locator(".control__label")
    .click();
  await expect(
    page.locator(".dashboard-widget-filter-target .item-card__name"),
  ).toHaveText([
    "Orders by customer",
    "Orders by another field",
    "Invoices by contact",
  ]);
  await page.getByRole("button", { name: "Add a widget", exact: true }).click();
  const association = page.waitForResponse((response) =>
    response.request().method() === "PATCH" &&
    response.url().endsWith(`/dashboard/widgets/${filter.id}/`),
  );
  await page.locator(".dropdown__items:visible .select__item").filter({
    has: page.getByText("Additional orders", { exact: true }),
  }).click();
  expect((await association).ok()).toBeTruthy();
  const conditions = page.locator(".modal__box").filter({
    has: page.getByRole("heading", {
      name: "Conditions for “Additional orders”",
      exact: true,
    }),
  });
  await expect(conditions).toBeVisible();
  await expect(
    conditions.locator(".filters__field .dropdown__selected-text"),
  ).toHaveText("Customer");
  await expect(
    conditions.locator(".filters__condition-item--misconfigured"),
  ).toHaveCount(0);
  await conditions.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Done editing", exact: true }).click();
  const filterInput = page
    .getByTestId(`dashboard-widget-${filter.id}`)
    .getByRole("textbox");
  await filterInput.fill("Acme");

  // These different values distinguish table-specific rules and the wrong template.
  await expect(summary(page, firstOrders)).toHaveText("2");
  await expect(summary(page, laterOrders)).toHaveText("1");
  await expect(summary(page, invoiceWidget)).toHaveText("1");
  await expect(summary(page, additionalOrders)).toHaveText("2");
  await filterInput.fill("Beta");
  await expect(summary(page, firstOrders)).toHaveText("1");
  await expect(summary(page, invoiceWidget)).toHaveText("2");
  await expect(summary(page, additionalOrders)).toHaveText("1");
});
