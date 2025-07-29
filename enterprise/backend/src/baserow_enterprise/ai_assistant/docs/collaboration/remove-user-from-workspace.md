# Baserow Documentation

Source: https://baserow.io/user-docs/remove-a-user-from-a-workspace

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Remove a user from a workspace

Workspace admins can remove one or multiple users from a workspace. Sometimes, after working with a collaborator in one of your workspaces for a period of time, you may find that it would be better to work on your project without that person. This support article will cover the steps to remove a user from your workspace.

> Only workspace admins can remove people from a workspace. Non-admins cannot view the collaborators within a workspace or remove a collaborator from a workspace.

## Remove a member

You must be a workspace admin to remove any member from a workspace. To delete a user from the list of members,

  1. Open the workspace you would like to remove a user from.
  2. Click the vertical ellipses ⋮ (three-dot) icon in the right corner next to the workspace name to view the list of collaborators.
  3. Select **Members**.
  4. On the **Members** page, locate the person you want to remove then click the ellipses icon to the right of the member’s details. This will cause a window to appear that says “Remove from workspace”.
  5. Select the delete icon to remove.

> Use the search feature to quickly find a member by their name or email address.

All done!

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/25ec383f-34a0-4d2e-99f6-54679e71e71e/Screenshot_2023-01-04_at_18.10.45.png)

## FAQ

### What happens when a member is removed?

Removing a member from a workspace is not undoable. This action will delete all of that user’s role assignments and team assignments permanently.

If a user is removed, they will lose access to all workspace data. They will have to be re-added to the workspace to regain access.

### There are no admins in a database and table, how can this be resolved?

Databases and Tables can be orphaned if an admin creates a database but removes access to it for all other users in the workspace. If the admin then leaves the workspace, no one else can access the database and its tables.

To resolve this issue, follow these steps:

  1. Invite a new user to the workspace who has not been excluded from the database.
  2. Assign the new user as an admin.
  3. Have the new admin grant access to the rest of the workspace, allowing users to access the database and its tables again.

### What is the difference between deleting a user and revoking workspace access?

It’s important to understand the differences between removing users from a workspace, table, or database and [permanently deleting a user account from a self-hosted instance](/user-docs/admin-panel-users#permanently-delete-a-user).

Removing a member means taking away their access to a particular workspace, table, or database. However, their user account remains intact. This is applicable to both the SaaS hosted and self-hosted versions.

On the other hand, deleting a user is specific to the self-hosted version. Instance Admins can permanently delete a user from the entire self-hosted instance. This action completely removes the user’s account, and they lose access to all workspaces, tables, and databases.

## Related content

  * [Add workspace collaborators](/user-docs/manage-workspace-permissions).
  * [Manage workspace members](/user-docs/managing-workspace-collaborators).
  * [Create and manage teams](/user-docs/create-and-manage-teams) _(available in enterprise version)_.

