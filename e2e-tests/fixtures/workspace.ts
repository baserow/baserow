import { getClient } from "../client";
import { User } from "./user";

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

export async function getUsersFirstWorkspace(user: User): Promise<Workspace> {
  const response: any = await getClient(user).get("workspaces/", {});
  let firstWorkspaceData = response.data[0];
  return new Workspace(firstWorkspaceData.id, firstWorkspaceData.name, user);
}
