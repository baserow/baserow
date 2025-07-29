# Baserow Documentation

Source: https://baserow.io/user-docs/assign-roles-to-teams-at-workspace-level

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Assign roles to teams at workspace level

Baserow Advanced and Enterprise plans come with advanced user management to boost data protection and privacy requirements. Role-based access control allows administrators to restrict access to data by assigning roles to users in workspaces, databases or tables.

> Role based permissions feature is available to users on [Baserow.io](http://Baserow.io) SaaS Advanced and Self-hosted Enterprise plans. To learn more about Baserow paid plans, [visit our pricing page](/pricing).

An admin can assign roles to Members and/or Teams at the workspace level and on individual databases and tables. This support article covers assigning roles to teams in bulk in a workspace. For assigning roles for other applications:

  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level).
  * [Assign roles to teams and members at database level](/user-docs/assign-roles-at-database-level).
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level).

## Overview

Baserow Teams are per Workspace and workspace members can be invited to teams. Teams allow admins to give or restrict permissions in bulk to multiple people.

A team will have a default role assigned at workspace level. When the team’s default role is set, every member of that team automatically gets assigned that role on the entire workspace and everything in it by default, unless exceptions are added to individual databases and tables.

> Member-specific roles will always override Team roles. To manage control, we recommend that you [assign Members “No Role” at the Workspace level](/user-docs/assign-roles-to-members-at-workspace-level) first, invite members to a team on workspace level, and then assign roles to the team on individual databases and tables as you see fit. Learn more about [the hierarchy of roles](/user-docs/role-based-access-control-rbac).

## Modify access or remove member from a team

To manage and assign roles to Members or Teams at the workspace level,

  1. From the dashboard, select a workspace you’d like to invite the new user(s) to
  2. Click the ‘**Members’** button under the workspace options. You can view the workspace members, teams and their workspace level roles on the **Members** page.

> There’s a hierarchy of permissions between a workspace, database, and table. You must first [invite a user to the workspace](/user-docs/manage-workspace-permissions) before inviting them as members of a specific team.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2c217b2b-58a7-461e-ae91-0eaab1bad1ef/Screenshot_2023-01-18_at_13.17.43.png)

A higher role has all of the permissions of the lower roles. Other users might inherit access to a Database or Table via their respective roles on the parent Database or Workspace.

Modify a team’s default role on the workspace level by selecting an option from the default role dropdown.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9644b0a2-fe03-4987-9b25-0ec8139e262d/Screenshot_2023-01-18_at_10.05.23.png)

## FAQ

### What happens when a member is removed?

Removing a member from a team is not undoable. If a user is removed, they will lose access to all team data. They will have to be re-added to the team to regain access.

### What is the difference between deleting a user and revoking access?

It’s important to understand the differences between removing users from a workspace, table, or database and [permanently deleting a user account from a self-hosted instance](/user-docs/admin-panel-users#permanently-delete-a-user).

Removing a member means taking away their access to a particular workspace, table, or database. However, their user account remains intact. This is applicable to both the SaaS hosted and self-hosted versions.

On the other hand, deleting a user is specific to the self-hosted version. Instance Admins can permanently delete a user from the entire self-hosted instance. This action completely removes the user’s account, and they lose access to all workspaces, tables, and databases.

## Related content

  * [Create and manage teams](/user-docs/create-and-manage-teams).
  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level).
  * [Assign roles to teams and members at database level](/user-docs/assign-roles-at-database-level).
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level).

