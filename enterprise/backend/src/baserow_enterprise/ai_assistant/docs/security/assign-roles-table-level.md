# Baserow Documentation

Source: https://baserow.io/user-docs/assign-roles-at-table-level

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Assign roles at table level

Baserow Advanced and Enterprise plans come with advanced user management to boost data protection and privacy requirements. Role-based access control allows administrators to restrict access to data by assigning roles to users in workspaces, databases or tables.

> Role based permissions feature is available to users on [Baserow.io](http://Baserow.io) SaaS Advanced and Self-hosted Enterprise plans. To learn more about Baserow paid plans, [visit our pricing page](/pricing).

An admin can assign roles to Members and/or Teams at the workspace level and on individual databases and tables. This support article covers assigning roles to members individually and teams in bulk on an individual table. For assigning roles for other applications:

  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level)
  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level)
  * [Assign roles to teams and members at database level](/user-docs/assign-roles-at-database-level)

> Table roles will override workspace and database roles. This means that a member who is explicitly assigned a role on a table will get that exact role, regardless of any workspace and database roles. Learn more about [the hierarchy of roles](/user-docs/role-based-access-control-rbac).

## Manage roles for a specific table

Members with Admin roles at the table level can invite members to a table and assign roles to users.

> There’s a hierarchy of permissions between a workspace, database, and table. You must first [invite a user to the workspace](/user-docs/manage-workspace-permissions) before inviting them as members of a specific table.

To manage and assign roles to members or teams on an individual table,

  1. Within the database, select a table you’d like to invite the member to

  2. Click on the vertical ellipsis beside the table then click “**Manage members”** from the options dropdown in the sidebar.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/aba38933-be70-4f6c-bc80-5fa6608072c8/Untitled.png)

  3. Click **Select Members** on the modal to add roles for individual users and teams on this specific table.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/281652e6-111b-41de-891b-9675f75ab52e/Screenshot_2023-01-18_at_18.41.51.png)

  4. Search and select the members and/or teams you want to invite to the table using the tick box or the **Select all** button. The modal will indicate the total number of members selected. Learn how to [invite members to a workspace](/user-docs/manage-workspace-permissions) or how to [create and add users to teams](/user-docs/create-and-manage-teams).

  5. Choose the member’s and/or team’s default role for the specific table. Click the default role drop-down to scroll through the list of permissions.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1f1c4988-f9aa-46fe-842d-3a21586deb84/Screenshot_2023-01-18_at_18.18.19.png)

  6. Then click the **Invite members/teams** button. The Invite button will indicate the total number selected.

## View users’ access in a table

You can see invited users that have access to the table and roles for the specific table on the **modal**.

> Note ⚠️: Other users might inherit access via their respective roles on the parent database or workspace. However, you won’t see users or teams who have inherited permission to see or have access to this table from their parent database or workspace here. You only see exceptions to the workspace or database defaults.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7b06690b-d100-4bd4-8cbd-9271edae03bf/Screenshot_2023-01-18_at_19.10.49.png)

The list of table members is not an exhaustive list of everyone who has a role on that table. It contains only the list of specific role assignments on that specific table. For example, if User A has a workspace level role of Admin, they will be an Admin on all databases and tables, if there are no exceptions added. However, the ‘Table-> Manage Members’ modal will now show User A as an Admin on that table.

## Modify access or remove member from a table

Admins can remove access from the **Manage members** modal.

To remove a member and/or team access from a table,

  1. Within the database, select a table you’d like to invite the member to

  2. Click on the vertical ellipsis beside the table then click “**Manage members”** from the options dropdown in the sidebar.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/54b4c7e5-9a6d-47e1-9c90-411df08d321d/Untitled.png)

  3. Remove or modify an existing member’s and/or team’s default role on a specific table by selecting an option from the default role dropdown.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b7df9cdc-111b-46c6-a56b-a7e99e7a4307/Screenshot_2023-01-18_at_19.18.04.png)

## FAQ

### What happens when a member is removed?

Removing member access from a table is not undoable. If a user is removed, they will lose access to all table data. They will have to be re-added to the table to regain access.

### What is the difference between deleting a user and revoking table access?

It’s important to understand the differences between removing users from a workspace, table, or database and [permanently deleting a user account from a self-hosted instance](/user-docs/admin-panel-users#permanently-delete-a-user).

Removing a member means taking away their access to a particular workspace, table, or database. However, their user account remains intact. This is applicable to both the SaaS hosted and self-hosted versions.

On the other hand, deleting a user is specific to the self-hosted version. Instance Admins can permanently delete a user from the entire self-hosted instance. This action completely removes the user’s account, and they lose access to all workspaces, tables, and databases.

## Related content

  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level).
  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level).
  * [Assign roles at database level](/user-docs/assign-roles-at-database-level).

