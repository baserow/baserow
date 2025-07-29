# Baserow Documentation

Source: https://baserow.io/user-docs/create-and-manage-teams

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Create and manage teams

> Available to users on [Baserow.io](http://Baserow.io) Enterprise plan.

With Baserow, you can use teams to organize your users into groups for better organization and reporting. You can have multiple teams in a workspace. This support article covers creating and managing teams.

Workspace admins can create a team hierarchy by [assigning roles to teams at workspace level](/user-docs/assign-roles-to-teams-at-workspace-level). Teams higher in the hierarchy can access everything owned by teams below them, but the lower teams cannot see everything owned by higher teams.

## Overview

Baserow teams are tied to Workspaces, and you can invite Workspace members to join Teams. Teams make it easy for admins to give or limit permissions to multiple people at once.

Each Team has a default role set at the Workspace level. When the default role is assigned to a Team, all its members automatically have that role throughout the entire Workspace and its contents. However, exceptions can be made for specific databases and tables if needed.

> A higher role has all of the permissions of the lower roles. Other users might inherit access to a Database or Table via their respective roles on the parent Database or Workspace.

## Create and invite members to a team

> There’s a hierarchy of permissions between a workspace, database, and table. You must first [invite a user to the workspace](/user-docs/manage-workspace-permissions) before inviting them as members of a specific team.

To create a team, select the **Teams** tab at the top of the **Members** page,

  1. Click the **Create team** button to open up a pop-over

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9733d07e-fe25-4b5d-9817-6a6e09a810ef/Screenshot_2023-01-04_at_16.09.41.png)

  2. Add the team name and set a default role for the team users.

  3. Choose the team’s default role at workspace level. Click the default role drop-down to scroll through the list of permissions.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/122bb90d-99c0-41b1-874e-cd57060f7350/Screenshot_2023-01-04_at_16.17.16.png)

  4. Add members from the existing workspace member list to the team by clicking the **Add members** button. Learn how to [invite users to a workspace](/user-docs/manage-workspace-permissions).

  5. Search and select the members you want to invite using the tick box or the **Select all** button. The modal will indicate the total number of members selected. Then click **Invite.**

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fac5e85e-ddf1-438d-a422-5e212379aa0c/Screenshot_2023-01-18_at_17.29.34.png)

  6. Click the **Save** button to create your team.

The member will be added to the team. Users in a team effectively have all of the permissions that are assigned to that team, unless more specific roles are assigned to individual users.

## Modify a team’s settings

After creating a team, Admins can edit the team’s name, default role or members from the **Teams** tab at the top of the **Members** page.

To edit an existing team,

  1. Click on the horizontal ellipsis beside the team ••• then click **Edit team** from the options dropdown.
  2. Make the desired changes, then click the **Save** button.

Modify a team’s default role on the workspace level by selecting an option from the default role dropdown.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9644b0a2-fe03-4987-9b25-0ec8139e262d/Screenshot_2023-01-18_at_10.05.23.png)

## Delete a team

To delete a team,

  1. Click on the horizontal ellipsis beside the team ••• then click **Delete team** from the options dropdown.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/bf46fc5a-6922-4c44-9834-fc07d402924d/Screenshot_2023-01-18_at_10.08.44.png)

## Add or remove members from a team

Admins can add or remove members of a team from the **Teams** tab at the top of the **Members** page.

To add a member to the team,

  1. Click on the horizontal ellipsis beside the team ••• then click **Edit team** from the options dropdown.
  2. Add members from the existing workspace member list to the team by clicking the **Add members** button. Learn how to [invite members to a workspace](/user-docs/assign-roles-to-members-at-workspace-level).
  3. Search and select the members you want to invite using the tick box or the **Select all** ” button. The modal will indicate the total number of members selected. Then click **Invite.**
  4. Make the desired changes, then click the **Save** button.

To delete a member from the team,

  1. Click on the horizontal ellipsis beside the team ••• then click **Edit team** from the options dropdown.
  2. Click on the delete icon beside the member’s details
  3. Make the desired changes, then click the **Save** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7790b3e4-e1f1-4cc3-b201-7dd26862f1d8/Screenshot_2023-01-04_at_16.23.27.png)

