import { getClient } from "../client";
import type { Workspace } from "./workspace";

/** Create a Local Baserow integration owned by the workspace shared application. */
export async function createWorkspaceLocalBaserowIntegration(
  workspace: Workspace,
  name = "Shared Local Baserow"
): Promise<{ id: number; name: string; application_id: number }> {
  const client = getClient(workspace.user);
  const { data: applications } = await client.get(
    `applications/workspace/${workspace.id}/`
  );
  const shared = applications.find(
    (application: { type: string }) => application.type === "shared"
  );
  if (!shared) {
    throw new Error("Workspace has no shared application");
  }
  const { data } = await client.post(`application/${shared.id}/integrations/`, {
    type: "local_baserow",
    name,
  });
  return data;
}
