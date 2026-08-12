import { getClient } from "../../client";
import { Workspace } from "../workspace";

export type DashboardWidget = {
  id: number;
  grid_x: number;
  grid_y: number;
  grid_width: number;
  grid_height: number;
};

export class Dashboard {
  constructor(
    public id: number,
    public name: string,
    public workspace: Workspace,
  ) {}
}

export async function createDashboard(
  dashboardName: string,
  workspace: Workspace,
): Promise<Dashboard> {
  const response: any = await getClient(workspace.user).post(
    `applications/workspace/${workspace.id}/`,
    {
      name: dashboardName,
      type: "dashboard",
    },
  );
  return new Dashboard(response.data.id, response.data.name, workspace);
}

export async function createSummaryWidget(
  dashboard: Dashboard,
  title: string,
): Promise<DashboardWidget> {
  const response: any = await getClient(dashboard.workspace.user).post(
    `dashboard/${dashboard.id}/widgets/`,
    {
      title,
      type: "summary",
    },
  );
  return response.data;
}

export async function getDashboardWidgets(
  dashboard: Dashboard,
): Promise<DashboardWidget[]> {
  const response: any = await getClient(dashboard.workspace.user).get(
    `dashboard/${dashboard.id}/widgets/`,
  );
  return response.data;
}

export async function updateDashboardWidgetLayout(
  dashboard: Dashboard,
  widgets: DashboardWidget[],
): Promise<DashboardWidget[]> {
  const response: any = await getClient(dashboard.workspace.user).patch(
    `dashboard/${dashboard.id}/widgets/layout/`,
    { widgets },
  );
  return response.data;
}
