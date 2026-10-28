import { getClient } from "../client";
import { waitForInvitationToken } from "./mail";
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
    },
  );
  await getClient(member).post(
    `workspaces/invitations/${inviteResponse.data.id}/accept/`,
    { token: await waitForInvitationToken(member.email) },
  );
}
