import { getClient } from "../client";
import { User } from "./user";

export class Workspace {
  constructor(public id: number, public name: string, public user: User) {}
}

export class WorkspaceInvitation {
  constructor(public id: number, public workspace_id: number, public email: string, public permissions: string, public message: string) { }
}

export async function createWorkspace(
  user: User,
  name: String = "Default workspace"
): Promise<Workspace> {
  const response: any = await getClient(user).post("workspaces/", { name });
  const workspaceData = response.data;
  return new Workspace(workspaceData.id, workspaceData.name, user);
}

export async function getUsersFirstWorkspace(user: User): Promise<Workspace> {
  const response: any = await getClient(user).get("workspaces/", {});
  let firstWorkspaceData = response.data[0];
  return new Workspace(firstWorkspaceData.id, firstWorkspaceData.name, user);
}

export async function createWorkspaceInvitation(from_user: User, workspace: Workspace, email: string, permissions: string, message: string, base_url: string): Promise<WorkspaceInvitation> {
  const response = await getClient(from_user).post(`workspaces/invitations/workspace/${workspace.id}/`, { email, permissions, message, base_url })
  const invitationData = response.data
  return new WorkspaceInvitation(invitationData.id, invitationData.workspace, invitationData.email, invitationData.permissions, invitationData.message)
}

export async function acceptWorkspaceInvitation(user: User, invitation: WorkspaceInvitation): Promise<void> {
  const response = await getClient(user).post(`/workspaces/invitations/${invitation.id}/accept/`)
}
