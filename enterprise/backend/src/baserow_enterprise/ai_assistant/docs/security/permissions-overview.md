# Baserow Documentation

Source: https://baserow.io/user-docs/permissions-overview

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Permissions overview

Permissions allow administrators to restrict access to data by assigning roles to users in workspaces, databases or tables.

When sharing your data, it’s important to be cautious. Permissions can be assigned to users by workspace admins. When you [invite users to a workspace](/user-docs/manage-workspace-permissions), database or table, you’ll be prompted to choose the initial setup.

## Roles on Free and Premium plans

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e43858ec29b82ded3aba2b7d37e623d06b698bb7.webp)

In Baserow Free and Premium plans, users can be assigned the following default roles within a workspace:

  * **Workspace admins** : are in charge of the workspace’s management.
  * **Members** : are people within your team who use Baserow.

| Members | Admins  
---|---|---  
Fully configure applications | ✓ | ✓  
Edit applications | ✓ | ✓  
Manage collaborators | 𐄂 | ✓  
Rename workspace | 𐄂 | ✓  
Delete workspace | 𐄂 | ✓  
View trash in workspace | 𐄂 | ✓  
  
Baserow Advanced and Enterprise plans come with advanced user management to boost data protection and privacy requirements.

## Role-based permission on Advanced and Enterprise plans

> Role-based access control feature is only available to users on [Baserow.io](http://Baserow.io) Cloud Advanced and Self-hosted Enterprise plans. To learn more about Baserow paid plans, [visit our pricing page](/pricing).

Roles permit users to execute a set of operations in a Workspace, Database or Table. You can assign a team or a user one of the following roles – **Admin, Builder, Editor, Commenter, and Viewer.** The role level is initially set when the user is invited or the team is created but can be changed later.

> ⚠️ **NOTE** : If your Advanced plan or Enterprise license runs out or you unregister it, role based permissions will be inactive _immediately_. Every user will automatically be assigned a Builder role for everything in the workspace, including databases and tables.

Here is an overview of what each role grants in a Workspace, Database or Table, in order of their hierarchy:

  1. **Admin:** Can do everything a Builder can do, including inviting workspace members, controlling their permissions and managing subscriptions of a workspace.

  2. **Builder:** Can do everything an Editor can do, plus creating, and editing fields, tables, views and databases.

  3. **Editor:** Can do everything a Commenter can do, plus editing cell values and creating and deleting rows in tables.

  4. **Commenter:** Can do everything a Viewer can do, including reading and writing row comments.

  5. **Viewer:** Can only read databases, tables, views, fields, cells, comments, and trash.

  6. **No Role** : Only users at the Workspace level can be assigned the No Role permission.

When a **No Role** permission is assigned, the user will get their default workspace-level role from their highest team workspace-level role for the teams they are in. If they are not in any teams, their workspace-level role will default to “No Access”.

  7. **No Access** : A user with No Access permission cannot do or see anything in the workspace, database or table to which this role is assigned.

For more specific details on each role level, please [refer to this support article](/user-docs/role-based-access-control-rbac).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9807d1ea-148a-4be0-9eae-0d23bcf8dbb3/image.png)

## Related content

  * [Understand role hierarchy](/user-docs/role-based-access-control-rbac).
  * [Role levels in Baserow](/user-docs/set-permission-level).
  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level).
  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level).
  * [Assign roles at database level](/user-docs/assign-roles-at-database-level).
  * [Assign roles at table level](/user-docs/assign-roles-at-table-level).

