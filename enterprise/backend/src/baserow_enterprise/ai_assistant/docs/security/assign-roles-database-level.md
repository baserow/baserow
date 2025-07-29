# Baserow Documentation

Source: https://baserow.io/user-docs/assign-roles-at-database-level

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Assign roles at database level

Baserow Advanced and Enterprise plans come with advanced user management to boost data protection and privacy requirements. Role-based access control allows administrators to restrict access to data by assigning roles to users in workspaces, databases or tables.

> Role based permissions feature is available to users on [Baserow.io](http://Baserow.io) SaaS Advanced and Self-hosted Enterprise plans. To learn more about Baserow paid plans, [visit our pricing page](/pricing).

An admin can assign roles to Members and/or Teams at the workspace level and on individual databases and tables. This support article covers assigning roles to members individually and teams in bulk on an individual database. For assigning roles for other applications:

  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level)
  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level)
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level)

> Database roles will override workspace roles. This means that a member who is explicitly assigned a role on a database will get that exact role, regardless of any workspace roles. Learn more about [the hierarchy of roles](/user-docs/role-based-access-control-rbac).

## Manage roles for a specific database

Members with Admin roles at the database level can invite members to a database and assign roles to users.

> There’s a hierarchy of permissions between a workspace, database, and table. You must first [invite a user to the workspace](/user-docs/manage-workspace-permissions) before inviting them as members of a specific database.

To manage and assign roles to members or teams on an individual database,

  1. Within the workspace, select a database you’d like to invite the member to

  2. Click on the vertical ellipsis beside the database then click **Manage members** from the options dropdown in the sidebar.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/009950f2-07d8-47ec-8126-696c3e268d9c/Screenshot_2023-01-18_at_18.13.30.png)

  3. Click **Select Members** on the modal to add roles for individual users and teams on this specific database.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6540ae0c-576d-48c6-9bb3-d8b8d8a18827/Screenshot_2023-01-18_at_18.15.03.png)

  4. Search and select the members and/or teams you want to invite to the database using the tick box or the **Select all** button. The modal will indicate the total number of members selected. Learn how to [invite members to a workspace](/user-docs/manage-workspace-permissions) or how to [create and add members to a team](/user-docs/create-and-manage-teams).

  5. Choose the member’s and/or team’s default role at database level. Click the default role drop-down to scroll through the list of permissions.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0c887fd8-8cb4-411a-adbe-dd9b522527a9/Screenshot_2023-01-18_at_18.18.19.png)

  6. Then click the **Invite members/teams** button. The Invite button will indicate the total number selected.

## View users’ access in a database

You can see invited users that have access to the database and their database level roles on the **modal**.

> Note ⚠️: Other users might inherit access via their respective roles on the parent workspace. However, you won’t see users or teams who have inherited permission to see or have access to this database from their parent workspace here. You only see exceptions to the workspace defaults.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/bf5cfc0d-6ad0-48f8-911a-3a2fb2c7994b/Screenshot_2023-01-18_at_18.11.48.png)

The list of database members is not an exhaustive list of everyone who has a role in that database. It contains only the list of specific role assignments on that specific database. For example, if User A has a workspace level role of Admin, they will be an Admin on all databases and tables, if there are no exceptions added. However, the ‘Database-> Manage Members’ modal will now show User A as an Admin on that database.

## Modify access or remove member from a database

Admins can remove access from the **Manage members** modal.

To remove a member and/or team access from a database,

  1. Within the workspace, select a database you’d like to invite the member to

  2. Click on the vertical ellipsis beside the database then click **Manage members** from the options dropdown in the sidebar.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e4f58160-9695-4079-8719-4479ce58a186/Screenshot_2023-01-18_at_18.13.30.png)

  3. Remove or modify an existing member’s and/or team’s default role on a specific database by selecting an option from the default role dropdown.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fbeeb85d-c422-458f-9698-7c14a7f80ce7/Screenshot_2023-01-18_at_19.18.04.png)

## FAQ

### What happens when a member is removed?

Removing member access from a database is not undoable. If a user is removed, they will lose access to all database data. They will have to be re-added to the database to regain access.

### What is the difference between deleting a user and revoking table access?

It’s important to understand the differences between removing users from a workspace, table, or database and [permanently deleting a user account from a self-hosted instance](/user-docs/admin-panel-users#permanently-delete-a-user).

Removing a member means taking away their access to a particular workspace, table, or database. However, their user account remains intact. This is applicable to both the SaaS hosted and self-hosted versions.

On the other hand, deleting a user is specific to the self-hosted version. Instance Admins can permanently delete a user from the entire self-hosted instance. This action completely removes the user’s account, and they lose access to all workspaces, tables, and databases.

## Related content

  * [Assign roles to members at workspace level](/user-docs/assign-roles-to-members-at-workspace-level)
  * [Assign roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level)
  * [Assign roles to teams and members at table level](/user-docs/assign-roles-at-table-level)

