# Baserow Documentation

Source: https://baserow.io/user-docs/assign-roles-to-members-at-workspace-level

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Assign roles to members at workspace level

Baserow Advanced and Enterprise plans come with advanced user management to boost data protection and privacy requirements. Role-based access control allows administrators to restrict access to data by assigning roles to users in workspaces, databases or tables.

> Role based permissions feature is available to users on [Baserow.io](http://Baserow.io) SaaS Advanced, Self-hosted Advanced, and Self-hosted Enterprise plans. To learn more about Baserow paid plans, [visit our pricing page](/pricing).

## Overview

An admin can assign roles to Members and/or Teams at the workspace level and on individual databases and tables. This support article covers assigning roles to members individually in a workspace. For assigning roles for other applications:

  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level).
  * [Assign roles to teams and members at database level](/user-docs/assign-roles-at-database-level).
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level).

Members are assigned individual user roles when they are invited to a workspace. The role assigned to a member will be their default role at workspace level.

After you add a workspace member and they accept the invite, they will have this workspace level default role on everything in the workspace. The member will have access to all databases and tables in the workspace at the role level assigned to them unless you add an exception on specific tables or databases.

To manage and assign roles to Members at the workspace level,

  1. From the dashboard, select a workspace you’d like to invite the new user(s) to
  2. Click the **Members** button under the workspace options. You can view the workspace members, teams and their workspace level roles on the **Members** page.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2c217b2b-58a7-461e-ae91-0eaab1bad1ef/Screenshot_2023-01-18_at_13.17.43.png)

## Assign roles at workspace level

Admins can invite new members to a workspace and assign default roles that members should have upon joining the workspace. When new members are invited to a workspace, they will have access to the entire workspace at the default role assigned to them.

Admins can further restrict access by adding members to a Team and assigning access to the team. Members within the team will have access to workspaces, databases and tables at the role level assigned to the team.

Member roles take priority over [team](/user-docs/create-and-manage-teams) roles. A workspace member who is explicitly assigned a role on a workspace, database or table will get that exact role, regardless of the default roles of the teams to which they belong.

> To assign the Team default role to members of a specific team, set the default roles of all Members to “No Role” at the workspace level. If you set the Members’ default role at the workspace level to anything other than “No Role,” this will override and ignore their team default roles in the entire workspace.

## FAQ

### What happens when a member is removed?

Removing member access from a workspace is not undoable. If a user is removed, they will lose access to all workspace data. They will have to be re-added to the workspace to regain access.

### What is the difference between deleting a user and removing a member?

It’s important to understand the differences between removing a member from a workspace, table, or database and [permanently deleting a user account from a self-hosted instance](/user-docs/admin-panel-users#permanently-delete-a-user).

Removing a member means taking away their access to a particular workspace, table, or database. However, their user account remains intact. This is applicable to both the SaaS hosted and self-hosted versions.

On the other hand, deleting a user is specific to the self-hosted version. Instance Admins can permanently delete a user from the entire self-hosted instance. This action completely removes the user’s account, and they lose access to all workspaces, tables, and databases.

## Related content

  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level).
  * [Assign roles to teams and members at database level](/user-docs/assign-roles-at-database-level).
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level).
  * [Remove a user from a workspace](/user-docs/remove-a-user-from-a-workspace).

