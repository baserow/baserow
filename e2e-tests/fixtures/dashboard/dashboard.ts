import { getClient } from "../../client";
import { Workspace } from "../workspace";

export type DashboardWidget = {
  id: number;
  grid_x: number;
  grid_y: number;
  grid_width: number;
  grid_height: number;
  data_source_id?: number;
};

/**
 * The sharing state of a dashboard as the application endpoints return it. The
 * password itself is write only and never comes back.
 */
export type DashboardSharing = {
  public: boolean;
  slug: string;
  public_has_password: boolean;
  show_logo: boolean;
};

export class Dashboard {
  constructor(
    public id: number,
    public name: string,
    public workspace: Workspace
  ) {}
}

export async function createDashboard(
  dashboardName: string,
  workspace: Workspace
): Promise<Dashboard> {
  const response: any = await getClient(workspace.user).post(
    `applications/workspace/${workspace.id}/`,
    {
      name: dashboardName,
      type: "dashboard",
      init_with_data: true,
    }
  );
  return new Dashboard(response.data.id, response.data.name, workspace);
}

export async function createSummaryWidget(
  dashboard: Dashboard,
  title: string
): Promise<DashboardWidget> {
  const response: any = await getClient(dashboard.workspace.user).post(
    `dashboard/${dashboard.id}/widgets/`,
    {
      title,
      type: "summary",
    }
  );
  return response.data;
}

export async function getDashboardWidgets(
  dashboard: Dashboard
): Promise<DashboardWidget[]> {
  const response: any = await getClient(dashboard.workspace.user).get(
    `dashboard/${dashboard.id}/widgets/`
  );
  return response.data;
}

export async function updateDashboardWidgetLayout(
  dashboard: Dashboard,
  widgets: DashboardWidget[]
): Promise<DashboardWidget[]> {
  const response: any = await getClient(dashboard.workspace.user).patch(
    `dashboard/${dashboard.id}/widgets/layout/`,
    { widgets }
  );
  return response.data;
}

/**
 * Configures the data source a widget was created with. A summary widget's
 * data source aggregates rows, so `{ table_id, field_id, aggregation_type }`
 * is enough to make it show a value. The dashboard's local Baserow
 * integration is attached to the data source on creation already.
 */
export async function updateDashboardDataSource(
  dashboard: Dashboard,
  dataSourceId: number,
  values: Record<string, unknown>
): Promise<any> {
  const response: any = await getClient(dashboard.workspace.user).patch(
    `dashboard/data-sources/${dataSourceId}/`,
    values
  );
  return response.data;
}

/**
 * Reads the sharing state of a dashboard, including the slug of its public
 * link, which the application endpoints return to its members only.
 */
export async function getDashboardSharing(
  dashboard: Dashboard
): Promise<DashboardSharing> {
  const response: any = await getClient(dashboard.workspace.user).get(
    `applications/${dashboard.id}/`
  );
  const {
    public: isPublic,
    slug,
    public_has_password,
    show_logo,
  } = response.data;
  return { public: isPublic, slug, public_has_password, show_logo };
}

/**
 * Changes the sharing state through the dedicated sharing endpoint, like the
 * share popover does: `{ public: true }` creates the link, `{ public_password }`
 * sets or (when empty) removes the password. Making the link private again
 * also removes the password.
 */
export async function updateDashboardSharing(
  dashboard: Dashboard,
  values: { public?: boolean; public_password?: string }
): Promise<DashboardSharing> {
  const response: any = await getClient(dashboard.workspace.user).patch(
    `dashboard/${dashboard.id}/sharing/`,
    values
  );
  const {
    public: isPublic,
    slug,
    public_has_password,
    show_logo,
  } = response.data;
  return { public: isPublic, slug, public_has_password, show_logo };
}
