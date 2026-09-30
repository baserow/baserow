import { getClient } from "../client";
import { User } from "./user";
import { Workspace } from "./workspace";

export type RoleScopeType =
  | "workspace"
  | "application"
  | "database_table"
  | "database_view";

export type RoleAssignment = {
  scopeType: RoleScopeType;
  scopeId: number;
  /** A role uid such as "EDITOR" or "NO_ACCESS", or null to remove the role. */
  role: string | null;
};

async function getMemberUserId(
  admin: User,
  workspace: Workspace,
  member: User,
): Promise<number> {
  const response: any = await getClient(admin).get(
    `workspaces/users/workspace/${workspace.id}/`,
  );
  const workspaceUser = response.data.find(
    (candidate: any) =>
      candidate.email.toLowerCase() === member.email.toLowerCase(),
  );
  if (workspaceUser === undefined) {
    throw new Error(`${member.email} is not in workspace ${workspace.id}.`);
  }
  return workspaceUser.user_id;
}

/** Assigns the member's RBAC roles in one batch; needs an enterprise license. */
export async function assignRoles(
  admin: User,
  workspace: Workspace,
  member: User,
  assignments: RoleAssignment[],
): Promise<void> {
  const memberId = await getMemberUserId(admin, workspace, member);
  await getClient(admin).post(`role/${workspace.id}/batch/`, {
    items: assignments.map(({ scopeType, scopeId, role }) => ({
      subject_id: memberId,
      subject_type: "auth.User",
      scope_type: scopeType,
      scope_id: scopeId,
      role,
    })),
  });
}
