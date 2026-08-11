import { getClient } from "../client";
import { User } from "./user";
import { baserowConfig } from "../playwright.config";

export class Workspace {
  constructor(public id: number, public name: string, public user: User) {}
}
export async function createWorkspace(
  user: User,
  name: String = "Default workspace"
): Promise<Workspace> {
  const response: any = await getClient(user).post("workspaces/", { name });
  const workspaceData = response.data;
  return new Workspace(workspaceData.id, workspaceData.name, user);
}

/**
 * Adds an existing user to a workspace. There is no endpoint that adds a
 * member outright, so this invites them and accepts on their behalf.
 */
export async function addUserToWorkspace(
  inviter: User,
  workspace: Workspace,
  invitee: User,
  permissions: "ADMIN" | "MEMBER" = "MEMBER"
): Promise<void> {
  const invitation: any = await getClient(inviter).post(
    `workspaces/invitations/workspace/${workspace.id}/`,
    {
      email: invitee.email,
      permissions,
      base_url: `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/workspace-invitation`,
    }
  );
  await getClient(invitee).post(
    `workspaces/invitations/${invitation.data.id}/accept/`
  );
}

export async function getUsersFirstWorkspace(user: User): Promise<Workspace> {
  const response: any = await getClient(user).get("workspaces/", {});
  let firstWorkspaceData = response.data[0];
  return new Workspace(firstWorkspaceData.id, firstWorkspaceData.name, user);
}
