import { baserowConfig } from "../../playwright.config";
import { createDatabase } from "../database/database";
import { createField } from "../database/field";
import { createRows } from "../database/rows";
import { createTable } from "../database/table";
import { Workspace } from "../workspace";
import {
  createDashboard,
  createSummaryWidget,
  Dashboard,
  DashboardWidget,
  updateDashboardDataSource,
} from "./dashboard";

export const SUMMARY_WIDGET_TITLE = "Total amount";
/** What the summary widget shows: the sum of the seeded amounts. */
export const SUMMARY_WIDGET_VALUE = "30";

export type DashboardWithSummary = {
  dashboard: Dashboard;
  widget: DashboardWidget;
};

/**
 * A dashboard with one summary widget that has something to show: the sum of a
 * number field over a small table in the same workspace. Nothing is shared yet,
 * sharing is what the tests using this do, through the UI or the sharing
 * endpoint.
 */
export async function createDashboardWithSummary(
  workspace: Workspace,
  name = "Shared dashboard"
): Promise<DashboardWithSummary> {
  const { user } = workspace;
  const database = await createDatabase(user, `${name} data`, workspace);
  // A header row only, so the table starts without the example rows.
  const table = await createTable(user, "Amounts", database, [["Name"]]);
  const amount = await createField(
    user,
    "Amount",
    "number",
    { number_decimal_places: 0 },
    table
  );
  await createRows(user, table, [
    { Name: "First", Amount: 10 },
    { Name: "Second", Amount: 20 },
  ]);

  const dashboard = await createDashboard(name, workspace);
  const widget = await createSummaryWidget(dashboard, SUMMARY_WIDGET_TITLE);
  if (!widget.data_source_id) {
    throw new Error("The summary widget was created without a data source");
  }
  await updateDashboardDataSource(dashboard, widget.data_source_id, {
    table_id: table.id,
    field_id: amount.id,
    aggregation_type: "sum",
  });

  return { dashboard, widget };
}

export function dashboardEditorUrl(dashboard: Dashboard): string {
  return `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`;
}

export function publicDashboardUrl(slug: string): string {
  return `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/public/dashboard/${slug}`;
}
