# Baserow Documentation

Source: https://baserow.io/user-docs/role-based-access-control-rbac

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Understanding role hierarchy

Baserow Role Based Permissions give organizations more flexibility around permissions that can be granted to users. Role-based access control allows admins to provide users with varying levels of access based on their roles.

This support article describes the various actions available to users at each role level.

> Assigning role-based permission is only available to users with a Self-hosted Enterprise License or on Cloud Hosted Advanced Plan on [Baserow.io](https://Baserow.io).

## Overview

Teams can better manage complex access protocols using role-based permissions to monitor who should have access to resources and data as well as what they can do with it.

The right role determines what actions users can or cannot take in the workspaces, databases, and tables to which they have access. You can assign members one of the following roles – **Admin, Builder, Editor, Commenter, Viewer, No Access** or **No Role.** For an overview of each role, [please refer to this support article](/user-docs/set-permission-level).

An admin can assign roles to Members and/or Teams at the workspace level and on individual databases and tables. For example, an admin can invite a user to a Baserow workspace while restricting their access to just viewing tables and databases, by assigning the user a “Viewer” role. Learn more about [assigning roles at Workspace, Database or Table levels](/user-docs/set-permission-level).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3c52c3a2-cb20-4bc9-a023-1bdf98c04288/Screenshot_2023-01-18_at_12.08.34.png)

For more information about how users and roles affect your billing, [see this support article](/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes).

## Hierarchy of roles at workspace, database, and table levels

Roles are hierarchical, which means that a higher role can perform all of the functions of a lower role. You can lower or raise the role of a user or team by assigning a role on a specific table or database.

When a user has varying roles across workspace, database and table levels, we pick the most specific roles first and ignore any database or workspace level roles.

  * Member roles take priority over Team roles. A workspace member who is explicitly assigned a role on a workspace, database or table will get that exact role, regardless of the default roles of the teams to which they belong.
  * Database roles will override Workspace roles. A role assigned to a team or a user on a Database will override that team or user’s default Workspace role.
  * Table roles will override Workspace and Database roles. A role assigned to a team or a user on a Table will override that team or user’s database or workspace role.

> Member-specific roles will always override Team roles. To manage control, we recommend that you assign Members “No Role” at the Workspace level first, [invite members to a team](/user-docs/assign-roles-to-teams-at-workspace-level) on workspace level, and then assign roles to the team on individual databases and tables as you see fit.

## Troubleshooting

### What is an ideal best practice to fully utilize role based permissions?

A higher role has all of the permissions of the lower roles. Other users might inherit access to a Database or Table via their respective roles on the parent Database or Workspace. For security, we recommend the following general workflow:

  1. Invite users to a workspace with “No Role” by default.
  2. To restrict access to a specific table or database and not the entire workspace, create a team and set the team’s default role as “No access”.
  3. Add workspace members to the team.
  4. Assign roles on specific tables and databases to the team.

### How is a user’s role decided?

When a user is in teams and has roles assigned to a workspace, but also on individual databases or tables, the following rules apply to decide which role to go with:

  * A role assigned to a user or team on a specific table always overrides a role on its database or workspace
  * A role assigned to a user or team on a specific database always overrides a role on its workspace
  * User roles will always override team roles on that same thing. That is, a user who has both an individual role on a table and also is a member of a team with a role on that table, the user’s individual role will always be picked.

For example, if a user has the following individual user permissions: Admin role at the workspace level, Builder role in database A, and Viewer role in table A. Also, the user is a member of a team with the following team permissions: Viewer role at the workspace level and Admin role on table A. This user’s active role for accessing table A is as a Viewer - the individual user role assigned to table A - which means they can only view the rows in the table and make no edits.

[Learn more about Baserow pricing and who is considered a “user” for billing purposes.](/user-docs/subscriptions-overview)

### Why grant access to users at a lower level?

Granting access to users at a lower level, such as individual databases instead of the entire workspace, can provide added security and control over sensitive information. While workspace members generally have access to all databases within the workspace, inviting users to specific databases allows you to restrict their access to sensitive or confidential data. This approach helps ensure that only authorized individuals can view the contents of certain databases.

For example, if there are two teams in a workspace: Sales Team A and Audit Team. While it is a good idea to have two separate databases for each team in a single workspace, it may not be a good idea for each team to be able to access each other’s databases. [Create a team and grant appropriate access to the team](/user-docs/assign-roles-to-teams-at-workspace-level), or assign key roles to members at the database level rather than at the workspace level.

## Related content

  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level)
  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level)
  * [Assign roles to teams and members at database level](/user-docs/assign-roles-at-database-level)
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level)

