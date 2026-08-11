import { getClient } from "../client";
import { User } from "./user";
import { Workspace } from "./workspace";

export async function addWorkspaceMember(
  owner: User,
  workspace: Workspace,
  member: User,
  permissions: string,
): Promise<void> {
  const inviteResponse: any = await getClient(owner).post(
    `workspaces/invitations/workspace/${workspace.id}/`,
    {
      email: member.email,
      permissions,
      base_url: "http://localhost",
    },
  );
  await getClient(member).post(
    `workspaces/invitations/${inviteResponse.data.id}/accept/`,
  );
}
