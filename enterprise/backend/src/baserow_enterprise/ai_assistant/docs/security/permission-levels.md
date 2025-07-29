# Baserow Documentation

Source: https://baserow.io/user-docs/set-permission-level

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Role levels in Baserow

> Assigning role based permission is only available to users with a Self-hosted Enterprise License or on Cloud Hosted Advanced Plan.

When you [invite users to a workspace](/user-docs/manage-workspace-permissions), you’ll be prompted to choose the initial setup. As a workspace admin, you can assign roles to members or teams at three levels: Workspace, Database, and Table. These levels determine how users can access and interact with data within the workspace, database, or table.

## Workspace level roles

When a member is added to a workspace, a default role is initially set. The member will have access to the entire workspace at the role level assigned to them. Learn how to [assign a default role for a workspace.](/user-docs/assign-roles-to-members-at-workspace-level)

The person who created the workspace is automatically designated as an admin. There may be more than one admin for a workspace.

Teams or members may gain access to databases and tables in that workspace, through their roles in the parent workspace. If a team or member joins a workspace, the default role at workspace level is automatically assigned to them on all databases and tables in the workspace, unless an exception is set and a role with a higher hierarchy takes precedence.

| Admin | Builder | Editor | Commenter | Viewer  
---|---|---|---|---|---  
General actions |  |  |  |  |   
Invite members into the workspace | ✓ |  |  |  |   
Manage roles of members of the workspace | ✓ |  |  |  |   
Remove access from all other users | ✓ |  |  |  |   
View the trash for database or workspace | ✓ | ✓ |  |  |   
Access/view the workspace, database and table within the workspace at your assigned role | ✓ | ✓ | ✓ | ✓ | ✓  
  
The power to invite a member into the workspace and manage existing users is restricted to the Admins of that Workspace. Admins on a Database or Table can only manage the roles for that Database or Table, not the entire Workspace.

## Database level roles

If a user or team has a role in a Database, they automatically get that role on every table in that database. They will only have access to tables in that specific database at the role level that you have assigned to them unless an exception is set and a role with a higher hierarchy takes precedence.

Learn how to [assign roles on individual databases](/user-docs/assign-roles-at-database-level).

| Admin | Builder | Editor | Commenter | Viewer  
---|---|---|---|---|---  
General actions |  |  |  |  |   
Invite users to Database at or below your role | ✓ |  |  |  |   
Manage roles of members on that Database | ✓ |  |  |  |   
Remove access from all other users * | ✓ |  |  |  |   
View the trash for database | ✓ | ✓ |  |  |   
Access/view the database and tables within the workspace at your assigned role | ✓ | ✓ | ✓ | ✓ | ✓  
Create, delete, rename and re-order databases |  |  |  |  |   
  
## Table level roles

If a user or team has a default role in a Table, they will only have access to that table at the role level to which they have been assigned. They automatically get that role on the specific table, unless an exception is set and a role with a higher hierarchy takes precedence.

Learn how to [assign roles on individual tables](/user-docs/assign-roles-at-table-level).

| Admin | Builder | Editor | Commenter | Viewer  
---|---|---|---|---|---  
General actions |  |  |  |  |   
Manage roles of members of that Table | ✓ |  |  |  |   
Remove access from all other users * | ✓ |  |  |  |   
Access/view the specific table at your assigned role | ✓ | ✓ | ✓ | ✓ | ✓  
Field actions |  |  |  |  |   
Create and delete fields, update them (fields or meta data of the table), rename them and re-order them | ✓ | ✓ |  |  |   
View actions |  |  |  |  |   
Make views, webhooks and generate links to share the view publicly | ✓ | ✓ |  |  |   
Row and Cell actions |  |  |  |  |   
Update cells in a table | ✓ | ✓ | ✓ |  |   
Update, create and delete rows | ✓ | ✓ | ✓ |  |   
Leave comments on every row | ✓ | ✓ | ✓ | ✓ |   
View the data in a table | ✓ | ✓ | ✓ | ✓ | ✓  
  
Admins in a Workspace, Database or Table can remove access from each other. For example, an admin can make a database and assign the “No Access” role to all other users to make it private.

For a full technical list of what each role can do, [view our internal database](/public/grid/BjMiRTijVPbem9KdtU9a1youuCXAS3S82cwazq_zYUk). The operations each role can do is stored in the database.

## Related content

  * [Assign roles on individual tables](/user-docs/assign-roles-at-table-level).
  * [Assign a default role for a workspace](/user-docs/assign-roles-to-members-at-workspace-level).
  * [Assign roles on individual databases](/user-docs/assign-roles-at-database-level).

